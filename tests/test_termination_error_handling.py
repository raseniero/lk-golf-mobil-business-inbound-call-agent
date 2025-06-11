"""
Test suite for call termination error handling functionality.

This module tests error scenarios during call termination including:
- LiveKit session errors
- Timeout handling
- Recovery mechanisms
- Error state transitions
- Error logging
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import logging

from agent import SimpleAgent, CallState


class TestTerminationErrorHandling:
    """Test error handling during call termination process."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent for testing."""
        agent = SimpleAgent()
        agent._agent_session = AsyncMock()
        agent.room = MagicMock()
        agent.call_session.start_call()
        return agent

    @pytest.mark.asyncio
    async def test_terminate_call_with_livekit_session_error(self, mock_agent):
        """Test termination handling when LiveKit session throws an error."""
        # Setup: Make room disconnect throw an exception
        mock_agent.room.disconnect = AsyncMock(side_effect=Exception("LiveKit connection error"))
        
        # Set initial state
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Execute termination
        await mock_agent._terminate_call()
        
        # Verify: Agent should handle error gracefully with partial success
        # The enhanced error handling allows termination to complete despite room disconnect failures
        assert mock_agent.call_state == CallState.ENDED
        warnings = mock_agent.call_metadata.get("warnings", {})
        assert "room_disconnect" in warnings
        assert "LiveKit connection error" in str(warnings["room_disconnect"])

    @pytest.mark.asyncio
    async def test_terminate_call_with_timeout_handling(self, mock_agent):
        """Test termination timeout scenarios."""
        # Setup: Make room disconnect hang (simulate timeout)
        async def hanging_disconnect():
            await asyncio.sleep(10)  # Longer than our timeout
            
        mock_agent.room.disconnect = hanging_disconnect
        
        # Set initial state
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Execute termination (should handle timeout gracefully)
        with patch('asyncio.wait_for') as mock_wait_for:
            mock_wait_for.side_effect = asyncio.TimeoutError("Disconnect timed out")
            await mock_agent._terminate_call()
        
        # Verify: Agent should complete termination despite timeout
        assert mock_agent.call_state == CallState.ENDED
        assert mock_agent.room is None

    @pytest.mark.asyncio
    async def test_error_recovery_mechanisms(self, mock_agent):
        """Test recovery from partial termination failures."""
        # Setup: Make call session end_call throw an error
        original_end_call = mock_agent.call_session.end_call
        mock_agent.call_session.end_call = MagicMock(side_effect=Exception("Session error"))
        
        # Set initial state
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Execute termination - should handle session error gracefully
        await mock_agent._terminate_call()
        
        # Verify: Agent should handle session error and complete termination
        assert mock_agent.call_state == CallState.ENDED
        warnings = mock_agent.call_metadata.get("warnings", {})
        assert "session_end" in warnings
        assert "Session error" in str(warnings["session_end"])

    @pytest.mark.asyncio
    async def test_error_state_transitions(self, mock_agent):
        """Test proper state transitions during error scenarios."""
        # Set initial state
        await mock_agent._set_call_state(CallState.ACTIVE)
        initial_state = mock_agent.call_state
        
        # Setup: Make both cleanup and emergency cleanup fail to trigger critical failure
        with patch.object(mock_agent, '_cleanup_call_resources', side_effect=Exception("Cleanup failed")):
            with patch.object(mock_agent, '_emergency_resource_cleanup', side_effect=Exception("Emergency failed")):
                with pytest.raises(RuntimeError, match="Critical termination failure"):
                    await mock_agent._terminate_call()
        
        # Verify: State should transition through TERMINATING to ERROR for critical failures
        assert initial_state == CallState.ACTIVE
        assert mock_agent.call_state == CallState.ERROR

    @pytest.mark.asyncio
    async def test_error_logging_format_and_content(self, mock_agent, caplog):
        """Test error logging format and content during termination failures."""
        with caplog.at_level(logging.ERROR):
            # Setup: Make room disconnect fail
            mock_agent.room.disconnect = AsyncMock(side_effect=RuntimeError("Network error"))
            
            # Set initial state
            await mock_agent._set_call_state(CallState.ACTIVE)
            
            # Execute termination
            await mock_agent._terminate_call()
            
            # Verify: Error should be logged with proper format
            error_logs = [record for record in caplog.records if record.levelname == "ERROR"]
            assert len(error_logs) > 0
            
            # Check log content - should contain "Failed to disconnect from room"
            error_log = error_logs[0]
            assert "Failed to disconnect from room" in error_log.message
            assert "Network error" in error_log.message

    @pytest.mark.asyncio
    async def test_graceful_degradation_when_termination_fails(self, mock_agent):
        """Test graceful degradation when primary termination fails."""
        # Setup: Make multiple components fail
        mock_agent.room.disconnect = AsyncMock(side_effect=Exception("Room disconnect failed"))
        mock_agent.call_session.end_call = MagicMock(side_effect=Exception("Session end failed"))
        
        # Set initial state
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Execute termination - should not raise despite multiple failures
        await mock_agent._terminate_call()
        
        # Verify: Agent should handle partial failures gracefully
        assert mock_agent.call_state == CallState.ENDED
        warnings = mock_agent.call_metadata.get("warnings", {})
        assert "room_disconnect" in warnings
        assert "session_end" in warnings
        assert mock_agent.room is None  # Room reference should be cleared

    @pytest.mark.asyncio
    async def test_multiple_termination_failures_in_sequence(self, mock_agent):
        """Test handling of multiple error scenarios in sequence."""
        # Test multiple termination attempts after errors
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # First termination attempt with room disconnect failure
        with patch.object(mock_agent, '_disconnect_from_room', side_effect=Exception("First failure")):
            await mock_agent._terminate_call()
        
        # Should handle gracefully with partial success
        assert mock_agent.call_state == CallState.ENDED
        
        # Second termination attempt - should ignore since already ended
        await mock_agent._terminate_call()
        
        # Should remain in ENDED state
        assert mock_agent.call_state == CallState.ENDED

    @pytest.mark.asyncio
    async def test_emergency_cleanup_on_critical_failure(self, mock_agent):
        """Test emergency cleanup when termination fails critically."""
        # Setup: Make primary termination fail, but emergency cleanup should still work
        original_cleanup = mock_agent._cleanup_call_resources
        mock_agent._cleanup_call_resources = MagicMock(side_effect=Exception("Cleanup failed"))
        
        # Mock the emergency cleanup path
        with patch.object(mock_agent, '_cleanup_call_resources') as mock_cleanup:
            mock_cleanup.side_effect = [Exception("First cleanup failed"), None]  # Fail then succeed
            
            await mock_agent._set_call_state(CallState.ACTIVE)
            
            # This should trigger emergency cleanup path
            await mock_agent._terminate_call()
            
            # Verify emergency cleanup was attempted
            assert mock_cleanup.call_count >= 1

    @pytest.mark.asyncio
    async def test_room_disconnection_with_participants_error(self, mock_agent):
        """Test room disconnection error handling when other participants are present."""
        # Setup: Mock room with participants that causes error during disconnect
        mock_agent.room.remote_participants = [MagicMock(), MagicMock()]  # 2 participants
        mock_agent.room.disconnect = AsyncMock(side_effect=Exception("Participant disconnect error"))
        
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Execute termination
        await mock_agent._terminate_call()
        
        # Verify: Should handle participant disconnect error gracefully
        assert mock_agent.call_state == CallState.ENDED
        warnings = mock_agent.call_metadata.get("warnings", {})
        assert "room_disconnect" in warnings
        assert mock_agent.room is None  # Room reference should still be cleared

    @pytest.mark.asyncio
    async def test_fallback_disconnection_mechanism(self, mock_agent):
        """Test fallback disconnection when graceful disconnect fails."""
        # Setup: Make graceful disconnect fail, but cleanup should continue
        mock_agent.room.disconnect = AsyncMock(side_effect=Exception("Graceful disconnect failed"))
        
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Execute termination
        await mock_agent._terminate_call()
        
        # Verify: Should continue with termination despite disconnect failure
        assert mock_agent.call_state == CallState.ENDED
        warnings = mock_agent.call_metadata.get("warnings", {})
        assert "room_disconnect" in warnings
        assert mock_agent.room is None  # Room should still be cleared as fallback

    @pytest.mark.asyncio
    async def test_error_codes_and_messages(self, mock_agent):
        """Test error codes and messages are properly set during failures."""
        # Test different types of errors produce appropriate error metadata
        test_error = RuntimeError("Specific test error")
        
        # Setup: Make room disconnect throw the specific error
        mock_agent.room.disconnect = AsyncMock(side_effect=test_error)
        
        await mock_agent._set_call_state(CallState.ACTIVE)
        await mock_agent._terminate_call()
        
        # Verify error information is captured in warnings for partial failures
        assert mock_agent.call_state == CallState.ENDED
        warnings = mock_agent.call_metadata.get("warnings", {})
        assert "room_disconnect" in warnings
        assert "Specific test error" in str(warnings["room_disconnect"])

    @pytest.mark.asyncio
    async def test_stack_trace_logging_on_errors(self, mock_agent, caplog):
        """Test that stack traces are logged for debugging purposes."""
        with caplog.at_level(logging.ERROR):
            # Create a specific error with traceable stack
            def failing_function():
                raise ValueError("Traceable error for testing")
            
            with patch.object(mock_agent, '_disconnect_from_room', side_effect=failing_function):
                await mock_agent._set_call_state(CallState.ACTIVE)
                await mock_agent._terminate_call()
                
                # Verify stack trace information is in logs
                error_logs = [record for record in caplog.records if record.levelname == "ERROR"]
                assert len(error_logs) > 0
                
                # Check that exc_info was used (indicates stack trace logging)
                error_with_trace = any(record.exc_info for record in error_logs)
                assert error_with_trace, "Expected at least one error log with stack trace"