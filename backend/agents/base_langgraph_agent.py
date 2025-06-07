"""
Base LangGraph agent implementation that provides common functionality
for all agents using the unified state model with normalized message storage.
"""

import logging
import uuid
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel

from agents.base_agent import BaseAgent, AgentRequest, AgentResponse, AgentStatus, AgentCapability
from agents.base_state import BaseAgentState, BaseAgentConfig
from services.conversation_service import conversation_service
from services.message_service import message_service
from schemas.message import MessageCreate, MessageUpdate

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
        """Create initial state for agent execution."""
        logger.info(f"Creating initial state for agent_type: {request.agent_type}")
        
        # Import message service at the top for use throughout the function
        from services.message_service import message_service
        
        # Build base state from request
        state_data = {
            "conversation_id": request.conversation_id,
            "user_input": request.user_input,
            "agent_type": request.agent_type,
            "capability": request.capability,
            "context": request.context,
            "notebook_context": request.notebook_context,
            "metadata": request.metadata,
            "llm_provider": request.metadata.get("llm_provider", "openai"),
            "messages": []
        }
        
        # Handle clarification responses if provided
        clarification_responses = request.metadata.get("clarification_responses", [])
        if clarification_responses:
            logger.info(f"Processing {len(clarification_responses)} clarification responses")
            
            # Create a user message in the database to represent the clarification responses
            try:
                # Format the clarification responses as a readable message
                clarification_text_parts = []
                
                # Try to get the clarification questions from the previous assistant message to format nicely
                clarification_questions = {}
                if request.conversation_id:
                    try:
                        recent_messages = message_service.get_conversation_messages(request.conversation_id)
                        # Look for the most recent message with clarification questions
                        for msg in reversed(recent_messages):
                            if (msg.role == 'assistant' and 
                                msg.needs_clarification and 
                                hasattr(msg, 'clarification_questions') and 
                                msg.clarification_questions):
                                # Parse clarification questions if they exist
                                questions = msg.clarification_questions
                                if isinstance(questions, str):
                                    import json
                                    try:
                                        questions = json.loads(questions)
                                    except:
                                        questions = []
                                elif isinstance(questions, list):
                                    questions = questions
                                else:
                                    questions = []
                                
                                # Create a mapping of question IDs to questions
                                for q in questions:
                                    if isinstance(q, dict) and 'id' in q and 'question' in q:
                                        clarification_questions[q['id']] = q['question']
                                break
                    except Exception as e:
                        logger.warning(f"Could not retrieve clarification questions: {e}")
                
                # Format the clarification responses with questions
                for response in clarification_responses:
                    question_id = response.get('id', '')
                    answer = response.get('answer', '')
                    question_text = clarification_questions.get(question_id, f"Question {question_id}")
                    
                    clarification_text_parts.append(f"Regarding '{question_text}': {answer}")
                
                clarification_message = f"Clarification responses for: \"{request.user_input}\"\n\n" + "\n\n".join(clarification_text_parts)
                
                # Create the clarification response message in the database
                clarification_msg = message_service.create_message(
                    conversation_id=request.conversation_id,
                    role="user",
                    content=clarification_message,
                    message_type="clarification_response"
                )
                logger.info(f"Created clarification response message: {clarification_msg.id}")
                
            except Exception as e:
                logger.error(f"Failed to create clarification response message: {e}")
            
            # Set clarification state
            state_data["clarification_responses"] = clarification_responses
            state_data["clarification_processed"] = True
        
        # Extract conversation context from previous messages (simplified approach)
        if request.conversation_id:
            try:
                previous_messages = message_service.get_conversation_messages(request.conversation_id)
                logger.info(f"Found {len(previous_messages)} previous messages for context")
                
                # Extract the most recent relevant context (last assistant message with generated content)
                for msg in reversed(previous_messages):
                    if (msg.role == 'assistant' and 
                        msg.query_generated and 
                        not msg.is_node_progress):  # Skip progress messages
                        
                        # Add this as context for the generation nodes to use
                        context = state_data.get("context", {})
                        context["previous_query"] = msg.query_generated
                        context["previous_results"] = msg.query_results or []
                        context["previous_agent_type"] = msg.agent_type
                        context["has_previous_context"] = True
                        state_data["context"] = context
                        
                        logger.info(f"✅ Added previous context from {msg.agent_type} agent")
                        logger.info(f"   - Previous query length: {len(msg.query_generated)} chars")
                        logger.info(f"   - Previous results count: {len(msg.query_results) if msg.query_results else 0}")
                        break
                else:
                    logger.info("No previous assistant messages with generated content found")
                    
            except Exception as e:
                logger.warning(f"Failed to extract conversation context: {e}")
        
        # Add user input as message
        if request.user_input:
            state_data["messages"].append({"role": "user", "content": request.user_input})
        
        logger.info(f"Created initial state for conversation: {state_data['conversation_id']}")
        return self.state_class(**state_data)
    
    def _save_state(self, state):
        """Persist state - no longer needed with message-based architecture."""
        # State is now persisted via message creation during execution
        # This method kept for compatibility but does nothing
        if isinstance(state, BaseModel):
            conversation_id = state.conversation_id
        else:
            conversation_id = state.get("conversation_id")
        
        logger.debug(f"State management now handled via messages for conversation: {conversation_id}")
        return conversation_id
    
    def _create_assistant_message(self, conversation_id: str, content: str, agent_results: Dict[str, Any]) -> str:
        """Create an assistant message with agent results in the database."""
        try:
            # Create the message
            message_data = MessageCreate(
                conversation_id=conversation_id,
                role='assistant',
                content=content,
                message_type='chat',
                agent_type=self.agent_type
            )
            
            message = message_service.create_message(message_data)
            
            # Update with agent results
            update_data = MessageUpdate(**agent_results)
            message_service.update_message(message.id, update_data)
            
            logger.info(f"Created assistant message {message.id} with agent results")
            return message.id
            
        except Exception as e:
            logger.error(f"Failed to create assistant message: {e}")
            # Return a fallback ID so the response can still work
            return f"msg_fallback_{uuid.uuid4().hex[:8]}"

    def _create_response_from_state(self, state) -> AgentResponse:
        """Create response from final state and save as message."""
        try:
            # Helper function to get values from either Pydantic model or dict
            def get_state_value(key, default=None):
                if isinstance(state, dict):
                    return state.get(key, default)
                else:
                    return getattr(state, key, default)
            
            conversation_id = get_state_value('conversation_id')
            if not conversation_id:
                logger.error("No conversation_id in state, cannot create message")
                return AgentResponse(
                    status=AgentStatus.ERROR,
                    message="Internal error: no conversation ID",
                    result=None
                )
            
            # Debug logging to see the final state
            needs_clarification = get_state_value('needs_clarification')
            logger.info(f"Creating response from state. needs_clarification: {needs_clarification}")
            logger.info(f"State has clarification_questions: {bool(get_state_value('clarification_questions'))}")
            logger.info(f"State has generated_code: {bool(get_state_value('generated_code'))}")
            logger.info(f"State has error_message: {bool(get_state_value('error_message'))}")
            
            # Check if clarification is needed
            if needs_clarification:
                clarification_questions = get_state_value('clarification_questions', [])
                message_content = "I need some clarification to provide the best response."
                
                # Create the message with clarification data
                try:
                    message_data = MessageCreate(
                        conversation_id=conversation_id,
                        role='assistant',
                        content=message_content,
                        message_type='clarification',
                        agent_type=self.agent_type
                    )
                    
                    message = message_service.create_message(message_data)
                    
                    # Update with clarification data
                    update_data = MessageUpdate(
                        needs_clarification=True,
                        clarification_questions=clarification_questions,
                        metadata={'clarification_type': 'request'}
                    )
                    message_service.update_message(message.id, update_data)
                    
                    logger.info(f"Created clarification message {message.id}")
                except Exception as e:
                    logger.error(f"Failed to create clarification message: {e}")
                
                logger.info(f"Returning clarification response with message: {message_content[:100]}...")
                return AgentResponse(
                    status=AgentStatus.NEEDS_CLARIFICATION,
                    message=message_content,
                    result={
                        "clarification_questions": clarification_questions
                    },
                    conversation_id=conversation_id,
                    clarification_questions=clarification_questions
                )
            
            # Check for errors
            error_message = get_state_value('error_message')
            if error_message:
                # Create error message
                try:
                    message_data = MessageCreate(
                        conversation_id=conversation_id,
                        role='assistant',
                        content=error_message,
                        message_type='error',
                        agent_type=self.agent_type
                    )
                    
                    message = message_service.create_message(message_data)
                    
                    # Update with error metadata
                    update_data = MessageUpdate(
                        has_error=True,
                        metadata={'error_type': 'execution_error'}
                    )
                    message_service.update_message(message.id, update_data)
                    
                    logger.info(f"Created error message {message.id}")
                except Exception as e:
                    logger.error(f"Failed to create error message: {e}")
                
                logger.info(f"Returning error response: {error_message}")
                return AgentResponse(
                    status=AgentStatus.ERROR,
                    message=error_message,
                    result=None,
                    conversation_id=conversation_id
                )
            
            # Success case - create message with agent results
            generated_code = get_state_value('generated_code')
            execution_results = get_state_value('execution_results')
            similar_results = get_state_value('similar_code', [])
            entity_matches = get_state_value('entity_matches', [])
            
            if generated_code:
                success_message = "Successfully generated and executed code."
                if execution_results:
                    result_count = len(execution_results) if isinstance(execution_results, list) else 1
                    success_message += f" Found {result_count} results."
                
                # Prepare agent results for message storage
                agent_results = {
                    'query_generated': generated_code,
                    'query_results': execution_results,
                    'execution_info': self._create_execution_info_from_state(state),
                    'similar_results': similar_results,
                    'entity_matches': entity_matches,
                    'has_generated_code': True,
                    'has_query_results': bool(execution_results)
                }
                
                # Create the message with agent results
                try:
                    message_data = MessageCreate(
                        conversation_id=conversation_id,
                        role='assistant',
                        content=success_message,
                        message_type='chat',
                        agent_type=self.agent_type
                    )
                    
                    message = message_service.create_message(message_data)
                    
                    # Update with agent results
                    update_data = MessageUpdate(**agent_results)
                    message_service.update_message(message.id, update_data)
                    
                    logger.info(f"Created success message {message.id} with agent results")
                except Exception as e:
                    logger.error(f"Failed to create success message: {e}")
                
                logger.info("Returning success response with generated code")
                return AgentResponse(
                    status=AgentStatus.SUCCESS,
                    message=success_message,
                    result={
                        "generated_code": generated_code,
                        "execution_results": execution_results,
                        "execution_info": self._create_execution_info_from_state(state),
                        "similar_results": similar_results,
                        "entity_matches": entity_matches
                    },
                    conversation_id=conversation_id
                )
            else:
                error_msg = "No code was generated"
                
                # Create error message
                try:
                    message_data = MessageCreate(
                        conversation_id=conversation_id,
                        role='assistant',
                        content=error_msg,
                        message_type='error',
                        agent_type=self.agent_type
                    )
                    
                    message = message_service.create_message(message_data)
                    
                    # Update with error metadata
                    update_data = MessageUpdate(
                        has_error=True,
                        metadata={'error_type': 'no_code_generated'}
                    )
                    message_service.update_message(message.id, update_data)
                    
                    logger.info(f"Created no-code error message {message.id}")
                except Exception as e:
                    logger.error(f"Failed to create no-code error message: {e}")
                
                logger.info("No generated code found, returning error")
                return AgentResponse(
                    status=AgentStatus.ERROR,
                    message=error_msg,
                    result=None,
                    conversation_id=conversation_id
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
            
            # Create initial user message in database if we have a conversation_id
            if request.conversation_id and request.user_input:
                try:
                    user_message_data = MessageCreate(
                        conversation_id=request.conversation_id,
                        role='user',
                        content=request.user_input,
                        message_type='chat'
                    )
                    user_message = message_service.create_message(user_message_data)
                    logger.info(f"Created user message {user_message.id}")
                except Exception as e:
                    logger.error(f"Failed to create user message: {e}")
            
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
            
            # Execute the graph asynchronously to support async nodes
            result_state = await self._graph.ainvoke(initial_state, config_dict)
            
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
    
    async def handle_request_streaming(self, request: AgentRequest, progress_callback=None):
        """
        Handle request using LangGraph workflow with streaming updates.
        
        Args:
            request: The agent request to process
            progress_callback: Async callback function for progress updates
            
        Yields:
            Intermediate state updates during graph execution
        """
        try:
            if not self._graph:
                raise RuntimeError(f"{self.agent_type} agent graph not available")
            
            # Create initial state and config
            initial_state = self._create_initial_state(request)
            config_obj = self._create_agent_config(request)
            
            # Convert config to dict format that LangGraph expects
            if hasattr(config_obj, '__dict__'):
                config_dict = {"configurable": config_obj.__dict__}
            else:
                config_dict = {"configurable": config_obj}
            
            # Track the final state
            final_state = None
            
            # Create initial user message in database if we have a conversation_id
            user_message_id = None
            if request.conversation_id and request.user_input:
                try:
                    user_message_data = MessageCreate(
                        conversation_id=request.conversation_id,
                        role='user',
                        content=request.user_input,
                        message_type='chat'
                    )
                    user_message = message_service.create_message(user_message_data)
                    user_message_id = user_message.id
                    logger.info(f"Created user message {user_message_id}")
                except Exception as e:
                    logger.error(f"Failed to create user message: {e}")
            
            # Create initial progress message
            if user_message_id:
                try:
                    progress_msg = message_service.create_progress_message(
                        user_message_id,
                        "Agent Execution",
                        "start", 
                        f"Starting {self.agent_type} agent execution...",
                        {"agent_type": self.agent_type, "capability": request.capability}
                    )
                    logger.info(f"Created start progress message {progress_msg.id}")
                except Exception as e:
                    logger.error(f"Failed to create start progress message: {e}")
            
            # Stream through graph execution
            logger.info(f"Starting streaming execution for {self.agent_type} agent")
            async for chunk in self._graph.astream(initial_state, config_dict):
                logger.info(f"Streaming chunk: {type(chunk)}")
                
                # Extract node name and state from chunk
                if isinstance(chunk, dict):
                    for node_name, node_state in chunk.items():
                        logger.info(f"Node '{node_name}' executed")
                        
                        # Create progress message for this node
                        if user_message_id:
                            try:
                                progress_msg = message_service.create_progress_message(
                                    user_message_id,
                                    node_name,
                                    "complete",
                                    f"Completed {node_name}",
                                    {
                                        "node_output": self._extract_node_output(node_state),
                                        "current_state": self._safe_state_summary(node_state)
                                    }
                                )
                                logger.info(f"Created node progress message {progress_msg.id} for {node_name}")
                            except Exception as e:
                                logger.error(f"Failed to create node progress message for {node_name}: {e}")
                        
                        # Send progress update if callback provided
                        if progress_callback:
                            await progress_callback(
                                node_name=node_name,
                                node_input=self._extract_node_input(node_state),
                                node_output=self._extract_node_output(node_state)
                            )
                        
                        # Keep track of the latest state
                        final_state = node_state
                        
                        # Yield the intermediate update
                        yield {
                            "type": "node_complete",
                            "node_name": node_name,
                            "node_output": self._extract_node_output(node_state),
                            "current_state": self._safe_state_summary(node_state)
                        }
            
            # Use the final state or fall back to initial state
            if final_state is None:
                logger.warning("No final state received from streaming, using initial state")
                final_state = initial_state
            
            # Save the state to conversation service
            conversation_id = self._save_state(final_state)
            
            # Update the conversation_id in the result state if it wasn't set
            if hasattr(final_state, 'conversation_id') and not final_state.conversation_id:
                final_state.conversation_id = conversation_id
            
            # Create and yield final response
            response = self._create_response_from_state(final_state)
            
            # Create completion progress message
            if user_message_id:
                try:
                    progress_msg = message_service.create_progress_message(
                        user_message_id,
                        "Agent Execution",
                        "complete",
                        f"{self.agent_type} agent execution completed",
                        {"status": response.status.value, "final_response": True}
                    )
                    logger.info(f"Created completion progress message {progress_msg.id}")
                except Exception as e:
                    logger.error(f"Failed to create completion progress message: {e}")
            
            yield {
                "type": "complete",
                "response": response
            }
            
        except Exception as e:
            logger.error(f"Error in streaming {self.agent_type} agent: %s", e, exc_info=True)
            
            # Create error progress message if we have user_message_id
            if 'user_message_id' in locals() and user_message_id:
                try:
                    progress_msg = message_service.create_progress_message(
                        user_message_id,
                        "Agent Execution",
                        "error",
                        f"Error in {self.agent_type} agent: {str(e)}",
                        {"error": str(e)}
                    )
                    logger.info(f"Created error progress message {progress_msg.id}")
                except Exception as e:
                    logger.error(f"Failed to create error progress message: {e}")
            
            yield {
                "type": "error",
                "error": str(e)
            }
    
    def _extract_node_input(self, state) -> Dict[str, Any]:
        """Extract relevant input information from node state for progress reporting."""
        # Helper function to get values from either Pydantic model or dict
        def get_state_value(key, default=None):
            if isinstance(state, dict):
                return state.get(key, default)
            else:
                return getattr(state, key, default)
        
        # Return key fields that show what the node is working on
        return {
            "user_input": get_state_value("user_input", "")[:100],  # Truncate for display
            "agent_type": get_state_value("agent_type", ""),
            "capability": get_state_value("capability", ""),
            "needs_clarification": get_state_value("needs_clarification", False)
        }
    
    def _extract_node_output(self, state) -> Dict[str, Any]:
        """Extract relevant output information from node state for progress reporting."""
        # Helper function to get values from either Pydantic model or dict
        def get_state_value(key, default=None):
            if isinstance(state, dict):
                return state.get(key, default)
            else:
                return getattr(state, key, default)
        
        # Return key fields that show what the node produced
        output = {}
        
        # Check for generated code/query
        generated_code = get_state_value("generated_code")
        if generated_code:
            output["generated_code_preview"] = generated_code[:200] + "..." if len(generated_code) > 200 else generated_code
        
        # Check for execution results
        execution_results = get_state_value("execution_results")
        if execution_results:
            output["execution_results_count"] = len(execution_results) if isinstance(execution_results, list) else 1
        
        # Check for search results - return actual matches instead of just counts
        similar_code = get_state_value("similar_code")
        if similar_code:
            output["similar_results_count"] = len(similar_code) if isinstance(similar_code, list) else 1
            output["similar_results"] = similar_code if isinstance(similar_code, list) else [similar_code]
        
        # Check for entity matches - return actual matches instead of just counts
        entity_matches = get_state_value("entity_matches")
        if entity_matches:
            output["entity_matches_count"] = len(entity_matches) if isinstance(entity_matches, list) else 1
            output["entity_matches"] = entity_matches if isinstance(entity_matches, list) else [entity_matches]

        # Check for workflow contextual search data (for workflow agent)
        contextual_search_data = get_state_value("contextual_search_data")
        if contextual_search_data and isinstance(contextual_search_data, dict):
            workflows = contextual_search_data.get("workflows", [])
            methods = contextual_search_data.get("methods", [])
            
            if workflows:
                output["similar_results_count"] = len(workflows)
                output["similar_results"] = workflows
            
            if methods:
                output["literature_examples"] = methods
                if "similar_results_count" not in output:
                    output["similar_results_count"] = 0
                output["similar_results_count"] += len(methods)
        
        # Check for clarification questions
        clarification_questions = get_state_value("clarification_questions")
        if clarification_questions:
            output["clarification_questions_count"] = len(clarification_questions) if isinstance(clarification_questions, list) else 1
        
        # Check for errors
        error_message = get_state_value("error_message")
        if error_message:
            output["error"] = error_message
        
        return output
    
    def _safe_state_summary(self, state) -> Dict[str, Any]:
        """Create a safe summary of the current state for frontend display."""
        # Helper function to get values from either Pydantic model or dict
        def get_state_value(key, default=None):
            if isinstance(state, dict):
                return state.get(key, default)
            else:
                return getattr(state, key, default)
        
        return {
            "has_generated_code": bool(get_state_value("generated_code")),
            "has_execution_results": bool(get_state_value("execution_results")),
            "needs_clarification": get_state_value("needs_clarification", False),
            "clarification_processed": get_state_value("clarification_processed", False),
            "error_present": bool(get_state_value("error_message")),
            "refinement_count": get_state_value("refinement_count", 0)
        }
    
    def get_conversation_state(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation state - deprecated, now handled via messages."""
        logger.warning("get_conversation_state is deprecated - state now managed via messages")
        return None

    def set_conversation_state(self, conversation_id: str, state: Dict[str, Any]) -> None:
        """Set conversation state - deprecated, now handled via messages."""
        logger.warning("set_conversation_state is deprecated - state now managed via messages")


# Common node functions that can be used by all agents
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