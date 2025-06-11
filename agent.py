import asyncio
import json
import logging
import re
import time
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

    async def on_enter(self):
        """Called when the agent enters a call."""
        await self._set_call_state(CallState.RINGING)

        try:
            self.call_session.start_call()
            self._agent_session = self.session  # Store the session from parent class

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
            logger.error(f"Error during call setup: {e}", exc_info=True)
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
            
        logger.debug(f"Processing input: '{text}'")
        
        # Use the utility function to detect termination phrases
        detected_phrase = detect_termination_phrase(text, self.termination_phrases)
        
        if detected_phrase:
            logger.debug(f"Termination phrase detected: '{detected_phrase}' in input: '{text}'")
            await self._handle_termination_phrase(detected_phrase)
            return
        
        logger.debug(f"No termination phrase found in '{text}'")
        
        # For non-matching input, always call generate_reply if we have a session
        # and we're not already in the process of terminating
        if self._agent_session and self._call_state != CallState.TERMINATING:
            try:
                # Log that we're generating a reply for non-matching input
                logger.debug(f"No termination phrase detected, generating reply for input: {text}")
                await self._agent_session.generate_reply()
            except Exception as e:
                logger.error(f"Error generating reply: {e}", exc_info=True)
        else:
            logger.debug("Skipping generate_reply - no active session or call is terminating")
                
    async def _handle_termination_phrase(self, phrase: str) -> None:
        """Handle the detection of a termination phrase.
        
        This method provides immediate acknowledgment of the termination request
        before proceeding with the actual call termination.
        
        Args:
            phrase: The termination phrase that was detected.
        """
        try:
            # Log the termination attempt
            logger.info(f"Termination phrase detected: '{phrase}' in input")
            
            # Provide immediate acknowledgment response
            await self._send_immediate_termination_response(phrase)
            
            # Call the termination handler
            await self.terminate_call()
            
        except Exception as e:
            logger.error(f"Error during call termination: {e}", exc_info=True)
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
            "that's all": "Understood. Thank you for the conversation!"
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
        """Core internal call termination logic.
        
        This method performs the actual cleanup and state transitions
        when a call is terminated. It handles:
        - State validation and transitions
        - Call session timing
        - Resource cleanup
        - Room disconnection
        - Error recovery
        """
        if self._call_state == CallState.ENDED:
            logger.warning("Call already ended, ignoring termination request")
            return
            
        logger.info("Initiating call termination...")
        
        # Set call state to TERMINATING
        await self._set_call_state(CallState.TERMINATING)
        
        try:
            # End the call session timing
            self.call_session.end_call()
            
            # Log call duration if available
            duration = self.call_session.get_duration()
            if duration is not None:
                self._call_metadata["duration"] = duration
                logger.info(f"Call duration: {duration:.2f} seconds")
            
            # Disconnect from LiveKit room if connected
            await self._disconnect_from_room()
                
            # Clean up call resources
            self._cleanup_call_resources()
            
            # Set final call state
            await self._set_call_state(CallState.ENDED)
            logger.info("Call terminated successfully")
            
        except Exception as e:
            logger.error(f"Error during call termination cleanup: {e}", exc_info=True)
            await self._set_call_state(CallState.ERROR, error=str(e))
            # Still try to clean up resources
            try:
                self._cleanup_call_resources()
            except Exception as cleanup_error:
                logger.error(f"Error during emergency cleanup: {cleanup_error}")
            raise
    
    async def _disconnect_from_room(self) -> None:
        """Enhanced room disconnection logic with timeout and error handling.
        
        This method handles:
        - Checking room connection status
        - Graceful disconnection with timeout
        - Participant cleanup notification
        - Error recovery and logging
        """
        if not hasattr(self, 'room') or not self.room:
            logger.debug("No room to disconnect from")
            return
            
        try:
            # Log participants before disconnection
            if hasattr(self.room, 'remote_participants'):
                participant_count = len(self.room.remote_participants)
                if participant_count > 0:
                    logger.info(f"Disconnecting from room with {participant_count} other participants")
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
