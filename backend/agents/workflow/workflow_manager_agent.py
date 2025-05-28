"""
Workflow Manager Agent

This agent plans multi-step workflows and coordinates execution by delegating
steps to specialised agents (e.g. `sparql`, `code`).

Current implementation keeps logic lightweight and heuristic-based – enough to
support the demos in `multi_agent_integration_demo.py` and to illustrate the
architecture described in the discussion.
"""

from __future__ import annotations

import logging
import uuid
from typing import Dict, Any, List, Optional

from pydantic import Field, BaseModel

from agents.base_agent import (
    BaseAgent,
    AgentCapability,
    AgentRequest,
    AgentResponse,
    AgentStatus,
)
from services.agent_registry import agent_registry

logger = logging.getLogger(__name__)


class WorkflowPlan(BaseModel):
    """Model for a workflow plan returned by the *plan_workflow* capability."""

    workflow_id: str = Field(...)
    steps: List[Dict[str, Any]] = Field(...)
    estimated_steps: int = Field(...)
    agents_involved: List[str] = Field(...)

    # runtime info (not part of initial planning)
    waiting_step: Optional[str] = None
    step_conversations: Dict[str, str] = Field(default_factory=dict)


class WorkflowManagerAgent(BaseAgent):
    """Simple workflow-manager agent that plans & executes notebook workflows."""

    def __init__(self):
        super().__init__(
            agent_type="workflow_manager",
            name="Workflow Manager Agent",
            description="Breaks down user requests into ordered steps and calls specialised agents.",
        )

        # capability: plan_workflow
        self.register_capability(
            AgentCapability(
                name="plan_workflow",
                description="Analyse user request and produce an ordered execution plan.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "user_input": {"type": "string"},
                    },
                    "required": ["user_input"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string"},
                        "workflow_plan": {"type": "object"},
                        "estimated_steps": {"type": "integer"},
                        "agents_involved": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                requires_conversation=False,
            )
        )

        # capability: execute_workflow
        self.register_capability(
            AgentCapability(
                name="execute_workflow",
                description="Execute a previously planned workflow identified by workflow_id.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string"},
                    },
                    "required": ["workflow_id"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string"},
                        "execution_results": {"type": "array"},
                        "failed_steps": {"type": "array"},
                    },
                },
                requires_conversation=False,
            )
        )

        # Internal store for workflow plans keyed by workflow_id
        self._workflow_store: Dict[str, WorkflowPlan] = {}

    # ---------------------------------------------------------------------
    # Core request handler
    # ---------------------------------------------------------------------

    async def handle_request(self, request: AgentRequest) -> AgentResponse:  # type: ignore[override]
        try:
            if request.capability == "plan_workflow":
                return await self._handle_plan_workflow(request)
            elif request.capability == "execute_workflow":
                return await self._handle_execute_workflow(request)
            else:
                return AgentResponse(
                    status=AgentStatus.ERROR,
                    message=f"Unknown capability '{request.capability}' for Workflow Manager",
                    result=None,
                )
        except Exception as e:
            logger.error("WorkflowManagerAgent error: %s", e, exc_info=True)
            return AgentResponse(
                status=AgentStatus.ERROR,
                message=str(e),
                result=None,
            )

    # ------------------------------------------------------------------
    # Conversation convenience (not critical for now)
    # ------------------------------------------------------------------

    def get_conversation_state(self, conversation_id: str) -> Optional[Dict[str, Any]]:  # noqa: D401
        return None  # not used for now

    def set_conversation_state(self, conversation_id: str, state: Dict[str, Any]) -> None:  # noqa: D401
        pass  # not used for now

    # ------------------------------------------------------------------
    # Capability implementations
    # ------------------------------------------------------------------

    async def _handle_plan_workflow(self, request: AgentRequest) -> AgentResponse:
        """Generate a naive plan based on heuristics (placeholder for LLM)."""
        user_request = request.user_input.strip()
        workflow_id = str(uuid.uuid4())

        steps: List[Dict[str, Any]] = []
        agents_involved: List[str] = []

        # Helper to decide if text implies a SPARQL data-fetch step
        def _needs_sparql(text: str) -> bool:
            text_l = text.lower()
            # keywords that suggest dataset discovery / data fetch
            fetch_kw = [
                "find",
                "fetch",
                "retrieve",
                "get",
                "query",
                "load",
                "discover",
            ]
            domain_kw = [
                "coral",
                "corals",
                "ice core",
                "sediment",
                "lipd",
                "d18o",
                "enso",
            ]
            if any(kw in text_l for kw in fetch_kw):
                return True
            # if mention of proxy types AND a temporal phrase like "years", "ka", etc.
            if any(kw in text_l for kw in domain_kw):
                if any(t in text_l for t in ["year", "yr", "ka", "bp", "past"]):
                    return True
            return False

        # Very lightweight heuristic plan – split by lines / bullets.
        lines = [line.strip(" •-*\n\t") for line in user_request.splitlines() if line.strip()]

        if not lines:
            lines = [user_request]

        # If there is only one line and it needs sparql, automatically add a code step afterwards.
        if len(lines) == 1 and _needs_sparql(lines[0]):
            # step 0 – sparql
            steps.append({
                "step_id": "t0",
                "agent_type": "sparql",
                "user_input": lines[0],
                "dependencies": [],
            })
            steps.append({
                "step_id": "t1",
                "agent_type": "code",
                "user_input": f"Generate Python code to analyse results from step t0. Original request: {lines[0]}",
                "dependencies": ["t0"],
            })
            agents_involved = ["sparql", "code"]
        else:
            for idx, line in enumerate(lines):
                line_lower = line.lower()
                if any(kw in line_lower for kw in ["find", "discover", "query", "sparql"]):
                    agent_type = "sparql"
                elif _needs_sparql(line):
                    # treat as data acquisition then analysis
                    # Insert two sub-steps for this single bullet
                    sp_step_id = f"t{idx}_a"
                    code_step_id = f"t{idx}_b"
                    steps.append({
                        "step_id": sp_step_id,
                        "agent_type": "sparql",
                        "user_input": line,
                        "dependencies": [f"t{idx-1}"] if idx > 0 else [],
                    })
                    steps.append({
                        "step_id": code_step_id,
                        "agent_type": "code",
                        "user_input": f"Generate Python code to analyse results from step {sp_step_id}. Original request: {line}",
                        "dependencies": [sp_step_id],
                    })
                    agents_involved.extend([a for a in ("sparql", "code") if a not in agents_involved])
                    continue  # skip default append below
                else:
                    agent_type = "code"

                step_id = f"t{idx}"
                dependencies = [f"t{idx-1}"] if idx > 0 else []
                steps.append(
                    {
                        "step_id": step_id,
                        "agent_type": agent_type,
                        "user_input": line,
                        "dependencies": dependencies,
                    }
                )
                if agent_type not in agents_involved:
                    agents_involved.append(agent_type)

        workflow_plan = {
            "steps": steps,
        }

        self._workflow_store[workflow_id] = WorkflowPlan(
            workflow_id=workflow_id,
            steps=steps,
            estimated_steps=len(steps),
            agents_involved=agents_involved,
        )

        logger.info("Planned workflow %s with %d steps", workflow_id, len(steps))

        return AgentResponse(
            status=AgentStatus.SUCCESS,
            message="Workflow planned successfully",
            result={
                "workflow_id": workflow_id,
                "workflow_plan": workflow_plan,
                "estimated_steps": len(steps),
                "agents_involved": agents_involved,
            },
        )

    async def _handle_execute_workflow(self, request: AgentRequest) -> AgentResponse:
        """Execute a stored workflow plan step-by-step."""
        workflow_id = request.context.get("workflow_id") or request.user_input or request.metadata.get(
            "workflow_id"
        )
        if not workflow_id:
            return AgentResponse(
                status=AgentStatus.ERROR,
                message="workflow_id not provided in context or input",
            )

        plan = self._workflow_store.get(workflow_id)
        if not plan:
            return AgentResponse(
                status=AgentStatus.ERROR,
                message=f"workflow_id '{workflow_id}' not found",
            )

        execution_results: List[Dict[str, Any]] = []
        failed_steps: List[Dict[str, Any]] = []

        # Forward any shared context from previous calls
        shared_context: Dict[str, Any] = {}

        # If we have clarification responses in metadata, pop them for later use
        clarification_responses = request.metadata.get("clarification_responses") if request.metadata else None
        target_step_id = request.metadata.get("target_step_id") if request.metadata else None

        for step in plan.steps:
            step_id = step["step_id"]
            agent_type = step["agent_type"]
            user_input = step["user_input"]
            logger.info("Executing workflow %s step %s (%s)", workflow_id, step_id, agent_type)

            # Build AgentRequest for this step
            step_metadata = request.metadata.copy() if request.metadata else {}

            # If this is a follow-up with clarification responses for this step, attach them
            if clarification_responses and (target_step_id is None or target_step_id == step_id):
                step_metadata = {**step_metadata, "clarification_responses": clarification_responses}
                # consume so it's not reused
                clarification_responses = None
                target_step_id = None

            # Reuse conversation_id if we have one stored for the step
            conversation_id = plan.step_conversations.get(step_id)

            agent_request = AgentRequest(
                agent_type=agent_type,
                capability="generate_query" if agent_type == "sparql" else "generate_code",
                user_input=user_input,
                context=shared_context,
                metadata=step_metadata,
                conversation_id=conversation_id,
            )

            response = await agent_registry.route_request(agent_request)

            # Persist conversation id for potential follow-ups
            if response.conversation_id:
                plan.step_conversations[step_id] = response.conversation_id

            if response.status == AgentStatus.SUCCESS:
                execution_results.append({
                    "step_id": step_id,
                    "status": response.status,
                    "result": response.result,
                })

                # Update shared context with new variables we care about
                if response.result:
                    shared_context.update({f"{step_id}_result": response.result})

            elif response.status == AgentStatus.NEEDS_CLARIFICATION:
                # Store waiting step and propagate clarification outward
                plan.waiting_step = step_id
                self._workflow_store[workflow_id] = plan  # update

                return AgentResponse(
                    status=AgentStatus.NEEDS_CLARIFICATION,
                    message=response.message,
                    result={
                        "workflow_id": workflow_id,
                        "step_id": step_id,
                        "clarification_questions": response.clarification_questions or response.result.get("clarification_questions", []),
                    },
                    conversation_id=response.conversation_id,
                )

            else:
                failed_steps.append({
                    "step_id": step_id,
                    "status": response.status,
                    "error": response.message,
                })
                # stop execution on first failure for simplicity
                logger.warning("Stopping workflow execution due to failure in step %s", step_id)
                break

        return AgentResponse(
            status=AgentStatus.SUCCESS if not failed_steps else AgentStatus.ERROR,
            message="Workflow executed" if not failed_steps else "Workflow executed with errors",
            result={
                "workflow_id": workflow_id,
                "execution_results": execution_results,
                "failed_steps": failed_steps,
            },
        ) 