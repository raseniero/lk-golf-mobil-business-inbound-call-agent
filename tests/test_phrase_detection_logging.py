import logging
import pytest
from unittest.mock import Mock, patch, call
from agent import SimpleAgent, CallState


class TestPhraseDetectionLogging:
    """Test suite for phrase detection logging functionality."""

    @pytest.fixture
    def agent(self):
        """Create a SimpleAgent instance for testing."""
        return SimpleAgent()

    @pytest.fixture
    def mock_logger(self):
        """Mock logger for testing log output."""
        with patch('agent.logger') as mock_log:
            yield mock_log

    def test_log_call_event_structure(self, agent, mock_logger):
        """Test that _log_call_event logs structured event data."""
        event_type = "PHRASE_DETECTED"
        data = {"phrase": "goodbye", "input_text": "goodbye everyone"}
        
        agent._log_call_event(event_type, data)
        
        # Verify structured logging call was made
        mock_logger.info.assert_called_once()
        log_call = mock_logger.info.call_args[0][0]
        
        # Check that log message contains event type and data
        assert event_type in log_call
        assert "goodbye" in log_call
        assert "input_text" in log_call

    def test_log_call_debug_with_data(self, agent, mock_logger):
        """Test that _log_call_debug logs debug messages with optional data."""
        message = "Processing user input"
        data = {"input_text": "hello world"}
        
        agent._log_call_debug(message, data)
        
        mock_logger.debug.assert_called_once()
        log_call = mock_logger.debug.call_args[0][0]
        
        assert message in log_call
        assert "hello world" in log_call

    def test_log_call_debug_without_data(self, agent, mock_logger):
        """Test that _log_call_debug works without optional data."""
        message = "Simple debug message"
        
        agent._log_call_debug(message)
        
        mock_logger.debug.assert_called_once()
        log_call = mock_logger.debug.call_args[0][0]
        assert message in log_call

    def test_log_call_error_with_exception(self, agent, mock_logger):
        """Test that _log_call_error logs errors with exception info."""
        message = "Error during processing"
        error = ValueError("Test error")
        data = {"context": "test_context"}
        
        agent._log_call_error(message, error, data)
        
        # Should call logger.error with exc_info=True
        mock_logger.error.assert_called_once()
        call_args, call_kwargs = mock_logger.error.call_args
        
        assert message in call_args[0]
        assert "ValueError" in call_args[0] or "Test error" in call_args[0]
        assert call_kwargs.get('exc_info') is True

    @pytest.mark.asyncio
    async def test_phrase_detection_logging_integration(self, agent, mock_logger):
        """Test that phrase detection triggers proper logging."""
        # Mock the agent session to avoid actual LLM calls
        agent._agent_session = Mock()
        agent._agent_session.generate_reply = Mock()
        
        # Test input that should trigger termination phrase detection
        test_input = "goodbye everyone"
        
        await agent.on_user_input(test_input)
        
        # Should log the phrase detection event
        assert mock_logger.info.called or mock_logger.debug.called
        
        # Check for specific logging calls
        all_calls = mock_logger.info.call_args_list + mock_logger.debug.call_args_list
        log_messages = [str(call) for call in all_calls]
        
        # Should have logged phrase detection
        phrase_detected = any("PHRASE_DETECTED" in msg for msg in log_messages)
        assert phrase_detected, f"No PHRASE_DETECTED log found in: {log_messages}"

    def test_logging_with_unicode_characters(self, agent, mock_logger):
        """Test logging handles unicode characters in phrases."""
        event_type = "PHRASE_DETECTED"
        data = {"phrase": "goodbyé", "input_text": "goodbyé amigos 👋"}
        
        agent._log_call_event(event_type, data)
        
        mock_logger.info.assert_called_once()
        # Should not raise any encoding errors

    def test_logging_with_empty_data(self, agent, mock_logger):
        """Test logging handles empty or None data gracefully."""
        agent._log_call_event("TEST_EVENT", {})
        agent._log_call_debug("Test message", None)
        
        # Should not raise any errors
        assert mock_logger.info.called
        assert mock_logger.debug.called

    def test_logging_with_large_input_text(self, agent, mock_logger):
        """Test logging handles large input text appropriately."""
        large_text = "hello " * 1000  # Very long input
        data = {"input_text": large_text}
        
        agent._log_call_debug("Processing large input", data)
        
        mock_logger.debug.assert_called_once()
        # Should handle large text without issues

    @pytest.mark.asyncio
    async def test_termination_phrase_logging_sequence(self, agent, mock_logger):
        """Test the complete logging sequence when a termination phrase is detected."""
        # Mock necessary components
        agent._agent_session = Mock()
        agent._agent_session.say = Mock()
        
        with patch.object(agent, 'terminate_call') as mock_terminate:
            await agent.on_user_input("goodbye")
            
            # Should have multiple logging calls in sequence
            assert mock_logger.info.called or mock_logger.debug.called
            
            # Check specific log events
            all_calls = mock_logger.info.call_args_list + mock_logger.debug.call_args_list
            log_messages = [str(call) for call in all_calls]
            
            # Should log phrase detection
            phrase_detected = any("PHRASE_DETECTED" in msg for msg in log_messages)
            assert phrase_detected
            
            # Should log termination initiation
            termination_initiated = any("TERMINATION_INITIATED" in msg for msg in log_messages)
            assert termination_initiated

    def test_log_format_consistency(self, agent, mock_logger):
        """Test that all logging methods produce consistent format."""
        # Test different logging methods
        agent._log_call_event("TEST_EVENT", {"key": "value"})
        agent._log_call_debug("Debug message", {"debug_key": "debug_value"})
        agent._log_call_error("Error message", Exception("test"), {"error_key": "error_value"})
        
        # All should have been called
        assert mock_logger.info.called
        assert mock_logger.debug.called  
        assert mock_logger.error.called
        
        # Log messages should follow consistent structure
        info_call = str(mock_logger.info.call_args)
        debug_call = str(mock_logger.debug.call_args)
        error_call = str(mock_logger.error.call_args)
        
        # All should contain structured information
        assert "TEST_EVENT" in info_call
        assert "Debug message" in debug_call
        assert "Error message" in error_call