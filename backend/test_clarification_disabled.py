#!/usr/bin/env python3
"""
Test to verify that clarification settings are properly respected
by all agents including workflow manager.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath('.'))

from agents.base_agent import AgentRequest
from routers.agents import handle_agent_request, initialize_agents

async def test_clarification_disabled():
    """Test that clarification is properly disabled when requested."""
    print("🧪 Testing Clarification Disabled Functionality")
    print("=" * 60)
    
    # Initialize agents first
    print("🔧 Initializing agents...")
    try:
        initialize_agents()
        print("✅ Agents initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize agents: {e}")
        return False
    
    # Test 1: Direct SPARQL agent with clarification disabled
    print("\n1️⃣ Testing Direct SPARQL Agent with Clarification Disabled")
    sparql_request = AgentRequest(
        agent_type="sparql",
        capability="generate_query",
        user_input="Find d18O datasets from the Holocene period",
        metadata={
            "llm_provider": "google",
            "enable_clarification": False,
            "clarification_threshold": "conservative"
        }
    )
    
    print(f"   Request: {sparql_request.user_input}")
    print(f"   Enable Clarification: {sparql_request.metadata.get('enable_clarification')}")
    
    try:
        response = await handle_agent_request(sparql_request)
        print(f"   Status: {response.status}")
        if response.status.value == "needs_clarification":
            print("   ❌ FAILED: SPARQL agent still requesting clarification despite disabled setting")
            return False
        else:
            print("   ✅ PASSED: SPARQL agent respecting clarification disabled setting")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False
    
    # Test 2: Direct Code agent with clarification disabled
    print("\n2️⃣ Testing Direct Code Agent with Clarification Disabled")
    code_request = AgentRequest(
        agent_type="code",
        capability="generate_code",
        user_input="Load LIPD data into pandas DataFrame",
        metadata={
            "llm_provider": "google",
            "enable_clarification": False,
            "clarification_threshold": "conservative"
        }
    )
    
    print(f"   Request: {code_request.user_input}")
    print(f"   Enable Clarification: {code_request.metadata.get('enable_clarification')}")
    
    try:
        response = await handle_agent_request(code_request)
        print(f"   Status: {response.status}")
        if response.status.value == "needs_clarification":
            print("   ❌ FAILED: Code agent still requesting clarification despite disabled setting")
            return False
        else:
            print("   ✅ PASSED: Code agent respecting clarification disabled setting")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False
    
    # Test 3: Workflow Manager with clarification disabled
    print("\n3️⃣ Testing Workflow Manager with Clarification Disabled")
    workflow_request = AgentRequest(
        agent_type="workflow_manager",
        capability="plan_workflow", 
        user_input="Find coral datasets and plot temperature anomalies",
        metadata={
            "llm_provider": "google",
            "enable_clarification": False,
            "clarification_threshold": "conservative"
        }
    )
    
    print(f"   Request: {workflow_request.user_input}")
    print(f"   Enable Clarification: {workflow_request.metadata.get('enable_clarification')}")
    
    try:
        response = await handle_agent_request(workflow_request)
        print(f"   Status: {response.status}")
        
        if response.status.value == "success" and response.result:
            workflow_id = response.result.get("workflow_id")
            if workflow_id:
                print(f"   Workflow planned: {workflow_id}")
                
                # Test workflow execution with clarification disabled
                print("\n4️⃣ Testing Workflow Execution with Clarification Disabled")
                execute_request = AgentRequest(
                    agent_type="workflow_manager",
                    capability="execute_workflow",
                    user_input=workflow_id,
                    context={"workflow_id": workflow_id},
                    metadata={
                        "llm_provider": "google",
                        "enable_clarification": False,
                        "clarification_threshold": "conservative",
                        "workflow_id": workflow_id
                    }
                )
                
                print(f"   Executing workflow: {workflow_id}")
                print(f"   Enable Clarification: {execute_request.metadata.get('enable_clarification')}")
                
                execute_response = await handle_agent_request(execute_request)
                print(f"   Status: {execute_response.status}")
                
                if execute_response.status.value == "needs_clarification":
                    print("   ❌ FAILED: Workflow execution still requesting clarification despite disabled setting")
                    return False
                else:
                    print("   ✅ PASSED: Workflow execution respecting clarification disabled setting")
            else:
                print("   ❌ FAILED: No workflow_id returned from planning")
                return False
        else:
            print(f"   ❌ FAILED: Workflow planning failed: {response.message}")
            return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False
    
    print("\n🎉 All tests passed! Clarification disabled functionality working correctly.")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_clarification_disabled())
    if not success:
        print("\n💥 Some tests failed!")
        sys.exit(1)
    else:
        print("\n✅ All clarification disabled tests passed!") 