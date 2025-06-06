"""
Workflow Manager Agent

This agent plans multi-step workflows and coordinates execution by delegating
steps to specialised agents (e.g. `sparql`, `code`).

Enhanced version uses LLM-based planning with context from:
1. Notebook workflow library (high weight) 
2. Literature methods library (lower weight, loose guidance)
3. Paleoclimatology domain knowledge
"""

from __future__ import annotations

import logging
import uuid
import json
import os
import sqlite3
from pathlib import Path
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
from services.search_integration_service import search_service
from services.service_manager import service_manager

# Import the utility function to handle custom agent creation
from utils.agent_utils import route_agent_request_with_custom_config

logger = logging.getLogger(__name__)

# SQLite DB path (shared with conversation data)
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "conversations.db"

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
    """Advanced workflow-manager agent that plans & executes notebook workflows using LLM and contextual search."""

    def __init__(self):
        super().__init__(
            agent_type="workflow_manager",
            name="Workflow Manager Agent",
            description="Breaks down user requests into ordered steps using LLM with notebook and literature context.",
        )

        # capability: plan_workflow
        self.register_capability(
            AgentCapability(
                name="plan_workflow",
                description="Analyse user request with contextual search and produce an LLM-generated execution plan.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "user_input": {"type": "string"},
                        "llm_provider": {
                            "type": "string", 
                            "enum": ["openai", "anthropic", "google", "xai", "ollama"], 
                            "default": "openai"
                        },
                        "model": {"type": "string", "default": None}
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

        # Internal in-memory cache
        self._workflow_store: Dict[str, WorkflowPlan] = {}

        # SQLite connection
        self._conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_plans (
                id TEXT PRIMARY KEY,
                plan_json TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

        self._load_workflows()

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
    # Enhanced LLM-based planning
    # ------------------------------------------------------------------

    async def _handle_plan_workflow(self, request: AgentRequest) -> AgentResponse:
        """Generate an LLM-based plan using contextual search for guidance."""
        user_request = request.user_input.strip()
        workflow_id = str(uuid.uuid4())

        try:
            # Get context from notebook workflows and literature methods
            logger.info("Searching for contextual guidance for workflow planning...")
            context = await search_service.get_context_for_planning(user_request)
            
            # Format context for LLM
            context_text = search_service.format_context_for_llm(context)
            
            # Create LLM prompt for workflow planning
            planning_prompt = self._create_planning_prompt(user_request, context_text)
            
            # Get LLM response using service manager
            try:
                # Get LLM provider from service manager (same pattern as code generation agent)
                llm_provider = getattr(request, 'llm_provider', None) or (request.metadata.get('llm_provider') if request.metadata else None) or 'openai'
                model = getattr(request, 'model', None) or (request.metadata.get('model') if request.metadata else None)
                
                llm = service_manager.get_llm_provider(
                    provider=llm_provider,
                    model=model
                )
                
                # Generate response using LangChain model with error handling
                llm_response = llm._call(planning_prompt)
                
                # Handle different response types (some models return AIMessage objects)
                if hasattr(llm_response, 'content'):
                    llm_response_text = llm_response.content
                elif hasattr(llm_response, 'text'):
                    llm_response_text = llm_response.text
                else:
                    llm_response_text = str(llm_response)
                
                # Parse LLM response to extract workflow steps
                steps, agents_involved = self._parse_llm_workflow_response(llm_response_text)
                
            except Exception as e:
                logger.warning(f"LLM planning failed, falling back to heuristic planning: {e}")
                # Fallback to simplified heuristic planning
                steps, agents_involved = self._fallback_heuristic_planning(user_request)

            workflow_plan = {
                "steps": steps,
                "context_used": {
                    "workflows_found": len(context.get("workflows", [])),
                    "methods_found": len(context.get("methods", [])),
                    "context_summary": context_text[:500] + "..." if len(context_text) > 500 else context_text,
                    # Include the actual examples for frontend display
                    "workflow_examples": context.get("workflows", []),
                    "method_examples": context.get("methods", [])
                }
            }

            self._store_workflow(workflow_id, WorkflowPlan(
                workflow_id=workflow_id,
                steps=steps,
                estimated_steps=len(steps),
                agents_involved=agents_involved,
            ))

            logger.info("Planned workflow %s with %d steps using %d workflow examples and %d method examples", 
                       workflow_id, len(steps), len(context.get("workflows", [])), len(context.get("methods", [])))

            return AgentResponse(
                status=AgentStatus.SUCCESS,
                message="Workflow planned successfully using contextual search and LLM",
                result={
                    "workflow_id": workflow_id,
                    "workflow_plan": workflow_plan,
                    "estimated_steps": len(steps),
                    "agents_involved": agents_involved,
                },
            )
            
        except Exception as e:
            logger.error(f"Error in workflow planning: {e}")
            return AgentResponse(
                status=AgentStatus.ERROR,
                message=f"Failed to plan workflow: {str(e)}",
                result=None,
            )

    def _create_planning_prompt(self, user_request: str, context_text: str) -> str:
        """Create the LLM prompt for workflow planning."""
        
        prompt = f"""You are an expert paleoclimatology workflow planner. Break down the user's request into actionable code steps that can be executed as notebook cells.

CONTEXT GUIDANCE:
{context_text}

USER REQUEST:
{user_request}

INSTRUCTIONS:
1. Analyze the user request and relevant context above
2. Give HIGHER WEIGHT to workflow examples (follow their patterns closely)
3. Use scientific methods as LOOSE GUIDANCE only (adapt concepts, don't copy exactly)
4. Apply your paleoclimatology domain knowledge to fill gaps
5. Break the task into 3-7 actionable steps that can be coded
6. Each step should be implementable as a notebook cell
7. Identify if steps need SPARQL (data fetching) or CODE (analysis/processing) agents

OUTPUT FORMAT (return JSON only):
{{
  "reasoning": "Brief explanation of your planning approach and how you used the context",
  "steps": [
    {{
      "step_id": "t0",
      "agent_type": "sparql|code",
      "user_input": "Clear instruction for what this step should accomplish",
      "dependencies": [],
      "rationale": "Why this step is needed"
    }},
    {{
      "step_id": "t1", 
      "agent_type": "sparql|code",
      "user_input": "Clear instruction for the next step",
      "dependencies": ["t0"],
      "rationale": "Why this step follows the previous"
    }}
  ]
}}

AGENT TYPES:
- "sparql": For discovering and fetching paleoclimate datasets (coral, ice core, sediment records)
- "code": For data analysis, visualization, modeling, statistical analysis

PALEOCLIMATOLOGY CONTEXT:
- Common data types: coral δ18O, ice core records, sediment cores, tree rings
- Common analyses: time series analysis, spectral analysis, correlation with climate indices
- Common climate indices: ENSO, AMO, NAO, PDO
- Typical workflows: data discovery → data loading → quality control → analysis → visualization
- Key periods: Holocene, Last Glacial Maximum, Medieval Warm Period, Little Ice Age

Return only the JSON object, no additional text."""

        return prompt

    def _parse_llm_workflow_response(self, llm_response: str) -> tuple[List[Dict[str, Any]], List[str]]:
        """Parse the LLM response to extract workflow steps."""
        import json
        import re
        
        try:
            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                workflow_data = json.loads(json_match.group())
            else:
                workflow_data = json.loads(llm_response)
            
            steps = workflow_data.get("steps", [])
            agents_involved = []
            
            # Extract unique agent types
            for step in steps:
                agent_type = step.get("agent_type")
                if agent_type and agent_type not in agents_involved:
                    agents_involved.append(agent_type)
            
            # Validate and clean up steps
            cleaned_steps = []
            for step in steps:
                cleaned_step = {
                    "step_id": step.get("step_id", f"t{len(cleaned_steps)}"),
                    "agent_type": step.get("agent_type", "code"),
                    "user_input": step.get("user_input", ""),
                    "dependencies": step.get("dependencies", []),
                }
                cleaned_steps.append(cleaned_step)
            
            return cleaned_steps, agents_involved
            
        except Exception as e:
            logger.error(f"Failed to parse LLM workflow response: {e}")
            raise

    def _fallback_heuristic_planning(self, user_request: str) -> tuple[List[Dict[str, Any]], List[str]]:
        """Fallback to simple heuristic planning if LLM fails."""
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

        return steps, agents_involved

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

        plan = self._get_workflow(workflow_id)
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
            
            # Gather results from dependency steps to give as focused context
            dependency_results: Dict[str, Any] = {}
            for dep_id in step.get("dependencies", []):
                dep_key = f"{dep_id}_result"
                if dep_key in shared_context:
                    dependency_results[dep_id] = shared_context[dep_key]

            # Compose context: include all shared context plus an explicit dependency section for clarity
            step_context = {
                **shared_context,  # full accumulated context
                "dependency_results": dependency_results  # focused relevant outputs
            }
            
            # Preserve clarification configuration settings from the original request
            # These should be passed to all individual agent steps
            enable_clarification = request.metadata.get("enable_clarification") if request.metadata else None
            clarification_threshold = request.metadata.get("clarification_threshold") if request.metadata else None
            if enable_clarification is not None:
                step_metadata["enable_clarification"] = enable_clarification
            if clarification_threshold is not None:
                step_metadata["clarification_threshold"] = clarification_threshold
            
            # Remove clarification responses from step metadata by default
            # They will only be added back if specifically intended for this step
            if "clarification_responses" in step_metadata:
                del step_metadata["clarification_responses"]

            # If this is a follow-up with clarification responses for this specific step, attach them
            if clarification_responses and target_step_id is not None and target_step_id == step_id:
                step_metadata["clarification_responses"] = clarification_responses
                # consume so it's not reused
                clarification_responses = None
                target_step_id = None

            # Reuse conversation_id if we have one stored for the step
            conversation_id = plan.step_conversations.get(step_id)

            agent_request = AgentRequest(
                agent_type=agent_type,
                capability="generate_query" if agent_type == "sparql" else "generate_code",
                user_input=user_input,
                context=step_context,
                metadata=step_metadata,
                conversation_id=conversation_id,
            )

            response = await route_agent_request_with_custom_config(agent_request)

            # Persist conversation id for potential follow-ups
            if response.conversation_id:
                plan.step_conversations[step_id] = response.conversation_id

            if response.status == AgentStatus.SUCCESS:
                execution_results.append({
                    "step_id": step_id,
                    "status": response.status,
                    "result": response.result,
                })

                # Store full result for global context
                shared_context[f"{step_id}_result"] = response.result
                # Additionally, if response.result contains structured fields like generated_code / generated_query,
                # bubble them up to top-level keys for easier reference by later LLM prompts.
                if isinstance(response.result, dict):
                    for k in ("generated_code", "generated_query", "execution_results"):
                        if k in response.result and response.result[k] is not None:
                            shared_context[f"{step_id}_{k}"] = response.result[k]

            elif response.status == AgentStatus.NEEDS_CLARIFICATION:
                # Store waiting step and propagate clarification outward
                plan.waiting_step = step_id
                self._store_workflow(workflow_id, plan)  # update with persistence

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

    def _save_workflow_to_db(self, workflow_id: str, plan: WorkflowPlan) -> None:
        try:
            plan_json = json.dumps(plan.model_dump(), ensure_ascii=False)
            self._conn.execute(
                "INSERT OR REPLACE INTO workflow_plans (id, plan_json) VALUES (?, ?)",
                (workflow_id, plan_json),
            )
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to save workflow {workflow_id} to DB: {e}")

    def _load_workflows(self) -> None:
        """Load workflow plans from SQLite into memory cache."""
        try:
            cur = self._conn.execute("SELECT id, plan_json FROM workflow_plans")
            for wid, pjson in cur.fetchall():
                try:
                    plan_data = json.loads(pjson)
                    self._workflow_store[wid] = WorkflowPlan(**plan_data)
                except Exception as e:
                    logger.warning(f"Skipping invalid workflow plan {wid}: {e}")
            logger.info(f"Loaded {len(self._workflow_store)} workflow plans from DB")
        except Exception as e:
            logger.error(f"Failed to load workflow plans from DB: {e}")

    def _store_workflow(self, workflow_id: str, plan: WorkflowPlan) -> None:
        """Store a workflow plan and persist to SQLite."""
        self._workflow_store[workflow_id] = plan
        self._save_workflow_to_db(workflow_id, plan)

    def _get_workflow(self, workflow_id: str) -> Optional[WorkflowPlan]:
        """Get a workflow plan from storage."""
        return self._workflow_store.get(workflow_id)

    # ------------------------------------------------------------------
    # Streaming support -------------------------------------------------
    # ------------------------------------------------------------------

    async def handle_request_streaming(self, request: AgentRequest, progress_callback=None):  # type: ignore
        """Stream workflow planning or execution with nested agent progress."""
        if request.capability == "plan_workflow":
            # Emit a start/complete pair so the UI shows progress during planning.
            planning_node_name = "plan_workflow"
            yield {
                "type": "node_start",
                "node_name": planning_node_name,
                "current_state": {}
            }

            resp = await self._handle_plan_workflow(request)

            # Mark planning finished
            yield {
                "type": "node_complete",
                "node_name": planning_node_name,
                "node_output": resp.result if hasattr(resp, "result") else None,
                "current_state": {"status": resp.status.value if hasattr(resp, "status") else "success"}
            }

            # Final complete event
            yield {"type": "complete", "response": resp.model_dump() if hasattr(resp, "model_dump") else resp}
            return

        if request.capability != "execute_workflow":
            # fall back to non-streaming
            resp = await self.handle_request(request)
            yield {"type": "complete", "response": resp.model_dump() if hasattr(resp, "model_dump") else resp}
            return

        workflow_id = request.context.get("workflow_id") or request.user_input or request.metadata.get("workflow_id")
        plan = self._get_workflow(workflow_id)
        if not plan:
            yield {"type": "error", "message": f"workflow_id '{workflow_id}' not found"}
            return

        shared_context: Dict[str, Any] = {}

        for step in plan.steps:
            step_id = step["step_id"]
            agent_type = step["agent_type"]
            user_input = step["user_input"]

            # Announce step start
            start_evt = {
                "type": "node_start",
                "node_name": f"{step_id}:{agent_type}",
                "current_state": {"step_id": step_id}
            }
            yield start_evt

            # Build sub-agent request
            step_metadata = request.metadata.copy() if request.metadata else {}
            
            # Gather results from dependency steps to give as focused context
            dependency_results: Dict[str, Any] = {}
            for dep_id in step.get("dependencies", []):
                dep_key = f"{dep_id}_result"
                if dep_key in shared_context:
                    dependency_results[dep_id] = shared_context[dep_key]

            # Compose context: include all shared context plus an explicit dependency section for clarity
            step_context = {
                **shared_context,  # full accumulated context
                "dependency_results": dependency_results  # focused relevant outputs
            }
            
            # Preserve clarification configuration settings from the original request
            # These should be passed to all individual agent steps
            enable_clarification = request.metadata.get("enable_clarification") if request.metadata else None
            clarification_threshold = request.metadata.get("clarification_threshold") if request.metadata else None
            if enable_clarification is not None:
                step_metadata["enable_clarification"] = enable_clarification
            if clarification_threshold is not None:
                step_metadata["clarification_threshold"] = clarification_threshold
            
            # Remove clarification responses from step metadata by default
            # They will only be added back if specifically intended for this step
            if "clarification_responses" in step_metadata:
                del step_metadata["clarification_responses"]

            # If this is a follow-up with clarification responses for this specific step, attach them
            if clarification_responses and target_step_id is not None and target_step_id == step_id:
                step_metadata["clarification_responses"] = clarification_responses
                # consume so it's not reused
                clarification_responses = None
                target_step_id = None

            # Reuse conversation_id if we have one stored for the step
            conversation_id = plan.step_conversations.get(step_id)

            agent_request = AgentRequest(
                agent_type=agent_type,
                capability="generate_query" if agent_type == "sparql" else "generate_code",
                user_input=user_input,
                context=step_context,
                metadata=step_metadata,
                conversation_id=conversation_id,
            )

            from services.agent_registry import agent_registry  # local import to avoid cycles

            sub_agent = agent_registry.get_agent(agent_type)

            if hasattr(sub_agent, "handle_request_streaming"):
                async for sub_evt in sub_agent.handle_request_streaming(agent_request):
                    # forward with prefixed node names
                    forwarded = dict(sub_evt)
                    if "node_name" in forwarded and forwarded["node_name"]:
                        forwarded["node_name"] = f"{step_id}.{forwarded['node_name']}"
                    yield forwarded
                    # collect results for shared context if complete
                    if forwarded.get("type") == "complete" and isinstance(forwarded.get("response"), dict):
                        res = forwarded["response"].get("result")
                        if res:
                            shared_context[f"{step_id}_result"] = res
            else:
                # non-streaming sub agent
                sub_resp = await sub_agent.handle_request(agent_request)
                yield {
                    "type": "node_complete",
                    "node_name": f"{step_id}:{agent_type}",
                    "node_output": sub_resp.result,
                    "current_state": {}
                }
                if sub_resp.result:
                    shared_context[f"{step_id}_result"] = sub_resp.result

            # mark step complete
            yield {
                "type": "node_complete",
                "node_name": f"{step_id}:{agent_type}",
                "node_output": {},
                "current_state": {"step_id": step_id, "status": "done"}
            }

        # After loop, produce final response via existing execute method
        final_resp = await self._handle_execute_workflow(request)
        yield {"type": "complete", "response": final_resp.model_dump() if hasattr(final_resp, "model_dump") else final_resp} 