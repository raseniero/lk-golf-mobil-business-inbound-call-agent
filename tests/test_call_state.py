import asyncio
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from enum import Enum, auto

from agent import SimpleAgent, CallState


class TestCallState(Enum):
    """Test-specific call states for verification"""

    IDLE = auto()
    RINGING = auto()
    ACTIVE = auto()
    TERMINATING = auto()
    ENDED = auto()
    ERROR = auto()


class TestCallStateManagement:
    """Test suite for call state management in SimpleAgent."""

    @pytest.fixture
    def agent(self):
        """Create a SimpleAgent instance with mocked dependencies."""
        # Mock the parent class's __init__
        with patch("livekit.agents.voice.Agent.__init__", return_value=None), patch(
            "livekit.agents.voice.Agent.session", new_callable=PropertyMock
        ) as mock_session_prop:

            # Create a mock session
            mock_session = MagicMock()
            mock_session.generate_reply = MagicMock(return_value=asyncio.Future())
            mock_session.generate_reply.return_value.set_result(True)
            mock_session_prop.return_value = mock_session

            # Create the agent
            agent = SimpleAgent()

            # Mock the parent class's session property getter
            type(agent).session = PropertyMock(return_value=mock_session)

            # Mock the parent class's _session attribute
            agent._session = mock_session

            return agent

    @pytest.mark.asyncio
    async def test_initial_state(self, agent):
        """Test that the agent initializes with the correct default state."""
        assert agent.call_state == CallState.IDLE
        assert not agent.is_speaking
        assert not agent.is_listening
        assert agent.call_metadata == {}

    @pytest.mark.asyncio
    async def test_call_flow_states(self, agent, caplog):
        """Test the complete call flow state transitions."""
        # Start with IDLE state
        assert agent.call_state == CallState.IDLE

        # Call enters (RINGING -> ACTIVE)
        await agent.on_enter()
        assert agent.call_state == CallState.ACTIVE
        assert agent.is_listening
        assert not agent.is_speaking
        assert agent.call_session.start_time is not None

        # Simulate speaking
        await agent._on_agent_speaking(True)
        assert agent.is_speaking

        # Simulate stop speaking
        await agent._on_agent_speaking(False)
        assert not agent.is_speaking

        # Clear any previous logs
        caplog.clear()

        # Disconnect (TERMINATING -> ENDED)
        await agent.on_disconnect()
        assert agent.call_state == CallState.ENDED
        assert not agent.is_listening
        assert not agent.is_speaking

        # Verify the call duration was logged
        assert any(
            "Call ended. Duration:" in record.message for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_error_handling(self, agent, caplog):
        """Test error handling during state transitions."""
        # Force an error during on_enter
        agent.session.generate_reply.side_effect = Exception("Test error")

        with pytest.raises(Exception):
            await agent.on_enter()

        # Should transition to ERROR state
        assert agent.call_state == CallState.ERROR
        assert "Test error" in agent.call_metadata.get("error", "")

        # Should log the error
        assert "Error during call setup" in caplog.text

    @pytest.mark.asyncio
    async def test_duplicate_state_transitions(self, agent):
        """Test that duplicate state transitions are handled gracefully."""
        # First start the call session to have a start time
        agent.call_session.start_call()
        await agent._set_call_state(CallState.ACTIVE)
        initial_time = agent.call_session.start_time

        # Try to set the same state again
        await agent._set_call_state(CallState.ACTIVE)

        # Should not change the state or call session start time
        assert agent.call_state == CallState.ACTIVE
        assert agent.call_session.start_time == initial_time

    @pytest.mark.asyncio
    async def test_metadata_persistence(self, agent):
        """Test that metadata is properly stored and persisted."""
        test_metadata = {"key1": "value1", "key2": 123}

        await agent._set_call_state(CallState.ACTIVE, **test_metadata)

        # Check that metadata is stored
        assert agent.call_metadata["key1"] == "value1"
        assert agent.call_metadata["key2"] == 123

        # Check that call_metadata returns a copy
        metadata_copy = agent.call_metadata
        metadata_copy["new_key"] = "should_not_affect_original"
        assert "new_key" not in agent.call_metadata
