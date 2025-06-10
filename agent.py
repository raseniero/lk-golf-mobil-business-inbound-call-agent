import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
import livekit.rtc as rtc
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import openai, silero, deepgram

from utils import load_prompt_markdown

load_dotenv()

logger = logging.getLogger("listen-and-respond")
logger.setLevel(logging.INFO)


class SimpleAgent(Agent):
    def __init__(self) -> None:
        # Initialize instance variables first
        self.call_start_time: Optional[float] = None
        self.room: Optional[rtc.Room] = None
        self.is_speaking: bool = False
        self.is_listening: bool = False
        self._agent_session: Optional[AgentSession] = None

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
        self.call_start_time = time.time()
        logger.info(f"Call started at {datetime.now().isoformat()}")
        self._agent_session = self.session  # Store the session from parent class

        # Set initial states
        self.is_speaking = False
        self.is_listening = True  # Start in listening mode

        # Generate initial greeting if we have a session
        if self._agent_session:
            await self._agent_session.generate_reply()

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
        if self.call_start_time:
            call_duration = time.time() - self.call_start_time
            logger.info(f"Call ended. Duration: {call_duration:.2f} seconds")
        else:
            logger.info("Call ended (no start time recorded)")


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
