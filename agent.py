import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Optional, Dict, Any, Set, Iterable
import traceback
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
    """Encapsulates call timing logic for duration tracking with enhanced calculations."""

    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def start_call(self):
        """Start tracking call duration."""
        self.start_time = time.time()
        self.end_time = None

    def end_call(self):
        """End call duration tracking."""
        if self.start_time is not None:
            self.end_time = time.time()

    def reset(self):
        """Reset the call session for reuse."""
        self.start_time = None
        self.end_time = None

    def get_duration(self) -> Optional[float]:
        """Get call duration in seconds.

        Returns:
            Duration in seconds as float, or None if start/end times are not available.
        """
        if self.start_time is not None and self.end_time is not None:
            return self.end_time - self.start_time
        return None

    def get_duration_minutes(self) -> Optional[float]:
        """Get call duration in minutes.

        Returns:
            Duration in minutes as float, or None if duration is not available.
        """
        duration = self.get_duration()
        if duration is not None:
            return duration / 60.0
        return None

    def get_duration_formatted(self) -> str:
        """Get human-readable formatted duration string.

        Returns:
            Formatted duration string like "2 minutes 30 seconds" or "unknown".
        """
        duration = self.get_duration()
        if duration is None:
            return "unknown"

        if duration < 0:
            return "invalid duration"

        # Convert to total seconds
        total_seconds = int(duration)

        # Calculate hours, minutes, seconds
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        # Handle fractional seconds for short durations
        if duration < 60:
            return f"{duration:.1f} seconds"

        # Build formatted string
        parts = []
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds > 0 or not parts:  # Always show seconds if no other parts
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

        return " ".join(parts)

    def is_short_call(self) -> bool:
        """Check if this is a short call (< 30 seconds).

        Returns:
            True if call duration is less than 30 seconds, False otherwise.
        """
        duration = self.get_duration()
        return duration is not None and duration < 30.0

    def is_medium_call(self) -> bool:
        """Check if this is a medium call (30 seconds - 5 minutes).

        Returns:
            True if call duration is between 30 seconds and 5 minutes, False otherwise.
        """
        duration = self.get_duration()
        return duration is not None and 30.0 <= duration < 300.0

    def is_long_call(self) -> bool:
        """Check if this is a long call (>= 5 minutes).

        Returns:
            True if call duration is 5 minutes or more, False otherwise.
        """
        duration = self.get_duration()
        return duration is not None and duration >= 300.0

    def get_call_classification(self) -> str:
        """Get the classification of the call based on duration.

        Returns:
            Classification string: 'short', 'medium', 'long', or 'unknown'.
        """
        if self.is_short_call():
            return "short"
        elif self.is_medium_call():
            return "medium"
        elif self.is_long_call():
            return "long"
        else:
            return "unknown"

    def get_duration_export_data(self) -> Dict[str, Any]:
        """Get comprehensive duration data for export/analytics.

        Returns:
            Dictionary containing all duration metrics and metadata.
        """
        duration = self.get_duration()
        duration_minutes = self.get_duration_minutes()

        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": duration,
            "duration_minutes": duration_minutes,
            "duration_formatted": self.get_duration_formatted(),
            "call_classification": self.get_call_classification(),
        }


load_dotenv()


def configure_logging():
    """Configure logging with appropriate formatting and handlers based on environment.

    Returns:
        logging.Logger: Configured logger instance for the application.
    """
    # Get log level from environment variable, default to INFO
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Valid log levels supported by Python logging
    VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

    # Validate log level, default to INFO if invalid
    if log_level not in VALID_LOG_LEVELS:
        log_level = "INFO"

    # Get or create logger
    logger = logging.getLogger("listen-and-respond")
    logger.setLevel(getattr(logging, log_level))

    # Avoid duplicate handlers if already configured
    if not logger.handlers:
        # Create console handler with formatting
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Configure the application logger
logger = configure_logging()


class SimpleAgent(Agent):
    # Default termination phrases (can be overridden in __init__)
    DEFAULT_TERMINATION_PHRASES = {
        "goodbye",
        "end call",
        "that's all",
        "thank you",
        "bye",
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

    def get_formatted_timestamp(self) -> str:
        """Get current timestamp in ISO 8601 format with timezone.

        Returns:
            Timestamp string in ISO 8601 format with UTC timezone (e.g., '2025-06-11T14:30:45.123456Z')
        """
        return datetime.now(timezone.utc).isoformat()

    def _log_call_start_timestamp(self):
        """Log call start with formatted timestamp."""
        timestamp = self.get_formatted_timestamp()
        logger.info(f"Call started at {timestamp}")
        return timestamp

    def _log_call_end_timestamp(self):
        """Log call end with formatted timestamp."""
        timestamp = self.get_formatted_timestamp()
        logger.info(f"Call ended at {timestamp}")
        return timestamp

    def _log_call_lifecycle_summary(self):
        """Log a summary of the call lifecycle with start/end timestamps and duration."""
        if (
            not hasattr(self.call_session, "start_time")
            or self.call_session.start_time is None
        ):
            logger.warning("Cannot log call lifecycle: no start time recorded")
            return

        # Get start timestamp from stored time
        start_timestamp = datetime.fromtimestamp(
            self.call_session.start_time, timezone.utc
        ).isoformat()

        # Get end timestamp
        end_timestamp = self.get_formatted_timestamp()

        # Calculate duration
        duration = self.call_session.get_duration()
        duration_str = f"{duration:.3f} seconds" if duration is not None else "unknown"

        logger.info(
            f"Call lifecycle summary: started at {start_timestamp}, "
            f"ended at {end_timestamp}, duration: {duration_str}"
        )

    def _log_call_duration_summary(self):
        """Log comprehensive call duration summary with enhanced formatting and analytics.

        This method logs detailed duration information including:
        - Raw duration in seconds
        - Human-readable formatted duration
        - Call classification (short/medium/long)
        - Duration statistics for analytics
        """
        duration_data = self.call_session.get_duration_export_data()

        if duration_data["duration_seconds"] is None:
            logger.warning("Cannot log duration summary: no valid duration data")
            return

        # Log structured duration information
        self._log_call_event(
            "CALL_DURATION_SUMMARY",
            {
                "duration_seconds": f"{duration_data['duration_seconds']:.3f}",
                "duration_formatted": duration_data["duration_formatted"],
                "call_classification": duration_data["call_classification"],
                "duration_minutes": (
                    f"{duration_data['duration_minutes']:.2f}"
                    if duration_data["duration_minutes"]
                    else "unknown"
                ),
            },
        )

        # Log human-readable summary
        logger.info(
            f"Call duration summary: {duration_data['duration_formatted']} "
            f"({duration_data['duration_seconds']:.3f} seconds) - "
            f"classified as {duration_data['call_classification']} call"
        )

    def _log_call_event(self, event_type: str, data: Dict[str, Any]):
        """Log call events with structured data.

        Args:
            event_type: The type of event being logged (e.g., 'PHRASE_DETECTED', 'TERMINATION_INITIATED')
            data: Dictionary containing event-specific data to be logged
        """
        timestamp = self.get_formatted_timestamp()

        # Create structured log message with expected fields
        data_str = ", ".join([f"{k}='{v}'" for k, v in (data or {}).items()])
        log_message = (
            f"event={event_type}, timestamp={timestamp}, state={self._call_state.name}"
        )

        if data_str:
            log_message += f", {data_str}"

        logger.info(log_message)

    def _log_call_debug(self, message: str, data: Optional[Dict[str, Any]] = None):
        """Log debug information with optional structured data.

        Args:
            message: The debug message to log
            data: Optional dictionary containing additional debug data
        """
        timestamp = self.get_formatted_timestamp()

        log_message = f"[{timestamp}] CALL_DEBUG: {message}"

        if data:
            data_str = ", ".join([f"{k}='{v}'" for k, v in data.items()])
            log_message += f" | {data_str}"

        logger.debug(log_message)

    def _log_call_error(
        self, message: str, error: Exception, data: Optional[Dict[str, Any]] = None
    ):
        """Log errors with structured data and exception info.

        Args:
            message: The error message to log
            error: The exception that occurred
            data: Optional dictionary containing additional error context
        """
        timestamp = self.get_formatted_timestamp()

        log_message = f"[{timestamp}] CALL_ERROR: {message} | error='{str(error)}'"

        if data:
            data_str = ", ".join([f"{k}='{v}'" for k, v in data.items()])
            log_message += f" | {data_str}"

        # Log with full exception info
        logger.error(log_message, exc_info=True)

    async def on_enter(self):
        """Called when the agent enters a call."""
        await self._set_call_state(CallState.RINGING)

        try:
            self.call_session.start_call()
            self._agent_session = self.session  # Store the session from parent class

            # Log call start with timestamp
            self._log_call_start_timestamp()

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

            # Log call end with timestamp
            self._log_call_end_timestamp()

            duration = self.call_session.get_duration()
            if duration is not None:
                self._call_metadata["duration"] = duration
                logger.info(f"Call ended. Duration: {duration:.2f} seconds")
            else:
                logger.info("Call ended (no start or end time recorded)")

            # Log comprehensive call lifecycle summary
            self._log_call_lifecycle_summary()

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

        # Use conditional debug logging for performance optimization
        if logger.isEnabledFor(logging.DEBUG):
            self._log_call_debug("Processing user input", {"input_text": text})

        # Use the utility function to detect termination phrases
        detected_phrase = detect_termination_phrase(text, self.termination_phrases)

        if detected_phrase:
            self._log_call_event(
                "PHRASE_DETECTED", {"phrase": detected_phrase, "input_text": text}
            )
            await self._handle_termination_phrase(detected_phrase)
            return

        if logger.isEnabledFor(logging.DEBUG):
            self._log_call_debug("No termination phrase found", {"input_text": text})

        # For non-matching input, always call generate_reply if we have a session
        # and we're not already in the process of terminating
        if self._agent_session and self._call_state != CallState.TERMINATING:
            try:
                if logger.isEnabledFor(logging.DEBUG):
                    self._log_call_debug(
                        "Generating reply for normal input", {"input_text": text}
                    )
                await self._agent_session.generate_reply()
            except Exception as e:
                self._log_call_error("Error generating reply", e, {"input_text": text})
        else:
            if logger.isEnabledFor(logging.DEBUG):
                self._log_call_debug(
                    "Skipping generate_reply - no active session or call is terminating"
                )

    async def _handle_termination_phrase(self, phrase: str) -> None:
        """Handle the detection of a termination phrase.

        This method provides immediate acknowledgment of the termination request
        before proceeding with the actual call termination.

        Args:
            phrase: The termination phrase that was detected.
        """
        try:
            self._log_call_event("TERMINATION_INITIATED", {"phrase": phrase})

            # Provide immediate acknowledgment response
            await self._send_immediate_termination_response(phrase)

            # Call the termination handler
            await self.terminate_call()

        except Exception as e:
            self._log_call_error("Error during call termination", e, {"phrase": phrase})
            # Don't re-raise to allow normal processing to continue if termination fails

    async def _send_immediate_termination_response(self, detected_phrase: str) -> None:
        """Send an immediate contextual response to a termination phrase.

        This method generates and sends a quick acknowledgment message based on
        the specific termination phrase that was detected, providing immediate
        feedback to the user that their request was understood.

        Args:
            detected_phrase: The specific termination phrase that was detected.
        """
        if not self._agent_session:
            logger.debug("No active session for immediate response")
            return

        try:
            # Generate contextual response based on the detected phrase
            response = self._generate_contextual_response(detected_phrase)

            # Send immediate response using the session's say method
            await self._agent_session.say(response)
            logger.debug(f"Sent immediate termination response: '{response}'")

        except Exception as e:
            logger.warning(f"Error sending immediate termination response: {e}")
            # Don't let response errors block termination

    def _generate_contextual_response(self, detected_phrase: str) -> str:
        """Generate a contextual response based on the detected termination phrase.

        Args:
            detected_phrase: The termination phrase that was detected.

        Returns:
            A contextual response string.
        """
        phrase_lower = detected_phrase.lower()

        # Map termination phrases to appropriate responses
        response_map = {
            "goodbye": "Goodbye! It was nice talking with you.",
            "bye": "Bye! Take care.",
            "thank you": "You're welcome! Have a great day.",
            "end call": "Ending the call now. Goodbye!",
            "that's all": "Understood. Thank you for the conversation!",
        }

        # Look for exact match first
        if phrase_lower in response_map:
            return response_map[phrase_lower]

        # Look for partial matches
        for phrase, response in response_map.items():
            if phrase in phrase_lower:
                return response

        # Default response if no specific match found
        return "Thank you! Goodbye."

    async def terminate_call(self) -> None:
        """Public interface for call termination.

        This method handles user-initiated call termination with proper
        error handling and logging.
        """
        try:
            await self._terminate_call()
        except Exception as e:
            logger.error(f"Error during call termination: {e}", exc_info=True)
            # Don't re-raise to allow graceful degradation

    async def _terminate_call(self) -> None:
        """Core internal call termination logic with comprehensive error handling.

        This method performs the actual cleanup and state transitions
        when a call is terminated. It handles:
        - State validation and transitions
        - Call session timing
        - Resource cleanup
        - Room disconnection
        - Error recovery and fallback mechanisms
        - Timeout protection
        """
        if self._call_state == CallState.ENDED:
            logger.warning("Call already ended, ignoring termination request")
            return

        self._log_call_event("CALL_TERMINATION", {"action": "initiating"})

        # Set call state to TERMINATING
        await self._set_call_state(CallState.TERMINATING)

        # Track individual operation failures for comprehensive error reporting
        operation_errors = {}
        critical_failure = False

        try:
            # Step 1: End the call session timing with error handling
            try:
                self.call_session.end_call()
                self._log_call_event("TERMINATION_STEP", {"step": "session_ended", "status": "success"})
            except Exception as session_error:
                operation_errors["session_end"] = str(session_error)
                self._log_call_error("Failed to end call session", session_error)
                # Continue with termination despite session timing failure

            # Step 2: Log call end timestamp with error handling
            try:
                self._log_call_end_timestamp()
                self._log_call_event("TERMINATION_STEP", {"step": "timestamp_logged", "status": "success"})
            except Exception as timestamp_error:
                operation_errors["timestamp_logging"] = str(timestamp_error)
                logger.warning(f"Failed to log end timestamp: {timestamp_error}")
                # Continue with termination despite logging failure

            # Step 3: Enhanced call duration summary with error handling
            try:
                duration = self.call_session.get_duration()
                if duration is not None:
                    self._call_metadata["duration"] = duration
                    self._log_call_duration_summary()
                    self._log_call_event("TERMINATION_STEP", {"step": "duration_logged", "status": "success"})
                else:
                    logger.warning("No duration data available for call termination logging")
                    self._log_call_event("TERMINATION_STEP", {"step": "duration_logged", "status": "no_data"})
            except Exception as duration_error:
                operation_errors["duration_logging"] = str(duration_error)
                logger.warning(f"Failed to log call duration: {duration_error}")
                # Continue with termination despite duration logging failure

            # Step 4: Log comprehensive call lifecycle summary with error handling
            try:
                self._log_call_lifecycle_summary()
                self._log_call_event("TERMINATION_STEP", {"step": "lifecycle_logged", "status": "success"})
            except Exception as lifecycle_error:
                operation_errors["lifecycle_logging"] = str(lifecycle_error)
                logger.warning(f"Failed to log call lifecycle summary: {lifecycle_error}")
                # Continue with termination despite lifecycle logging failure

            # Step 5: Disconnect from LiveKit room with enhanced error handling and timeout
            try:
                if hasattr(self, "room") and self.room:
                    # Log participants before disconnection
                    if hasattr(self.room, "remote_participants"):
                        participant_count = len(self.room.remote_participants)
                        if participant_count > 0:
                            logger.info(f"Disconnecting from room with {participant_count} other participants")
                        else:
                            logger.info("Disconnecting from room (no other participants)")
                    
                    # Attempt graceful disconnection with timeout
                    await asyncio.wait_for(self.room.disconnect(), timeout=5.0)
                    logger.info("Successfully disconnected from LiveKit room")
                    
                    # Clear room reference
                    self.room = None
                    logger.debug("Cleared room reference")
                else:
                    logger.debug("No room to disconnect from")
                
                self._log_call_event("TERMINATION_STEP", {"step": "room_disconnected", "status": "success"})
            except asyncio.TimeoutError:
                operation_errors["room_disconnect"] = "Timeout after 5 seconds"
                logger.warning("Room disconnection timed out, proceeding with forced cleanup")
                # Force clear room reference as fallback
                await self._force_room_cleanup()
            except Exception as disconnect_error:
                operation_errors["room_disconnect"] = str(disconnect_error)
                self._log_call_error("Failed to disconnect from room", disconnect_error)
                # Attempt forced cleanup as fallback
                try:
                    await self._force_room_cleanup()
                    self._log_call_event("TERMINATION_STEP", {"step": "room_force_cleaned", "status": "success"})
                except Exception as force_error:
                    operation_errors["room_force_cleanup"] = str(force_error)
                    logger.error(f"Failed to force clean room: {force_error}")
                    critical_failure = True

            # Step 6: Clean up call resources with error handling
            try:
                self._cleanup_call_resources()
                self._log_call_event("TERMINATION_STEP", {"step": "resources_cleaned", "status": "success"})
            except Exception as cleanup_error:
                operation_errors["resource_cleanup"] = str(cleanup_error)
                self._log_call_error("Failed to clean up call resources", cleanup_error)
                # Attempt emergency cleanup
                try:
                    await self._emergency_resource_cleanup()
                    self._log_call_event("TERMINATION_STEP", {"step": "emergency_cleanup", "status": "success"})
                except Exception as emergency_error:
                    operation_errors["emergency_cleanup"] = str(emergency_error)
                    logger.error(f"Emergency cleanup failed: {emergency_error}")
                    critical_failure = True

            # Step 7: Set final call state based on operation results
            if operation_errors and critical_failure:
                # Critical failure - set ERROR state with comprehensive error info
                error_summary = f"Critical termination failure. Errors: {operation_errors}"
                await self._set_call_state(CallState.ERROR, error=error_summary, operation_errors=operation_errors)
                self._log_call_event("CALL_TERMINATED", {"status": "critical_failure", "errors": operation_errors})
                raise RuntimeError(error_summary)
            elif operation_errors:
                # Partial failure - log warnings but consider termination successful
                logger.warning(f"Call terminated with partial failures: {operation_errors}")
                await self._set_call_state(CallState.ENDED, warnings=operation_errors)
                self._log_call_event("CALL_TERMINATED", {"status": "partial_success", "warnings": operation_errors})
            else:
                # Complete success
                await self._set_call_state(CallState.ENDED)
                self._log_call_event("CALL_TERMINATED", {"status": "success"})

        except Exception as e:
            # Catastrophic failure during termination process
            error_context = {
                "original_error": str(e),
                "operation_errors": operation_errors,
                "call_state": self._call_state.name
            }
            
            self._log_call_error("Catastrophic error during call termination", e, error_context)

            # Set ERROR state with comprehensive context
            await self._set_call_state(CallState.ERROR, error=str(e), context=error_context)
            
            # Attempt final emergency cleanup regardless of previous failures
            await self._catastrophic_failure_cleanup()
            
            # Re-raise to maintain error propagation
            raise RuntimeError(f"Call termination failed catastrophically: {e}") from e

    async def _disconnect_from_room(self) -> None:
        """Enhanced room disconnection logic with timeout and error handling.

        This method handles:
        - Checking room connection status
        - Graceful disconnection with timeout
        - Participant cleanup notification
        - Error recovery and logging
        """
        if not hasattr(self, "room") or not self.room:
            logger.debug("No room to disconnect from")
            return

        try:
            # Log participants before disconnection
            if hasattr(self.room, "remote_participants"):
                participant_count = len(self.room.remote_participants)
                if participant_count > 0:
                    logger.info(
                        f"Disconnecting from room with {participant_count} other participants"
                    )
                else:
                    logger.info("Disconnecting from room (no other participants)")

            # Attempt graceful disconnection with timeout
            try:
                # Set a reasonable timeout for disconnection (5 seconds)
                await asyncio.wait_for(self.room.disconnect(), timeout=5.0)
                logger.info("Successfully disconnected from LiveKit room")
            except asyncio.TimeoutError:
                logger.warning("Room disconnection timed out after 5 seconds")
                # Continue with cleanup - don't block termination
            except Exception as disconnect_error:
                logger.warning(f"Error during room disconnect: {disconnect_error}")
                # Continue with cleanup - disconnection failures shouldn't stop termination

        except Exception as e:
            logger.error(f"Unexpected error in room disconnection: {e}", exc_info=True)
            # Continue with cleanup even if disconnect fails completely
        finally:
            # Clear room reference regardless of disconnect success
            try:
                self.room = None
                logger.debug("Cleared room reference")
            except Exception as clear_error:
                logger.error(f"Error clearing room reference: {clear_error}")

    async def _force_room_cleanup(self) -> None:
        """Force cleanup of room resources when graceful disconnect fails.
        
        This method is used as a fallback when normal room disconnection fails.
        It forcibly clears the room reference and performs minimal cleanup.
        """
        try:
            logger.info("Performing forced room cleanup")
            
            # Force clear room reference immediately
            if hasattr(self, 'room'):
                self.room = None
                
            # Reset any room-related state
            if hasattr(self, '_agent_session'):
                try:
                    # Attempt to clear session room reference if it exists
                    if hasattr(self._agent_session, 'room'):
                        self._agent_session.room = None
                except Exception as session_error:
                    logger.debug(f"Could not clear session room reference: {session_error}")
                    
            logger.info("Forced room cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during forced room cleanup: {e}", exc_info=True)
            # Don't re-raise - this is already a fallback mechanism

    async def _emergency_resource_cleanup(self) -> None:
        """Emergency cleanup when normal resource cleanup fails.
        
        This method attempts to clean up critical resources with minimal operations
        to prevent resource leaks when normal cleanup fails.
        """
        try:
            logger.info("Performing emergency resource cleanup")
            
            # Reset critical state variables
            self.is_speaking = False
            self.is_listening = False
            
            # Clear metadata with fallback
            try:
                if hasattr(self, '_call_metadata'):
                    self._call_metadata.clear()
            except Exception:
                # Create new metadata dict if clearing fails
                self._call_metadata = {}
                
            # Ensure session is cleared
            try:
                if hasattr(self, '_agent_session'):
                    self._agent_session = None
            except Exception as session_error:
                logger.debug(f"Could not clear agent session: {session_error}")
                
            logger.info("Emergency resource cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during emergency resource cleanup: {e}", exc_info=True)
            # Don't re-raise - this is emergency cleanup

    async def _catastrophic_failure_cleanup(self) -> None:
        """Final cleanup attempt when termination fails catastrophically.
        
        This method performs minimal, essential cleanup operations that should
        work even when the system is in an unstable state.
        """
        try:
            logger.critical("Performing catastrophic failure cleanup")
            
            # Force clear all references with individual try-catch blocks
            try:
                self.room = None
            except Exception:
                pass
                
            try:
                self._agent_session = None
            except Exception:
                pass
                
            try:
                self.is_speaking = False
                self.is_listening = False
            except Exception:
                pass
                
            try:
                # Reset call session if possible
                if hasattr(self, 'call_session') and hasattr(self.call_session, 'reset'):
                    self.call_session.reset()
            except Exception:
                pass
                
            try:
                # Ensure we have clean metadata
                self._call_metadata = {}
            except Exception:
                pass
                
            logger.critical("Catastrophic failure cleanup completed")
            
        except Exception as e:
            # Even catastrophic cleanup failed - log but don't raise
            logger.critical(f"Catastrophic failure cleanup itself failed: {e}")
            # This is the last resort - no exceptions should propagate from here


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
