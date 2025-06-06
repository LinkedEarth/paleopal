import json
import logging
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Data directory and SQLite DB path
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DATA_DIR.mkdir(exist_ok=True)
_DB_PATH = _DATA_DIR / "conversations.db"

class ConversationStateService:
    """Service for persisting SPARQL agent conversation states."""

    _lock = Lock()

    def __init__(self):
        self._states: Dict[str, Any] = {}
        self._conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_states (
                id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL
            )
            """
        )
        self._conn.commit()
        self._load()

    def _load(self):
        """Load all states from SQLite into memory cache."""
        try:
            cur = self._conn.execute("SELECT id, state_json FROM conversation_states")
            rows = cur.fetchall()
            self._states = {row[0]: json.loads(row[1]) for row in rows}
            logger.info(f"Loaded {len(self._states)} conversation states from SQLite")
        except Exception as e:
            logger.error(f"Error loading states from SQLite: {e}")

    def _save_state_to_db(self, state_id: str, state_json_str: str):
        """Insert or replace single state into SQLite."""
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT OR REPLACE INTO conversation_states (id, state_json) VALUES (?, ?)",
                    (state_id, state_json_str),
                )
                self._conn.commit()
        except Exception as e:
            logger.error(f"Error saving state {state_id} to SQLite: {e}")

    def get(self, state_id: str) -> Optional[Dict[str, Any]]:
        return self._states.get(state_id)

    def _clean_state_for_json(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Clean state to remove non-JSON-serializable objects."""
        try:
            # Make a deep copy of the state
            import copy
            cleaned_state = copy.deepcopy(state)
            
            # Convert LangChain messages to plain dictionaries
            if "messages" in cleaned_state:
                messages = cleaned_state["messages"]
                cleaned_messages = []
                
                for msg in messages:
                    if hasattr(msg, 'content') and hasattr(msg, 'type'):
                        # It's a LangChain message object
                        if hasattr(msg, 'type') and msg.type == 'human':
                            msg_dict = {
                                "role": "user",
                                "content": msg.content
                            }
                        elif hasattr(msg, 'type') and msg.type == 'ai':
                            msg_dict = {
                                "role": "assistant", 
                                "content": msg.content
                            }
                        else:
                            # Generic handling for other message types
                            msg_dict = {
                                "role": getattr(msg, 'type', 'unknown'),
                                "content": str(msg.content)
                            }
                        
                        # Preserve any additional attributes from the original message
                        if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs:
                            msg_dict.update(msg.additional_kwargs)
                        
                        cleaned_messages.append(msg_dict)
                    elif isinstance(msg, dict):
                        # It's already a dictionary, keep as-is
                        cleaned_messages.append(msg)
                    else:
                        # Try to convert to string as fallback
                        cleaned_messages.append({
                            "role": "unknown",
                            "content": str(msg)
                        })
                
                cleaned_state["messages"] = cleaned_messages
            
            # Remove any other non-serializable objects
            keys_to_remove = []
            for key, value in cleaned_state.items():
                try:
                    json.dumps(value)
                except (TypeError, ValueError):
                    logger.warning(f"Removing non-serializable key '{key}' from state")
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del cleaned_state[key]
            
            return cleaned_state
            
        except Exception as e:
            logger.error(f"Error cleaning state for JSON: {e}")
            # Return a minimal state as fallback
            return {
                "user_query": state.get("user_query", ""),
                "generated_query": state.get("generated_query", ""),
                "query_results": state.get("query_results", []),
                "needs_clarification": state.get("needs_clarification", False),
                "clarification_questions": state.get("clarification_questions", []),
                "clarification_responses": state.get("clarification_responses", [])
            }

    def set(self, state_id: str, state: Dict[str, Any]):
        try:
            # Clean the state to remove non-JSON-serializable objects
            state_copy = self._clean_state_for_json(state)
            
            # Verify it's actually JSON serializable
            json.dumps(state_copy)
            
            self._states[state_id] = state_copy
            state_json_str = json.dumps(state_copy, ensure_ascii=False)
            self._save_state_to_db(state_id, state_json_str)
            logger.debug(f"Saved conversation state for {state_id}")
        except Exception as e:
            logger.error(f"Error setting conversation state for {state_id}: {e}")

    def delete(self, state_id: str):
        logger.info(f"Attempting to delete conversation state: {state_id}")
        try:
            # Check if state exists in memory cache
            existed_in_memory = state_id in self._states
            logger.info(f"State {state_id} existed in memory cache: {existed_in_memory}")
            
            if state_id in self._states:
                del self._states[state_id]
                logger.info(f"Removed state {state_id} from memory cache")
            
            # Delete from database
            with self._lock:
                cursor = self._conn.execute("DELETE FROM conversation_states WHERE id = ?", (state_id,))
                self._conn.commit()
                rows_deleted = cursor.rowcount
                logger.info(f"Deleted {rows_deleted} rows from conversation_states table for state_id: {state_id}")
            
            logger.info(f"Successfully deleted conversation state for {state_id}")
        except Exception as e:
            logger.error(f"Error deleting conversation state for {state_id}: {e}")
            raise

    def clear_old_states(self, max_age_days: int = 30):
        """Clear states older than max_age_days (if we had timestamps)"""
        # For now, just a placeholder - could be enhanced with timestamps
        pass

# Singleton instance
conversation_state_service = ConversationStateService() 