import requests
import logging
from typing import Dict, List, Any, Optional
import textwrap
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SPARQLService:
    """
    Service for executing SPARQL queries against a GraphDB endpoint.
    """
    
    def __init__(self, endpoint_url: str = "http://localhost:7200/repositories/paleopal"):
        """
        Initialize the SPARQL service.
        
        Args:
            endpoint_url: URL of the GraphDB SPARQL endpoint
        """
        self.endpoint_url = endpoint_url
        logger.info(f"Initialized SPARQL service with endpoint: {endpoint_url}")
        
    def execute_query(self, query: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute a SPARQL query and return the results.
        
        Args:
            query: SPARQL query string
            limit: Optional limit to add if query doesn't already have one
            
        Returns:
            Dictionary containing query results
        """
        # Clean the query of any markdown code block syntax
        query = self._clean_query(query)
        
        # Only add LIMIT if the query doesn't already have one and limit is specified
        if limit and not re.search(r'\bLIMIT\s+\d+', query, re.IGNORECASE):
            query += f" LIMIT {limit}"
        
        headers = {
            "Accept": "application/sparql-results+json,application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "query": query
        }
        
        try:
            logger.info(f"Executing SPARQL query: {textwrap.shorten(query, width=100, placeholder='...')}")
            # Add a timeout to avoid hanging on slow endpoints
            response = requests.post(self.endpoint_url, headers=headers, data=data, timeout=10.0)
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            logger.info(f"SPARQL query executed successfully")
            
            return result
        except requests.exceptions.Timeout:
            logger.error(f"Timeout executing SPARQL query (10s limit)")
            return {"error": "Query timed out after 10 seconds"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error executing SPARQL query: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            return {"error": str(e)}
    
    def _clean_query(self, query: str) -> str:
        """
        Clean the query of any markdown code block syntax.
        
        Args:
            query: SPARQL query string, possibly with markdown formatting
            
        Returns:
            Clean SPARQL query
        """
        # Remove ```sparql and ``` markers if present
        if query.startswith("```sparql"):
            query = re.sub(r"^```sparql\s*", "", query)
            query = re.sub(r"\s*```$", "", query)
        elif query.startswith("```"):
            query = re.sub(r"^```\s*", "", query)
            query = re.sub(r"\s*```$", "", query)
        
        return query.strip()
    
    def format_results(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Format the SPARQL query results into a more user-friendly format.
        
        Args:
            result: Raw SPARQL query results
            
        Returns:
            Formatted list of result rows
        """
        if "error" in result:
            return [{"error": result["error"]}]
        
        try:
            formatted_results = []
            
            if "results" in result and "bindings" in result["results"]:
                bindings = result["results"]["bindings"]
                variables = result.get("head", {}).get("vars", [])
                
                for binding in bindings:
                    row = {}
                    for var, value in binding.items():
                        # Include the value type for better understanding
                        row[var] = {
                            "value": value["value"],
                            "type": value.get("type", "literal"),
                            "datatype": value.get("datatype", "")
                        }
                    formatted_results.append(row)
                
                # If no results, return empty list with variables
                if not formatted_results and variables:
                    return [{"variables": variables, "message": "No results found"}]
            
            return formatted_results
        except Exception as e:
            logger.error(f"Error formatting SPARQL results: {str(e)}")
            return [{"error": f"Error formatting results: {str(e)}"}]
    
    def format_results_table(self, result: Dict[str, Any]) -> str:
        """
        Format the SPARQL query results as a markdown table for human readability.
        
        Args:
            result: Raw SPARQL query results
            
        Returns:
            Markdown table string
        """
        if "error" in result:
            return f"Error: {result['error']}"
        
        try:
            if "results" in result and "bindings" in result["results"]:
                bindings = result["results"]["bindings"]
                variables = result.get("head", {}).get("vars", [])
                
                if not bindings:
                    return "No results found."
                
                # Create the table header
                table = "| " + " | ".join(variables) + " |\n"
                table += "| " + " | ".join(["---"] * len(variables)) + " |\n"
                
                # Add each row
                for binding in bindings:
                    row_values = []
                    for var in variables:
                        if var in binding:
                            val = binding[var]["value"]
                            # Truncate long values
                            if len(val) > 50:
                                val = val[:47] + "..."
                            row_values.append(val)
                        else:
                            row_values.append("")
                    
                    table += "| " + " | ".join(row_values) + " |\n"
                
                return table
            
            return "No results found or invalid results format."
        except Exception as e:
            logger.error(f"Error formatting SPARQL results as table: {str(e)}")
            return f"Error formatting results: {str(e)}"
    
    def get_result_stats(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get statistics about the query results.
        
        Args:
            result: Raw SPARQL query results
            
        Returns:
            Dictionary with statistics
        """
        stats = {
            "count": 0,
            "variables": [],
            "has_error": False,
            "error_message": None
        }
        
        if "error" in result:
            stats["has_error"] = True
            stats["error_message"] = result["error"]
            return stats
        
        try:
            if "results" in result and "bindings" in result["results"]:
                bindings = result["results"]["bindings"]
                variables = result.get("head", {}).get("vars", [])
                
                stats["count"] = len(bindings)
                stats["variables"] = variables
            
            return stats
        except Exception as e:
            stats["has_error"] = True
            stats["error_message"] = str(e)
            return stats
    
    def test_connection(self) -> bool:
        """
        Test if the connection to the SPARQL endpoint is working.
        
        Returns:
            True if connection is successful, False otherwise
        """
        test_query = "SELECT * WHERE { ?s ?p ?o } LIMIT 1"
        
        try:
            # Use a shorter timeout for connection testing
            headers = {
                "Accept": "application/sparql-results+json,application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "query": test_query
            }
            
            logger.info(f"Testing connection to SPARQL endpoint: {self.endpoint_url}")
            response = requests.post(self.endpoint_url, headers=headers, data=data, timeout=5.0)
            response.raise_for_status()
            
            # Check if the response is valid JSON
            result = response.json()
            logger.info(f"Successfully connected to SPARQL endpoint")
            return "results" in result
        except requests.exceptions.Timeout:
            logger.error(f"Connection test timed out after 5 seconds")
            return False
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error: Could not connect to {self.endpoint_url}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to SPARQL endpoint: {str(e)}")
            return False 