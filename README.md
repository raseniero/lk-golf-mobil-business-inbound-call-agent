# Golf Mobile Business Inbound Call Agent

A LiveKit-based voice agent designed to handle inbound calls for golf mobile businesses. This intelligent voice assistant can interact with callers in real-time, providing information and assistance for golf-related inquiries.

## Features

- **Real-time Voice Interaction**: Seamless conversation flow with natural turn-taking
- **Advanced Speech Processing**: High-quality speech-to-text and text-to-speech
- **Intelligent Responses**: Powered by OpenAI GPT-4o for contextual understanding
- **Golf Business Focused**: Specialized prompts and responses for golf mobile services
- **LiveKit Integration**: Built on LiveKit's robust real-time communication platform
- **Call Termination Detection**: Automatically detects and responds to termination phrases
- **Call State Management**: Comprehensive state tracking (IDLE, RINGING, ACTIVE, TERMINATING, ENDED, ERROR)
- **Call Duration Tracking**: Detailed call timing and duration analytics
- **Error Recovery**: Robust error handling with graceful degradation and fallback mechanisms
- **Performance Optimized**: Handles multiple concurrent calls efficiently

## Architecture

The agent uses a modern tech stack optimized for voice interactions:

- **LiveKit Agents**: Framework for real-time voice interactions
- **OpenAI GPT-4o**: Language model for understanding and generating responses
- **OpenAI TTS**: Text-to-speech synthesis for natural voice output
- **Deepgram**: Speech-to-text conversion for accurate transcription
- **Silero VAD**: Voice activity detection for smooth conversation flow

## Prerequisites

- Python 3.8+
- Node.js 16+ (for additional tooling)
- Task (task runner) - [Install Task](https://taskfile.dev/installation/)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd lk-golf-mobil-business-inbound-call-agent
```

### 2. Set Up Python Environment

```bash
# Create and activate virtual environment
task venv-setup

# Install Python dependencies
task pip-install-requirements.txt
```

### 3. Install Node.js Dependencies

```bash
npm install
```

### 4. Download Required ML Models

```bash
task agent-download-files
```

### 5. Environment Configuration

Create a `.env` file in the project root with the following API keys:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Deepgram Configuration
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# LiveKit Configuration
LIVEKIT_URL=your_livekit_server_url
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

# Logging Configuration (optional)
LOG_LEVEL=INFO  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## Usage

### Running the Agent

Start the voice agent in development mode:

```bash
task agent-run
```

The agent will:
1. Connect to the LiveKit server
2. Wait for incoming calls
3. Automatically greet callers
4. Handle voice interactions based on configured prompts

### Development Commands

```bash
# Set up development environment
task venv-setup

# Install dependencies
task pip-install-requirements.txt

# Run the agent
task agent-run

# Download ML models
task agent-download-files

# Clean environment
task venv-clean

# Format code
.venv/bin/black .

# Run tests
.venv/bin/python -m pytest tests/

# Run specific test file
.venv/bin/python -m pytest tests/test_call_termination.py -v

# Run tests with coverage
.venv/bin/python -m pytest tests/ --cov=. --cov-report=html
```

## Configuration

### Agent Prompts

The agent's behavior is controlled by prompts in the `prompts/` directory:

- `prompts/basic_prompt.md`: Main instruction set for the agent

To modify the agent's responses or add new capabilities, edit the relevant prompt files.

### Call Termination Configuration

The agent recognizes these default termination phrases:
- "goodbye"
- "bye"
- "thank you"
- "end call"
- "that's all"

To customize termination phrases, modify the `DEFAULT_TERMINATION_PHRASES` set in `agent.py`.

### Logging Configuration

Set the `LOG_LEVEL` environment variable to control logging verbosity:
- `DEBUG`: Detailed debugging information
- `INFO`: General informational messages (default)
- `WARNING`: Warning messages only
- `ERROR`: Error messages only
- `CRITICAL`: Critical issues only

### Project Structure

```
├── agent.py              # Main SimpleAgent implementation with call state management
├── utils.py              # Utilities for prompt loading and phrase detection
├── prompts/              # Agent instruction prompts
│   └── basic_prompt.md   # Primary agent instructions
├── tests/                # Comprehensive test suite
│   ├── test_call_termination.py
│   ├── test_error_handling.py
│   ├── test_performance_*.py
│   └── ... (20+ test files)
├── Taskfile.yaml         # Development task definitions
├── requirements.txt      # Python dependencies
├── package.json          # Node.js dependencies
├── CLAUDE.md            # AI assistant instructions
└── .env                 # Environment variables (create this)
```

## How It Works

1. **Initialization**: Agent starts and connects to LiveKit server
2. **Call Handling**: When a caller connects, the agent automatically initiates conversation
3. **Speech Processing**: 
   - Deepgram converts caller speech to text
   - GPT-4o processes the text and generates appropriate responses
   - OpenAI TTS converts responses back to speech
4. **Voice Activity Detection**: Silero VAD manages conversation flow and turn-taking
5. **Termination Detection**: Agent monitors for termination phrases like "goodbye", "thank you", "bye"
6. **Response Delivery**: Synthesized speech is delivered to the caller
7. **Call Cleanup**: Proper resource cleanup and state management on call termination

## Deployment

### Local Development

Use the provided Task commands for local development and testing.

### Production Deployment

1. Ensure all environment variables are properly configured
2. Set up LiveKit server infrastructure
3. Deploy the agent with appropriate scaling configuration
4. Monitor agent performance and conversation quality

## API Keys Setup

You'll need to obtain API keys from:

- **OpenAI**: [OpenAI API](https://platform.openai.com/)
- **Deepgram**: [Deepgram Console](https://console.deepgram.com/)
- **LiveKit**: [LiveKit Cloud](https://cloud.livekit.io/) or self-hosted instance

## Contributing

1. Follow the existing code style (use Black for Python formatting)
2. Test changes locally before submitting
3. Update prompts in the `prompts/` directory for behavioral changes
4. Ensure all dependencies are properly documented

## Troubleshooting

### Common Issues

1. **Missing API Keys**: Ensure all required environment variables are set in `.env`
2. **Model Download Failures**: Run `task agent-download-files` to download required ML models
3. **Audio Issues**: Check LiveKit server connectivity and audio device permissions
4. **Dependencies**: Ensure both Python and Node.js dependencies are installed

### Debug Mode

Enable verbose logging by setting the LOG_LEVEL environment variable:

```bash
LOG_LEVEL=DEBUG task agent-run
```

### Testing

The project includes a comprehensive test suite with over 150 tests covering:

- Call state management
- Termination phrase detection
- Error handling and recovery
- Performance and concurrency
- Integration scenarios

Run tests with:

```bash
# All tests
.venv/bin/python -m pytest tests/

# Specific test category
.venv/bin/python -m pytest tests/test_performance_*.py -v

# With coverage report
.venv/bin/python -m pytest tests/ --cov=. --cov-report=html
```

## License

[Add appropriate license information]

## Support

[Add support contact information or issue reporting guidelines]