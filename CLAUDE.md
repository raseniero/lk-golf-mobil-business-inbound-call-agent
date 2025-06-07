# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a LiveKit-based voice agent project for golf mobile business inbound call handling. The project is primarily Python-based using the LiveKit agents framework, with some Node.js dependencies for additional tooling.

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
- `agent.py`: Main SimpleAgent class extending LiveKit's Agent
- `utils.py`: Prompt loading utilities for YAML and Markdown files
- `prompts/`: Directory containing agent instruction prompts

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

### Code Formatting
```bash
.venv/bin/black .    # Format Python code using Black
```

## Environment Setup

Create a `.env` file with required API keys:
- `OPENAI_API_KEY`: For LLM and TTS services
- `DEEPGRAM_API_KEY`: For STT services
- `LIVEKIT_URL` and `LIVEKIT_API_KEY`: For LiveKit server connection