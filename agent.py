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
        self.call_start_time: Optional[float] = None
        self.room: Optional[rtc.Room] = None

        super().__init__(
            instructions=load_prompt_markdown("basic_prompt.md"),
            stt=deepgram.STT(),
            llm=openai.LLM(model="gpt-4o"),
            tts=openai.TTS(),
            vad=silero.VAD.load(),
        )

        # Register event handlers
        self.on("agent_speaking", self._on_agent_speaking)
        self.on("agent_listening", self._on_agent_listening)

    async def on_enter(self):
        """Called when the agent enters a call."""
        self.call_start_time = time.time()
        logger.info(f"Call started at {datetime.now().isoformat()}")
        self.session.generate_reply()

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
    await ctx.connect()

    # Create agent instance
    agent = SimpleAgent()
    agent.room = ctx.room

    # Set up room handlers
    await setup_room_handlers(ctx.room, agent)

    # Create and start agent session
    session = AgentSession()
    await session.start(agent=agent, room=ctx.room)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
