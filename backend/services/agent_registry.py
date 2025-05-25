"""
Agent registry for managing multiple agents in the paleoclimate analysis system.
"""

import logging
from typing import Dict, List, Optional, Any
from agents.base_agent import BaseAgent, AgentRequest, AgentResponse, AgentStatus

logger = logging.getLogger(__name__)

class AgentRegistry:
    """Registry for managing multiple agents and routing requests."""
    
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self._agent_instances: Dict[str, BaseAgent] = {}
    
    def register_agent(self, agent: BaseAgent) -> None:
        """
        Register an agent in the registry.
        
        Args:
            agent: The agent instance to register
        """
        agent_type = agent.agent_type
        if agent_type in self._agents:
            logger.warning(f"Agent type '{agent_type}' already registered, replacing")
        
        self._agents[agent_type] = agent
        logger.info(f"Registered agent: {agent_type} ({agent.name})")
    
    def unregister_agent(self, agent_type: str) -> None:
        """
        Unregister an agent from the registry.
        
        Args:
            agent_type: Type of agent to unregister
        """
        if agent_type in self._agents:
            del self._agents[agent_type]
            logger.info(f"Unregistered agent: {agent_type}")
        else:
            logger.warning(f"Agent type '{agent_type}' not found for unregistration")
    
    def get_agent(self, agent_type: str) -> Optional[BaseAgent]:
        """
        Get an agent by type.
        
        Args:
            agent_type: Type of agent to retrieve
            
        Returns:
            Agent instance or None if not found
        """
        return self._agents.get(agent_type)
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """
        List all registered agents and their capabilities.
        
        Returns:
            List of agent information dictionaries
        """
        return [agent.get_info() for agent in self._agents.values()]
    
    def get_capabilities(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all capabilities across all agents.
        
        Returns:
            Dictionary mapping agent types to their capabilities
        """
        capabilities = {}
        for agent_type, agent in self._agents.items():
            capabilities[agent_type] = [
                {
                    "name": cap.name,
                    "description": cap.description,
                    "requires_conversation": cap.requires_conversation
                }
                for cap in agent.capabilities.values()
            ]
        return capabilities
    
    async def route_request(self, request: AgentRequest) -> AgentResponse:
        """
        Route a request to the appropriate agent.
        
        Args:
            request: The agent request to route
            
        Returns:
            AgentResponse from the target agent
        """
        try:
            # Find the target agent
            agent = self.get_agent(request.agent_type)
            if not agent:
                return AgentResponse(
                    status=AgentStatus.ERROR,
                    message=f"Agent type '{request.agent_type}' not found",
                    result=None
                )
            
            # Validate the request
            if not agent.validate_request(request):
                return AgentResponse(
                    status=AgentStatus.ERROR,
                    message=f"Invalid request for agent '{request.agent_type}'",
                    result=None
                )
            
            # Route to the agent
            logger.info(f"Routing request to agent: {request.agent_type}.{request.capability}")
            response = await agent.handle_request(request)
            
            # Add conversation ID if not set
            if not response.conversation_id and request.conversation_id:
                response.conversation_id = request.conversation_id
            
            return response
            
        except Exception as e:
            logger.error(f"Error routing request to {request.agent_type}: {e}", exc_info=True)
            return AgentResponse(
                status=AgentStatus.ERROR,
                message=f"Internal error: {str(e)}",
                result=None
            )
    
    def find_agents_with_capability(self, capability_name: str) -> List[str]:
        """
        Find all agents that support a specific capability.
        
        Args:
            capability_name: Name of the capability to search for
            
        Returns:
            List of agent types that support the capability
        """
        matching_agents = []
        for agent_type, agent in self._agents.items():
            if capability_name in agent.capabilities:
                matching_agents.append(agent_type)
        return matching_agents
    
    def get_agent_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status information for all registered agents.
        
        Returns:
            Dictionary with status information for each agent
        """
        status = {}
        for agent_type, agent in self._agents.items():
            try:
                status[agent_type] = {
                    "name": agent.name,
                    "description": agent.description,
                    "capabilities_count": len(agent.capabilities),
                    "status": "active"
                }
            except Exception as e:
                status[agent_type] = {
                    "name": getattr(agent, 'name', 'Unknown'),
                    "description": getattr(agent, 'description', 'Unknown'),
                    "capabilities_count": 0,
                    "status": "error",
                    "error": str(e)
                }
        return status

# Global registry instance
agent_registry = AgentRegistry() 