import json
import logging
from pathlib import Path
from threading import Lock
from typing import List, Optional
from datetime import datetime

from schemas.conversation import Conversation

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DATA_DIR.mkdir(exist_ok=True)
_CONV_FILE = _DATA_DIR / "conversations.json"

class ConversationService:
    """Service for persisting and retrieving conversations."""

    _lock = Lock()

    def __init__(self):
        self._conversations = {}
        self._load()

    def _load(self):
        if _CONV_FILE.exists():
            try:
                data = json.loads(_CONV_FILE.read_text())
                for conv_json in data:
                    conv = Conversation(**conv_json)
                    self._conversations[conv.id] = conv
                logger.info(f"Loaded {len(self._conversations)} conversations from disk")
            except Exception as e:
                logger.error(f"Error loading conversations: {e}")
        else:
            logger.info("Conversation file does not exist; starting fresh")

    def _save(self):
        try:
            with self._lock:
                _CONV_FILE.write_text(json.dumps([c.dict(by_alias=True) for c in self._conversations.values()], ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"Error saving conversations: {e}")

    # Public API
    def list_conversations(self) -> List[Conversation]:
        return sorted(self._conversations.values(), key=lambda c: c.updated_at or c.created_at, reverse=True)

    def get(self, conv_id: str) -> Optional[Conversation]:
        return self._conversations.get(conv_id)

    def upsert(self, conversation: Conversation):
        now_iso = datetime.utcnow().isoformat()
        if not conversation.created_at:
            conversation.created_at = now_iso
        conversation.updated_at = now_iso
        self._conversations[conversation.id] = conversation
        self._save()

    def delete(self, conv_id: str):
        if conv_id in self._conversations:
            del self._conversations[conv_id]
            self._save()

# Singleton instance
conversation_service = ConversationService() 