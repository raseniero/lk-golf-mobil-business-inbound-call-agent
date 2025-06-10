import asyncio
import logging
import time
from enum import Enum, auto
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
import livekit.rtc as rtc
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import openai, silero, deepgram

from utils import load_prompt_markdown


class CallState(Enum):
    """Represents the possible states of a call."""
    IDLE = auto()           # Initial state before call starts
    RINGING = auto()        # Call is incoming/ringing
    ACTIVE = auto()         # Call is in progress
    TERMINATING = auto()    # Call is being terminated
    ENDED = auto()          # Call has ended
    ERROR = auto()          # Call is in error state

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
    def __init__(self) -> None:
        # Initialize instance variables
        self.call_session: CallSession = CallSession()
        self.room: Optional[rtc.Room] = None
        self.is_speaking: bool = False
        self.is_listening: bool = False
        self._agent_session: Optional[AgentSession] = None
        self._call_state: CallState = CallState.IDLE
        self._call_metadata: Dict[str, Any] = {}  # Store additional call-related data

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
