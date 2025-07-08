import sqlite3
import json
import logging
import uuid
from datetime import datetime
from threading import Lock
from typing import List, Optional, Dict, Any
from pathlib import Path
import os

from schemas.message import Message, MessageCreate, MessageUpdate, ExecutionResult
from services.service_manager import service_manager

logger = logging.getLogger(__name__)

# Database path
_DATA_DIR = Path("data")
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_DB_PATH = _DATA_DIR / "conversations.db"
_PLOTS_DIR = _DATA_DIR / "plots"

# Maximum number of results to store per message to avoid oversized context
MAX_STORED_RESULTS = 50

class MessageService:
    """Service for managing individual messages with unified schema across all agents."""
    
    _instance = None
    _initialized = False
    _lock = Lock()
    
    def __new__(cls):
        """Ensure only one instance of MessageService exists."""
        if cls._instance is None:
            cls._instance = super(MessageService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the message service (only once)."""
        if MessageService._initialized:
            return
            
        self._init_db()
        MessageService._initialized = True
    
    def _init_db(self):
        """Initialize the messages table with unified schema."""
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
                        
                        -- Generation results (unified)
                        generated_code TEXT,
                        
                        -- Execution results (unified structure)
                        execution_results TEXT,  -- JSON array of ExecutionResult objects
                        result_variable_names TEXT,  -- JSON array
                        
                        -- Agent-specific metadata
                        agent_metadata TEXT,  -- JSON
                        
                        -- Search and context results
                        similar_results TEXT,  -- JSON
                        entity_matches TEXT,  -- JSON
                        
                        -- Clarification
                        needs_clarification BOOLEAN DEFAULT FALSE,
                        clarification_questions TEXT,  -- JSON
                        clarification_responses TEXT,  -- JSON
                        
                        -- UI flags
                        has_execution_results BOOLEAN DEFAULT FALSE,
                        has_generated_code BOOLEAN DEFAULT FALSE,
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
                logger.info("Messages table initialized successfully with unified schema")
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
    
    def _serialize_execution_results(self, execution_results: Optional[List[Any]]) -> Optional[str]:
        """Serialize execution results to JSON (handles both ExecutionResult objects and dicts)."""
        if not execution_results:
            return None
        try:
            serialized_results = []
            for result in execution_results:
                if hasattr(result, 'dict'):
                    # It's a Pydantic model
                    serialized_results.append(result.dict())
                elif isinstance(result, dict):
                    # It's already a dictionary
                    serialized_results.append(result)
                else:
                    # Convert to dict if possible
                    serialized_results.append(dict(result))
            return json.dumps(serialized_results, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to serialize execution results: {e}")
            return None
    
    def _deserialize_execution_results(self, json_str: Optional[str]) -> Optional[List[ExecutionResult]]:
        """Deserialize JSON to ExecutionResult objects."""
        if not json_str:
            return None
        try:
            data = json.loads(json_str)
            return [ExecutionResult(**item) for item in data]
        except Exception as e:
            logger.warning(f"Failed to deserialize execution results: {e}")
            return None
    
    def _row_to_message(self, row: sqlite3.Row) -> Message:
        """Convert database row to Message object."""
        try:
            # Parse JSON fields safely
            def safe_json_loads(value, default=None):
                if value is None:
                    return default
                try:
                    return json.loads(value) if isinstance(value, str) else value
                except (json.JSONDecodeError, TypeError):
                    return default
            
            # Parse execution results and convert back to ExecutionResult objects
            execution_results_data = safe_json_loads(row[8], [])  # execution_results is now at index 8
            execution_results = []
            if execution_results_data:
                for result_data in execution_results_data:
                    try:
                        execution_results.append(ExecutionResult(**result_data))
                    except Exception as e:
                        logger.warning(f"Failed to parse execution result: {e}")
                        continue
            
            return Message(
                id=row[0],
                conversation_id=row[1],
                sequence_number=row[2],
                role=row[3],
                content=row[4],
                message_type=row[5],
                agent_type=row[6],
                generated_code=row[7],
                execution_results=execution_results,
                result_variable_names=safe_json_loads(row[9], []),  # adjusted index
                agent_metadata=safe_json_loads(row[10]),  # adjusted index
                similar_results=safe_json_loads(row[11], []),  # adjusted index
                entity_matches=safe_json_loads(row[12], []),  # adjusted index
                needs_clarification=bool(row[13]) if row[13] is not None else False,  # adjusted index
                clarification_questions=safe_json_loads(row[14], []),  # adjusted index
                clarification_responses=safe_json_loads(row[15], []),  # adjusted index
                has_execution_results=bool(row[16]) if row[16] is not None else False,  # adjusted index
                has_generated_code=bool(row[17]) if row[17] is not None else False,  # adjusted index
                has_error=bool(row[18]) if row[18] is not None else False,  # adjusted index
                is_node_progress=bool(row[19]) if row[19] is not None else False,  # adjusted index
                owner_message_id=row[20],  # adjusted index
                phase=row[21],  # adjusted index
                node_name=row[22],  # adjusted index
                created_at=row[23],  # adjusted index
                updated_at=row[24],  # adjusted index
                metadata=safe_json_loads(row[25])  # adjusted index
            )
        except Exception as e:
            logger.error(f"Error converting row to message: {e}")
            logger.error(f"Row data: {row}")
            raise
    
    def _truncate_list(self, data: Any, limit: int = MAX_STORED_RESULTS):
        """Return at most `limit` items if input is a list, otherwise return as-is."""
        if isinstance(data, list) and len(data) > limit:
            return data[:limit]
        return data
    
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
        
        # Broadcast to WebSocket listeners
        try:
            from websocket_manager import ws_manager
            ws_manager.broadcast(message.conversation_id, {
                "type": "message_created",
                "message": message.dict()
            })
        except Exception as e:
            logger.warning(f"Websocket broadcast failed: {e}")
        
        logger.info(f"Created message {message_id} in conversation {message_data.conversation_id}")
        return message
    
    def _insert_message(self, message: Message):
        """Insert a message into the database."""
        with self._lock:
            with sqlite3.connect(_DB_PATH) as conn:
                conn.execute("""
                    INSERT INTO messages (
                        id, conversation_id, sequence_number, role, content,
                        message_type, agent_type, generated_code,
                        execution_results, result_variable_names, agent_metadata,
                        similar_results, entity_matches, needs_clarification, clarification_questions, clarification_responses,
                        has_execution_results, has_generated_code, has_error,
                        is_node_progress, owner_message_id, phase, node_name, created_at, updated_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    message.id, message.conversation_id, message.sequence_number, 
                    message.role, message.content, message.message_type, message.agent_type,
                    message.generated_code,
                    self._serialize_execution_results(message.execution_results),
                    self._serialize_json_field(message.result_variable_names),
                    self._serialize_json_field(message.agent_metadata),
                    self._serialize_json_field(self._truncate_list(message.similar_results)),
                    self._serialize_json_field(message.entity_matches),
                    message.needs_clarification,
                    self._serialize_json_field(message.clarification_questions),
                    self._serialize_json_field(message.clarification_responses),
                    message.has_execution_results, message.has_generated_code, message.has_error,
                    message.is_node_progress, message.owner_message_id,
                    message.phase, message.node_name, message.created_at, message.updated_at,
                    self._serialize_json_field(message.metadata)
                ))
                conn.commit()
    
    def update_message_results(
        self,
        message_id: str,
        generated_code: Optional[str] = None,
        execution_results: Optional[List[ExecutionResult]] = None,
        result_variable_names: Optional[List[str]] = None,
        agent_metadata: Optional[Dict[str, Any]] = None,
        similar_results: Optional[List[Any]] = None,
        entity_matches: Optional[List[Any]] = None,
        needs_clarification: Optional[bool] = None,
        clarification_questions: Optional[List[Any]] = None,
        clarification_responses: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Message]:
        """Update message with execution results and metadata."""
        try:
            # Build update data
            update_data = {}
            
            if generated_code is not None:
                update_data["generated_code"] = generated_code
                update_data["has_generated_code"] = bool(generated_code)
            
            if execution_results is not None:
                # Handle mixed ExecutionResult objects and dictionaries
                serialized_results = []
                for result in execution_results:
                    if isinstance(result, ExecutionResult):
                        serialized_results.append(result.model_dump())
                    elif isinstance(result, dict):
                        serialized_results.append(result)
                    else:
                        logger.warning(f"Unexpected execution result type: {type(result)}")
                        continue
                
                update_data["execution_results"] = json.dumps(serialized_results)
                update_data["has_execution_results"] = len(serialized_results) > 0
                
                # Check for errors in execution results
                has_error = any(
                    result.get("type") == "execution_error" or result.get("error")
                    for result in serialized_results
                )
                update_data["has_error"] = has_error
            
            if result_variable_names is not None:
                update_data["result_variable_names"] = json.dumps(result_variable_names)
            
            if agent_metadata is not None:
                update_data["agent_metadata"] = json.dumps(agent_metadata)
            
            if similar_results is not None:
                update_data["similar_results"] = json.dumps(similar_results)
            
            if entity_matches is not None:
                update_data["entity_matches"] = json.dumps(entity_matches)
            
            if needs_clarification is not None:
                update_data["needs_clarification"] = needs_clarification
            
            if clarification_questions is not None:
                update_data["clarification_questions"] = json.dumps(clarification_questions)
            
            if clarification_responses is not None:
                update_data["clarification_responses"] = json.dumps(clarification_responses)
            
            if metadata is not None:
                update_data["metadata"] = json.dumps(metadata)
            
            # Add timestamp
            update_data["updated_at"] = datetime.utcnow().isoformat()
            
            # Execute update
            query = """
                UPDATE messages 
                SET """ + ", ".join([f"{k} = ?" for k in update_data.keys()]) + """
                WHERE id = ?
            """
            
            values = list(update_data.values()) + [message_id]
            
            with self._lock:
                with sqlite3.connect(_DB_PATH) as conn:
                    conn.execute(query, values)
                    conn.commit()
            
            # Retrieve updated message to broadcast
            updated_msg = self.get_message(message_id)

            # Broadcast the update so clients refresh their copy
            try:
                from websocket_manager import ws_manager
                if updated_msg:
                    ws_manager.broadcast(updated_msg.conversation_id, {
                        "type": "message_updated",
                        "message": updated_msg.dict()
                    })
            except Exception as e:
                logger.warning(f"Websocket broadcast (message_updated) failed: {e}")

            return updated_msg
            
        except Exception as e:
            logger.error(f"Error updating message results: {e}")
            return None
    
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
                # Get the message before deletion for plot cleanup
                cursor = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
                row = cursor.fetchone()
                if not row:
                    return False
                
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
                message_row = cursor.fetchone()
                message = self._row_to_message(message_row)
                conversation_id = message.conversation_id
                
                # Clean up plots for this message
                self._cleanup_plots_for_message(message)
                
                # Get and clean up plots for progress messages
                progress_cursor = conn.execute("SELECT * FROM messages WHERE owner_message_id = ?", (message_id,))
                progress_rows = progress_cursor.fetchall()
                for progress_row in progress_rows:
                    progress_message = self._row_to_message(progress_row)
                    self._cleanup_plots_for_message(progress_message)
                
                # Delete progress messages first
                conn.execute("DELETE FROM messages WHERE owner_message_id = ?", (message_id,))
                
                # Delete the message itself
                cursor = conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
                conn.commit()
                
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info(f"Deleted message {message_id} and its progress messages")
                    
                # Rebuild the execution state to accurately reflect remaining messages
                try:
                    # Get remaining messages (excluding progress messages)
                    remaining_messages = self.get_conversation_messages(conversation_id, include_progress=False)
                    # Use smart rebuild to only remove variables from this specific message
                    execution_service = service_manager.get_execution_service()
                    execution_service.smart_rebuild_conversation_state(
                        conversation_id,
                        [message],  # Only this message was deleted
                        remaining_messages
                    )
                    logger.info(
                        f"Smart rebuilt execution state for conversation {conversation_id} after deleting message {message_id}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to rebuild execution state for conversation {conversation_id} after deletion: {e}"
                    )
                
                return deleted
    
    def delete_messages_from_sequence(self, conversation_id: str, from_sequence: int) -> int:
        """Delete messages from a specific sequence number onwards."""
        with self._lock:
            with sqlite3.connect(_DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                
                # Get all messages that will be deleted for plot cleanup
                cursor = conn.execute(
                    "SELECT * FROM messages WHERE conversation_id = ? AND sequence_number >= ?",
                    (conversation_id, from_sequence)
                )
                messages_to_delete = [self._row_to_message(row) for row in cursor.fetchall()]
                
                # Clean up plots for all messages being deleted
                for message in messages_to_delete:
                    self._cleanup_plots_for_message(message)
                
                # Get progress messages for these messages and clean up their plots too
                message_ids = [msg.id for msg in messages_to_delete]
                for msg_id in message_ids:
                    progress_cursor = conn.execute("SELECT * FROM messages WHERE owner_message_id = ?", (msg_id,))
                    progress_rows = progress_cursor.fetchall()
                    for progress_row in progress_rows:
                        progress_message = self._row_to_message(progress_row)
                        self._cleanup_plots_for_message(progress_message)
                
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
                    
                    # Rebuild the execution state to accurately reflect remaining messages
                    try:
                        # Get remaining messages (excluding progress messages)
                        remaining_messages = self.get_conversation_messages(conversation_id, include_progress=False)
                        # Use smart rebuild to only remove variables from deleted messages
                        execution_service = service_manager.get_execution_service()
                        execution_service.smart_rebuild_conversation_state(
                            conversation_id,
                            messages_to_delete,  # All messages that were deleted
                            remaining_messages
                        )
                        logger.info(
                            f"Smart rebuilt execution state for conversation {conversation_id} after deleting {len(messages_to_delete)} messages from sequence {from_sequence}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to rebuild execution state for conversation {conversation_id} after deletion: {e}"
                        )
                
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
            content=content,
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
        
        # Broadcast progress update
        try:
            from websocket_manager import ws_manager
            ws_manager.broadcast(progress_message.conversation_id, {
                "type": "progress",
                "message": progress_message.dict()
            })
        except Exception:
            pass
        
        logger.info(f"Created progress message {progress_id} for owner {owner_message_id}")
        return progress_message
    
    def _cleanup_plots_for_message(self, message: Message) -> None:
        """Clean up plot files associated with a message."""
        if not message.execution_results:
            return
            
        plots_to_delete = []
        for result in message.execution_results:
            if result.plots:
                plots_to_delete.extend(result.plots)
        
        self._delete_plot_files(plots_to_delete)
    
    def _cleanup_plots_for_conversation(self, conversation_id: str) -> None:
        """Clean up all plot files for a conversation by filename pattern."""
        try:
            if not _PLOTS_DIR.exists():
                return
                
            # Find all plot files for this conversation
            pattern = f"plot_{conversation_id}_*"
            plots_to_delete = []
            
            for plot_file in _PLOTS_DIR.glob(pattern):
                plots_to_delete.append(plot_file.name)
            
            self._delete_plot_files(plots_to_delete)
            logger.info(f"Cleaned up {len(plots_to_delete)} plot files for conversation {conversation_id}")
            
        except Exception as e:
            logger.warning(f"Failed to clean up plots for conversation {conversation_id}: {e}")
    
    def _delete_plot_files(self, plot_filenames: List[str]) -> None:
        """Delete specific plot files from disk."""
        if not plot_filenames:
            return
            
        deleted_count = 0
        for filename in plot_filenames:
            try:
                plot_path = _PLOTS_DIR / filename
                if plot_path.exists():
                    os.remove(plot_path)
                    deleted_count += 1
                    logger.debug(f"Deleted plot file: {filename}")
            except Exception as e:
                logger.warning(f"Failed to delete plot file {filename}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} plot files from disk")

# Global instance - lazy initialization to avoid multiprocessing issues
# Global message service instance
message_service = MessageService() 