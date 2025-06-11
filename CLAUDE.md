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
- Automatic termination phrase detection triggers state transitions
- Configurable termination phrases (default: "goodbye", "bye", "thank you", "end call", "that's all")

**Error Handling and Recovery:**
- Comprehensive error handling in call termination with fallback mechanisms
- Graceful degradation: partial failures result in warnings while maintaining successful termination
- Critical failures trigger ERROR state with detailed error context
- Emergency cleanup procedures for catastrophic failures
- Timeout protection for room disconnection operations (5-second timeout)
- Structured error logging with stack traces for debugging
- Fallback room cleanup when graceful disconnection fails
- Three-tier cleanup system: _cleanup_call_resources(), _force_room_cleanup(), _emergency_resource_cleanup()
- Catastrophic failure handler as last resort with _catastrophic_failure_cleanup()

**Implementation Details:**
- The SimpleAgent initializes with all services in constructor (STT, LLM, TTS, VAD)
- Agent instructions are loaded from `prompts/basic_prompt.md` via `load_prompt_markdown()` 
- The agent automatically generates a reply on session enter via `on_enter()`
- Uses LiveKit's JobContext pattern with `entrypoint()` function
- All ML model downloads and setup happen through Task commands
- Phrase detection uses optimized regex patterns with caching for performance
- Call termination includes immediate "Goodbye!" response before cleanup
- Comprehensive event logging with structured JSON format for analytics

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

# Run performance tests
.venv/bin/python -m pytest tests/test_performance_*.py -v

# Run integration tests
.venv/bin/python -m pytest tests/test_integration_*.py -v
```

**Test Coverage:**
- 20+ test files with 150+ test cases
- Unit tests for all core functions
- Integration tests for complete call flows
- Performance tests for concurrent calls and stress scenarios
- Error handling validation tests
- Comprehensive edge case coverage

### Code Formatting
```bash
.venv/bin/black .    # Format Python code using Black
```

### Logging Configuration

Configure logging verbosity using the `LOG_LEVEL` environment variable:

```bash
# Debug mode (verbose logging)
LOG_LEVEL=DEBUG task agent-run

# Production mode (minimal logging)  
LOG_LEVEL=WARNING task agent-run

# Default (balanced logging)
LOG_LEVEL=INFO task agent-run
```

Available levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

The agent uses conditional debug logging for performance optimization in high-frequency operations like user input processing.

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
- `LOG_LEVEL`: Optional logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) - defaults to INFO