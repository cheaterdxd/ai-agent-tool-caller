"""Intent parser using Ollama for natural language understanding."""

import json
import re
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import ollama


class IntentParser:
    """Parse natural language into structured intents using Ollama."""
    
    SYSTEM_PROMPT = """You are an intent parser for an AI agent. Extract structured information from user commands.
    
Available actions:
- search: Search for information on the web
- add_note: Add a note to the RAG knowledge base
- list_tasks: List scheduled tasks
- cancel_task: Cancel a scheduled task
- unknown: Cannot understand the intent

Extract these fields:
- action: The main action (search, add_note, list_tasks, cancel_task, unknown)
- query: The search query or note content
- schedule: When to execute (immediate, specific time in ISO format, or null)
- recurrence: If recurring (daily, weekly, monthly, or null)
- task_name: For cancel_task action, the name of task to cancel

Respond ONLY with valid JSON in this exact format:
{
  "action": "search",
  "query": "articles about Thales",
  "schedule": "2026-02-08T14:00:00",
  "recurrence": null,
  "task_name": null
}

If schedule is relative (e.g., "tomorrow at 2pm"), convert to ISO format.
If no schedule specified, use "immediate".
If query contains quotes, preserve them.
Be precise with dates and times."""

    def __init__(self, model: str = "qwen2.5:7b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.client = ollama.Client(host=base_url)
    
    async def parse(self, message: str) -> Dict[str, Any]:
        """Parse natural language message into structured intent."""
        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"Parse this command: {message}"}
                ],
                options={"temperature": 0.3}
            )
            
            content = response['message']['content']
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    parsed['schedule'] = self._normalize_schedule(parsed.get('schedule'))
                    return parsed
                except json.JSONDecodeError:
                    return {"action": "unknown", "error": "Failed to parse JSON"}
            
            return {"action": "unknown", "error": "No JSON found in response"}
        except Exception as e:
            return {"action": "unknown", "error": str(e)}
    
    def _normalize_schedule(self, schedule: Optional[str]) -> Optional[str]:
        """Convert various time formats to ISO format."""
        if not schedule or schedule == "immediate":
            return "immediate"
        
        # If already ISO format, return as-is
        try:
            datetime.fromisoformat(schedule.replace('Z', '+00:00'))
            return schedule
        except ValueError:
            pass
        
        # Handle relative times
        now = datetime.now()
        schedule_lower = schedule.lower()
        
        if schedule_lower == "tomorrow":
            return (now + timedelta(days=1)).isoformat()
        elif schedule_lower == "today":
            return now.isoformat()
        elif schedule_lower.startswith("in "):
            # Handle "in X minutes/hours/days"
            parts = schedule_lower.split()
            if len(parts) >= 3:
                try:
                    amount = int(parts[1])
                    unit = parts[2]
                    if "minute" in unit:
                        return (now + timedelta(minutes=amount)).isoformat()
                    elif "hour" in unit:
                        return (now + timedelta(hours=amount)).isoformat()
                    elif "day" in unit:
                        return (now + timedelta(days=amount)).isoformat()
                except ValueError:
                    pass
        
        return schedule
