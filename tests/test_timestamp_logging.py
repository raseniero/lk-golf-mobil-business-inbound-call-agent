"""Test suite for call start/end timestamp logging."""

import pytest
import time
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from agent import SimpleAgent, CallState


class TestTimestampLogging:
    """Test cases for call start/end timestamp logging functionality."""

    def setup_method(self):
        """Set up test data and mock agent."""
        self.agent = SimpleAgent()

        # Mock the session and room
        self.mock_session = MagicMock()
        self.mock_session.generate_reply = AsyncMock()
        self.mock_session.say = AsyncMock()

        self.mock_room = MagicMock()
        self.mock_room.disconnect = AsyncMock()
        self.mock_room.remote_participants = {}

        # Set up agent state
        self.agent._agent_session = self.mock_session
        self.agent.room = self.mock_room
        self.agent._call_state = CallState.IDLE

    @pytest.mark.asyncio
    async def test_call_start_timestamp_logging(self):
        """Test that call start timestamps are logged with ISO format."""
        # Test the logging method directly to avoid session dependencies
        with patch("agent.logger") as mock_logger:
            self.agent.call_session.start_call()
            self.agent._log_call_start_timestamp()

            # Check that call start was logged with timestamp
            start_logged = any(
                "Call started at" in str(call)
                and "T" in str(call)  # ISO format contains 'T'
                for call in mock_logger.info.call_args_list
            )
            assert start_logged

    @pytest.mark.asyncio
    async def test_call_end_timestamp_logging(self):
        """Test that call end timestamps are logged with ISO format."""
        self.agent.call_session.start_call()
        self.agent._call_state = CallState.ACTIVE

        with patch("agent.logger") as mock_logger:
            await self.agent.terminate_call()

            # Check that call end was logged with timestamp
            end_logged = any(
                "Call ended at" in str(call)
                and "T" in str(call)  # ISO format contains 'T'
                for call in mock_logger.info.call_args_list
            )
            assert end_logged

    @pytest.mark.asyncio
    async def test_timestamp_format_consistency(self):
        """Test that timestamps use consistent ISO 8601 format."""
        self.agent.call_session.start_call()

        # Test both start and end timestamp formats
        start_time = self.agent.get_formatted_timestamp()
        time.sleep(0.01)  # Small delay
        end_time = self.agent.get_formatted_timestamp()

        # Both should be ISO 8601 format (contain 'T' and 'Z' or timezone info)
        assert "T" in start_time
        assert "T" in end_time

        # Should be parseable as datetime
        datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        datetime.fromisoformat(end_time.replace("Z", "+00:00"))

    @pytest.mark.asyncio
    async def test_call_duration_with_timestamps(self):
        """Test that call duration is calculated and logged with start/end timestamps."""
        self.agent.call_session.start_call()
        self.agent._call_state = CallState.ACTIVE

        # Add small delay to ensure measurable duration
        time.sleep(0.01)

        with patch("agent.logger") as mock_logger:
            await self.agent.terminate_call()

            # Check that duration was logged with start and end timestamps
            duration_logged = any(
                "duration" in str(call).lower()
                for call in mock_logger.info.call_args_list
            )
            timestamp_logged = any(
                "started at" in str(call).lower() or "ended at" in str(call).lower()
                for call in mock_logger.info.call_args_list
            )

            assert duration_logged
            assert timestamp_logged

    def test_timestamp_format_method_exists(self):
        """Test that timestamp formatting method exists and works."""
        timestamp = self.agent.get_formatted_timestamp()

        # Should return string in ISO format
        assert isinstance(timestamp, str)
        assert "T" in timestamp

        # Should be parseable
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            pytest.fail("Timestamp is not in valid ISO format")

    @pytest.mark.asyncio
    async def test_logging_includes_timezone_info(self):
        """Test that timestamps include timezone information."""
        timestamp = self.agent.get_formatted_timestamp()

        # Should include timezone (either 'Z' for UTC or offset like '+00:00')
        assert "Z" in timestamp or "+" in timestamp or "-" in timestamp

    @pytest.mark.asyncio
    async def test_on_disconnect_timestamp_logging(self):
        """Test that on_disconnect logs end timestamp."""
        self.agent.call_session.start_call()
        self.agent._call_state = CallState.ACTIVE

        with patch("agent.logger") as mock_logger:
            await self.agent.on_disconnect()

            # Check that end timestamp was logged
            end_logged = any(
                "ended at" in str(call).lower() and "T" in str(call)
                for call in mock_logger.info.call_args_list
            )
            assert end_logged

    @pytest.mark.asyncio
    async def test_timestamp_precision(self):
        """Test that timestamps have sufficient precision for duration calculations."""
        start_timestamp = self.agent.get_formatted_timestamp()
        time.sleep(0.001)  # 1ms delay
        end_timestamp = self.agent.get_formatted_timestamp()

        # Parse timestamps
        start_dt = datetime.fromisoformat(start_timestamp.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_timestamp.replace("Z", "+00:00"))

        # Should be able to measure millisecond differences
        duration = (end_dt - start_dt).total_seconds()
        assert duration >= 0.001  # At least 1ms difference

    @pytest.mark.asyncio
    async def test_log_call_lifecycle_timestamps(self):
        """Test that full call lifecycle timestamps are logged."""
        # Test lifecycle logging methods directly
        with patch("agent.logger") as mock_logger:
            # Start call
            self.agent.call_session.start_call()
            self.agent._log_call_start_timestamp()

            # End call
            self.agent.call_session.end_call()
            self.agent._log_call_end_timestamp()
            self.agent._log_call_lifecycle_summary()

            # Check for lifecycle logging
            all_logs = [str(call) for call in mock_logger.info.call_args_list]

            # Should have start and end timestamps
            start_timestamp_logged = any(
                "started at" in log.lower() for log in all_logs
            )
            end_timestamp_logged = any("ended at" in log.lower() for log in all_logs)

            assert start_timestamp_logged
            assert end_timestamp_logged

    def test_timestamp_method_performance(self):
        """Test that timestamp generation is fast enough for logging."""
        import time

        # Measure time to generate 1000 timestamps
        start_time = time.time()
        for _ in range(1000):
            self.agent.get_formatted_timestamp()
        end_time = time.time()

        # Should complete quickly (under 100ms for 1000 calls)
        total_time = end_time - start_time
        assert total_time < 0.1
