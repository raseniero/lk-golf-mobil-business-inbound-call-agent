import asyncio
import json
import logging
import re
import time
from datetime import datetime
from enum import Enum, auto
from typing import Optional, Dict, Any, Set, Iterable
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
import livekit.rtc as rtc
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import openai, silero, deepgram

from utils import load_prompt_markdown, detect_termination_phrase


class CallState(Enum):
    """Represents the possible states of a call."""

    IDLE = auto()  # Initial state before call starts
    RINGING = auto()  # Call is incoming/ringing
    ACTIVE = auto()  # Call is in progress
    TERMINATING = auto()  # Call is being terminated
    ENDED = auto()  # Call has ended
    ERROR = auto()  # Call is in error state


class CallSession:
    """Encapsulates call timing logic for duration tracking."""

    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def start_call(self):
        self.start_time = time.time()
        self.end_time = None

    def end_call(self):
        if self.start_time is not None:
            self.end_time = time.time()

    def get_duration(self) -> Optional[float]:
        if self.start_time is not None and self.end_time is not None:
            return self.end_time - self.start_time
        return None


load_dotenv()

logger = logging.getLogger("listen-and-respond")
logger.setLevel(logging.INFO)


class SimpleAgent(Agent):
    # Default termination phrases (can be overridden in __init__)
    DEFAULT_TERMINATION_PHRASES = {
        "goodbye",
        "end call",
        "that's all",
        "thank you",
        "bye"
    }

    def __init__(self, termination_phrases: Optional[Iterable[str]] = None) -> None:
        # Initialize instance variables
        self.call_session: CallSession = CallSession()
        self.room: Optional[rtc.Room] = None
        self.is_speaking: bool = False
        self.is_listening: bool = False
        self._agent_session: Optional[AgentSession] = None
        self._call_state: CallState = CallState.IDLE
        self._call_metadata: Dict[str, Any] = {}  # Store additional call-related data
        
        # Initialize termination phrases - use defaults if None or empty list is provided
        if termination_phrases is None or not list(termination_phrases):
            self.termination_phrases: Set[str] = set(self.DEFAULT_TERMINATION_PHRASES)
        else:
            self.termination_phrases: Set[str] = set(termination_phrases)

        # Initialize the parent class with required components
        super().__init__(
            instructions=load_prompt_markdown("basic_prompt.md"),
            stt=deepgram.STT(),
            llm=openai.LLM(model="gpt-4o"),
            tts=openai.TTS(),
            vad=silero.VAD.load(),
        )

    def _format_log_message(self, event: str, metadata: Dict[str, Any] = None) -> str:
        """Format a standardized log message for call events.
        
        Args:
            event: The event type (e.g., 'CALL_START', 'PHRASE_DETECTED')
            metadata: Optional metadata dictionary to include in the log
            
        Returns:
            Formatted log message string with consistent structure
        """
        if metadata is None:
            metadata = {}
        
        # Create base log structure
        log_data = {
            "event": event,
            "timestamp": datetime.now().isoformat(),
            "state": self._call_state.name,
            "call_id": getattr(self, '_call_id', None),
        }
        
        # Add call session data if available
        if hasattr(self, 'call_session') and self.call_session:
            if self.call_session.start_time:
                log_data["call_start"] = datetime.fromtimestamp(self.call_session.start_time).isoformat()
            duration = self.call_session.get_duration()
            if duration is not None:
                log_data["duration"] = round(duration, 3)
        
        # Add any additional metadata
        log_data.update(metadata)
        
        # Create readable log message
        base_msg = f"[{event}] state={self._call_state.name}"
        
        # Add key metadata to the readable part
        if "duration" in log_data:
            base_msg += f" duration={log_data['duration']}s"
        if "phrase" in metadata:
            base_msg += f" phrase='{metadata['phrase']}'"
        if "error" in metadata:
            base_msg += f" error='{metadata['error']}'"
        
        # Add structured data as JSON for parsing
        base_msg += f" | {json.dumps(log_data, separators=(',', ':'))}"
        
        return base_msg

    def _log_call_event(self, event: str, metadata: Dict[str, Any] = None):
        """Log a call event with standardized format.
        
        Args:
            event: The event type to log
            metadata: Optional metadata to include
        """
        message = self._format_log_message(event, metadata)
        logger.info(message)

    def _log_call_error(self, error_message: str, exception: Exception = None, metadata: Dict[str, Any] = None):
        """Log a call error with standardized format.
        
        Args:
            error_message: Human-readable error description
            exception: Optional exception object
            metadata: Optional additional metadata
        """
        if metadata is None:
            metadata = {}
        
        metadata["error"] = error_message
        if exception:
            metadata["exception_type"] = type(exception).__name__
            metadata["exception_message"] = str(exception)
        
        message = self._format_log_message("ERROR", metadata)
        logger.error(message, exc_info=exception is not None)

    def _log_call_debug(self, debug_message: str, metadata: Dict[str, Any] = None):
        """Log debug information with standardized format.
        
        Args:
            debug_message: Debug message to log
            metadata: Optional additional metadata
        """
        if metadata is None:
            metadata = {}
        
        metadata["debug_message"] = debug_message
        message = self._format_log_message("DEBUG", metadata)
        logger.debug(message)

    async def on_enter(self):
        """Called when the agent enters a call."""
        await self._set_call_state(CallState.RINGING)

        try:
            self.call_session.start_call()
            self._agent_session = self.session  # Store the session from parent class

            # Log call start event
            self._log_call_event("CALL_START", {
                "start_time": datetime.fromtimestamp(self.call_session.start_time).isoformat()
            })

            # Set initial states
            self.is_speaking = False
            self.is_listening = True  # Start in listening mode

            # Transition to active state
            await self._set_call_state(CallState.ACTIVE)

            # Generate initial greeting if we have a session
            if self._agent_session:
                await self._agent_session.generate_reply()

            return True

        except Exception as e:
            self._log_call_error("Error during call setup", e)
            await self._set_call_state(CallState.ERROR, error=str(e))
            raise  # Re-raise the exception to fail the operation

    async def _on_agent_speaking(self, is_speaking: bool):
        """Handle agent speaking state changes."""
        self.is_speaking = is_speaking
        logger.debug(f"Agent {'started' if is_speaking else 'stopped'} speaking")

    async def _on_agent_listening(self, is_listening: bool):
        """Handle agent listening state changes."""
        self.is_listening = is_listening
        logger.debug(f"Agent is {'now' if is_listening else 'no longer'} listening")

    async def on_disconnect(self):
        """Called when the agent disconnects from the call."""
        if self._call_state == CallState.ENDED:
            return

        await self._set_call_state(CallState.TERMINATING)

        try:
            # Log call duration if we have a start time
            self.call_session.end_call()
            duration = self.call_session.get_duration()
            if duration is not None:
                self._call_metadata["duration"] = duration
                logger.info(f"Call ended. Duration: {duration:.2f} seconds")
            else:
                logger.info("Call ended (no start or end time recorded)")

            # Perform any cleanup
            self._cleanup_call_resources()

        except Exception as e:
            logger.error(f"Error during call termination: {e}", exc_info=True)
            await self._set_call_state(CallState.ERROR, error=str(e))
            raise
        finally:
            if self._call_state != CallState.ERROR:
                await self._set_call_state(CallState.ENDED)

    async def _set_call_state(self, new_state: CallState, **metadata):
        """Safely transition to a new call state with optional metadata.

        Args:
            new_state: The state to transition to
            **metadata: Additional metadata to store with the state change
        """
        if self._call_state == new_state:
            return

        old_state = self._call_state
        self._call_state = new_state

        # Store any metadata with the state
        if metadata:
            self._call_metadata.update(metadata)

        logger.info(
            f"Call state changed: {old_state.name} -> {new_state.name}"
            + (f" | {metadata}" if metadata else "")
        )

    def _cleanup_call_resources(self):
        """Clean up any resources associated with the call."""
        # Reset states
        self.is_speaking = False
        self.is_listening = False

        # Clear any call-specific data
        self._call_metadata.clear()

    @property
    def call_state(self) -> CallState:
        """Get the current call state."""
        return self._call_state

    @property
    def call_metadata(self) -> Dict[str, Any]:
        """Get a copy of the call metadata."""
        return self._call_metadata.copy()

    async def _on_user_input(self, text: str) -> None:
        """Process user input and check for termination phrases.
        
        This is an alias for on_user_input for backward compatibility with tests.
        """
        await self.on_user_input(text)
        
    async def on_user_input(self, text: str) -> None:
        """Process user input and check for termination phrases.
        
        This method is called when user input is received. It checks if the input
        contains any termination phrases and handles the call termination flow if needed.
        
        Args:
            text: The user input text to process. Can be None or empty.
        """
        if not text or not text.strip():
            # Skip empty or whitespace-only input
            return
            
        self._log_call_debug("Processing user input", {"input_text": text})
        
        # Use the utility function to detect termination phrases
        detected_phrase = detect_termination_phrase(text, self.termination_phrases)
        
        if detected_phrase:
            self._log_call_event("PHRASE_DETECTED", {
                "phrase": detected_phrase,
                "input_text": text
            })
            await self._handle_termination_phrase(detected_phrase)
            return
        
        self._log_call_debug("No termination phrase found", {"input_text": text})
        
        # For non-matching input, always call generate_reply if we have a session
        # and we're not already in the process of terminating
        if self._agent_session and self._call_state != CallState.TERMINATING:
            try:
                self._log_call_debug("Generating reply for normal input", {"input_text": text})
                await self._agent_session.generate_reply()
            except Exception as e:
                self._log_call_error("Error generating reply", e, {"input_text": text})
        else:
            self._log_call_debug("Skipping generate_reply - no active session or call is terminating")
                
    async def _handle_termination_phrase(self, phrase: str) -> None:
        """Handle the detection of a termination phrase.
        
        Args:
            phrase: The termination phrase that was detected.
        """
        try:
            self._log_call_event("TERMINATION_INITIATED", {"phrase": phrase})
            
            # Call the termination handler
            await self.terminate_call()
            
        except Exception as e:
            self._log_call_error("Error during call termination", e, {"phrase": phrase})
            # Don't re-raise to allow normal processing to continue if termination fails
            
    async def terminate_call(self) -> None:
        """Handle call termination.
        
        This method performs the necessary cleanup and state transitions
        when a call is terminated by the user.
        """
        if self._call_state == CallState.ENDED:
            self._log_call_debug("Call already ended, ignoring termination request")
            return
            
        self._log_call_event("CALL_TERMINATION", {"action": "initiating"})
        
        # Set call state to TERMINATING
        await self._set_call_state(CallState.TERMINATING)
        
        try:
            # End the call session
            self.call_session.end_call()
            
            # Log call duration if available
            duration = self.call_session.get_duration()
            if duration is not None:
                self._call_metadata["duration"] = duration
                self._log_call_event("CALL_DURATION", {"duration": duration})
                
            # Clean up call resources
            self._cleanup_call_resources()
            
            # Set final call state
            await self._set_call_state(CallState.ENDED)
            self._log_call_event("CALL_TERMINATED", {"status": "success"})
            
        except Exception as e:
            self._log_call_error("Error during call termination", e)
            await self._set_call_state(CallState.ERROR, error=str(e))
            raise


async def setup_room_handlers(room: rtc.Room, agent: SimpleAgent):
    """Set up room-level event handlers."""

    @room.on("track_published")
    def on_track_published(publication, participant):
        logger.info(f"Track published by {participant.identity}")

        # Only set up the ended handler if the track is available
        if publication.track is not None:

            @publication.track.on("ended")
            def on_ended():
                logger.info(f"Track ended from {participant.identity}")

    @room.on("track_subscribed")
    def on_track_subscribed(track, *_):
        logger.info(f"Track subscribed: {track.sid}")

    @room.on("disconnected")
    def on_disconnected():
        logger.info("Disconnected from room")
        agent.room = None


async def entrypoint(ctx: JobContext):
    # Connect to the LiveKit room
    await ctx.connect()

    try:
        # Create agent instance
        agent = SimpleAgent()
        agent.room = ctx.room

        # Set up room handlers
        await setup_room_handlers(ctx.room, agent)

        # Create and start agent session
        session = AgentSession()
        await session.start(agent=agent, room=ctx.room)

        # Keep the agent running until disconnected
        while True:
            await asyncio.sleep(1)
            if not agent.room:
                break

    except Exception as e:
        logger.error(f"Error in agent entrypoint: {e}", exc_info=True)
        raise
    finally:
        logger.info("Agent session ended")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
