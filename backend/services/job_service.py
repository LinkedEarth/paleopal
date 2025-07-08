import sqlite3, logging, uuid
from pathlib import Path
from threading import Lock
from datetime import datetime
from typing import List, Optional

from schemas.job import Job, JobCreate

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DATA_DIR.mkdir(exist_ok=True)
_DB_PATH = _DATA_DIR / "conversations.db"  # reuse same db file

class JobService:
    _lock = Lock()

    def __init__(self):
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(_DB_PATH) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS jobs (
                        id TEXT PRIMARY KEY,
                        conv_id TEXT NOT NULL,
                        owner_message_id TEXT NOT NULL,
                        state TEXT NOT NULL,
                        error TEXT,
                        started_at TEXT NOT NULL,
                        finished_at TEXT
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_conv ON jobs(conv_id)")
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to init jobs table: {e}")
            raise

    # util
    def _row_to_job(self, row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            conversation_id=row["conv_id"],  # Use the alias field name
            owner_message_id=row["owner_message_id"],
            state=row["state"],
            error=row["error"],
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
        )

    # CRUD
    def create_job(self, data: JobCreate) -> Job:
        job_id = f"job_{int(datetime.now().timestamp()*1000)}_{uuid.uuid4().hex[:6]}"
        now_iso = datetime.now().isoformat()
        with self._lock, sqlite3.connect(_DB_PATH) as conn:
            conn.execute(
                "INSERT INTO jobs (id, conv_id, owner_message_id, state, error, started_at) VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, data.conv_id, data.owner_message_id, data.state, data.error, now_iso),
            )
            conn.commit()
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> Optional[Job]:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                return None
            return self._row_to_job(row)

    def list_jobs(self, conv_id: Optional[str] = None, state: Optional[str] = None) -> List[Job]:
        query = "SELECT * FROM jobs"
        params = []
        conditions = []
        if conv_id:
            conditions.append("conv_id=?")
            params.append(conv_id)
        if state:
            conditions.append("state=?")
            params.append(state)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY started_at DESC"
        with sqlite3.connect(_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_job(r) for r in rows]

    def update_job_state(self, job_id: str, new_state: str, error: Optional[str] = None):
        finished_at = datetime.now().isoformat() if new_state in ("done", "error") else None
        with self._lock, sqlite3.connect(_DB_PATH) as conn:
            conn.execute(
                "UPDATE jobs SET state=?, error=?, finished_at=? WHERE id=?",
                (new_state, error, finished_at, job_id),
            )
            conn.commit()

        # Broadcast update
        try:
            job = self.get_job(job_id)
            from websocket_manager import ws_manager
            ws_manager.broadcast(job.conv_id, {
                "type": "job_updated",
                "job": job.dict()
            })
        except Exception:
            pass

# Global instance - lazy initialization to avoid multiprocessing issues
# Global job service instance
job_service = JobService() 