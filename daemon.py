#!/usr/bin/env python3
"""Main daemon process for AI Agent."""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add external modules to path
sys.path.insert(0, "external/discord-bridge")
sys.path.insert(0, "external/LEANN")

from discord_bridge import Bridge, CommandRouter

from agent.core import AgentCore
from agent.parser import IntentParser
from agent.scheduler import TaskScheduler
from agent.task_manager import TaskManager
from tools.browser_pool import BrowserPool
from tools.search import SearchTool
from tools.rag import LEANNTool

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AgentDaemon:
    """Main daemon process."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        
        # Initialize components
        self.core = AgentCore()
        self.task_manager = TaskManager()
        self.scheduler = TaskScheduler(
            missed_tasks_file=self.config.get('scheduler_missed_task_file', 'storage/missed_tasks.json')
        )
        self.parser = IntentParser(
            model=self.config.get('ollama_intent_model', 'qwen2.5:7b'),
            base_url=self.config.get('ollama_url', 'http://localhost:11434')
        )
        self.browser_pool = BrowserPool(
            max_instances=self.config.get('browser_max_instances', 3),
            rate_limit_delay=self.config.get('browser_rate_limit_delay', 30),
            max_per_day=self.config.get('browser_max_searches_per_day', 50),
            headless=self.config.get('browser_headless', True),
            ollama_model=self.config.get('ollama_intent_model', 'qwen2.5:7b')
        )
        self.search_tool = SearchTool(self.browser_pool)
        self.rag = LEANNTool(
            index_path=self.config.get('lean_index_path', 'storage/lean_index')
        )
        
        # Discord bridge
        self.bridge = Bridge(config_path=config_path)
        self.router = CommandRouter()
        self._setup_routes()
        
        self.running = False
        self.current_user_id: str = None
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML."""
        import yaml
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            return {}
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}
    
    def _setup_routes(self):
        """Setup Discord command routes."""
        
        @self.router.command("tasks", description="List all scheduled tasks")
        async def tasks_cmd(message, args):
            tasks = self.task_manager.list_tasks(status='pending')
            if tasks:
                response = "📋 **Scheduled Tasks:**\n"
                for task in tasks[:10]:  # Limit to 10
                    response += f"• `{task['name']}` - {task['schedule']}\n"
            else:
                response = "📋 No scheduled tasks."
            await message.reply(response)
        
        @self.router.command("cancel", description="Cancel a task by name")
        async def cancel_cmd(message, args):
            if not args:
                await message.reply("❌ Usage: `!cancel <task_name>`")
                return
            
            task_name = args.strip()
            # Cancel in scheduler
            self.scheduler.cancel_task(task_name)
            # Cancel in task manager
            success = self.task_manager.cancel_task(task_name)
            
            if success:
                await message.reply(f"✅ Task `{task_name}` cancelled.")
            else:
                await message.reply(f"❌ Task `{task_name}` not found or already executed.")
        
        @self.router.command("status", description="Check daemon status")
        async def status_cmd(message, args):
            status = "🟢 Running" if self.running else "🔴 Stopped"
            browser_status = f"Browsers: {len(self.browser_pool.browsers)} instances"
            daily_searches = f"Searches today: {self.browser_pool.daily_count}/{self.browser_pool.max_per_day}"
            
            await message.reply(f"{status}\n{browser_status}\n{daily_searches}")
        
        @self.router.default
        async def default_handler(message, args):
            """Handle natural language commands."""
            self.current_user_id = str(message.author_id)
            content = message.content
            
            logger.info(f"Processing natural language from {message.author_name}: {content}")
            
            # Parse intent
            intent = await self.parser.parse(content)
            logger.info(f"Parsed intent: {intent}")
            
            # Handle the intent
            await self._handle_intent(intent, message)
    
    async def _handle_intent(self, intent: Dict[str, Any], message):
        """Handle parsed intent."""
        action = intent.get('action', 'unknown')
        query = intent.get('query', '')
        schedule = intent.get('schedule', 'immediate')
        recurrence = intent.get('recurrence')
        
        if action == 'unknown':
            error = intent.get('error', 'Could not understand command')
            await message.reply(f"❌ {error}")
            return
        
        if action == 'list_tasks':
            # Trigger tasks command
            await self.router.handle(message)
            return
        
        if action == 'cancel_task':
            task_name = intent.get('task_name', '')
            if task_name:
                success = self.task_manager.cancel_task(task_name)
                if success:
                    await message.reply(f"✅ Task `{task_name}` cancelled.")
                else:
                    await message.reply(f"❌ Task `{task_name}` not found.")
            else:
                await message.reply("❌ No task name specified.")
            return
        
        # Generate task name
        task_name = f"{action}-{query[:20].replace(' ', '-')}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        if schedule == 'immediate':
            # Send immediate acknowledgment to prevent Discord timeout
            status_msg = await message.reply(f"⏳ Processing {action} request... (this may take a moment)")
            
            # Execute in background to not block Discord
            asyncio.create_task(self._execute_long_task(action, query, message, status_msg))
        else:
            # Schedule for later
            try:
                # Parse schedule time
                if isinstance(schedule, str):
                    run_date = datetime.fromisoformat(schedule.replace('Z', '+00:00'))
                else:
                    run_date = schedule
                
                # Save to task manager
                self.task_manager.create_task(
                    name=task_name,
                    action=action,
                    params={'query': query},
                    schedule=schedule,
                    user_id=self.current_user_id,
                    recurrence=recurrence
                )
                
                # Schedule with APScheduler
                success = self.scheduler.schedule_one_time(
                    task_id=task_name,
                    action=action,
                    params={'query': query},
                    run_date=run_date,
                    callback=self._execute_scheduled_task,
                    user_id=self.current_user_id
                )
                
                if success:
                    time_str = run_date.strftime('%Y-%m-%d %H:%M')
                    await message.reply(f"⏰ Task scheduled for {time_str}\nName: `{task_name}`")
                else:
                    await message.reply("❌ Failed to schedule task.")
                    
            except Exception as e:
                logger.error(f"Error scheduling task: {e}")
                await message.reply(f"❌ Error scheduling: {str(e)}")
    
    async def _execute_long_task(self, action: str, query: str, original_message, status_message):
        """Execute long-running task and update status message with results."""
        try:
            if action == 'search':
                results = await self.search_tool.search(query)
                await self.rag.add_search_results(results)
                
                # Prepare result message
                result_text = f"✅ **Search Complete for '{query}'**\n\n"
                result_text += f"Found {len(results)} articles and added to RAG.\n\n"
                result_text += "**Top Results:**\n"
                for i, r in enumerate(results[:5], 1):
                    result_text += f"{i}. **{r.get('title', 'Unknown')}**\n"
                    result_text += f"   {r.get('url', 'No URL')}\n\n"
                
                # Send result as reply to status message
                await status_message.reply(result_text)
                
                # Also DM the user
                await self._notify_user(str(original_message.author_id), f"✅ Search '{query}' complete! Found {len(results)} articles.")
            
            elif action == 'add_note':
                success = await self.rag.add_document(query)
                if success:
                    await status_message.reply(f"✅ Note added to RAG system.\n\n**Content:** {query[:200]}...")
                else:
                    await status_message.reply("❌ Failed to add note to RAG system.")
            
        except Exception as e:
            logger.error(f"Error executing long task: {e}")
            await status_message.reply(f"❌ **Error:** {str(e)}\n\nPlease try again or check logs for details.")
    
    async def _execute_scheduled_task(
        self,
        task_id: str,
        action: str,
        params: Dict[str, Any],
        user_id: str
    ):
        """Execute a scheduled task."""
        logger.info(f"Executing scheduled task: {task_id}")
        
        try:
            query = params.get('query', '')
            
            if action == 'search':
                results = await self.search_tool.search(query)
                await self.rag.add_search_results(results)
                await self._notify_user(
                    user_id,
                    f"⏰ Scheduled search complete for '{query}':\n" +
                    f"Found {len(results)} articles and added to RAG."
                )
            
            # Update task status
            self.task_manager.update_task_status(task_id, 'completed', datetime.now().isoformat())
            
        except Exception as e:
            logger.error(f"Error executing scheduled task {task_id}: {e}")
            self.task_manager.increment_retry(task_id)
            await self._notify_user(user_id, f"❌ Task `{task_id}` failed: {str(e)}")
    
    async def _notify_user(self, user_id: str, message: str):
        """Send DM to user."""
        try:
            user = await self.bridge._client.fetch_user(int(user_id))
            # Split long messages
            chunks = [message[i:i+1900] for i in range(0, len(message), 1900)]
            for chunk in chunks:
                await user.send(chunk)
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")
    
    async def _process_missed_tasks(self):
        """Process tasks missed while offline."""
        missed = self.scheduler.load_missed_tasks()
        if missed:
            logger.info(f"Found {len(missed)} missed tasks")
            # Notify about missed tasks
            # TODO: Implement missed task recovery logic
            self.scheduler.clear_missed_tasks()
    
    async def start(self):
        """Start the daemon."""
        logger.info("Starting AI Agent Daemon...")
        
        # Ensure directories exist
        os.makedirs("storage", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        
        # Initialize browser pool
        await self.browser_pool.initialize()
        
        # Check for missed tasks
        await self._process_missed_tasks()
        
        # Start scheduler
        self.scheduler.start()
        
        # Start Discord bridge
        self.running = True
        discord_task = asyncio.create_task(self.bridge.run())
        await self.bridge.wait_for_ready()
        
        logger.info("Agent daemon started successfully!")
        
        # Main loop
        try:
            async for message in self.bridge.listen():
                await self.router.handle(message)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the daemon gracefully."""
        logger.info("Stopping daemon...")
        self.running = False
        
        self.scheduler.shutdown()
        await self.browser_pool.cleanup()
        await self.bridge.stop()
        
        logger.info("Daemon stopped.")


async def main():
    """Main entry point."""
    daemon = AgentDaemon()
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        asyncio.create_task(daemon.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await daemon.start()
    except KeyboardInterrupt:
        await daemon.stop()


if __name__ == "__main__":
    asyncio.run(main())
