import sqlite3
import json
import logging
from pathlib import Path
from threading import Lock
from typing import List, Optional, Any, Dict
from datetime import datetime, timedelta
import uuid

from schemas.conversation import Conversation, ConversationCreate, ConversationUpdate
from services.message_service import message_service

logger = logging.getLogger(__name__)

# Database path - same as other services
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DATA_DIR.mkdir(exist_ok=True)
_DB_PATH = _DATA_DIR / "conversations.db"

class ConversationService:
    """Service for managing conversations with normalized message storage."""
    
    _lock = Lock()
    
    def __init__(self):
        self._init_db()
    
    def _init_db(self):
        """Initialize the conversations table (simplified schema)."""
        try:
            with sqlite3.connect(_DB_PATH) as conn:                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        llm_provider TEXT DEFAULT 'google',
                        selected_agent TEXT DEFAULT 'sparql',
                        enable_clarification BOOLEAN DEFAULT FALSE,
                        clarification_threshold TEXT DEFAULT 'conservative',
                        waiting_for_clarification BOOLEAN DEFAULT FALSE,
                        clarification_questions TEXT,  -- JSON
                        clarification_answers TEXT,    -- JSON
                        original_request TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        metadata TEXT  -- JSON
                    )
                """)
                
                # Create index
                conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at)")
                
                conn.commit()
                logger.info("Conversations table initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing conversations table: {e}")
            raise

    def _serialize_json_field(self, data: Any) -> Optional[str]:
        """Serialize data to JSON string, handling None."""
        if data is None:
            return None
        return json.dumps(data, ensure_ascii=False)
    
    def _deserialize_json_field(self, json_str: Optional[str]) -> Any:
        """Deserialize JSON string back to data, handling None."""
        if not json_str:
            return None
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Failed to deserialize JSON: {json_str}")
            return None
    
    def _row_to_conversation(self, row: sqlite3.Row, include_messages: bool = True) -> Conversation:
        """Convert database row to Conversation object."""
        conv_data = dict(row)
        
        # Parse JSON fields
        conv_data['clarification_questions'] = self._deserialize_json_field(conv_data['clarification_questions'])
        conv_data['clarification_answers'] = self._deserialize_json_field(conv_data['clarification_answers'])
        conv_data['metadata'] = self._deserialize_json_field(conv_data['metadata'])
        
        # Convert boolean fields (SQLite stores as 0/1)
        bool_fields = ['waiting_for_clarification', 'enable_clarification']
        for field in bool_fields:
            if field in conv_data:
                conv_data[field] = bool(conv_data[field])
        
        # Load messages from separate table
        if include_messages:
            conv_data['messages'] = message_service.get_conversation_messages(conv_data['id'])
        else:
            conv_data['messages'] = []
        
        return Conversation(**conv_data)
    
    def list_conversations(self, include_messages: bool = False) -> List[Conversation]:
        """Get all conversations, sorted by updated_at descending."""
        with sqlite3.connect(_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM conversations 
                ORDER BY updated_at DESC
            """)
            rows = cursor.fetchall()
            
            return [self._row_to_conversation(row, include_messages) for row in rows]
    
    def get_conversation(self, conv_id: str, include_messages: bool = True) -> Optional[Conversation]:
        """Get a single conversation by ID."""
        with sqlite3.connect(_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM conversations WHERE id = ?
            """, (conv_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return self._row_to_conversation(row, include_messages)
    
    def create_conversation(self, conversation_data: ConversationCreate) -> Conversation:
        """Create a new conversation."""
        # Use provided ID if available, otherwise generate one
        if hasattr(conversation_data, 'id') and conversation_data.id:
            conv_id = conversation_data.id
        else:
            # Generate ID with random suffix to avoid collisions
            conv_id = f"c_{int(datetime.utcnow().timestamp() * 1000)}_{uuid.uuid4().hex[:6]}"
        
        now_iso = datetime.utcnow().isoformat()
        
        conversation = Conversation(
            id=conv_id,
            title=conversation_data.title,
            llm_provider=conversation_data.llm_provider,
            selected_agent=conversation_data.selected_agent,
            enable_clarification=conversation_data.enable_clarification,
            clarification_threshold=conversation_data.clarification_threshold,
            metadata=conversation_data.metadata,
            created_at=now_iso,
            updated_at=now_iso
        )
        
        self._insert_conversation(conversation)
        logger.info(f"Created conversation {conv_id}: {conversation_data.title}")
        return conversation
    
    def update_conversation(self, conv_id: str, update_data: ConversationUpdate) -> Optional[Conversation]:
        """Update conversation metadata (not messages)."""
        conversation = self.get_conversation(conv_id, include_messages=False)
        if not conversation:
            return None
        
        # Update fields from update_data
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(conversation, field, value)
        
        # Update timestamp
        conversation.updated_at = datetime.utcnow().isoformat()
        
        self._update_conversation(conversation)
        logger.info(f"Updated conversation {conv_id}")
        return conversation
    
    def _insert_conversation(self, conversation: Conversation):
        """Insert a new conversation into the database."""
        with self._lock:
            with sqlite3.connect(_DB_PATH) as conn:
                conn.execute("""
                    INSERT INTO conversations (
                        id, title, llm_provider, selected_agent, enable_clarification,
                        clarification_threshold, waiting_for_clarification, clarification_questions,
                        clarification_answers, original_request, created_at, updated_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    conversation.id, conversation.title, conversation.llm_provider, conversation.selected_agent,
                    conversation.enable_clarification, conversation.clarification_threshold,
                    conversation.waiting_for_clarification, self._serialize_json_field(conversation.clarification_questions),
                    self._serialize_json_field(conversation.clarification_answers), conversation.original_request,
                    conversation.created_at, conversation.updated_at, self._serialize_json_field(conversation.metadata)
                ))
                conn.commit()
    
    def _update_conversation(self, conversation: Conversation):
        """Update an existing conversation in the database."""
        with self._lock:
            with sqlite3.connect(_DB_PATH) as conn:
                conn.execute("""
                    UPDATE conversations SET
                        title = ?, llm_provider = ?, selected_agent = ?, enable_clarification = ?,
                        clarification_threshold = ?, waiting_for_clarification = ?, clarification_questions = ?,
                        clarification_answers = ?, original_request = ?, updated_at = ?, metadata = ?
                    WHERE id = ?
                """, (
                    conversation.title, conversation.llm_provider, conversation.selected_agent,
                    conversation.enable_clarification, conversation.clarification_threshold,
                    conversation.waiting_for_clarification, self._serialize_json_field(conversation.clarification_questions),
                    self._serialize_json_field(conversation.clarification_answers), conversation.original_request,
                    conversation.updated_at, self._serialize_json_field(conversation.metadata), conversation.id
                ))
                conn.commit()
    
    def delete_conversation(self, conv_id: str) -> bool:
        """Delete a conversation and all its messages."""
        with self._lock:
            with sqlite3.connect(_DB_PATH) as conn:
                # Enable foreign keys for this connection
                conn.execute("PRAGMA foreign_keys = ON")
                
                # First delete all messages for this conversation
                cursor = conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
                messages_deleted = cursor.rowcount
                
                # Then delete the conversation
                cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
                conversation_deleted = cursor.rowcount > 0
                
                conn.commit()
                
                if conversation_deleted:
                    # Clean up execution state for this conversation
                    try:
                        from services.python_execution_service import python_execution_service
                        python_execution_service.clear_conversation_state(conv_id)
                        logger.info(f"Deleted conversation {conv_id}, {messages_deleted} messages, and execution state")
                    except Exception as e:
                        logger.warning(f"Failed to clear execution state for conversation {conv_id}: {e}")
                    logger.info(f"Deleted conversation {conv_id} and {messages_deleted} associated messages")
                else:
                    logger.warning(f"Conversation {conv_id} not found for deletion (deleted {messages_deleted} orphaned messages)")
                
                return conversation_deleted
    
    def conversation_exists(self, conv_id: str) -> bool:
        """Check if a conversation exists."""
        with sqlite3.connect(_DB_PATH) as conn:
            cursor = conn.execute("SELECT 1 FROM conversations WHERE id = ? LIMIT 1", (conv_id,))
            return cursor.fetchone() is not None
    
    def get_conversation_count(self) -> int:
        """Get total number of conversations."""
        with sqlite3.connect(_DB_PATH) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM conversations")
            return cursor.fetchone()[0]
    
    def cleanup_old_conversations(self, max_age_days: int = 90) -> int:
        """Delete conversations older than max_age_days."""
        cutoff_date = (datetime.utcnow() - timedelta(days=max_age_days)).isoformat()
        
        with self._lock:
            with sqlite3.connect(_DB_PATH) as conn:
                # Get conversation IDs that will be deleted for execution state cleanup
                cursor = conn.execute(
                    "SELECT id FROM conversations WHERE created_at < ?", 
                    (cutoff_date,)
                )
                conversation_ids = [row[0] for row in cursor.fetchall()]
                
                # Delete the conversations
                cursor = conn.execute(
                    "DELETE FROM conversations WHERE created_at < ?", 
                    (cutoff_date,)
                )
                conn.commit()
                
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    # Clean up execution states for deleted conversations
                    try:
                        from services.python_execution_service import python_execution_service
                        for conv_id in conversation_ids:
                            python_execution_service.clear_conversation_state(conv_id)
                        logger.info(f"Cleaned up {deleted_count} old conversations and their execution states")
                    except Exception as e:
                        logger.warning(f"Failed to clear execution states during cleanup: {e}")
                    logger.info(f"Cleaned up {deleted_count} old conversations")
                
                return deleted_count
    
    def debug_database_state(self) -> dict:
        """Get debug information about the database state."""
        with sqlite3.connect(_DB_PATH) as conn:
            # Get conversation count
            cursor = conn.execute("SELECT COUNT(*) FROM conversations")
            conv_count = cursor.fetchone()[0]
            
            # Get message count
            cursor = conn.execute("SELECT COUNT(*) FROM messages")
            msg_count = cursor.fetchone()[0]
            
            # Get recent conversations
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, title, created_at, updated_at 
                FROM conversations 
                ORDER BY updated_at DESC 
                LIMIT 5
            """)
            recent_convs = [dict(row) for row in cursor.fetchall()]
            
            return {
                "conversation_count": conv_count,
                "message_count": msg_count,
                "recent_conversations": recent_convs,
                "database_path": str(_DB_PATH)
            }

    # Legacy methods for backward compatibility (will be removed later)
    def delete_message(self, conv_id: str, message_index: int) -> bool:
        """Delete a message by index (legacy method)."""
        messages = message_service.get_conversation_messages(conv_id)
        if message_index < 0 or message_index >= len(messages):
            return False
        
        message_to_delete = messages[message_index]
        return message_service.delete_message(message_to_delete.id)
    
    def delete_messages_from_index(self, conv_id: str, from_index: int) -> bool:
        """Delete messages from a specific index onwards."""
        try:
            # Delete messages via message service
            deleted_count = message_service.delete_messages_from_sequence(conv_id, from_index + 1)  # Convert to sequence number
            
            if deleted_count > 0:
                # Update conversation timestamp
                conversation = self.get_conversation(conv_id, include_messages=False)
                if conversation:
                    conversation.updated_at = datetime.utcnow().isoformat()
                    self._update_conversation(conversation)
                    
                logger.info(f"Deleted {deleted_count} messages from conversation {conv_id} starting at index {from_index}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting messages from index: {e}")
            return False

# Global instance
conversation_service = ConversationService() 