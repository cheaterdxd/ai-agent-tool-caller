"""Task manager for CRUD operations on scheduled tasks."""

import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path


class TaskManager:
    """Manage tasks with SQLite backend."""
    
    def __init__(self, db_path: str = "storage/scheduler.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    action TEXT NOT NULL,
                    params TEXT NOT NULL,
                    schedule TEXT NOT NULL,
                    recurrence TEXT,
                    user_id TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    executed_at TEXT,
                    retry_count INTEGER DEFAULT 0
                )
            """)
            conn.commit()
    
    def create_task(
        self,
        name: str,
        action: str,
        params: Dict[str, Any],
        schedule: str,
        user_id: str,
        recurrence: Optional[str] = None
    ) -> bool:
        """Create a new task."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO tasks (name, action, params, schedule, recurrence, user_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (name, action, json.dumps(params), schedule, recurrence, user_id, datetime.now().isoformat())
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False
    
    def get_task(self, name: str) -> Optional[Dict[str, Any]]:
        """Get task by name."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all tasks, optionally filtered by status."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if status:
                cursor = conn.execute("SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC", (status,))
            else:
                cursor = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    
    def cancel_task(self, name: str) -> bool:
        """Cancel a task by name."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE name = ? AND status = 'pending'", (name,))
            conn.commit()
            return cursor.rowcount > 0
    
    def update_task_status(self, name: str, status: str, executed_at: Optional[str] = None):
        """Update task status."""
        with sqlite3.connect(self.db_path) as conn:
            if executed_at:
                conn.execute(
                    "UPDATE tasks SET status = ?, executed_at = ? WHERE name = ?",
                    (status, executed_at, name)
                )
            else:
                conn.execute(
                    "UPDATE tasks SET status = ? WHERE name = ?",
                    (status, name)
                )
            conn.commit()
    
    def increment_retry(self, name: str):
        """Increment retry count for a task."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE tasks SET retry_count = retry_count + 1 WHERE name = ?", (name,))
            conn.commit()
    
    def cleanup_old_tasks(self, days: int = 30):
        """Remove tasks older than specified days."""
        cutoff = datetime.now() - __import__('datetime').timedelta(days=days)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM tasks WHERE created_at < ?", (cutoff.isoformat(),))
            conn.commit()
