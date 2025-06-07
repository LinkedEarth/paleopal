"""
Node handlers for the SPARQL generation agent.
Updated to work with Pydantic state and unified config.
"""

import logging
import re
import json
import uuid
from typing import Dict, Any, List
from langchain.chat_models.base import BaseChatModel
from langchain.schema import HumanMessage, SystemMessage
from .state import SparqlAgentState, SparqlAgentConfig
from agents.base_state import MAX_REFINEMENTS
from agents.base_langgraph_agent import get_config_value, get_message_value
from .tools import execute_sparql_query
from services.llm_providers import LLMProviderFactory
from .ontology_context import ONTOLOGY_PREFIXES, ONTOLOGY_CLASSES, ONTOLOGY_PROPERTIES, PROPERTY_VALIDATION
from services.service_manager import service_manager
from services.search_integration_service import search_service
from config import DEFAULT_LLM_PROVIDER

logger = logging.getLogger(__name__)

def extract_user_query(state: SparqlAgentState, config: SparqlAgentConfig) -> Dict[str, Any]:
    """Extract user query from the latest message."""
    try:
        logger.info("=== EXTRACT USER QUERY NODE CALLED ===")
        
        messages = state.messages or []
        if not messages:
            return {
                "error_message": "No messages found in state",
                "conversation_id": state.conversation_id
            }
        
        # Get the last message (most recent user input)
        last_message = messages[-1]
        
        # Handle both dict and object message formats
        if isinstance(last_message, dict):
            user_query = last_message.get("content", "")
        else:
            user_query = getattr(last_message, "content", "")
        
        if not user_query:
            return {
                "error_message": "No user query found in last message",
                "conversation_id": state.conversation_id
            }
        
        logger.info(f"Extracted user query: '{user_query[:50]}...'")
        
        return {
            "user_query": user_query,
            "conversation_id": state.conversation_id  # Preserve conversation_id
        }
    except Exception as e:
        logger.error(f"Error extracting user query: {e}")
        return {
            "error_message": str(e),
            "conversation_id": state.conversation_id
        }

def get_similar_queries_node(state: SparqlAgentState, config: SparqlAgentConfig) -> Dict[str, Any]:
    """Get similar SPARQL queries from the database."""
    try:
        user_input = state.user_input or ""
        if not user_input:
            return {
                "similar_code": [],
                "conversation_id": state.conversation_id
            }
        
        # Use the search service to get similar queries
        import asyncio
        similar_queries = asyncio.run(search_service.search_sparql_queries(user_input, top_k=3))
        
        logger.info(f"Found {len(similar_queries)} similar SPARQL queries")
        return {
            "similar_code": similar_queries,
            "conversation_id": state.conversation_id  # Preserve conversation_id
        }
    except Exception as e:
        logger.error(f"Error getting similar queries: {e}")
        return {
            "error_message": str(e),
            "conversation_id": state.conversation_id
        }

def extract_paleo_terms(llm: BaseChatModel, user_query: str) -> List[str]:
    """
    Extract relevant paleoclimate terms from a user query using an LLM.
    
    Args:
        llm: LLM model to use
        user_query: Raw user query
        
    Returns:
        List of extracted paleoclimate terms
    """
    try:
        # Construct a prompt that asks the LLM to extract relevant terms
                # Simple prompt for entity term extraction
        prompt = f"""Analyze this paleoclimate query and extract key domain terms that may match ontology entities:

Query: "{user_query}"

Extract specialized terms like:
- Archive types (coral, ice core, speleothem, etc.)
- Variables (d18O, temperature, precipitation, etc.)
- Units (permil, degrees Celsius, etc.)
- Proxy types (radiocarbon, alkenone, etc.)

Return ONLY a JSON array of the extracted terms:
["term1", "term2", "term3"]
"""

        # Generate the extraction using LangChain message types
        messages = [
            SystemMessage(content="You are a paleoclimate data expert. Extract only the relevant terms without explanation."),
            HumanMessage(content=prompt)
        ]
        # Execute LLM directly with the prompt
        response = llm._call(messages).strip()

        # Extract JSON from the response
        json_pattern = re.compile(r'\[\s*".*"\s*\]', re.DOTALL)
        match = json_pattern.search(response)

        terms = []
        if match:
            try:
                terms = json.loads(match.group(0))
            except Exception as e:
                logger.warning(f"Error parsing LLM output as JSON: {str(e)}")
                # Fallback: try to find JSON with more relaxed pattern
                match = re.search(r'(\[.*\])', response, re.DOTALL)
                if match:
                    try:
                        terms = json.loads(match.group(1))
                    except Exception as e:
                        logger.warning(f"Error parsing with relaxed pattern: {str(e)}")

        logger.info(f"Extracted paleo terms: {terms}")
        return terms
    except Exception as e:
        logger.error(f"Error extracting paleo terms: {e}")
        # Return the user query as a single term as fallback
        return [user_query]

def get_entity_matches_node(state: SparqlAgentState, config: SparqlAgentConfig) -> Dict[str, Any]:
    """Get entity matches for the user query (fallback if not already available)."""
    try:
        # Check if entity matches are already available from unified context
        if hasattr(state, 'entity_matches') and state.entity_matches:
            logger.info(f"Entity matches already available from unified context: {len(state.entity_matches)} matches")
            return {}  # No additional updates needed
        
        # Fallback: Get entity matches individually if not available from unified context
        logger.info("Entity matches not available from unified context, retrieving individually as fallback")
        
        # Use the search service directly (it now includes term extraction)
        import asyncio
        entity_matches = asyncio.run(search_service.search_ontology_entities(
            query=state.user_input or "",
            use_term_extraction=True  # Enable LLM-based term extraction
        ))
        
        logger.info(f"Found {len(entity_matches)} entity matches via fallback search")
        return {
            "entity_matches": entity_matches,
            "conversation_id": state.conversation_id  # Preserve conversation_id
        }
        
    except Exception as e:
        logger.error(f"Error getting entity matches: {e}")
        return {
            "error_message": str(e),
            "conversation_id": state.conversation_id
        }

def identify_clarification_needs(
    llm: BaseChatModel,
    user_query: str,
    entity_matches: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Identify if the user query needs clarification and generate appropriate questions.
    
    Args:
        llm: LLM model to use
        user_query: Raw user query
        entity_matches: Entity matches found for the query
        
    Returns:
        Dict with 'needs_clarification' flag and 'questions' list if needed
    """
    try:
        # Group matched entities by their type
        entity_groups = {}
        for match in entity_matches:
            entity_type = match.get('type', 'Unknown')
            uri = match.get('uri', '')
            label = match.get('label', uri.split('#')[-1] if '#' in uri else uri.split('/')[-1])
            similarity = match.get('similarity', 0.0)
            
            if entity_type not in entity_groups:
                entity_groups[entity_type] = []
            
            entity_groups[entity_type].append({
                'uri': uri,
                'label': label,
                'similarity': similarity
            })
        
        # Check for potential ambiguities
        ambiguities = []
        
        # Case 1: Multiple high-confidence matches of the same type
        for entity_type, matches in entity_groups.items():
            if len(matches) > 1:
                # Check if multiple matches have high confidence (similarity > 0.7)
                high_confidence_matches = [m for m in matches if m['similarity'] > 0.7]
                if len(high_confidence_matches) > 1:
                    ambiguities.append({
                        'type': entity_type,
                        'matches': high_confidence_matches,
                        'description': f"Multiple {entity_type} matches with high confidence"
                    })
        
        # Case 2: Matches across different entity types for similar terms
        # (e.g., d18O as both a variable and a proxy)
        term_groups = {}
        for match in entity_matches:
            label = match.get('label', '').lower()
            uri = match.get('uri', '')
            entity_type = match.get('type', 'Unknown')
            
            # Extract the main term (e.g., "d18O" from "d18O measurement")
            # This regex specifically handles paleoclimate terms like d18O, d13C, etc.
            main_terms = re.findall(r'\b([a-zA-Z0-9]+(?:\-[a-zA-Z0-9]+)*|d\d+O|d\d+C|Sr\/Ca|Mg\/Ca)\b', label, re.IGNORECASE)
            for term in main_terms:
                term = term.lower()  # Normalize to lowercase
                if term not in term_groups:
                    term_groups[term] = []
                term_groups[term].append({
                    'uri': uri,
                    'type': entity_type,
                    'label': match.get('label', '')
                })
        
        # Identify terms that appear across different entity types
        for term, entities in term_groups.items():
            entity_types = set(e['type'] for e in entities)
            if len(entity_types) > 1 and len(term) > 2:  # Avoid short, common words
                # Add specific handling for common paleoclimate ambiguities
                is_common_proxy = term.lower() in ['d18o', 'd13c', 'mg/ca', 'sr/ca', 'uk37', 'toc']
                
                ambiguities.append({
                    'term': term,
                    'entity_types': list(entity_types),
                    'matches': entities,
                    'is_common_proxy': is_common_proxy,
                    'description': f"The term '{term}' appears in multiple entity types: {', '.join(entity_types)}"
                })
        
        # If we found ambiguities, generate clarification questions
        if ambiguities:
            # Format the ambiguities for the LLM prompt
            ambiguities_text = []
            
            for i, a in enumerate(ambiguities):
                # Add detailed information about each ambiguity
                ambiguity_desc = f"{i+1}. {a['description']}"
                
                # Add details for each entity match
                match_details = []
                for match in a.get('matches', []):
                    match_type = match.get('type', 'Unknown')
                    match_label = match.get('label', 'Unknown')
                    match_details.append(f"   - {match_label} (as {match_type})")
                
                # Join all the details
                ambiguity_text = ambiguity_desc + "\n" + "\n".join(match_details)
                ambiguities_text.append(ambiguity_text)
            
            # Join all ambiguities with spacing
            ambiguities_formatted = "\n\n".join(ambiguities_text)
            
            # Create a prompt to generate clarification questions
            prompt = f"""Based on the user's query and the entity matches found, I need to generate clarification questions.

USER QUERY: "{user_query}"

AMBIGUITIES DETECTED:
{ambiguities_formatted}

For each ambiguity, generate a clear, concise question to ask the user. These questions should help disambiguate the query.
Each question should:
1. Be specific about the ambiguity
2. Offer clear choices (as an array of strings)
3. Explain briefly why this clarification will help

Special cases for paleoclimate terms:
- For d18O, ask if they're looking for d18O as a variable, as a proxy, or both
- For terms that can be both a variable and a proxy, explain the difference
- For terms with multiple versions, ask for specificity

Generate the questions in a JSON format like this:
```json
{{
  "questions": [
    {{
      "id": "q1",
      "question": "The full question text",
      "choices": ["Option 1", "Option 2", "Both", "Neither"],
      "context": "Brief explanation of why this clarification is needed"
    }},
    {{
      "id": "q2",
      "question": "Another question if needed",
      "choices": ["Choice A", "Choice B", "Choice C"],
      "context": "Brief explanation for this question"
    }}
  ]
}}
```

IMPORTANT: Include meaningful choices as array items, not comma-separated text.
Return ONLY the valid JSON without any additional text."""

            # Generate the clarification questions
            messages = [
                SystemMessage(content="You are a paleoclimate data expert helping to generate clarification questions. Return only valid JSON."),
                HumanMessage(content=prompt)
            ]
            
            response = llm._call(messages).strip()
            
            # Extract JSON from the response
            json_pattern = re.compile(r'\{.*\}', re.DOTALL)
            match = json_pattern.search(response)
            
            questions = []
            if match:
                try:
                    json_str = match.group(0)
                    json_data = json.loads(json_str)
                    
                    # Extract the questions from the JSON
                    if "questions" in json_data:
                        questions = json_data["questions"]
                except Exception as e:
                    logger.warning(f"Error parsing LLM output as JSON: {str(e)}")
                    # Try a more relaxed approach
                    try:
                        # Use regex to look for JSON array pattern
                        array_match = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
                        if array_match:
                            questions = json.loads(array_match.group(0))
                    except Exception as nested_e:
                        logger.warning(f"Error with relaxed JSON parsing: {str(nested_e)}")
            
            # Return the result
            if questions:
                return {
                    'needs_clarification': True,
                    'questions': questions,
                    'ambiguities': ambiguities
                }
        
        # No ambiguities or couldn't generate questions
        return {
            'needs_clarification': False,
            'questions': []
        }
    except Exception as e:
        logger.error(f"Error in identify_clarification_needs: {e}")
        # Return no clarification needed in case of error
        return {
            'needs_clarification': False,
            'questions': []
        }

def clarify_query_node(state: SparqlAgentState, config: SparqlAgentConfig) -> Dict[str, Any]:
    """
    Analyze the query and entity matches to identify if clarification is needed.
    If so, add clarification questions to the state.
    """
    try:
        # Access the LLM directly from service manager
        llm = service_manager.get_llm_provider(state.llm_provider or DEFAULT_LLM_PROVIDER)
        
        # Skip if we don't have entity matches
        if not state.entity_matches:
            return {"needs_clarification": False}
        
        # Identify if clarification is needed
        clarification_info = identify_clarification_needs(
            llm,
            state.user_input,
            state.entity_matches
        )
        
        # Return only the updated fields
        return {
            "needs_clarification": clarification_info.get("needs_clarification", False),
            "clarification_questions": clarification_info.get("questions", []),
            "clarification_ambiguities": clarification_info.get("ambiguities", [])
        }
    except Exception as e:
        logger.error(f"Error in clarify_query_node: {e}")
        return {"error_message": str(e)}

def should_ask_for_clarification(state: SparqlAgentState) -> str:
    """
    Determine if we should ask for clarification from the user.
    
    Returns:
        str: "true" if clarification is needed, "false" otherwise
    """
    
    # Log detailed state information for debugging
    logger.info(f"Clarification check - "
                f"needs_clarification: {state.needs_clarification}, "
                f"has_responses: {bool(state.clarification_responses)}, "
                f"processed: {state.clarification_processed}")
    
    # If clarification has been explicitly turned off, don't ask
    if state.needs_clarification is False:
        logger.info("Clarification explicitly turned off")
        return "false"
        
    # If we already have clarification responses, don't ask again
    if state.clarification_responses:
        logger.info("Clarification responses already provided, not asking again")
        return "false"
        
    # If the clarification has been processed, don't ask again
    if state.clarification_processed:
        logger.info("Clarification already processed, not asking again")
        return "false"
    
    # Check if we need clarification and have questions
    if state.needs_clarification and state.clarification_questions:
        questions = state.clarification_questions
        logger.info(f"Clarification needed with {len(questions)} question(s)")
        return "true"
    
    return "false"

def process_clarification_response(state: SparqlAgentState, config: SparqlAgentConfig) -> Dict[str, Any]:
    """
    Process the user's response to clarification questions and update the state.
    This assumes the last message in the state is the user's response to clarification.
    """
    try:
        # Get the clarification response (assumed to be the last message)
        messages = state.messages or []
        if not messages or len(messages) < 2:
            # Not enough messages to have a response
            logger.warning("Not enough messages to process clarification response")
            return {"clarification_processed": False}
        
        # Get the user's response (last message)
        last_message = messages[-1]
        
        # Extract the text using the helper function
        clarification_response = ""
        
        # Check if the last message is from a user and get content
        role = get_message_value(last_message, 'role')
        if role == 'user':
            clarification_response = get_message_value(last_message, 'content', '')
        
        # Fallback: try alternative extraction methods
        if not clarification_response:
            if hasattr(last_message, "text"):
                clarification_response = last_message.text()
            elif hasattr(last_message, "content"):
                clarification_response = str(last_message.content)
        
        # Safeguard: if no response was extracted, add a default
        if not clarification_response:
            logger.warning("No clarification response could be extracted")
            clarification_response = "Please continue with the best option"
        
        # Process the clarification response
        return process_multiple_clarification_responses(state, clarification_response)
    except Exception as e:
        logger.error(f"Error processing clarification response: {e}", exc_info=True)
        # Return a state that allows the flow to continue despite the error
        return {
            "error_message": str(e),
            "clarification_processed": True,
            "needs_clarification": False  # Force continuing without more clarification
        }

def process_multiple_clarification_responses(state: SparqlAgentState, response_text: str) -> Dict[str, Any]:
    """
    Process multiple clarification responses.
    
    Args:
        state: Current agent state
        response_text: User's response text
        
    Returns:
        Updated state with processed clarification responses
    """
    try:
        # Get the current list of responses and questions
        responses = state.clarification_responses or []
        questions = state.clarification_questions or []
        
        # If we have no questions, return without changes
        if not questions:
            logger.warning("No clarification questions found")
            return {"clarification_processed": True, "needs_clarification": False}
        
        # If we have multiple lines in the response, it might be multiple answers
        response_lines = [line.strip() for line in response_text.split('\n') if line.strip()]
        
        # If we have the same number of lines as unanswered questions, treat each line as a separate answer
        unanswered_questions = [q for q in questions if not any(r.get("question_id") == q.get("id") for r in responses)]
        
        if len(response_lines) == len(unanswered_questions) and len(response_lines) > 1:
            # Process each line as a separate answer
            for i, question in enumerate(unanswered_questions):
                if i < len(response_lines):
                    responses.append({
                        "question_id": question.get("id", f"q{i+1}"),
                        "response": response_lines[i],
                        "question": question.get("question", "")
                    })
        else:
            # Treat the entire response as an answer to the first unanswered question
            if unanswered_questions:
                first_question = unanswered_questions[0]
                
                responses.append({
                    "question_id": first_question.get("id", "q1"),
                    "response": response_text,
                    "question": first_question.get("question", "")
                })
        
        # Check if we still have unanswered questions
        updated_unanswered = [q for q in questions if not any(r.get("question_id") == q.get("id") for r in responses)]
        needs_more_clarification = len(updated_unanswered) > 0
        
        # If all questions are answered, mark as processed
        clarification_processed = not needs_more_clarification
        
        return {
            "clarification_responses": responses,
            "clarification_processed": clarification_processed,
            "needs_clarification": needs_more_clarification
        }
    except Exception as e:
        logger.error(f"Error processing multiple clarification responses: {e}", exc_info=True)
        # Return a state that allows the flow to continue despite the error
        return {
            "error_message": str(e),
            "clarification_processed": True,
            "needs_clarification": False
        }

def build_property_validation_prompt(
    prefixes: str, 
    common_properties: str, 
    validation_examples: str
) -> str:
    """
    Build the property validation portion of the SPARQL prompt.
    
    Args:
        prefixes: Ontology prefixes
        common_properties: Property relationships
        validation_examples: Examples of valid property usage
        
    Returns:
        Formatted property validation prompt section
    """
    return f"""PREFIXES:
{prefixes}

PROPERTIES:
[domain] -> [property] -> [range]
----------------------------------
{common_properties}

VALID PROPERTY PATTERNS:
{validation_examples}

PROPERTY USAGE RULES:
1. Each property MUST be used with subjects and objects of the correct type
2. Check the property list to see which domains (subjects) and ranges (objects) are valid
3. For example, if you see "le:Dataset -> le:hasPaleoData -> le:PaleoData":
   - CORRECT: ?dataset a le:Dataset . ?dataset le:hasPaleoData ?paleoData . ?paleoData a le:PaleoData .
   - INCORRECT: ?variable le:hasPaleoData ?dataset (wrong domain)
   - INCORRECT: ?dataset le:hasPaleoData ?measurement (wrong range)
4. Never create property paths that don't exist in the ontology
5. For temperature variable, check: variable.hasInterpretation.hasVariable.variable is interp:temperature
6. If you need to chain multiple properties, verify each link in the chain has the correct domain/range"""

def build_query_constraints_prompt() -> str:
    """
    Build the query constraints portion of the SPARQL prompt.
    
    Returns:
        Formatted query constraints prompt section
    """
    return """CONSTRAINTS:
1. ONLY use properties from the PROPERTIES list, and use the correct domain and range
2. Standard rdf/rdfs properties are allowed
3. For locations, use geo:lat/geo:long with bounds
4. For variables/archives/proxies/units, use direct entity URIs
5. For temporal resolution, filter on time variable resolution
6. For temporal resolution, use the units of the time variable
7. For temperature variable, check: variable.hasInterpretation.hasVariable is interp:temperature

TIME RESOLUTION PATTERN:
```
?dataset le:hasPaleoData ?paleoData .
?paleoData le:hasMeasurementTable ?dataTable .
?dataTable le:hasVariable ?timeVar .
?timeVar le:hasStandardVariable ?stdVar .
FILTER(?stdVar IN (pvar:age, pvar:year))
?timeVar le:hasResolution ?resolution .
?timeVar le:hasUnits ?timeUnits ;
           le:hasMaxValue ?maxResolutionValue .
FILTER(?timeUnits IN (punits:yr_AD, punits:yr_BP, punits:yr))
FILTER(?maxResolutionValue <= 1)

TEMPERATURE VARIABLE PATTERN:
```
?dataset le:hasPaleoData ?paleoData .
?paleoData le:hasMeasurementTable ?dataTable .
?dataTable le:hasVariable ?tempVar .
?tempVar le:hasInterpretation ?interpretation .
?interpretation le:hasVariable interp:temperature
```"""

def build_clarification_detection_prompt(
    user_query: str,
    entity_matches_text: str,
    clarification_text: str,
    property_validation: str,
    constraints_text: str,
    similar_queries_text: str
) -> str:
    """
    Build the prompt for detecting if clarification is needed.
    
    Args:
        user_query: The user's query
        entity_matches_text: Formatted entity matches
        clarification_text: Previous clarification if any
        property_validation: Property validation section
        constraints_text: Query constraints section
        similar_queries_text: Similar queries section
        
    Returns:
        Complete prompt for clarification detection
    """
    return f"""You are a SPARQL query generation expert. Analyze if you need any clarification to generate a precise SPARQL query.

USER QUERY: {user_query}{clarification_text}

{property_validation}

ENTITIES:
{entity_matches_text}

{constraints_text}

SIMILAR SPARQL QUERIES:
{similar_queries_text}

INSTRUCTIONS:
1. Analyze the user query to determine if any clarification is needed before generating a SPARQL query
2. Look for ambiguities, missing information, or terms that could be interpreted in multiple ways
3. Common clarification needs:
   - Multiple entity interpretations (e.g., d18O as both variable and proxy)
   - Ambiguous temporal constraints (e.g., "high resolution" without specifics)
   - Vague geographic references (e.g., "Pacific" without coordinates)
   - Incomplete query context (e.g., missing units, missing archive types)
4. Identify ALL clarification needs - if multiple issues are found, generate multiple questions

RESPONSE FORMAT:
If clarification is needed, return a valid JSON object with this structure:
```json
{{
  "needs_clarification": true,
  "questions": [
    {{
      "id": "q1",
      "question": "Your first specific clarification question?",
      "choices": ["Option 1", "Option 2", "Both", "Neither"],
      "context": "Brief explanation for first question"
    }},
    {{
      "id": "q2",
      "question": "Your second specific clarification question?",
      "choices": ["Choice A", "Choice B", "Choice C"],
      "context": "Brief explanation for second question"
    }}
  ]
}}
```

If NO clarification is needed, return:
```json
{{
  "needs_clarification": false
}}
```

IMPORTANT: 
1. For each question, provide meaningful choice options in the "choices" array, not as comma-separated text.
2. Each choice should be a clear, distinct option that helps resolve the ambiguity.
3. Return ONLY the complete, valid JSON with no other text before or after it.
4. Make sure to include all closing braces and brackets to ensure the JSON is valid.
5. Validate your JSON format before returning it - it must be properly formatted."""

def format_entity_matches(entity_matches: List[Dict[str, Any]]) -> str:
    """
    Format entity matches for inclusion in the prompt.
    
    Args:
        entity_matches: List of entity matches from database
        
    Returns:
        Formatted entity matches text
    """
    if not entity_matches:
        return "None"
        
    entity_matches_lines = []
    for m in entity_matches:
        # Check for required fields
        if not all(k in m for k in ['uri', 'type']):
            continue
        
        # Get values with defaults
        uri = m.get('uri', '')
        entity_type = m.get('type', 'Unknown')
        similarity = m.get('similarity', 0.0)
        
        # Extract the ID from the URI (take the part after the last # or /)
        instance_id = uri.split('#')[-1] if '#' in uri else uri.split('/')[-1]
        
        # Determine the prefix based on URI patterns
        prefix = "le"
        if "paleo_variables" in uri:
            prefix = "pvar"
        elif "paleo_proxy" in uri:
            prefix = "pproxy"
        elif "archive" in uri:
            prefix = "arch"
        elif "paleo_units" in uri:
            prefix = "punits"
        
        # Only add if we have valid URI and ID
        if uri and instance_id:
            entity_matches_lines.append(
                f"{prefix}:{instance_id} ({entity_type}) {similarity:.2f}"
            )
    
    return "\n".join(entity_matches_lines) if entity_matches_lines else "None"

def detect_clarification_needs(
    llm: BaseChatModel,
    user_query: str,
    similar_queries: List[Dict[str, Any]],
    entity_matches: List[Dict[str, Any]],
    clarification_info: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Detect if clarification is needed for a user query.
    
    Args:
        llm: The language model to use
        user_query: The user's query
        similar_queries: Similar queries from database
        entity_matches: Entity matches from database
        clarification_info: Previous clarification info if any
        
    Returns:
        Dict with clarification details if needed
    """
    try:
        # Format similar queries for the prompt - keep compact
        similar_queries_text = "\n".join([
            f"Q: {q.get('query', '')}\nS: {q.get('sparql', '')}"
            for q in similar_queries if q.get('query') and q.get('sparql')
        ]) if similar_queries else "None"
        
        # Format entity matches with compact format
        entity_matches_text = format_entity_matches(entity_matches)
        
        # Format clarification information if available
        clarification_text = ""
        if clarification_info and clarification_info.get("clarification_processed"):
            # Format all clarification responses
            if clarification_info.get("clarification_responses"):
                clarification_text = "\nUSER CLARIFICATIONS:\n"
                for resp in clarification_info.get("clarification_responses", []):
                    question = resp.get("question", "")
                    response = resp.get("response", "")
                    clarification_text += f"Question: {question}\nResponse: {response}\n\n"
        
        # Use the automatically generated ontology context
        prefixes = ONTOLOGY_PREFIXES
        common_properties = ONTOLOGY_PROPERTIES
        validation_examples = PROPERTY_VALIDATION
        
        # Build the property validation section
        property_validation = build_property_validation_prompt(
            prefixes, common_properties, validation_examples
        )
        
        # Build the constraints section
        constraints_text = build_query_constraints_prompt()
        
        # Build the clarification detection prompt
        clarification_prompt = build_clarification_detection_prompt(
            user_query, 
            entity_matches_text, 
            clarification_text, 
            property_validation, 
            constraints_text, 
            similar_queries_text
        )
        
        # Generate the clarification decision using LangChain message types
        messages = [
            SystemMessage(content="You are a SPARQL query expert determining if clarification is needed. Return only valid JSON with all closing brackets and proper formatting. Double-check that your JSON is complete before submitting."),
            HumanMessage(content=clarification_prompt)
        ]
        
        clarification_response = llm._call(messages).strip()
        # logger.info(f"Raw clarification response: {clarification_response[:200]}...")
        
        # Default values
        needs_clarification = False
        clarification_questions = []
        
        # Check if we already have a clarification response - if so, don't ask again
        if clarification_info and clarification_info.get("clarification_processed"):
            logger.info("Clarification already provided, skipping clarification check")
            needs_clarification = False
        else:
            # Extract JSON from the response - simplified approach
            try:
                # First try to parse the entire response - this handles the cleanest case
                try:
                    json_data = json.loads(clarification_response)
                    logger.info("Successfully parsed complete JSON response")
                except json.JSONDecodeError:
                    # If that fails, try to find the JSON object in the response
                    logger.info("Full JSON parse failed, trying to extract JSON object")
                    
                    # Try multiple patterns to find valid JSON
                    json_patterns = [
                        r'```json\s*(\{.*\})\s*```', # Match JSON in code blocks
                        r'```\s*(\{.*\})\s*```',      # Match JSON in generic code blocks
                        r'(\{.*\})'              # Match any JSON object
                    ]
                    
                    json_data = None
                    for pattern in json_patterns:
                        match = re.search(pattern, clarification_response, re.DOTALL)
                        if match:
                            try:
                                json_data = json.loads(match.group(1))
                                logger.info(f"Successfully extracted JSON using pattern: {pattern}")
                                break
                            except json.JSONDecodeError:
                                continue
                
                # If we have JSON data, extract the information
                if json_data:
                    # Get needs_clarification from the JSON
                    needs_clarification = json_data.get("needs_clarification", False)
                    
                    # Get questions from the JSON if any
                    if needs_clarification and "questions" in json_data:
                        json_questions = json_data.get("questions", [])
                        
                        # Process each question
                        for i, q in enumerate(json_questions):
                            question_id = q.get("id", f"sparql_q{i+1}_{uuid.uuid4().hex[:8]}")
                            question_text = q.get("question", "")
                            question_choices = q.get("choices", [])
                            question_context = q.get("context", "")
                            
                            # Only add if we have a valid question
                            if question_text:
                                clarification_questions.append({
                                    "id": question_id,
                                    "question": question_text,
                                    "choices": question_choices,
                                    "context": question_context
                                })
                else:
                    # Try to extract structured information using regex if JSON parsing failed
                    logger.warning("JSON extraction failed, trying regex patterns")
                    
                    # Check if clarification is needed
                    if "needs_clarification" in clarification_response.lower():
                        needs_clarification = "true" in clarification_response.lower() and "needs_clarification" in clarification_response.lower()
                    
                    # Try to extract questions using regex patterns
                    question_matches = re.findall(r'"question"\s*:\s*"([^"]+)"', clarification_response)
                    
                    # If we found questions, try to extract the corresponding choices
                    for i, q_text in enumerate(question_matches):
                        # Try to find choices for this question
                        choices = []
                        
                        # Look for choice arrays after this question
                        choice_match = re.search(r'"question"\s*:\s*"' + re.escape(q_text) + r'"[^[]*"choices"\s*:\s*(\[[^\]]+\])', clarification_response)
                        if choice_match:
                            try:
                                # Try to parse the choices JSON array
                                choices_str = choice_match.group(1).replace("'", '"')  # Replace single quotes with double for JSON
                                choices = json.loads(choices_str)
                            except:
                                # If parsing fails, try a simpler approach to extract individual choices
                                choices_text = choice_match.group(1)
                                choices = re.findall(r'"([^"]+)"', choices_text)
                        
                        clarification_questions.append({
                            "id": f"sparql_q{i+1}_{uuid.uuid4().hex[:8]}",
                            "question": q_text.strip(),
                            "choices": choices,
                            "context": "Extracted from unstructured response"
                        })
                
                # If we have at least one question, we need clarification
                if clarification_questions:
                    needs_clarification = True
                elif needs_clarification and not clarification_questions:
                    # We determined clarification is needed but didn't parse any questions
                    # Add a default question as fallback
                    clarification_questions.append({
                        "id": f"sparql_q1_{uuid.uuid4().hex[:8]}",
                        "question": "Could you please clarify your query?",
                        "choices": [],
                        "context": "Additional details would help generate a more precise SPARQL query."
                    })
            except Exception as e:
                logger.warning(f"Error parsing clarification response: {str(e)}")
                # Simple fallback if all parsing fails
                if "clarification" in clarification_response.lower():
                    needs_clarification = True
                    clarification_questions.append({
                        "id": f"sparql_q1_{uuid.uuid4().hex[:8]}",
                        "question": "Could you please clarify your query?",
                        "choices": [],
                        "context": "I couldn't parse the clarification needs correctly."
                    })
        
        # Return the clarification details
        return {
            "needs_clarification": needs_clarification,
            "clarification_questions": clarification_questions
        }
    except Exception as e:
        logger.error(f"Error in detect_clarification_needs: {e}", exc_info=True)
        return {
            "needs_clarification": False
        }

def generate_sparql(
    llm: BaseChatModel,
    user_query: str,
    similar_queries: List[Dict[str, Any]],
    entity_matches: List[Dict[str, Any]],
    clarification_info: Dict[str, Any] = None
) -> str:
    """
    Generate a SPARQL query using the LLM.
    
    Args:
        llm: The language model to use
        user_query: The user's query
        similar_queries: Similar queries from database
        entity_matches: Entity matches from database
        clarification_info: Previous clarification info if any
        
    Returns:
        The generated SPARQL query
    """
    try:
        # Format similar queries for the prompt - keep compact
        similar_queries_text = "\n".join([
            f"Q: {q.get('query', '')}\nS: {q.get('sparql', '')}"
            for q in similar_queries if q.get('query') and q.get('sparql')
        ]) if similar_queries else "None"
        
        # Format entity matches with compact format
        entity_matches_text = format_entity_matches(entity_matches)
        
        # Format clarification information if available
        clarification_text = ""
        if clarification_info and clarification_info.get("clarification_processed"):
            # Format all clarification responses
            if clarification_info.get("clarification_responses"):
                clarification_text = "\nUSER CLARIFICATIONS:\n"
                for resp in clarification_info.get("clarification_responses", []):
                    question = resp.get("question", "")
                    response = resp.get("response", "")
                    clarification_text += f"Question: {question}\nResponse: {response}\n\n"
        
        # Use the automatically generated ontology context
        prefixes = ONTOLOGY_PREFIXES
        common_properties = ONTOLOGY_PROPERTIES
        validation_examples = PROPERTY_VALIDATION
        
        # Build the property validation section
        property_validation = build_property_validation_prompt(
            prefixes, common_properties, validation_examples
        )
        
        # Build the constraints section
        constraints_text = build_query_constraints_prompt()
        
        # Build the query generation prompt
        generation_prompt = build_query_generation_prompt(
            user_query, 
            entity_matches_text, 
            clarification_text, 
            property_validation, 
            constraints_text, 
            similar_queries_text
        )
        
        # Generate the query using LangChain message types
        messages = [
            SystemMessage(content="You are a SPARQL query generation expert. Generate only the SPARQL query without any explanation, JSON wrapping, or additional text."),
            HumanMessage(content=generation_prompt)
        ]
        
        response = llm._call(messages)
        return response.strip()
        
    except Exception as e:
        logger.error(f"Error in generate_sparql: {e}", exc_info=True)
        error_type = type(e).__name__
        
        # Return a simple query that will execute but show there was an error
        return f"""
        SELECT ?error
        WHERE {{
            BIND("Error generating SPARQL query: {error_type}" AS ?error)
        }}
        LIMIT 1
        """

def generate_query_node(state: SparqlAgentState, config: SparqlAgentConfig) -> Dict[str, Any]:
    """Enhanced SPARQL query generation with comprehensive contextual information."""
    try:
        logger.info("=== ENHANCED GENERATE_QUERY_NODE CALLED ===")
        
        # Get LLM directly from service manager
        llm = service_manager.get_llm_provider(state.llm_provider or DEFAULT_LLM_PROVIDER)
        
        user_input = state.user_input or ""
        similar_queries = state.similar_code or []
        entity_matches = state.entity_matches or []
        
        # Build minimal context dict for prompt formatting
        contextual_data = {
            "similar_queries": similar_queries,
            "entities": entity_matches,
            "query": user_input
        }
        
        # Add previous context if available (replaces refinement-specific logic)
        context = state.context or {}
        if context.get("has_previous_context"):
            logger.info("=== ADDING PREVIOUS CONTEXT TO QUERY GENERATION ===")
            contextual_data["refinement_context"] = {
                "is_refinement": True,
                "previous_query": context.get("previous_query"),
                "previous_results": context.get("previous_results"),
                "refinement_request": user_input,
                "previous_agent_type": context.get("previous_agent_type")
            }
            logger.info(f"Previous query length: {len(context.get('previous_query', ''))}")
            logger.info(f"Previous results count: {len(context.get('previous_results', []))}")
            logger.info(f"Previous agent type: {context.get('previous_agent_type')}")
        
        logger.info(f"user_input: '{user_input}'")
        logger.info(f"similar_queries count: {len(similar_queries)}")
        logger.info(f"entity_matches count: {len(entity_matches)}")
        logger.info(f"contextual_data keys: {list(contextual_data.keys())}")
        
        if not user_input:
            logger.error("No user input provided")
            return {"error_message": "No user input provided for SPARQL generation"}
        
        # Format comprehensive context for LLM using the unified search service
        context_prompt = ""
        if similar_queries or entity_matches or contextual_data.get("refinement_context"):
            context_prompt = search_service.format_sparql_context_for_llm(contextual_data)
            logger.info(f"Formatted context prompt length: {len(context_prompt)}")
        else:
            logger.warning("No contextual data available for formatting")
        
        # Prepare clarification info if available
        clarification_info = None
        if state.clarification_processed:
            clarification_info = {
                "clarification_processed": state.clarification_processed,
                "clarification_questions": state.clarification_questions,
                "clarification_responses": state.clarification_responses
            }
        
        # Format clarification information if available
        clarification_text = ""
        if clarification_info and clarification_info.get("clarification_processed"):
            if clarification_info.get("clarification_responses"):
                clarification_text = "\nUSER CLARIFICATIONS:\n"
                for resp in clarification_info.get("clarification_responses", []):
                    question = resp.get("question", "")
                    response = resp.get("response", "")
                    clarification_text += f"Question: {question}\nResponse: {response}\n\n"
        
        # Use the automatically generated ontology context
        prefixes = ONTOLOGY_PREFIXES
        common_properties = ONTOLOGY_PROPERTIES
        validation_examples = PROPERTY_VALIDATION
        
        # Build the property validation section
        property_validation = build_property_validation_prompt(
            prefixes, common_properties, validation_examples
        )
        
        # Build the constraints section
        constraints_text = build_query_constraints_prompt()
        
        # Create enhanced prompt using comprehensive context
        system_prompt = (
            "You are a SPARQL query generation expert. Generate only the SPARQL query without any explanation, "
            "JSON wrapping, or additional text. Use the comprehensive context provided to create accurate, "
            "well-formed SPARQL queries that follow ontology patterns and constraints."
        )
        
        user_prompt = (
            f"QUERY: {user_input}{clarification_text}\n\n"
            f"COMPREHENSIVE CONTEXT:\n{context_prompt}\n\n"
            f"{property_validation}\n\n"
            f"{constraints_text}\n\n"
            "INSTRUCTIONS:\n"
            "1. Use similar queries as patterns and adapt them to the current request\n"
            "2. Use ontology entities that match the query terms\n"
            "3. Follow property validation rules and constraints\n"
            "4. Generate syntactically correct SPARQL\n"
            "5. Include proper PREFIX declarations\n\n"
            "Return ONLY the SPARQL query without any explanation or formatting."
        )
        
        # Generate query using LLM
        logger.info("Calling LLM to generate enhanced SPARQL query...")
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        sparql_query = llm._call(messages).strip()
        
        # Clean up the query (remove markdown if present)
        if sparql_query.startswith("```sparql"):
            sparql_query = sparql_query.replace("```sparql", "").replace("```", "").strip()
        elif sparql_query.startswith("```"):
            sparql_query = sparql_query.replace("```", "").strip()
        
        logger.info(f"Generated SPARQL query length: {len(sparql_query)}")
        logger.info(f"Generated SPARQL query preview: {sparql_query[:200]}...")
        
        # Add context summary for logging
        context_summary = f"Used {len(contextual_data.get('similar_queries', []))} similar queries, " \
                         f"{len(contextual_data.get('entities', []))} ontology entities"
        
        result = {
            "generated_code": sparql_query,
            "context_used": context_summary,
            "conversation_id": state.conversation_id  # Preserve conversation_id
        }
        
        logger.info(f"Returning enhanced result with generated_code length: {len(result['generated_code'])}")
        return result
        
    except Exception as e:
        logger.error(f"Error generating query: {e}", exc_info=True)
        return {
            "error_message": str(e),
            "conversation_id": state.conversation_id  # Preserve conversation_id even in error case
        }

def execute_query_node(state: SparqlAgentState, config: SparqlAgentConfig) -> Dict[str, Any]:
    """Execute the generated SPARQL query."""
    try:
        if not state.generated_code:
            raise ValueError("No generated query found in state")
        
        # Access the service directly from service manager
        sparql_service = service_manager.get_sparql_service()
        
        # Get the query and log it
        query = state.generated_code
        logger.info(f"Executing SPARQL query: {query[:200]}...")
        
        try:
            # Call the tool without await (synchronously)
            results = execute_sparql_query(
                sparql_service,
                query
            )
            return {
                "execution_results": results,
                "conversation_id": state.conversation_id  # Preserve conversation_id
            }
        except Exception as e:
            logger.error(f"Error executing SPARQL query: {e}")
            # Create a friendly error message
            error_message = f"Error executing query: {str(e)}"
            
            # Return a structured error result instead of raising an exception
            return {
                "error_message": error_message,
                "execution_results": [{"error": error_message}],
                "conversation_id": state.conversation_id  # Preserve conversation_id
            }
    except Exception as e:
        logger.error(f"Error in execute_query_node: {e}")
        return {
            "error_message": str(e),
            "execution_results": [{"error": f"Error: {str(e)}"}],
            "conversation_id": state.conversation_id  # Preserve conversation_id even in error case
        }

def should_refine_query(state: SparqlAgentState) -> str:
    """Determine if the query should be refined.
    
    This is used as a conditional for routing in the graph.
    
    Returns:
        str: "true" if the query should be refined, "false" otherwise
    """
    # Check refinement count first to avoid infinite loops
    refinement_count = state.refinement_count or 0
    if refinement_count >= MAX_REFINEMENTS:
        logger.info(f"Maximum refinement attempts reached ({refinement_count}), stopping refinement")
        # At this point, we should give up and not ask for clarification
        return "false"
    
    # Check if there's an explicit error message
    if state.error_message:
        logger.info(f"Error message found, triggering refinement (attempt {refinement_count + 1})")
        return "true"
    
    # Check if execution_results contains error indicators
    execution_results = state.execution_results or []
    if execution_results and isinstance(execution_results, list) and len(execution_results) > 0:
        first_result = execution_results[0]
        if isinstance(first_result, dict) and "error" in first_result:
            logger.info(f"Error in execution results, triggering refinement (attempt {refinement_count + 1})")
            return "true"
    
    # Check if we have no execution results at all (could indicate an error)
    if not execution_results:
        logger.info(f"No execution results found, triggering refinement (attempt {refinement_count + 1})")
        return "true"
    
    # If we reach here, the query seems successful
    logger.info("Query appears successful, no refinement needed")
    return "false"

def refine_query(
    llm: BaseChatModel,
    user_input: str,
    current_query: str,
    execution_results: List[Dict[str, Any]],
    similar_queries: List[Dict[str, Any]] = None,
    entity_matches: List[Dict[str, Any]] = None
) -> str:
    """
    Refine a SPARQL query based on execution results and user feedback.
    
    Args:
        llm: Language model for refinement
        user_input: The user's query
        current_query: Current SPARQL query to refine
        execution_results: Results from the current query execution
        similar_queries: Similar queries for context
        entity_matches: Matched entities for context
    
    Returns:
        Refined SPARQL query string
    """
    try:
        # Analysis logic for refinement...
        is_refinement = "Original query context:" in user_input or "Please generate a new SPARQL query that builds upon" in user_input
        
        prompt = f"""
Refine this SPARQL query based on the execution results and user requirements.

CURRENT QUERY:
{current_query}

{user_input}{clarification_text}

EXECUTION RESULTS ANALYSIS:
- Result count: {len(execution_results)}
- Analysis: [Analysis based on results...]

Provide the refined SPARQL query:
"""

        # Generate refined query using LangChain message types
        messages = [
            SystemMessage(content="You are a SPARQL query refinement expert. Generate only the refined SPARQL query."),
            HumanMessage(content=prompt)
        ]
        
        refined_query = llm._call(messages).strip()
        
        # Clean up the refined query (remove markdown if present)
        if refined_query.startswith("```sparql"):
            refined_query = refined_query.replace("```sparql", "").replace("```", "").strip()
        elif refined_query.startswith("```"):
            refined_query = refined_query.replace("```", "").strip()
        
        logger.info(f"Refined query: {refined_query[:200]}...")
        
        # Return only the updated fields
        return {
            "generated_code": refined_query,
            "error_message": None,
            "execution_results": None,
            "refinement_count": state.refinement_count or 0 + 1
        }
    except Exception as e:
        logger.error(f"Error refining query: {e}")
        return {
            "error_message": f"Error during refinement: {str(e)}",
            "refinement_count": state.refinement_count or 0 + 1
        }

def refine_query_node(state: SparqlAgentState, config: SparqlAgentConfig) -> Dict[str, Any]:
    """Refine the generated query based on results or errors."""
    try:
        # Access the LLM directly from service manager
        llm = service_manager.get_llm_provider(state.llm_provider or DEFAULT_LLM_PROVIDER)
        
        # Construct refinement prompt
        error_msg = state.error_message or ""
        results = state.execution_results or []
        current_query = state.generated_code or ""
        refinement_count = state.refinement_count or 0
        
        # Prepare error description for the LLM
        error_description = ""
        if error_msg:
            error_description = f"Error Message: {error_msg}\n\n"
        elif results and isinstance(results, list) and len(results) > 0:
            first_result = results[0]
            if isinstance(first_result, dict) and "error" in first_result:
                error_description = f"Query execution error: {first_result['error']}\n\n"
        
        logger.info(f"Refining query (attempt {refinement_count + 1}/3)")
        logger.info(f"Current query: {current_query[:200]}...")
        logger.info(f"Error: {error_description.strip()}")
        
        prompt = f"""The previous SPARQL query generated an error or unsatisfactory results.
Please refine the query to fix the issues.

Current Query:
{current_query}

{error_description}Query Results:
{results}

Please provide a refined SPARQL query that addresses these issues.
Focus on:
1. Correct SPARQL syntax
2. Valid property names and URIs
3. Proper PREFIX declarations
4. Logical query structure

Return ONLY the SPARQL query without any explanation."""

        # Generate refined query using LangChain message types
        messages = [
            SystemMessage(content="You are a SPARQL query refinement expert. Generate only the refined SPARQL query."),
            HumanMessage(content=prompt)
        ]
        
        refined_query = llm._call(messages).strip()
        
        # Clean up the refined query (remove markdown if present)
        if refined_query.startswith("```sparql"):
            refined_query = refined_query.replace("```sparql", "").replace("```", "").strip()
        elif refined_query.startswith("```"):
            refined_query = refined_query.replace("```", "").strip()
        
        logger.info(f"Refined query: {refined_query[:200]}...")
        
        # Return only the updated fields
        return {
            "generated_code": refined_query,
            "error_message": None,
            "execution_results": None,
            "refinement_count": refinement_count + 1,
            "conversation_id": state.conversation_id  # Preserve conversation_id
        }
    except Exception as e:
        logger.error(f"Error refining query: {e}")
        return {
            "error_message": f"Error during refinement: {str(e)}",
            "refinement_count": (state.refinement_count or 0) + 1,
            "conversation_id": state.conversation_id  # Preserve conversation_id
        }

def detect_clarification_node(state: SparqlAgentState, config: SparqlAgentConfig) -> Dict[str, Any]:
    """
    Analyze the query and entity matches to identify if clarification is needed.
    This is a separate node that runs before query generation.
    """
    try:
        logger.info("=== DETECT CLARIFICATION NODE CALLED ===")
        
        # Debug logging to see what the config object looks like
        # logger.info(f"Config type: {type(config)}")
        # logger.info(f"Config content: {config}")
        # if hasattr(config, '__dict__'):
        #     logger.info(f"Config attributes: {config.__dict__}")
        
        # Check if clarification is disabled in config
        enable_clarification = get_config_value(config, 'enable_clarification', True)
        logger.info(f"Retrieved enable_clarification: {enable_clarification}")
        if not enable_clarification:
            logger.info("Clarification detection disabled in config")
            return {"needs_clarification": False}
        
        # Skip clarification for refinement requests
        context = state.context or {}
        if context.get("has_previous_context"):
            logger.info("Skipping clarification detection for refinement request")
            return {"needs_clarification": False}
        
        # Skip clarification if it has already been processed
        if state.clarification_processed:
            logger.info("Skipping clarification detection - clarification already processed")
            return {"needs_clarification": False}
        
        # Skip clarification if we have clarification responses to process
        if state.clarification_responses:
            logger.info("Skipping clarification detection - clarification responses present")
            return {"needs_clarification": False}
        
        # Access the LLM directly from service manager
        llm = service_manager.get_llm_provider(state.llm_provider or DEFAULT_LLM_PROVIDER)
        
        # Skip if we don't have entity matches
        if not state.entity_matches:
            logger.info("No entity matches, skipping clarification detection")
            return {"needs_clarification": False}
            
        # Skip if we've already processed a clarification for this query
        # Skip if we already have clarification responses
        if state.clarification_responses:
            logger.info("Clarification responses already provided, skipping clarification detection")
            return {"needs_clarification": False}
        
        # Apply threshold-based logic for simple queries
        clarification_threshold = get_config_value(config, 'clarification_threshold', 'conservative')
        user_input = state.user_input or ""
        
        # For permissive threshold, skip clarification for simple, clear queries
        if clarification_threshold == "permissive":
            simple_patterns = [
                r'\bshow\s+me\s+\w+\s+datasets?\b',  # "show me coral datasets"
                r'\blist\s+all\s+\w+\b',             # "list all coral"
                r'\bselect\s+all\s+datasets?\b',     # "select all datasets"
                r'\bget\s+\w+\s+data\b'              # "get coral data"
            ]
            
            for pattern in simple_patterns:
                if re.search(pattern, user_input.lower()):
                    logger.info(f"Permissive threshold: skipping clarification for simple query pattern: {pattern}")
                    return {"needs_clarification": False}
        
        # Prepare clarification info if available
        clarification_info = None
        if state.clarification_processed:
            clarification_info = {
                "clarification_processed": state.clarification_processed,
                "clarification_questions": state.clarification_questions,
                "clarification_responses": state.clarification_responses
            }
        
        # Check if clarification is needed using our refactored function
        result = detect_clarification_needs(
            llm,
            state.user_input or "",
            state.similar_code or [],
            state.entity_matches or [],
            clarification_info
        )
        
        # Apply threshold filtering to the LLM result
        needs_clarification = result.get("needs_clarification", False)
        
        if needs_clarification and clarification_threshold == "strict":
            # In strict mode, only ask for clarification if there are multiple high-confidence ambiguities
            questions = result.get("clarification_questions", [])
            if len(questions) < 2:
                logger.info("Strict threshold: skipping clarification with fewer than 2 questions")
                needs_clarification = False
        
        # If clarification is needed, add the questions to the state
        if needs_clarification:
            logger.info(f"Clarification needed (threshold: {clarification_threshold}), adding questions to state")
            response = {
                "needs_clarification": True,
                "clarification_questions": result.get("clarification_questions", []),
                "conversation_id": state.conversation_id  # Preserve conversation_id
            }
            logger.info(f"DETECT CLARIFICATION RETURNING: {response}")
            return response
        else:
            logger.info(f"No clarification needed (threshold: {clarification_threshold})")
            return {
                "needs_clarification": False,
                "conversation_id": state.conversation_id  # Preserve conversation_id
            }
    except Exception as e:
        logger.error(f"Error in detect_clarification_node: {e}", exc_info=True)
        return {
            "error_message": str(e), 
            "needs_clarification": False,
            "conversation_id": state.conversation_id
        }

def finalize_query_node(state: SparqlAgentState, config: SparqlAgentConfig) -> Dict[str, Any]:
    """
    Finalize the query processing and clean up the state.
    This handles both successful queries and cases where refinement was exhausted.
    """
    try:
        refinement_count = state.refinement_count or 0
        has_error = bool(state.error_message)
        
        # Check if query results contain errors
        execution_results = state.execution_results or []
        has_error_results = False
        if execution_results and isinstance(execution_results, list) and len(execution_results) > 0:
            first_result = execution_results[0]
            if isinstance(first_result, dict) and "error" in first_result:
                has_error_results = True
        
        # Add final message
        messages = state.messages or []
        
        # Gather final artifacts
        final_generated_code = state.generated_code or None
        final_execution_results = state.execution_results or None
        # Determine final message/status
        if refinement_count >= 3 and (has_error or has_error_results):
            message_content = "Query processing completed after maximum refinement attempts."
            final_status = "refinement_exhausted"
        elif execution_results and not has_error and not has_error_results:
            message_content = f"SPARQL query executed successfully. Found {len(execution_results)} results."
            final_status = "success"
        else:
            message_content = "Query processing completed."
            final_status = "completed"
        
        messages.append({"role": "assistant", "content": message_content})
        
        return {
            "messages": messages,
            "needs_clarification": False,
            "final_status": final_status,
            "generated_code": final_generated_code,
            "execution_results": final_execution_results,
            "conversation_id": state.conversation_id  # Preserve conversation_id
        }
    except Exception as e:
        logger.error(f"Error in finalize_query_node: {e}")
        return {
            "error_message": str(e),
            "needs_clarification": False,
            "final_status": "error",
            "conversation_id": state.conversation_id  # Preserve conversation_id even in error case
        }

def build_query_generation_prompt(
    user_query: str,
    entity_matches_text: str,
    clarification_text: str,
    property_validation: str,
    constraints_text: str,
    similar_queries_text: str
) -> str:
    """
    Build the prompt for generating a SPARQL query.
    
    Args:
        user_query: The user's query
        entity_matches_text: Formatted entity matches
        clarification_text: Previous clarification if any
        property_validation: Property validation section
        constraints_text: Query constraints section
        similar_queries_text: Similar queries section
        
    Returns:
        Complete prompt for query generation
    """
    # Check if this is a refinement request based on the query content
    is_refinement = "Original query context:" in user_query or "Please generate a new SPARQL query that builds upon" in user_query
    
    if is_refinement:
        return f"""You are a SPARQL query refinement expert. The user is asking to modify or improve an existing SPARQL query.

REFINEMENT REQUEST:
{user_query}{clarification_text}

{property_validation}

ENTITIES:
{entity_matches_text}

{constraints_text}

SIMILAR SPARQL QUERIES FOR REFERENCE:
{similar_queries_text}

INSTRUCTIONS:
- Carefully read the original query context and the user's refinement request
- Generate a new SPARQL query that incorporates the requested changes
- Ensure the new query is syntactically correct and follows SPARQL best practices
- Consider performance optimizations where appropriate
- Maintain the original intent while implementing the requested modifications

OUTPUT FORMAT:
Return ONLY the refined SPARQL query. Do not include:
- JSON formatting or wrapping
- Explanations or comments
- Code block markers (```)
- Any additional text

Example of correct output:
PREFIX le: <http://linked.earth/ontology#>
SELECT ?dataset ?name WHERE {{
    ?dataset a le:Dataset .
    ?dataset le:hasName ?name .
}}"""
    else:
        return f"""You are a SPARQL query generation expert. Generate a SPARQL query for this request.

QUERY: {user_query}{clarification_text}

{property_validation}

ENTITIES:
{entity_matches_text}

{constraints_text}

SIMILAR SPARQL QUERIES:
{similar_queries_text}

OUTPUT FORMAT:
Return ONLY the SPARQL query. Do not include:
- JSON formatting or wrapping (e.g., {{"query": "..."}} )
- Explanations or comments
- Code block markers (```)
- Any additional text or metadata

Example of correct output:
PREFIX le: <http://linked.earth/ontology#>
SELECT ?dataset ?name WHERE {{
    ?dataset a le:Dataset .
    ?dataset le:hasName ?name .
}}

INCORRECT examples (do not format like this):
- json {{ "query": "SELECT ..." }}
- ```sparql SELECT ... ```
- Here's the SPARQL query: SELECT ...""" 