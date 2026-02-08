"""Task scheduler using APScheduler with SQLite backend."""

import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger


class TaskScheduler:
    """Schedule and execute tasks with APScheduler."""
    
    def __init__(
        self,
        db_path: str = "storage/scheduler.db",
        missed_tasks_file: str = "storage/missed_tasks.json",
        timezone: str = "UTC"
    ):
        self.db_path = db_path
        self.missed_tasks_file = missed_tasks_file
        self.timezone = timezone
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self.job_callbacks: Dict[str, Callable] = {}
        
        Path(missed_tasks_file).parent.mkdir(parents=True, exist_ok=True)
    
    def start(self):
        """Start the scheduler."""
        self.scheduler.start()
    
    def shutdown(self):
        """Shutdown the scheduler."""
        self.scheduler.shutdown()
    
    def schedule_task(
        self,
        task_id: str,
        action: str,
        params: Dict[str, Any],
        trigger: Any,
        callback: Callable,
        user_id: str
    ) -> bool:
        """Schedule a task with APScheduler."""
        try:
            job = self.scheduler.add_job(
                func=self._execute_task,
                trigger=trigger,
                id=task_id,
                args=[task_id, action, params, callback, user_id],
                replace_existing=True
            )
            self.job_callbacks[task_id] = callback
            return True
        except Exception as e:
            print(f"Error scheduling task {task_id}: {e}")
            return False
    
    async def _execute_task(
        self,
        task_id: str,
        action: str,
        params: Dict[str, Any],
        callback: Callable,
        user_id: str
    ):
        """Execute a scheduled task."""
        try:
            await callback(task_id, action, params, user_id)
        except Exception as e:
            print(f"Error executing task {task_id}: {e}")
    
    def schedule_one_time(
        self,
        task_id: str,
        action: str,
        params: Dict[str, Any],
        run_date: datetime,
        callback: Callable,
        user_id: str
    ) -> bool:
        """Schedule a one-time task."""
        trigger = DateTrigger(run_date=run_date)
        return self.schedule_task(task_id, action, params, trigger, callback, user_id)
    
    def schedule_recurring(
        self,
        task_id: str,
        action: str,
        params: Dict[str, Any],
        cron_expression: str,
        callback: Callable,
        user_id: str
    ) -> bool:
        """Schedule a recurring task with cron expression."""
        try:
            trigger = CronTrigger.from_crontab(cron_expression)
            return self.schedule_task(task_id, action, params, trigger, callback, user_id)
        except Exception as e:
            print(f"Error parsing cron expression: {e}")
            return False
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task."""
        try:
            self.scheduler.remove_job(task_id)
            return True
        except Exception:
            return False
    
    def save_missed_task(self, task: Dict[str, Any]):
        """Save a missed task to file."""
        missed = []
        if Path(self.missed_tasks_file).exists():
            with open(self.missed_tasks_file, 'r') as f:
                missed = json.load(f)
        
        missed.append(task)
        
        with open(self.missed_tasks_file, 'w') as f:
            json.dump(missed, f, indent=2)
    
    def load_missed_tasks(self) -> list:
        """Load missed tasks from file."""
        if Path(self.missed_tasks_file).exists():
            with open(self.missed_tasks_file, 'r') as f:
                return json.load(f)
        return []
    
    def clear_missed_tasks(self):
        """Clear missed tasks file."""
        if Path(self.missed_tasks_file).exists():
            Path(self.missed_tasks_file).unlink()
