#!/usr/bin/env python
"""
Example client for interacting with the SPARQL API and handling clarifications properly.
This demonstrates how to:
1. Send an initial query
2. Check if clarification is needed
3. Send a response to the clarification
4. Receive the final SPARQL query
"""

import requests
import re
import sys

# Configuration
API_URL = "http://localhost:8000"  # Update this to your actual API URL

def generate_sparql(query, clarification_response=None):
    """
    Generate a SPARQL query, handling clarifications properly.
    
    Args:
        query: The natural language query
        clarification_response: Optional response to a clarification question
        
    Returns:
        The API response
    """
    # Prepare the request payload
    payload = {
        "query": query,
        "llm_provider": "openai"  # or your preferred provider
    }
    
    # Add clarification response if provided
    if clarification_response:
        payload["clarification_response"] = clarification_response
    
    # Send the request
    response = requests.post(f"{API_URL}/sparql/generate", json=payload)
    
    # Check if the request was successful
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None
    
    # Parse the response
    return response.json()

def handle_interactive_query():
    """Handle an interactive query with potential clarifications."""
    # Get the query from the user
    query = input("Enter your query: ")
    
    # Send the initial query
    response = generate_sparql(query)
    if not response:
        print("Failed to get response")
        return
    
    # Check if clarification is needed
    while response.get("needs_clarification", False):
        # Print the clarification question
        print("\nClarification needed:")
        print(response["message"])
        
        # Get the user's response
        clarification_response = input("\nYour response: ")
        
        # Send the clarification response
        response = generate_sparql(query, clarification_response)
        if not response:
            print("Failed to get response")
            return
    
    # Print the final SPARQL query
    print("\nGenerated SPARQL Query:")
    print(response["sparql_query"])
    
    # Print the results count if available
    if response.get("result_count") is not None:
        print(f"\nResults: {response['result_count']}")

def handle_automated_query(query, auto_select="option 2"):
    """
    Handle a query with automated clarification responses.
    This is useful for testing or batch processing.
    
    Args:
        query: The natural language query
        auto_select: Which option to automatically select (default: "option 2")
    """
    print(f"Query: {query}")
    
    # Send the initial query
    response = generate_sparql(query)
    if not response:
        print("Failed to get response")
        return
    
    # Check if clarification is needed
    if response.get("needs_clarification", False):
        print("\nClarification needed:")
        print(response["message"])
        
        # Extract state_id for properly tracking the conversation
        state_id = response.get("state_id")
        if not state_id:
            # Try to extract from message as fallback
            state_id_match = re.search(r'state_id=([a-f0-9-]+)', response["message"])
            state_id = state_id_match.group(1) if state_id_match else None
        
        if state_id:
            print(f"State ID: {state_id}")
            # Modify the query to include the state_id to ensure proper tracking
            query = f"{query} (state_id={state_id})"
        
        # Extract choices if available
        clarification_question = response.get("clarification_question", {})
        choices = clarification_question.get("choices", [])
        
        # Determine the response - either use the provided auto_select or pick from choices
        clarification_response = auto_select
        if choices:
            if auto_select.startswith("option "):
                try:
                    option_num = int(auto_select.split(" ")[1]) - 1
                    if 0 <= option_num < len(choices):
                        clarification_response = choices[option_num]
                    # Otherwise keep the original auto_select
                except (ValueError, IndexError):
                    pass
            elif auto_select.isdigit():
                # If it's just a number, try to use it as an index
                try:
                    option_num = int(auto_select) - 1
                    if 0 <= option_num < len(choices):
                        clarification_response = choices[option_num]
                except (ValueError, IndexError):
                    pass
        
        print(f"Automated response: {clarification_response}")
        
        # Send the clarification response
        response = generate_sparql(query, clarification_response)
        if not response:
            print("Failed to get response")
            return
    
    # Print the final SPARQL query
    print("\nGenerated SPARQL Query:")
    print(response.get("sparql_query", "No query generated"))
    
    # Print any error if present
    if not response.get("sparql_query") and response.get("message"):
        print("\nError or message:")
        print(response["message"])

if __name__ == "__main__":
    # Check for command-line arguments
    if len(sys.argv) > 1:
        # Use arguments as query
        query = sys.argv[1]
        auto_select = sys.argv[2] if len(sys.argv) > 2 else "option 2"
        handle_automated_query(query, auto_select)
    else:
        # Run interactive mode
        handle_interactive_query() 