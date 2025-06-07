import sqlite3
import json
import logging
import uuid
from datetime import datetime
from threading import Lock
from typing import List, Optional, Dict, Any
from pathlib import Path

from schemas.message import Message, MessageCreate, MessageUpdate

logger = logging.getLogger(__name__)

# Database path
_DATA_DIR = Path("data")
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_DB_PATH = _DATA_DIR / "conversations.db"

class MessageService:
    """Service for managing individual messages with rich metadata."""
    
    _lock = Lock()
    
    def __init__(self):
        self._init_db()
    
    def _init_db(self):
        """Initialize the messages table."""
        try:
            with sqlite3.connect(_DB_PATH) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        sequence_number INTEGER NOT NULL,
                        
                        -- Core content
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        
                        -- Classification
                        message_type TEXT DEFAULT 'chat',
                        agent_type TEXT,
                        
                        -- Agent execution results
                        query_generated TEXT,
                        query_results TEXT,  -- JSON
                        execution_info TEXT,  -- JSON
                        similar_results TEXT,  -- JSON
                        entity_matches TEXT,  -- JSON
                        
                        -- Workflow data
                        workflow_plan TEXT,  -- JSON
                        workflow_id TEXT,
                        execution_results TEXT,  -- JSON (note: same name but different from query_results)
                        failed_steps TEXT,  -- JSON
                        
                        -- Clarification
                        needs_clarification BOOLEAN DEFAULT FALSE,
                        clarification_questions TEXT,  -- JSON
                        
                        -- UI flags
                        has_query_results BOOLEAN DEFAULT FALSE,
                        has_generated_code BOOLEAN DEFAULT FALSE,
                        has_workflow_plan BOOLEAN DEFAULT FALSE,
                        has_workflow_execution BOOLEAN DEFAULT FALSE,
                        has_error BOOLEAN DEFAULT FALSE,
                        
                        -- Progress tracking
                        is_node_progress BOOLEAN DEFAULT FALSE,
                        owner_message_id TEXT,
                        phase TEXT,
                        node_name TEXT,
                        
                        -- Timestamps
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        
                        -- Additional metadata
                        metadata TEXT,  -- JSON
                        
                        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                        UNIQUE(conversation_id, sequence_number)
                    )
                """)
                
                # Create indexes for performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_sequence ON messages(conversation_id, sequence_number)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_owner ON messages(owner_message_id)")
                
                conn.commit()
                logger.info("Messages table initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing messages table: {e}")
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
    
    def _row_to_message(self, row: sqlite3.Row) -> Message:
        """Convert database row to Message object."""
        data = dict(row)
        
        # Deserialize JSON fields
        json_fields = [
            'query_results', 'execution_info', 'similar_results', 'entity_matches',
            'workflow_plan', 'execution_results', 'failed_steps', 
            'clarification_questions', 'metadata'
        ]
        
        for field in json_fields:
            if field in data:
                data[field] = self._deserialize_json_field(data[field])
        
        # Convert boolean fields
        bool_fields = [
            'needs_clarification', 'has_query_results', 'has_generated_code', 
            'has_workflow_plan', 'has_workflow_execution', 'has_error', 'is_node_progress'
        ]
        for field in bool_fields:
            if field in data:
                data[field] = bool(data[field])
        
        return Message(**data)
    
    def create_message(self, message_data: MessageCreate) -> Message:
        """Create a new message in a conversation."""
        now_iso = datetime.utcnow().isoformat()
        message_id = f"msg_{int(datetime.utcnow().timestamp() * 1000)}_{uuid.uuid4().hex[:8]}"
        
        # Get next sequence number for this conversation
        with sqlite3.connect(_DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM messages WHERE conversation_id = ?",
                (message_data.conversation_id,)
            )
            sequence_number = cursor.fetchone()[0]
        
        # Create the message
        message = Message(
            id=message_id,
            conversation_id=message_data.conversation_id,
            sequence_number=sequence_number,
            role=message_data.role,
            content=message_data.content,
            message_type=message_data.message_type,
            agent_type=message_data.agent_type,
            metadata=message_data.metadata,
            created_at=now_iso,
            updated_at=now_iso
        )
        
        self._insert_message(message)
        logger.info(f"Created message {message_id} in conversation {message_data.conversation_id}")
        return message
    
    def _insert_message(self, message: Message):
        """Insert a message into the database."""
        with self._lock:
            with sqlite3.connect(_DB_PATH) as conn:
                conn.execute("""
                    INSERT INTO messages (
                        id, conversation_id, sequence_number, role, content,
                        message_type, agent_type, query_generated, query_results, execution_info,
                        similar_results, entity_matches, workflow_plan, workflow_id, execution_results,
                        failed_steps, needs_clarification, clarification_questions, has_query_results,
                        has_generated_code, has_workflow_plan, has_workflow_execution, has_error,
                        is_node_progress, owner_message_id, phase, node_name, created_at, updated_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    message.id, message.conversation_id, message.sequence_number, 
                    message.role, message.content, message.message_type, message.agent_type,
                    message.query_generated, self._serialize_json_field(message.query_results),
                    self._serialize_json_field(message.execution_info), self._serialize_json_field(message.similar_results),
                    self._serialize_json_field(message.entity_matches), self._serialize_json_field(message.workflow_plan),
                    message.workflow_id, self._serialize_json_field(message.execution_results),
                    self._serialize_json_field(message.failed_steps), message.needs_clarification,
                    self._serialize_json_field(message.clarification_questions), message.has_query_results,
                    message.has_generated_code, message.has_workflow_plan, message.has_workflow_execution,
                    message.has_error, message.is_node_progress, message.owner_message_id,
                    message.phase, message.node_name, message.created_at, message.updated_at,
                    self._serialize_json_field(message.metadata)
                ))
                conn.commit()
    
    def update_message(self, message_id: str, update_data: MessageUpdate) -> Optional[Message]:
        """Update a message with new results and metadata."""
        message = self.get_message(message_id)
        if not message:
            return None
        
        # Update fields from update_data
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(message, field, value)
        
        # Update UI flags based on data
        message.has_query_results = bool(message.query_results)
        message.has_generated_code = bool(message.query_generated)
        message.has_workflow_plan = bool(message.workflow_plan)
        message.has_workflow_execution = bool(message.execution_results)
        message.has_error = message.message_type == 'error' or (message.metadata and message.metadata.get('is_error'))
        
        # Update timestamp
        message.updated_at = datetime.utcnow().isoformat()
        
        # Save to database
        with self._lock:
            with sqlite3.connect(_DB_PATH) as conn:
                conn.execute("""
                    UPDATE messages SET
                        query_generated = ?, query_results = ?, execution_info = ?,
                        similar_results = ?, entity_matches = ?, workflow_plan = ?,
                        workflow_id = ?, execution_results = ?, failed_steps = ?,
                        needs_clarification = ?, clarification_questions = ?,
                        has_query_results = ?, has_generated_code = ?, has_workflow_plan = ?,
                        has_workflow_execution = ?, has_error = ?, updated_at = ?, metadata = ?
                    WHERE id = ?
                """, (
                    message.query_generated, self._serialize_json_field(message.query_results),
                    self._serialize_json_field(message.execution_info), self._serialize_json_field(message.similar_results),
                    self._serialize_json_field(message.entity_matches), self._serialize_json_field(message.workflow_plan),
                    message.workflow_id, self._serialize_json_field(message.execution_results),
                    self._serialize_json_field(message.failed_steps), message.needs_clarification,
                    self._serialize_json_field(message.clarification_questions), message.has_query_results,
                    message.has_generated_code, message.has_workflow_plan, message.has_workflow_execution,
                    message.has_error, message.updated_at, self._serialize_json_field(message.metadata),
                    message_id
                ))
                conn.commit()
        
        logger.info(f"Updated message {message_id}")
        return message
    
    def get_message(self, message_id: str) -> Optional[Message]:
        """Get a single message by ID."""
        with sqlite3.connect(_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return self._row_to_message(row)
    
    def get_conversation_messages(self, conversation_id: str, include_progress: bool = False) -> List[Message]:
        """Get all messages for a conversation, ordered by sequence number."""
        with sqlite3.connect(_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            
            if include_progress:
                cursor = conn.execute(
                    "SELECT * FROM messages WHERE conversation_id = ? ORDER BY sequence_number ASC",
                    (conversation_id,)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM messages WHERE conversation_id = ? AND is_node_progress = FALSE ORDER BY sequence_number ASC",
                    (conversation_id,)
                )
            
            rows = cursor.fetchall()
            return [self._row_to_message(row) for row in rows]
    
    def get_progress_messages(self, owner_message_id: str) -> List[Message]:
        """Get progress messages for a specific owner message."""
        with sqlite3.connect(_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM messages WHERE owner_message_id = ? AND is_node_progress = TRUE ORDER BY created_at ASC",
                (owner_message_id,)
            )
            rows = cursor.fetchall()
            return [self._row_to_message(row) for row in rows]
    
    def delete_message(self, message_id: str) -> bool:
        """Delete a message and all its progress messages."""
        with self._lock:
            with sqlite3.connect(_DB_PATH) as conn:
                # Delete progress messages first
                conn.execute("DELETE FROM messages WHERE owner_message_id = ?", (message_id,))
                
                # Delete the message itself
                cursor = conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
                conn.commit()
                
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info(f"Deleted message {message_id} and its progress messages")
                return deleted
    
    def delete_messages_from_sequence(self, conversation_id: str, from_sequence: int) -> int:
        """Delete messages from a specific sequence number onwards."""
        with self._lock:
            with sqlite3.connect(_DB_PATH) as conn:
                # Get message IDs that will be deleted to clean up progress messages
                cursor = conn.execute(
                    "SELECT id FROM messages WHERE conversation_id = ? AND sequence_number >= ?",
                    (conversation_id, from_sequence)
                )
                message_ids = [row[0] for row in cursor.fetchall()]
                
                # Delete progress messages for these messages
                for msg_id in message_ids:
                    conn.execute("DELETE FROM messages WHERE owner_message_id = ?", (msg_id,))
                
                # Delete the messages themselves
                cursor = conn.execute(
                    "DELETE FROM messages WHERE conversation_id = ? AND sequence_number >= ?",
                    (conversation_id, from_sequence)
                )
                
                conn.commit()
                deleted_count = cursor.rowcount
                
                if deleted_count > 0:
                    logger.info(f"Deleted {deleted_count} messages from sequence {from_sequence} in conversation {conversation_id}")
                
                return deleted_count
    
    def create_progress_message(self, owner_message_id: str, node_name: str, phase: str, 
                              content: str = "", metadata: Optional[Dict[str, Any]] = None) -> Message:
        """Create a progress message linked to an owner message."""
        # Get owner message to determine conversation
        owner_message = self.get_message(owner_message_id)
        if not owner_message:
            raise ValueError(f"Owner message {owner_message_id} not found")
        
        now_iso = datetime.utcnow().isoformat()
        progress_id = f"prog_{int(datetime.utcnow().timestamp() * 1000)}_{uuid.uuid4().hex[:8]}"
        
        # Get next sequence number
        with sqlite3.connect(_DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM messages WHERE conversation_id = ?",
                (owner_message.conversation_id,)
            )
            sequence_number = cursor.fetchone()[0]
        
        progress_message = Message(
            id=progress_id,
            conversation_id=owner_message.conversation_id,
            sequence_number=sequence_number,
            role="assistant",
            content=content or f"Processing: {node_name} ({phase})",
            message_type="progress",
            is_node_progress=True,
            owner_message_id=owner_message_id,
            phase=phase,
            node_name=node_name,
            metadata=metadata,
            created_at=now_iso,
            updated_at=now_iso
        )
        
        self._insert_message(progress_message)
        logger.info(f"Created progress message {progress_id} for {owner_message_id}: {node_name} ({phase})")
        return progress_message

# Global instance
message_service = MessageService() 