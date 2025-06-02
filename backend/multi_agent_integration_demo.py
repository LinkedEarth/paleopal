#!/usr/bin/env python3
"""
Multi-Agent Integration Demo

This script demonstrates the new multi-agent integration capabilities:
1. Code Generation Agent automatically calling SPARQL Agent
2. Workflow Manager Agent coordinating complex workflows
3. Inter-agent communication and context sharing

Run this script to see the multi-agent system in action.
"""

import asyncio
import json
import logging
from typing import Dict, Any

import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure agents get registered when this script is run standalone
import routers.agents  # noqa: F401  # triggers initialize_agents on import

from agents.base_agent import AgentRequest, AgentStatus
from services.agent_registry import agent_registry

# -----------------------------------------------------------------------------
# Helper: call agent and handle clarification interactively via CLI
# -----------------------------------------------------------------------------

async def call_agent_interactive(request: AgentRequest):
    """Route a request; if the agent asks for clarification, prompt the user."""

    while True:
        response = await agent_registry.route_request(request)

        if response.status != AgentStatus.NEEDS_CLARIFICATION:
            return response

        # Show clarification questions and collect answers from CLI
        questions = response.clarification_questions or (
            response.result.get("clarification_questions") if response.result else []
        )

        if not questions:
            print("Agent requested clarification but provided no questions. Aborting.")
            return response

        print("\nAgent requires clarification. Please answer the following questions:")
        answers = []
        for idx, q in enumerate(questions, 1):
            q_text = q.get("question", q.get("text", str(q)))
            choices = q.get("choices") or q.get("options")
            prompt_text = f"{idx}. {q_text}"
            if choices and isinstance(choices, (list, tuple)):
                prompt_text += "\n   Choices: " + ", ".join(str(c) for c in choices)
            user_ans = input(f"{prompt_text}\n> ")
            answers.append({
                "question_id": q.get("id", f"q{idx}"),
                "question": q_text,
                "response": user_ans,
            })

        # Include target_step_id if provided in response.result
        follow_metadata = {**(request.metadata or {}), "clarification_responses": answers}
        if response.result and isinstance(response.result, dict) and response.result.get("step_id"):
            follow_metadata["target_step_id"] = response.result["step_id"]

        request = AgentRequest(
            agent_type=request.agent_type,
            capability=request.capability,
            conversation_id=response.conversation_id,
            user_input=request.user_input,
            context=request.context,
            notebook_context=request.notebook_context,
            metadata=follow_metadata,
        )

# -----------------------------------------------------------------------------

async def demo_workflow_manager():
    """Demonstrate workflow manager for complex multi-agent workflows."""
    print("\n" + "="*60)
    print("DEMO 2: Workflow Manager")
    print("="*60)
    
    # Complex request requiring multiple agents
    complex_request = "Use corals d18O from past 10,000 years to understand how ENSO has changed"
    
    print(f"Workflow Request: {complex_request}")
    
    # Step 1: Plan the workflow
    plan_request = AgentRequest(
        agent_type="workflow_manager",
        capability="plan_workflow",
        user_input=complex_request,
        context={},
        metadata={"llm_provider": "google"}
    )
    
    print("\nStep 1: Planning workflow...")
    try:
        plan_response = await call_agent_interactive(plan_request)
        
        if plan_response.status == "success":
            workflow_plan = plan_response.result
            workflow_id = workflow_plan.get("workflow_id")
            
            print(f"✓ Workflow planned successfully!")
            print(f"  Workflow ID: {workflow_id}")
            print(f"  Steps: {workflow_plan.get('estimated_steps', 0)}")
            print(f"  Agents involved: {workflow_plan.get('agents_involved', [])}")
            
            # Show workflow steps
            plan_details = workflow_plan.get("workflow_plan", {})
            steps = plan_details.get("steps", [])
            print(f"\nWorkflow Steps:")
            for i, step in enumerate(steps, 1):
                print(f"  {i}. {step.get('agent_type', 'unknown')} - {step.get('user_input', '')[:50]}...")
                if step.get('dependencies'):
                    print(f"     Dependencies: {step['dependencies']}")
            
            # Step 2: Execute the workflow
            print(f"\nStep 2: Executing workflow...")
            execute_request = AgentRequest(
                agent_type="workflow_manager",
                capability="execute_workflow",
                user_input="",
                context={"workflow_id": workflow_id},
                metadata={}
            )
            
            execute_response = await call_agent_interactive(execute_request)
            
            print(f"Execution Status: {execute_response.status}")
            print(f"Message: {execute_response.message}")
            
            if execute_response.result:
                execution_results = execute_response.result.get("execution_results", [])
                failed_steps = execute_response.result.get("failed_steps", [])
                
                print(f"\nExecution Summary:")
                print(f"  Completed steps: {len(execution_results)}")
                print(f"  Failed steps: {len(failed_steps)}")
                
                for result in execution_results:
                    step_id = result.get("step_id", "unknown")
                    status = result.get("status", "unknown")
                    print(f"    {step_id}: {status}")
                
                if failed_steps:
                    print(f"\nFailed Steps:")
                    for failure in failed_steps:
                        print(f"    {failure.get('step_id', 'unknown')}: {failure.get('error', 'unknown error')}")

                # ------------------------------------------------------------------
                # Optional: write workflow outputs to a notebook
                # ------------------------------------------------------------------

                if execution_results:
                    nb = new_notebook()
                    nb.cells.append(new_markdown_cell("# PaleoPal Workflow Demo\nGenerated by multi_agent_integration_demo.py"))

                    for step in execution_results:
                        sid = step.get("step_id")
                        res = step.get("result", {}) or {}

                        # Add a markdown description cell
                        nb.cells.append(new_markdown_cell(f"## Step {sid}"))

                        code_to_add = None
                        if isinstance(res, dict):
                            if res.get("generated_code"):
                                code_to_add = res["generated_code"]
                            elif res.get("sparql_query"):
                                q = res["sparql_query"]
                                code_to_add = f"query_{sid} = \"\"\"\n{q}\n\"\"\"\nresults_{sid} = graphdb.query(query_{sid})"

                        if code_to_add:
                            nb.cells.append(new_code_cell(code_to_add))

                    notebook_path = "workflow_demo_output.ipynb"
                    with open(notebook_path, "w") as f:
                        nbformat.write(nb, f)
                    print(f"\nNotebook written to {notebook_path}")
        
        else:
            print(f"✗ Workflow planning failed: {plan_response.message}")
            
    except Exception as e:
        print(f"Error in workflow demo: {e}")

async def demo_manual_agent_coordination():
    """Demonstrate manual coordination between agents."""
    print("\n" + "="*60)
    print("DEMO 3: Manual Agent Coordination")
    print("="*60)
    
    print("Step 1: Get data with SPARQL Agent...")
    
    # First, get data using SPARQL agent
    sparql_request = AgentRequest(
        agent_type="sparql",
        capability="generate_query",
        user_input="Find coral proxy data from the Pacific Ocean for ENSO analysis",
        context={},
        metadata={}
    )
    
    try:
        sparql_response = await agent_registry.route_request(sparql_request)
        
        print(f"SPARQL Status: {sparql_response.status}")
        print(f"SPARQL Message: {sparql_response.message}")
        
        if sparql_response.status == "success" and sparql_response.result:
            sparql_results = sparql_response.result.get("results", [])
            sparql_query = sparql_response.result.get("sparql_query", "")
            
            print(f"✓ Found {len(sparql_results)} datasets")
            print(f"SPARQL Query: {sparql_query[:100]}..." if sparql_query else "No query returned")
            
            # Step 2: Use the SPARQL results in code generation
            print(f"\nStep 2: Generate analysis code using the fetched data...")
            
            code_request = AgentRequest(
                agent_type="code",
                capability="generate_code",
                user_input="Create code to analyze the coral data for ENSO signals using spectral analysis",
                context={
                    "data_context": {
                        "sparql_results": sparql_results,
                        "sparql_query": sparql_query,
                        "data_source": "graphdb_triplestore",
                        "datasets_found": len(sparql_results)
                    }
                },
                metadata={"llm_provider": "google"}
            )
            
            code_response = await agent_registry.route_request(code_request)
            
            print(f"Code Generation Status: {code_response.status}")
            print(f"Code Generation Message: {code_response.message}")
            
            if code_response.result:
                generated_code = code_response.result.get("generated_code", "")
                libraries = code_response.result.get("required_libraries", [])
                
                print(f"✓ Generated {len(generated_code)} characters of code")
                print(f"Required Libraries: {libraries}")
                
                # Show code snippet
                if generated_code:
                    lines = generated_code.split('\n')[:8]
                    print(f"\nCode Preview:")
                    for i, line in enumerate(lines, 1):
                        print(f"{i:2d}: {line}")
                    if len(generated_code.split('\n')) > 8:
                        print("    ... (truncated)")
        
        else:
            print(f"✗ SPARQL query failed: {sparql_response.message}")
            
    except Exception as e:
        print(f"Error in manual coordination demo: {e}")

async def demo_agent_status():
    """Show current agent status and capabilities."""
    print("\n" + "="*60)
    print("DEMO 4: Agent Status and Capabilities")
    print("="*60)
    
    # List all available agents
    agents = agent_registry.list_agents()
    
    print(f"Available Agents: {len(agents)}")
    for agent in agents:
        agent_type = agent.get("agent_type", "unknown")
        name = agent.get("name", "Unknown")
        description = agent.get("description", "No description")
        capabilities = agent.get("capabilities", {})
        
        print(f"\n{agent_type.upper()} AGENT:")
        print(f"  Name: {name}")
        print(f"  Description: {description}")
        print(f"  Capabilities: {len(capabilities)}")
        
        for cap_name, cap_info in capabilities.items():
            cap_desc = cap_info.get("description", "No description")
            requires_conv = cap_info.get("requires_conversation", False)
            print(f"    - {cap_name}: {cap_desc}")
            if requires_conv:
                print(f"      (requires conversation)")

async def main():
    """Run all demos."""
    print("Multi-Agent Integration Demo")
    print("This demo showcases the new multi-agent capabilities in PaleoPal")
    
    # Show agent status first
    await demo_agent_status()
    
    # Demo 1: Workflow manager
    await demo_workflow_manager()
    
    # Demo 2: Manual agent coordination
    await demo_manual_agent_coordination()
    
    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60)
    print("The multi-agent integration system provides:")
    print("✓ Complex workflow planning and execution")
    print("✓ Inter-agent communication and context sharing")
    print("✓ Dependency management and error handling")
    print("\nSee backend/docs/MULTI_AGENT_INTEGRATION.md for detailed documentation.")

if __name__ == "__main__":
    # Run the demo
    asyncio.run(main()) 
