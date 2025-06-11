"""Test suite for call termination logging format."""

import pytest
import logging
import time
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from agent import SimpleAgent, CallState


class TestLoggingFormat:
    """Test cases for standardized logging format in call termination."""

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
        self.agent._call_state = CallState.ACTIVE

    @pytest.mark.asyncio
    async def test_log_format_call_start(self):
        """Test log format for call start events."""
        # Test the logging method directly since on_enter has session dependencies
        with patch("agent.logger") as mock_logger:
            self.agent.call_session.start_call()
            self.agent._log_call_event(
                "CALL_START",
                {
                    "start_time": datetime.fromtimestamp(
                        self.agent.call_session.start_time
                    ).isoformat()
                },
            )

            # Check for structured call start log
            call_start_logged = any(
                "CALL_START" in str(call) for call in mock_logger.info.call_args_list
            )
            assert call_start_logged

    @pytest.mark.asyncio
    async def test_log_format_phrase_detection(self):
        """Test log format for termination phrase detection."""
        self.agent.call_session.start_call()

        with patch("agent.logger") as mock_logger:
            await self.agent.on_user_input("goodbye everyone")

            # Check for structured phrase detection log
            phrase_logged = any(
                "PHRASE_DETECTED" in str(call)
                for call in mock_logger.info.call_args_list
            )
            assert phrase_logged

    @pytest.mark.asyncio
    async def test_log_format_call_termination(self):
        """Test log format for call termination events."""
        self.agent.call_session.start_call()

        with patch("agent.logger") as mock_logger:
            await self.agent.terminate_call()

            # Check for structured termination logs
            termination_logged = any(
                "CALL_TERMINATION" in str(call)
                for call in mock_logger.info.call_args_list
            )
            assert termination_logged

    @pytest.mark.asyncio
    async def test_log_format_call_duration(self):
        """Test log format for call duration tracking."""
        self.agent.call_session.start_call()

        with patch("agent.logger") as mock_logger:
            await self.agent.terminate_call()

            # Check for structured duration log
            duration_logged = any(
                "CALL_DURATION" in str(call) for call in mock_logger.info.call_args_list
            )
            assert duration_logged

    @pytest.mark.asyncio
    async def test_log_format_error_handling(self):
        """Test log format for error scenarios."""
        # Test the error logging method directly
        with patch("agent.logger") as mock_logger:
            test_error = Exception("Test error message")
            self.agent._log_call_error("Connection failed", test_error)

            # Check for structured error log
            error_logged = any(
                "ERROR" in str(call) for call in mock_logger.error.call_args_list
            )
            assert error_logged

    def test_log_format_includes_metadata(self):
        """Test that log messages include relevant metadata."""
        # Test that the logging format includes structured metadata
        self.agent._call_metadata["test_key"] = "test_value"

        with patch("agent.logger") as mock_logger:
            # Simulate a log call with metadata
            self.agent._log_call_event("TEST_EVENT", {"duration": 5.5})

            # Verify the log format includes metadata
            mock_logger.info.assert_called_once()
            log_call = mock_logger.info.call_args[0][0]
            assert "TEST_EVENT" in log_call
            assert "duration" in log_call

    def test_log_format_consistency(self):
        """Test that all log messages follow consistent format."""
        expected_fields = ["event", "timestamp", "state"]

        with patch("agent.logger") as mock_logger:
            # Test multiple log events
            self.agent._log_call_event("CALL_START", {})
            self.agent._log_call_event("PHRASE_DETECTED", {"phrase": "goodbye"})
            self.agent._log_call_event("CALL_END", {"duration": 10.5})

            # Verify all logs follow consistent format
            assert mock_logger.info.call_count == 3

            for call in mock_logger.info.call_args_list:
                log_message = call[0][0]
                # Each log should contain structured information
                assert any(field in log_message for field in expected_fields)

    def test_log_levels_appropriate(self):
        """Test that appropriate log levels are used for different events."""
        with patch("agent.logger") as mock_logger:
            # Info level for normal events
            self.agent._log_call_event("CALL_START", {})
            mock_logger.info.assert_called()

            # Error level for errors
            self.agent._log_call_error("Connection failed", Exception("Test"))
            mock_logger.error.assert_called()

            # Debug level for detailed events
            self.agent._log_call_debug("Processing input", {"text": "hello"})
            mock_logger.debug.assert_called()

    def test_log_format_performance(self):
        """Test that logging doesn't significantly impact performance."""
        start_time = time.time()

        # Log many events to test performance
        for i in range(1000):
            self.agent._log_call_event("TEST_EVENT", {"iteration": i})

        end_time = time.time()

        # Logging 1000 events should complete quickly
        assert (end_time - start_time) < 0.1

    def test_log_format_handles_special_characters(self):
        """Test that log format handles special characters safely."""
        special_data = {
            "phrase": 'goodbye "quoted" text',
            "input": "text with \n newlines \t tabs",
            "error": "exception with 'quotes' and unicode: ñáéíóú",
        }

        with patch("agent.logger") as mock_logger:
            self.agent._log_call_event("TEST_SPECIAL", special_data)

            # Should not raise exception and should log safely
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args[0][0]
            assert "TEST_SPECIAL" in log_message
