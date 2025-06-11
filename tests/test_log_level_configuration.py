"""Test suite for log level configuration functionality."""

import logging
import os
import pytest
from unittest.mock import patch, Mock
from agent import SimpleAgent, configure_logging


class TestLogLevelConfiguration:
    """Test cases for environment-based log level configuration."""

    def test_configure_logging_default_level(self):
        """Test that configure_logging defaults to INFO level when no LOG_LEVEL is set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove LOG_LEVEL from environment
            if "LOG_LEVEL" in os.environ:
                del os.environ["LOG_LEVEL"]

            logger = configure_logging()
            assert logger.level == logging.INFO

    def test_configure_logging_debug_level(self):
        """Test that configure_logging sets DEBUG level when LOG_LEVEL=DEBUG."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            logger = configure_logging()
            assert logger.level == logging.DEBUG

    def test_configure_logging_warning_level(self):
        """Test that configure_logging sets WARNING level when LOG_LEVEL=WARNING."""
        with patch.dict(os.environ, {"LOG_LEVEL": "WARNING"}):
            logger = configure_logging()
            assert logger.level == logging.WARNING

    def test_configure_logging_error_level(self):
        """Test that configure_logging sets ERROR level when LOG_LEVEL=ERROR."""
        with patch.dict(os.environ, {"LOG_LEVEL": "ERROR"}):
            logger = configure_logging()
            assert logger.level == logging.ERROR

    def test_configure_logging_critical_level(self):
        """Test that configure_logging sets CRITICAL level when LOG_LEVEL=CRITICAL."""
        with patch.dict(os.environ, {"LOG_LEVEL": "CRITICAL"}):
            logger = configure_logging()
            assert logger.level == logging.CRITICAL

    def test_configure_logging_case_insensitive(self):
        """Test that LOG_LEVEL environment variable is case insensitive."""
        with patch.dict(os.environ, {"LOG_LEVEL": "debug"}):
            logger = configure_logging()
            assert logger.level == logging.DEBUG

        with patch.dict(os.environ, {"LOG_LEVEL": "Warning"}):
            logger = configure_logging()
            assert logger.level == logging.WARNING

    def test_configure_logging_invalid_level_defaults_to_info(self):
        """Test that invalid LOG_LEVEL values default to INFO."""
        with patch.dict(os.environ, {"LOG_LEVEL": "INVALID"}):
            logger = configure_logging()
            assert logger.level == logging.INFO

        with patch.dict(os.environ, {"LOG_LEVEL": "TRACE"}):
            logger = configure_logging()
            assert logger.level == logging.INFO

        with patch.dict(os.environ, {"LOG_LEVEL": ""}):
            logger = configure_logging()
            assert logger.level == logging.INFO

    def test_configure_logging_handler_setup(self):
        """Test that configure_logging sets up console handler with proper formatting."""
        with patch.dict(os.environ, {"LOG_LEVEL": "INFO"}):
            logger = configure_logging()

            # Should have at least one handler
            assert len(logger.handlers) >= 1

            # Handler should be a StreamHandler
            handler = logger.handlers[0]
            assert isinstance(handler, logging.StreamHandler)

            # Handler should have a formatter
            assert handler.formatter is not None

    def test_configure_logging_no_duplicate_handlers(self):
        """Test that calling configure_logging multiple times doesn't create duplicate handlers."""
        with patch.dict(os.environ, {"LOG_LEVEL": "INFO"}):
            logger1 = configure_logging()
            initial_handler_count = len(logger1.handlers)

            logger2 = configure_logging()
            final_handler_count = len(logger2.handlers)

            # Should not have added additional handlers
            assert final_handler_count == initial_handler_count
            assert logger1 is logger2  # Should return the same logger instance

    def test_logger_name_consistency(self):
        """Test that the logger name remains consistent."""
        logger = configure_logging()
        assert logger.name == "listen-and-respond"

    def test_conditional_debug_logging_enabled(self):
        """Test that conditional debug logging works when DEBUG level is enabled."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            logger = configure_logging()
            assert logger.isEnabledFor(logging.DEBUG) is True

    def test_conditional_debug_logging_disabled(self):
        """Test that conditional debug logging works when DEBUG level is disabled."""
        with patch.dict(os.environ, {"LOG_LEVEL": "INFO"}):
            logger = configure_logging()
            assert logger.isEnabledFor(logging.DEBUG) is False

        with patch.dict(os.environ, {"LOG_LEVEL": "WARNING"}):
            logger = configure_logging()
            assert logger.isEnabledFor(logging.DEBUG) is False

    def test_agent_uses_configured_logger(self):
        """Test that SimpleAgent uses the configured logger with proper level."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            # Import agent module to trigger logger configuration
            import agent

            # Reload the module to ensure fresh logger configuration
            import importlib

            importlib.reload(agent)

            # Agent logger should use DEBUG level
            assert agent.logger.level == logging.DEBUG

    def test_log_level_environment_integration(self):
        """Test full integration of log level configuration through environment variables."""
        test_cases = [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ]

        for env_value, expected_level in test_cases:
            with patch.dict(os.environ, {"LOG_LEVEL": env_value}):
                logger = configure_logging()
                assert (
                    logger.level == expected_level
                ), f"Failed for LOG_LEVEL={env_value}"

    def test_log_formatter_includes_required_fields(self):
        """Test that the log formatter includes timestamp, logger name, level, and message."""
        logger = configure_logging()
        handler = logger.handlers[0]
        formatter = handler.formatter

        # Create a test log record
        record = logging.LogRecord(
            name="test-logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted_message = formatter.format(record)

        # Should contain the basic required fields
        assert "test-logger" in formatted_message
        assert "INFO" in formatted_message
        assert "Test message" in formatted_message
        # Should have timestamp (asctime)
        assert (
            len(formatted_message.split(" - ")) >= 4
        )  # timestamp - name - level - message

    @pytest.mark.asyncio
    async def test_agent_log_levels_in_action(self):
        """Test that different log levels work correctly in actual agent usage."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            # Reinitialize to pick up new log level
            import agent
            import importlib

            importlib.reload(agent)

            simple_agent = agent.SimpleAgent()

            with patch("agent.logger") as mock_logger:
                # Test debug logging
                simple_agent._log_call_debug("Debug message", {"key": "value"})
                mock_logger.debug.assert_called_once()

                # Test info logging
                simple_agent._log_call_event("TEST_EVENT", {"data": "test"})
                mock_logger.info.assert_called_once()

                # Test error logging
                test_error = Exception("Test error")
                simple_agent._log_call_error("Error message", test_error)
                mock_logger.error.assert_called_once()
