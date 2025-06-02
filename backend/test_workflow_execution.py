#!/usr/bin/env python3
"""
Test script to verify workflow execution calls agents and returns results.
"""

import asyncio
import logging
from agents.base_agent import AgentRequest
from services.agent_registry import agent_registry
from agents.sparql.sparql_generation_agent import SparqlGenerationAgent
from agents.code.code_generation_agent import CodeGenerationAgent
from agents.workflow.workflow_manager_agent import WorkflowManagerAgent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_workflow_execution():
    """Test the workflow planning and execution process."""
    
    # Initialize and register agents (same as in routers/agents.py)
    try:
        print("Initializing agents...")
        initialize_agents()
        
    except Exception as e:
        print(f"Error initializing agents: {e}")
        return
    
    print("\n" + "="*60)
    print("TESTING WORKFLOW EXECUTION")
    print("="*60)
    
    # Step 1: Plan a workflow
    print("\nStep 1: Planning workflow...")
    plan_request = AgentRequest(
        agent_type="workflow_manager",
        capability="plan_workflow",
        user_input="Find temperature proxy data from ice cores and create a time series plot",
        context={},
        metadata={"llm_provider": "google"}
    )
    
    try:
        plan_response = await agent_registry.route_request(plan_request)
        print(f"Planning Status: {plan_response.status}")
        print(f"Planning Message: {plan_response.message}")
        
        if plan_response.status != "success":
            print("❌ Workflow planning failed!")
            return
            
        workflow_result = plan_response.result
        workflow_id = workflow_result.get("workflow_id")
        workflow_plan = workflow_result.get("workflow_plan", {})
        steps = workflow_plan.get("steps", [])
        
        print(f"✅ Workflow planned successfully!")
        print(f"   Workflow ID: {workflow_id}")
        print(f"   Steps: {len(steps)}")
        
        # Show planned steps
        for i, step in enumerate(steps, 1):
            print(f"   {i}. [{step.get('agent_type', 'unknown')}] {step.get('user_input', '')[:50]}...")
            
    except Exception as e:
        print(f"❌ Error during planning: {e}")
        return
    
    # Step 2: Execute the workflow
    print(f"\nStep 2: Executing workflow {workflow_id}...")
    exec_request = AgentRequest(
        agent_type="workflow_manager",
        capability="execute_workflow",
        user_input="",
        context={"workflow_id": workflow_id},
        metadata={"llm_provider": "google"}
    )
    
    try:
        exec_response = await agent_registry.route_request(exec_request)
        print(f"Execution Status: {exec_response.status}")
        print(f"Execution Message: {exec_response.message}")
        
        if exec_response.result:
            execution_results = exec_response.result.get("execution_results", [])
            failed_steps = exec_response.result.get("failed_steps", [])
            
            print(f"✅ Execution completed!")
            print(f"   Successful steps: {len(execution_results)}")
            print(f"   Failed steps: {len(failed_steps)}")
            
            # Show execution results
            for i, result in enumerate(execution_results):
                step_id = result.get("step_id")
                status = result.get("status")
                step_result = result.get("result", {})
                
                print(f"\n   Step {i+1} ({step_id}): {status}")
                
                # Show generated code if available
                if "generated_code" in step_result:
                    generated_code = step_result["generated_code"]
                    print(f"      Generated code: {generated_code[:100]}...")
                
                # Show execution results if available
                if "execution_results" in step_result:
                    exec_results = step_result["execution_results"]
                    if isinstance(exec_results, list):
                        print(f"      Execution results: {len(exec_results)} items")
                    else:
                        print(f"      Execution results: {exec_results}")
            
            # Show failed steps
            for i, failure in enumerate(failed_steps):
                step_id = failure.get("step_id")
                error = failure.get("error")
                print(f"\n   ❌ Failed Step {i+1} ({step_id}): {error}")
                
        else:
            print("❌ No execution results returned!")
            
    except Exception as e:
        print(f"❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()

def initialize_agents():
    """Initialize all agents for testing."""
    # Initialize SPARQL agent
    sparql_agent = SparqlGenerationAgent()
    agent_registry.register_agent(sparql_agent)
    
    # Initialize Code Generation agent
    code_agent = CodeGenerationAgent()
    agent_registry.register_agent(code_agent)
    
    # Initialize Workflow Manager agent
    workflow_agent = WorkflowManagerAgent()
    agent_registry.register_agent(workflow_agent)
    
    print(f"Registered agents: {agent_registry.list_agents()}")

if __name__ == "__main__":
    asyncio.run(test_workflow_execution()) 