"""
Base LangGraph agent implementation that provides common functionality
for all agents using the unified state model.
"""

import logging
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel

from agents.base_agent import BaseAgent, AgentRequest, AgentResponse, AgentStatus, AgentCapability
from agents.base_state import BaseAgentState, BaseAgentConfig
from services.conversation_state_service import conversation_state_service

logger = logging.getLogger(__name__)


def get_config_value(config, key: str, default=None):
    """
    Helper function to get config values that handles both dict and Pydantic model formats.
    
    Args:
        config: Configuration object (dict or Pydantic model)
        key: Configuration key to retrieve
        default: Default value if key not found
        
    Returns:
        Configuration value or default
    """
    if isinstance(config, dict):
        # LangGraph passes config as nested dict with 'configurable' key
        configurable = config.get('configurable', {})
        return configurable.get(key, default)
    else:
        return getattr(config, key, default)


def get_message_value(message, key: str, default=None):
    """
    Helper function to get message values that handles both dict and LangChain message formats.
    
    Args:
        message: Message object (dict or LangChain message)
        key: Message key to retrieve (e.g., 'content', 'role', 'type')
        default: Default value if key not found
        
    Returns:
        Message value or default
    """
    if isinstance(message, dict):
        return message.get(key, default)
    elif hasattr(message, key):
        return getattr(message, key, default)
    elif key == 'content' and hasattr(message, 'content'):
        return message.content
    elif key == 'role' and hasattr(message, 'type'):
        # Map LangChain message types to roles
        msg_type = getattr(message, 'type', '')
        if msg_type == 'human':
            return 'user'
        elif msg_type == 'ai':
            return 'assistant'
        else:
            return msg_type
    else:
        return default


class BaseLangGraphAgent(BaseAgent, ABC):
    """Base class for agents that use LangGraph with unified state management."""
    
    def __init__(self, agent_type: str, name: str, description: str, state_class: Type[BaseAgentState] = BaseAgentState):
        super().__init__(agent_type, name, description)
        self.state_class = state_class
        self._graph = None
        self._build_graph()
    
    @abstractmethod
    def _build_graph(self) -> None:
        """Build the LangGraph workflow. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def _create_agent_config(self, request: AgentRequest) -> BaseAgentConfig:
        """Create agent-specific configuration from request. Must be implemented by subclasses."""
        pass
    
    def _create_initial_state(self, request: AgentRequest):
        """Create initial state instance from request."""
        # Retrieve stored state dict if exists
        stored_dict = None
        if request.conversation_id:
            stored_dict = conversation_state_service.get(request.conversation_id)
        
        # Build base dict
        state_data = {
            "conversation_id": request.conversation_id,
            "user_input": request.user_input,
            "agent_type": request.agent_type,
            "capability": request.capability,
            "context": request.context,
            "notebook_context": request.notebook_context,
            "metadata": request.metadata,
            "llm_provider": request.metadata.get("llm_provider", "openai"),
        }
        
        # Extract clarification responses from metadata if present
        clarification_responses = request.metadata.get("clarification_responses")
        if clarification_responses:
            state_data["clarification_responses"] = clarification_responses
            logger.info(f"Found clarification responses in request: {len(clarification_responses)} responses")
        
        # Check if this is a refinement request
        if stored_dict and request.conversation_id:
            # This is a follow-up message in an existing conversation
            # Check if the previous state had a successful query result
            has_previous_query = stored_dict.get("generated_code") is not None
            has_successful_results = stored_dict.get("execution_results") is not None
            no_pending_clarification = not stored_dict.get("needs_clarification", False)
            no_clarification_responses = not clarification_responses
            
            logger.info(f"Refinement detection - conversation_id: {request.conversation_id}")
            logger.info(f"  has_previous_query: {has_previous_query}")
            logger.info(f"  has_successful_results: {has_successful_results}")
            logger.info(f"  no_pending_clarification: {no_pending_clarification}")
            logger.info(f"  no_clarification_responses: {no_clarification_responses}")
            
            # If we have a previous successful query and this is a new user input without clarification responses,
            # treat it as a refinement request
            if has_previous_query and no_pending_clarification and no_clarification_responses:
                # Make the condition less strict - don't require successful results, just a previous query
                state_data["is_refinement"] = True
                state_data["refinement_request"] = request.user_input
                state_data["previous_query"] = stored_dict.get("generated_code")
                state_data["previous_results"] = stored_dict.get("execution_results", [])
                logger.info(f"Detected refinement request: '{request.user_input[:100]}...'")
            else:
                logger.info("Not a refinement request - treating as new query")
        
        if stored_dict:
            state_data = {**stored_dict, **state_data}
            # merge messages etc handled below
        else:
            state_data["messages"] = []
        
        # Handle messages append
        if request.user_input:
            msgs = state_data.get("messages", [])
            msgs.append({"role": "user", "content": request.user_input})
            state_data["messages"] = msgs
        
        # Convert to model
        return self.state_class(**state_data)
    
    def _save_state(self, state):
        """Persist state (Pydantic model) and return conversation id"""
        if isinstance(state, BaseModel):
            state_dict = state.model_dump()
            conversation_id = state_dict.get("conversation_id")
        else:
            state_dict = state
            conversation_id = state.get("conversation_id")
        
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            state_dict["conversation_id"] = conversation_id
            if isinstance(state, BaseModel):
                state.conversation_id = conversation_id
        
        conversation_state_service.set(conversation_id, state_dict)
        return conversation_id
    
    def _create_response_from_state(self, state) -> AgentResponse:
        """Create response from final state."""
        try:
            # Helper function to get values from either Pydantic model or dict
            def get_state_value(key, default=None):
                if isinstance(state, dict):
                    return state.get(key, default)
                else:
                    return getattr(state, key, default)
            
            # Debug logging to see the final state
            needs_clarification = get_state_value('needs_clarification')
            logger.info(f"Creating response from state. needs_clarification: {needs_clarification}")
            logger.info(f"State has clarification_questions: {bool(get_state_value('clarification_questions'))}")
            logger.info(f"State has generated_code: {bool(get_state_value('generated_code'))}")
            logger.info(f"State has error_message: {bool(get_state_value('error_message'))}")
            
            # Check if clarification is needed
            if needs_clarification:
                # Get the clarification message from the last message
                messages = get_state_value('messages', [])
                if messages:
                    last_message = messages[-1]
                    # Handle both dict and LangChain message objects using helper function
                    message = get_message_value(last_message, 'content', 'Clarification needed')
                else:
                    message = "Clarification needed"
                
                logger.info(f"Returning clarification response with message: {message[:100]}...")
                return AgentResponse(
                    status=AgentStatus.NEEDS_CLARIFICATION,
                    message=message,
                    result={
                        "clarification_questions": get_state_value('clarification_questions', [])
                    },
                    conversation_id=get_state_value('conversation_id'),
                    clarification_questions=get_state_value('clarification_questions', [])  # Add at top level for frontend compatibility
                )
            
            # Check for errors
            error_message = get_state_value('error_message')
            if error_message:
                logger.info(f"Returning error response: {error_message}")
                return AgentResponse(
                    status=AgentStatus.ERROR,
                    message=error_message,
                    result=None,
                    conversation_id=get_state_value('conversation_id')
                )
            
            # Success case
            generated_code = get_state_value('generated_code')
            execution_results = get_state_value('execution_results')
            
            if generated_code:
                logger.info("Returning success response with generated code")
                return AgentResponse(
                    status=AgentStatus.SUCCESS,
                    message="Query generated and executed successfully",
                    result={
                        "generated_code": generated_code,
                        "execution_results": execution_results,
                        "execution_info": self._create_execution_info_from_state(state)
                    },
                    conversation_id=get_state_value('conversation_id')
                )
            else:
                logger.info("No generated code found, returning error")
                return AgentResponse(
                    status=AgentStatus.ERROR,
                    message="No code was generated",
                    result=None,
                    conversation_id=get_state_value('conversation_id')
                )
                
        except Exception as e:
            logger.error(f"Error creating response from state: {e}")
            return AgentResponse(
                status=AgentStatus.ERROR,
                message=f"Error processing response: {str(e)}",
                result=None,
                conversation_id=get_state_value('conversation_id') if 'get_state_value' in locals() else None
            )
    
    def _create_result_from_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Create result dict from state. Can be overridden by subclasses."""
        return {
            "generated_code": state.get("generated_code", ""),
            "execution_results": state.get("execution_results", []),
            "needs_clarification": False,
        }
    
    def _create_execution_info_from_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Create execution info from state. Can be overridden by subclasses."""
        # Helper function to get values from either Pydantic model or dict
        def get_state_value(key, default=None):
            if isinstance(state, dict):
                return state.get(key, default)
            else:
                return getattr(state, key, default)
        
        execution_results = get_state_value('execution_results', [])
        return {
            "language": "python",  # Default, can be overridden
            "result_count": len(execution_results) if isinstance(execution_results, list) else 0,
            "libraries": [],
            "expected_outputs": ["Generated code results"]
        }
    
    async def handle_request(self, request: AgentRequest) -> AgentResponse:
        """Handle request using LangGraph workflow."""
        try:
            if not self._graph:
                raise RuntimeError(f"{self.agent_type} agent graph not available")
            
            # Create initial state and config
            initial_state = self._create_initial_state(request)
            config_obj = self._create_agent_config(request)
            
            # Convert config to dict format that LangGraph expects
            # Don't serialize the config object - pass it directly so LLM objects remain intact
            if hasattr(config_obj, '__dict__'):
                # It's a Pydantic model or object with attributes
                config_dict = {"configurable": config_obj.__dict__}
            else:
                # It's already a dict
                config_dict = {"configurable": config_obj}
            
            # Execute the graph
            result_state = self._graph.invoke(initial_state, config_dict)
            
            # Debug logging to see what the graph returned
            logger.info(f"Graph execution completed. Result state type: {type(result_state)}")
            if hasattr(result_state, 'needs_clarification'):
                logger.info(f"Result state needs_clarification: {result_state.needs_clarification}")
            elif isinstance(result_state, dict):
                logger.info(f"Result state needs_clarification: {result_state.get('needs_clarification')}")
            else:
                logger.info(f"Result state attributes: {dir(result_state)}")
            
            # Save the state to conversation service
            conversation_id = self._save_state(result_state)
            
            # Update the conversation_id in the result state if it wasn't set
            if hasattr(result_state, 'conversation_id') and not result_state.conversation_id:
                result_state.conversation_id = conversation_id
            
            # Create response from final state
            return self._create_response_from_state(result_state)
            
        except Exception as e:
            logger.error(f"Error in {self.agent_type} agent: %s", e, exc_info=True)
            return AgentResponse(
                status=AgentStatus.ERROR,
                message=str(e),
                result=None,
            )
    
    def get_conversation_state(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation state."""
        return conversation_state_service.get(conversation_id)
    
    def set_conversation_state(self, conversation_id: str, state: Dict[str, Any]) -> None:
        """Set conversation state."""
        conversation_state_service.set(conversation_id, state)


# Common node functions that can be used by all agents
def extract_user_query_node(state: BaseAgentState) -> Dict[str, Any]:
    """Extract user query from messages."""
    messages = state.messages or []
    if not messages:
        return {"error_message": "No messages found in state"}
    
    last_message = messages[-1]
    user_query = get_message_value(last_message, "content", "")
    
    return {"user_query": user_query}


def process_clarification_response_node(state: BaseAgentState) -> Dict[str, Any]:
    """Process clarification responses."""
    clarification_responses = state.clarification_responses or []
    if not clarification_responses:
        return {"error_message": "No clarification responses provided"}
    
    # Mark clarification as processed
    return {
        "clarification_processed": True,
        "needs_clarification": False,
    }


def finalize_response_node(state: BaseAgentState) -> Dict[str, Any]:
    """Finalize the response with a summary message."""
    generated_code = state.generated_code or ""
    execution_results = state.execution_results or []
    
    if generated_code:
        message_content = f"Successfully generated {state.capability or 'code'}."
        if execution_results:
            message_content += f" Execution returned {len(execution_results)} results."
    else:
        message_content = "Request processed successfully."
    
    messages = state.messages or []
    messages.append({"role": "assistant", "content": message_content})
    
    return {"messages": messages} 