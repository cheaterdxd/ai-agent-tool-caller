# AI Agent Tool Caller

An autonomous AI agent that schedules and executes tasks via natural language commands through Discord.

## Features

- **Natural Language Processing**: Parse commands like "search articles about Thales start at 2pm"
- **Task Scheduling**: APScheduler with SQLite backend for persistent task storage
- **Web Search**: Automated Google search using browser-use with rate limiting
- **RAG System**: LEANN integration for knowledge storage and retrieval
- **Discord Integration**: Real-time chat interface via Discord bridge module
- **Missed Task Recovery**: Automatically handles tasks scheduled while offline
- **Rate Limiting**: Prevents Google blocks (30s delay, 50 searches/day)
- **Local-First**: Uses Ollama for LLM, fully private

## Architecture

```
ai-agent-tool-caller/
├── daemon.py              # Main daemon process
├── cli.py                 # CLI interface
├── agent/                 # Core agent logic
│   ├── core.py           # Main orchestrator
│   ├── parser.py         # Ollama intent parser
│   ├── scheduler.py      # Task scheduler
│   └── task_manager.py   # Task CRUD operations
├── tools/                 # Tool implementations
│   ├── search.py         # browser-use wrapper
│   ├── browser_pool.py   # Multi-browser manager
│   └── rag.py           # LEANN RAG integration
├── external/             # Git submodules
│   ├── discord-bridge/   # Your Discord bridge
│   └── LEANN/           # RAG system
└── storage/              # Data storage
    ├── scheduler.db      # SQLite database
    └── missed_tasks.json # Missed tasks queue
```

## Prerequisites

- Python 3.11+
- Ollama installed locally
- Discord bot token
- Git

## Installation

### 1. Clone the repository

```bash
git clone --recursive https://github.com/cheaterdxd/ai-agent-tool-caller.git
cd ai-agent-tool-caller
```

### 2. Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
# Install submodules
pip install -e external/discord-bridge
pip install -e external/LEANN

# Install main dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 4. Configure

```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your Discord token and settings
```

### 5. Setup Ollama models

```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

## Usage

### Start the daemon

```bash
python daemon.py
```

Or use CLI:
```bash
python cli.py start    # Start daemon in background
python cli.py stop     # Stop daemon
python cli.py status   # Check daemon status
```

### Discord Commands

Once the bot is running, use these commands in Discord:

```
!tasks                          # List all scheduled tasks
!cancel <task_name>            # Cancel a task by name
!help                          # Show available commands
```

### Natural Language Commands

The agent understands natural language:

```
"search articles about Thales start at 2pm"
"add this note 'Nhi likes cat' to my RAG system"
"search AI news every morning at 9am"
"find Python tutorials tomorrow afternoon"
```

## Configuration

Edit `config.yaml`:

```yaml
discord:
  token: "your_discord_bot_token_here"
  command_prefix: "!"

ollama:
  url: "http://localhost:11434"
  intent_model: "qwen2.5:7b"
  embedding_model: "nomic-embed-text"

browser:
  max_instances: 3
  rate_limit_delay: 30
  max_searches_per_day: 50

retention:
  task_history_days: 30
```

## How It Works

1. **Discord Message** → User sends command via Discord
2. **Intent Parsing** → Ollama LLM parses natural language into structured intent
3. **Task Scheduling** → If scheduled for later, task stored in SQLite with APScheduler
4. **Execution** → At scheduled time, browser-use performs Google search
5. **RAG Storage** → Results added to LEANN vector database
6. **Notification** → Discord DM sent with results

## Rate Limiting

To avoid Google blocks:
- 30 second delay between searches
- Maximum 50 searches per day
- 3 concurrent browser instances maximum
- Automatic retry with exponential backoff

## Development

### Run tests
```bash
pytest tests/ -v
```

### Lint code
```bash
ruff check agent/ tools/
ruff format agent/ tools/
```

## License

MIT License

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
