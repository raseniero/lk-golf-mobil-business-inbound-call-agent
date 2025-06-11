# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a LiveKit-based voice agent project for golf mobile business inbound call handling. The project is primarily Python-based using the LiveKit agents framework, with Node.js dependencies for Task Master AI project management tooling.

## Architecture

The main agent is implemented in `agent.py` using:
- **LiveKit Agents**: Framework for real-time voice interactions
- **OpenAI**: LLM (GPT-4o) and TTS services
- **Deepgram**: Speech-to-text (STT) service
- **Silero**: Voice activity detection (VAD)

The agent follows a simple pattern:
1. Listens for user speech via Deepgram STT
2. Processes input through OpenAI GPT-4o
3. Responds with synthesized speech via OpenAI TTS
4. Uses Silero VAD for turn-taking detection

**Key Components:**
- `agent.py`: Main SimpleAgent class with CallState management and CallSession tracking
- `utils.py`: Prompt loading utilities for YAML and Markdown files
- `prompts/`: Directory containing agent instruction prompts
- `tests/`: Pytest-based test suite for call state management and termination features
- `rules/`: AI assistant rule definitions for PRD creation and task processing

**Call State Management:**
- CallState enum defines: IDLE, RINGING, ACTIVE, TERMINATING, ENDED, ERROR states
- CallSession class tracks call timing with start_call(), end_call(), get_duration() methods  
- SimpleAgent manages state transitions with `_set_call_state()` and proper error handling
- All state changes are logged with metadata persistence

**Implementation Details:**
- The SimpleAgent initializes with all services in constructor (STT, LLM, TTS, VAD)
- Agent instructions are loaded from `prompts/basic_prompt.md` via `load_prompt_markdown()` 
- The agent automatically generates a reply on session enter via `on_enter()`
- Uses LiveKit's JobContext pattern with `entrypoint()` function
- All ML model downloads and setup happen through Task commands

## Development Commands

Use Task (Taskfile.yaml) for all development operations:

```bash
# Set up Python environment
task venv-setup
task pip-install-requirements.txt

# Run the agent in development mode
task agent-run

# Download required ML models
task agent-download-files

# Clean up environment
task venv-clean
```

For Node.js dependencies:
```bash
npm install    # Install Node.js tooling dependencies
```

### Testing
```bash
# Run tests using pytest
.venv/bin/python -m pytest tests/

# Run specific test file
.venv/bin/python -m pytest tests/test_call_state.py

# Run tests with coverage
.venv/bin/python -m pytest tests/ --cov=. --cov-report=html
```

### Code Formatting
```bash
.venv/bin/black .    # Format Python code using Black
```

## Task Master AI Integration

This project uses Task Master AI for project management and task tracking:

```bash
# Initialize Task Master AI project
npx task-master-ai init

# Parse PRD documents to generate tasks
npx task-master-ai parse-prd

# View current tasks
npx task-master-ai get-tasks

# Get next task to work on
npx task-master-ai next-task
```

**Project Structure for Task Master:**
- `tasks/`: Contains generated task files and PRD-based task lists
- `specs/`: Project specifications and requirements
- `rules/`: Contains AI assistant rules for PRD creation (`rc-create-prd.md`) and task processing (`rc-generate-tasks.md`, `rc-process-task-list.md`)

## Environment Setup

Create a `.env` file with required API keys:
- `OPENAI_API_KEY`: For LLM and TTS services
- `DEEPGRAM_API_KEY`: For STT services
- `LIVEKIT_URL` and `LIVEKIT_API_KEY`: For LiveKit server connection