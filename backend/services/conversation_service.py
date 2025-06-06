import sqlite3
import json
import logging
from pathlib import Path
from threading import Lock
from typing import List, Optional, Any
from datetime import datetime, timedelta

from schemas.conversation import Conversation

logger = logging.getLogger(__name__)

# Database path - same as other services
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DATA_DIR.mkdir(exist_ok=True)
_DB_PATH = _DATA_DIR / "conversations.db"

class ConversationService:
    """Unified service for managing conversations and their data."""
    
    _lock = Lock()
    
    def __init__(self):
        self._init_db()
    
    def _init_db(self):
        """Initialize the conversations table with all necessary fields."""
        try:
            with sqlite3.connect(_DB_PATH) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        messages TEXT NOT NULL,  -- JSON array of Message objects
                        state_id TEXT,
                        
                        -- Clarification handling
                        waiting_for_clarification BOOLEAN DEFAULT FALSE,
                        clarification_questions TEXT,  -- JSON array
                        clarification_answers TEXT,    -- JSON object
                        original_request_context TEXT, -- JSON object
                        
                        -- Agent and LLM settings
                        llm_provider TEXT DEFAULT 'google',
                        selected_agent TEXT DEFAULT 'sparql',
                        
                        -- UI state
                        is_loading BOOLEAN DEFAULT FALSE,
                        error TEXT,
                        
                        -- Clarification settings
                        enable_clarification BOOLEAN DEFAULT FALSE,
                        clarification_threshold TEXT DEFAULT 'conservative',
                        
                        -- Execution state
                        execution_start_time INTEGER,
                        
                        -- Timestamps
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                conn.commit()
                logger.info("Conversations table initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing conversations table: {e}")
            raise
    
    def _serialize_message_list(self, messages: List[Any]) -> str:
        """Convert messages to JSON string, handling Message objects."""
        if not messages:
            return "[]"
        
        serializable_messages = []
        for msg in messages:
            if hasattr(msg, 'dict'):
                # It's a Pydantic model
                serializable_messages.append(msg.dict(by_alias=True))
            elif isinstance(msg, dict):
                # It's already a dict
                serializable_messages.append(msg)
            else:
                # Convert to dict
                serializable_messages.append({"role": "unknown", "content": str(msg)})
        
        return json.dumps(serializable_messages, ensure_ascii=False)
    
    def _deserialize_message_list(self, json_str: str) -> List[dict]:
        """Convert JSON string back to message list."""
        if not json_str:
            return []
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Failed to deserialize messages: {json_str}")
            return []
    
    def _row_to_conversation(self, row: sqlite3.Row) -> Conversation:
        """Convert database row to Conversation object."""
        conv_data = dict(row)
        
        # Parse JSON fields
        conv_data['messages'] = self._deserialize_message_list(conv_data['messages'])
        conv_data['clarification_questions'] = json.loads(conv_data['clarification_questions']) if conv_data['clarification_questions'] else []
        conv_data['clarification_answers'] = json.loads(conv_data['clarification_answers']) if conv_data['clarification_answers'] else {}
        conv_data['original_request_context'] = json.loads(conv_data['original_request_context']) if conv_data['original_request_context'] else None
        
        # Convert boolean fields (SQLite stores as 0/1)
        bool_fields = ['waiting_for_clarification', 'is_loading', 'enable_clarification']
        for field in bool_fields:
            if field in conv_data:
                conv_data[field] = bool(conv_data[field])
        
        return Conversation(**conv_data)
    
    def list_conversations(self) -> List[Conversation]:
        """Get all conversations, sorted by updated_at descending."""
        with sqlite3.connect(_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM conversations 
                ORDER BY updated_at DESC
            """)
            rows = cursor.fetchall()
            
            return [self._row_to_conversation(row) for row in rows]
    
    def get_conversation(self, conv_id: str) -> Optional[Conversation]:
        """Get a single conversation by ID."""
        with sqlite3.connect(_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM conversations WHERE id = ?
            """, (conv_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return self._row_to_conversation(row)
    
    def create_conversation(self, conversation: Conversation) -> Conversation:
        """Create a new conversation."""
        # Set timestamps
        now_iso = datetime.utcnow().isoformat()
        if not conversation.created_at:
            conversation.created_at = now_iso
        conversation.updated_at = now_iso
        
        # Set defaults
        if not conversation.llm_provider:
            conversation.llm_provider = "google"
        if not conversation.selected_agent:
            conversation.selected_agent = "sparql"
        if not conversation.clarification_threshold:
            conversation.clarification_threshold = "conservative"
        
        self._upsert_conversation(conversation)
        return conversation
    
    def update_conversation(self, conversation: Conversation) -> Conversation:
        """Update an existing conversation."""
        # Update timestamp
        conversation.updated_at = datetime.utcnow().isoformat()
        
        self._upsert_conversation(conversation)
        return conversation
    
    def _upsert_conversation(self, conversation: Conversation):
        """Internal method to insert or update a conversation."""
        with self._lock:
            with sqlite3.connect(_DB_PATH) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO conversations (
                        id, title, messages, state_id,
                        waiting_for_clarification, clarification_questions, clarification_answers, 
                        original_request_context, llm_provider, selected_agent,
                        is_loading, error, enable_clarification, clarification_threshold,
                        execution_start_time, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    conversation.id,
                    conversation.title,
                    self._serialize_message_list(conversation.messages),
                    conversation.state_id,
                    conversation.waiting_for_clarification or False,
                    json.dumps(conversation.clarification_questions) if conversation.clarification_questions else "[]",
                    json.dumps(conversation.clarification_answers) if conversation.clarification_answers else "{}",
                    json.dumps(conversation.original_request_context) if conversation.original_request_context else None,
                    conversation.llm_provider or 'google',
                    conversation.selected_agent or 'sparql',
                    conversation.is_loading or False,
                    conversation.error,
                    conversation.enable_clarification or False,
                    conversation.clarification_threshold or 'conservative',
                    conversation.execution_start_time,
                    conversation.created_at,
                    conversation.updated_at
                ))
                conn.commit()
    
    def delete_conversation(self, conv_id: str) -> bool:
        """Delete a conversation by ID. Returns True if deleted, False if not found."""
        logger.info(f"Starting deletion of conversation {conv_id}")
        
        # First get the conversation to check if it has a state_id
        conversation = self.get_conversation(conv_id)
        logger.info(f"Retrieved conversation: {conversation.id if conversation else 'None'}")
        
        if conversation:
            logger.info(f"Conversation state_id: {conversation.state_id}")
        
        with self._lock:
            with sqlite3.connect(_DB_PATH) as conn:
                cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
                conn.commit()
                deleted = cursor.rowcount > 0
        
        logger.info(f"Conversation deletion result: {deleted}")
        
        # If conversation was deleted, clean up associated resources
        if deleted and conversation:
            logger.info(f"Starting cleanup for conversation {conv_id}")
            
            # Clean up conversation state if it exists
            if conversation.state_id:
                logger.info(f"Cleaning up conversation state: {conversation.state_id}")
                try:
                    # Import here to avoid circular imports
                    from services.conversation_state_service import conversation_state_service
                    conversation_state_service.delete(conversation.state_id)
                    logger.info(f"Successfully cleaned up conversation state {conversation.state_id} for deleted conversation {conv_id}")
                except Exception as e:
                    logger.error(f"Error cleaning up conversation state {conversation.state_id} for conversation {conv_id}: {e}")
            else:
                logger.info(f"No state_id found for conversation {conv_id}, skipping conversation state cleanup")
            
            # Clean up workflow plans that reference this conversation
            logger.info(f"Starting workflow cleanup for conversation {conv_id}")
            try:
                deleted_workflows = self._cleanup_workflow_plans_for_conversation(conv_id)
                logger.info(f"Cleaned up {deleted_workflows} workflow plans for deleted conversation {conv_id}")
            except Exception as e:
                logger.error(f"Error cleaning up workflow plans for conversation {conv_id}: {e}")
        else:
            logger.info(f"Skipping cleanup - deleted: {deleted}, conversation: {conversation is not None}")
        
        return deleted

    def _cleanup_workflow_plans_for_conversation(self, conversation_id: str) -> int:
        """Clean up workflow plans that reference the given conversation ID."""
        logger.info(f"Searching for workflow plans referencing conversation {conversation_id}")
        deleted_count = 0
        
        try:
            # Get all workflow plans from the database
            with sqlite3.connect(_DB_PATH) as conn:
                cursor = conn.execute("SELECT id, plan_json FROM workflow_plans")
                workflow_rows = cursor.fetchall()
                
                logger.info(f"Found {len(workflow_rows)} total workflow plans in database")
                
                workflows_to_delete = []
                
                for workflow_id, plan_json in workflow_rows:
                    try:
                        plan_data = json.loads(plan_json)
                        step_conversations = plan_data.get("step_conversations", {})
                        creator_conversation_id = plan_data.get("creator_conversation_id")
                        
                        logger.info(f"Workflow {workflow_id} step_conversations: {step_conversations}, creator: {creator_conversation_id}")
                        
                        # Check if this workflow references the deleted conversation
                        # Either as creator or in step conversations
                        should_delete = False
                        if creator_conversation_id == conversation_id:
                            should_delete = True
                            logger.info(f"Workflow {workflow_id} was created by deleted conversation {conversation_id}")
                        elif conversation_id in step_conversations.values():
                            should_delete = True
                            logger.info(f"Workflow {workflow_id} has steps referencing deleted conversation {conversation_id}")
                        
                        if should_delete:
                            workflows_to_delete.append(workflow_id)
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Failed to parse workflow plan {workflow_id}: {e}")
                        continue
                
                logger.info(f"Found {len(workflows_to_delete)} workflows to delete: {workflows_to_delete}")
                
                # Delete the workflows that reference the deleted conversation
                for workflow_id in workflows_to_delete:
                    cursor = conn.execute("DELETE FROM workflow_plans WHERE id = ?", (workflow_id,))
                    if cursor.rowcount > 0:
                        deleted_count += 1
                        logger.info(f"Deleted workflow plan {workflow_id}")
                    else:
                        logger.warning(f"Failed to delete workflow plan {workflow_id} - not found in database")
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error during workflow cleanup for conversation {conversation_id}: {e}")
            raise
        
        return deleted_count
    
    def conversation_exists(self, conv_id: str) -> bool:
        """Check if a conversation exists."""
        with sqlite3.connect(_DB_PATH) as conn:
            cursor = conn.execute("SELECT 1 FROM conversations WHERE id = ? LIMIT 1", (conv_id,))
            return cursor.fetchone() is not None
    
    def get_conversation_count(self) -> int:
        """Get the total number of conversations."""
        with sqlite3.connect(_DB_PATH) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM conversations")
            return cursor.fetchone()[0]
    
    def cleanup_old_conversations(self, max_age_days: int = 90) -> int:
        """Delete conversations older than max_age_days. Returns number deleted."""
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
        cutoff_iso = cutoff_date.isoformat()
        
        with self._lock:
            with sqlite3.connect(_DB_PATH) as conn:
                cursor = conn.execute(
                    "DELETE FROM conversations WHERE created_at < ?", 
                    (cutoff_iso,)
                )
                conn.commit()
                return cursor.rowcount

    def debug_database_state(self) -> dict:
        """Debug method to examine the current state of all database tables."""
        debug_info = {
            "conversations": [],
            "conversation_states": [],
            "workflow_plans": []
        }
        
        try:
            with sqlite3.connect(_DB_PATH) as conn:
                # Get conversations
                cursor = conn.execute("SELECT id, title, state_id FROM conversations")
                debug_info["conversations"] = [
                    {"id": row[0], "title": row[1], "state_id": row[2]} 
                    for row in cursor.fetchall()
                ]
                
                # Get conversation states
                cursor = conn.execute("SELECT id FROM conversation_states")
                debug_info["conversation_states"] = [row[0] for row in cursor.fetchall()]
                
                # Get workflow plans with their step_conversations
                cursor = conn.execute("SELECT id, plan_json FROM workflow_plans")
                workflow_plans = []
                for row in cursor.fetchall():
                    try:
                        plan_data = json.loads(row[1])
                        step_conversations = plan_data.get("step_conversations", {})
                        creator_conversation_id = plan_data.get("creator_conversation_id")
                        workflow_plans.append({
                            "id": row[0],
                            "step_conversations": step_conversations,
                            "creator_conversation_id": creator_conversation_id
                        })
                    except json.JSONDecodeError:
                        workflow_plans.append({
                            "id": row[0],
                            "step_conversations": "PARSE_ERROR",
                            "creator_conversation_id": "PARSE_ERROR"
                        })
                debug_info["workflow_plans"] = workflow_plans
                
        except Exception as e:
            logger.error(f"Error getting debug info: {e}")
            debug_info["error"] = str(e)
        
        logger.info(f"Database state: {debug_info}")
        return debug_info

# Singleton instance
conversation_service = ConversationService() 