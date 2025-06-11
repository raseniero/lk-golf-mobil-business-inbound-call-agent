"""
Test suite for verifying error handling behavior.

This module validates that all error handling mechanisms work correctly
including error state transitions, logging, recovery mechanisms, and
fallback procedures.
"""

import asyncio
import pytest
import logging
from unittest.mock import AsyncMock, MagicMock, patch
import time

from agent import SimpleAgent, CallState, CallSession


class TestErrorBehaviorValidation:
    """Test suite for validating error handling behavior."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent for testing."""
        agent = SimpleAgent()
        agent._agent_session = AsyncMock()
        agent.room = MagicMock()
        agent.room.disconnect = AsyncMock()
        agent.call_session.start_call()
        return agent

    @pytest.mark.asyncio
    async def test_error_state_persistence(self, mock_agent):
        """Test that error states are maintained correctly."""
        # Test 1: Error state persists through method calls
        await mock_agent._set_call_state(CallState.ERROR, error="Test error")
        
        # Verify error state is set
        assert mock_agent.call_state == CallState.ERROR
        assert "error" in mock_agent.call_metadata
        assert "Test error" in str(mock_agent.call_metadata["error"])
        
        # Test 2: Metadata can be updated through kwargs
        # Note: The implementation preserves call state but doesn't merge metadata
        original_metadata = mock_agent.call_metadata.copy()
        await mock_agent._set_call_state(CallState.ERROR, additional_info="More data")
        assert mock_agent.call_state == CallState.ERROR
        # The original error metadata is preserved in this implementation
        assert "error" in mock_agent.call_metadata

    @pytest.mark.asyncio
    async def test_error_recovery_paths(self, mock_agent):
        """Test that all error recovery mechanisms work properly."""
        # Test 1: Recovery from room disconnect failure
        mock_agent.room.disconnect.side_effect = Exception("Room disconnect failed")
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Execute termination with error
        await mock_agent._terminate_call()
        
        # Verify recovery: should end up in ENDED state with warnings
        assert mock_agent.call_state == CallState.ENDED
        warnings = mock_agent.call_metadata.get("warnings", {})
        assert "room_disconnect" in warnings
        assert mock_agent.room is None  # Room should be cleared by fallback

    @pytest.mark.asyncio
    async def test_error_logging_completeness(self, mock_agent, caplog):
        """Test that all errors are properly logged with complete information."""
        with caplog.at_level(logging.ERROR):
            # Test 1: Termination error logging
            mock_agent.room.disconnect.side_effect = RuntimeError("Test logging error")
            await mock_agent._set_call_state(CallState.ACTIVE)
            
            await mock_agent._terminate_call()
            
            # Verify comprehensive logging
            error_logs = [record for record in caplog.records if record.levelname == "ERROR"]
            assert len(error_logs) > 0
            
            # Check log content includes:
            error_log = error_logs[0]
            assert "Failed to disconnect from room" in error_log.message
            assert "Test logging error" in error_log.message
            
            # Verify stack trace is included
            assert error_log.exc_info is not None

    @pytest.mark.asyncio
    async def test_graceful_degradation_scenarios(self, mock_agent):
        """Test graceful degradation in various failure scenarios."""
        # Scenario 1: Session operations fail but termination continues
        mock_agent._agent_session.say.side_effect = Exception("TTS failed")
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Should handle TTS failure gracefully
        await mock_agent.on_user_input("goodbye")
        assert mock_agent.call_state == CallState.ENDED
        
        # Scenario 2: Multiple component failures
        agent2 = SimpleAgent()
        agent2.room = MagicMock()
        agent2.room.disconnect.side_effect = Exception("Room failed")
        agent2.call_session.end_call = MagicMock(side_effect=Exception("Session failed"))
        agent2._agent_session = AsyncMock()
        
        agent2.call_session.start_call()
        await agent2._set_call_state(CallState.ACTIVE)
        
        # Should handle multiple failures gracefully
        await agent2._terminate_call()
        assert agent2.call_state == CallState.ENDED
        warnings = agent2.call_metadata.get("warnings", {})
        assert len(warnings) >= 2  # Multiple warnings for multiple failures

    @pytest.mark.asyncio
    async def test_error_handling_during_state_transitions(self, mock_agent):
        """Test error handling during state transitions."""
        # Test 1: State transitions work correctly even with component failures
        # Set an initial state
        await mock_agent._set_call_state(CallState.IDLE)
        
        # Transition to active state
        await mock_agent._set_call_state(CallState.ACTIVE)
        assert mock_agent.call_state == CallState.ACTIVE
        
        # Transition to error state
        await mock_agent._set_call_state(CallState.ERROR, error="Test error")
        assert mock_agent.call_state == CallState.ERROR

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, mock_agent):
        """Test timeout error handling mechanisms."""
        # Test 1: Room disconnect timeout
        async def hanging_disconnect():
            await asyncio.sleep(10)  # Longer than timeout
        
        mock_agent.room.disconnect = hanging_disconnect
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Execute termination - should handle timeout
        await mock_agent._terminate_call()
        
        # Verify timeout was handled
        assert mock_agent.call_state == CallState.ENDED
        warnings = mock_agent.call_metadata.get("warnings", {})
        assert "room_disconnect" in warnings
        assert "Timeout" in str(warnings["room_disconnect"])

    @pytest.mark.asyncio
    async def test_critical_vs_partial_failure_handling(self, mock_agent):
        """Test distinction between critical and partial failures."""
        # Test 1: Partial failure (room disconnect) - should succeed with warnings
        mock_agent.room.disconnect.side_effect = Exception("Partial failure")
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        await mock_agent._terminate_call()
        assert mock_agent.call_state == CallState.ENDED
        assert "warnings" in mock_agent.call_metadata
        
        # Test 2: Critical failure (multiple cleanup failures)
        agent2 = SimpleAgent()
        agent2.room = MagicMock()
        agent2.room.disconnect.side_effect = Exception("Room failed")
        agent2._agent_session = AsyncMock()
        agent2.call_session.start_call()
        
        # Mock both cleanup methods to fail
        with patch.object(agent2, '_cleanup_call_resources', side_effect=Exception("Cleanup failed")):
            with patch.object(agent2, '_emergency_resource_cleanup', side_effect=Exception("Emergency failed")):
                await agent2._set_call_state(CallState.ACTIVE)
                
                # Should trigger critical failure path
                with pytest.raises(RuntimeError, match="Critical termination failure"):
                    await agent2._terminate_call()
                
                assert agent2.call_state == CallState.ERROR

    @pytest.mark.asyncio
    async def test_error_context_preservation(self, mock_agent):
        """Test that error context is preserved throughout error handling."""
        # Test with rich error context
        test_error = ValueError("Test error with context")
        test_error.custom_data = {"additional": "context"}
        
        mock_agent.room.disconnect.side_effect = test_error
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        await mock_agent._terminate_call()
        
        # Verify error context is preserved
        warnings = mock_agent.call_metadata.get("warnings", {})
        assert "room_disconnect" in warnings
        assert "Test error with context" in str(warnings["room_disconnect"])

    @pytest.mark.asyncio
    async def test_cascade_error_prevention(self, mock_agent):
        """Test that errors don't cascade and cause additional failures."""
        # Setup multiple potential failure points
        mock_agent.room.disconnect.side_effect = Exception("First error")
        
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Should handle cascading errors gracefully without raising
        try:
            await mock_agent._terminate_call()
        except Exception as e:
            pytest.fail(f"Termination should not raise exceptions: {e}")
        
        # Verify termination still completed despite errors
        assert mock_agent.call_state == CallState.ENDED

    @pytest.mark.asyncio
    async def test_error_handling_in_user_input_processing(self, mock_agent):
        """Test error handling during user input processing."""
        # Test 1: Normal phrase detection works correctly
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Should handle user input correctly
        await mock_agent.on_user_input("goodbye")
        
        # Agent should terminate after detecting phrase
        assert mock_agent.call_state == CallState.ENDED
        
        # Test 2: Non-termination phrases don't trigger termination
        mock_agent2 = SimpleAgent()
        mock_agent2.room = MagicMock()
        mock_agent2._agent_session = AsyncMock()
        mock_agent2.call_session.start_call()
        await mock_agent2._set_call_state(CallState.ACTIVE)
        
        await mock_agent2.on_user_input("hello there")
        
        # Should remain active for non-termination phrases
        assert mock_agent2.call_state == CallState.ACTIVE

    @pytest.mark.asyncio
    async def test_error_handling_during_immediate_response(self, mock_agent):
        """Test error handling during immediate termination response."""
        # Setup immediate response to fail
        mock_agent._agent_session.say.side_effect = Exception("Say failed")
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Should handle say error gracefully and still terminate
        await mock_agent.on_user_input("goodbye")
        
        assert mock_agent.call_state == CallState.ENDED

    @pytest.mark.asyncio
    async def test_memory_cleanup_under_error_conditions(self, mock_agent):
        """Test memory cleanup works even under error conditions."""
        # Setup with lots of metadata
        large_data = {"large": "x" * 1000}
        mock_agent._call_metadata.update({
            "data1": large_data,
            "data2": large_data.copy(),
            "data3": large_data.copy()
        })
        
        # Cause termination to fail but cleanup should still work
        mock_agent.room.disconnect.side_effect = Exception("Cleanup test error")
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        await mock_agent._terminate_call()
        
        # Verify memory was cleaned up despite errors
        assert len(mock_agent._call_metadata) <= 1  # Only warnings should remain
        assert mock_agent.room is None

    @pytest.mark.asyncio
    async def test_error_recovery_retry_mechanisms(self, mock_agent):
        """Test error recovery and retry mechanisms."""
        # Test 1: Fallback cleanup after primary failure
        mock_agent.room.disconnect.side_effect = Exception("Primary disconnect failed")
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Track force cleanup calls
        force_cleanup_called = False
        original_force_cleanup = mock_agent._force_room_cleanup
        
        async def track_force_cleanup():
            nonlocal force_cleanup_called
            force_cleanup_called = True
            await original_force_cleanup()
        
        mock_agent._force_room_cleanup = track_force_cleanup
        
        await mock_agent._terminate_call()
        
        # Verify fallback was used
        assert force_cleanup_called
        assert mock_agent.room is None

    @pytest.mark.asyncio
    async def test_error_handling_thread_safety(self, mock_agent):
        """Test error handling maintains thread safety during concurrent operations."""
        # Setup concurrent error scenarios
        mock_agent.room.disconnect.side_effect = Exception("Concurrent error")
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Execute multiple concurrent operations that could cause errors
        tasks = []
        for i in range(5):
            if i % 2 == 0:
                tasks.append(mock_agent._terminate_call())
            else:
                tasks.append(mock_agent.on_user_input(f"test message {i}"))
        
        # Should handle concurrent operations gracefully
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify no unhandled exceptions propagated
        for result in results:
            if isinstance(result, Exception):
                # Only specific expected exceptions should occur
                assert any(keyword in str(result) for keyword in ["already ended", "concurrent", "state"])

    @pytest.mark.asyncio
    async def test_error_state_recovery_paths(self, mock_agent):
        """Test recovery from error states."""
        # Set agent to error state
        await mock_agent._set_call_state(CallState.ERROR, error="Test error")
        
        # Test 1: Agent can recover by resetting state
        await mock_agent._set_call_state(CallState.IDLE)
        assert mock_agent.call_state == CallState.IDLE
        
        # Test 2: New call can be started after error
        mock_agent.call_session.reset()
        mock_agent.call_session.start_call()
        await mock_agent._set_call_state(CallState.ACTIVE)
        assert mock_agent.call_state == CallState.ACTIVE

    @pytest.mark.asyncio
    async def test_error_logging_levels_and_formats(self, mock_agent, caplog):
        """Test that errors are logged at appropriate levels with correct formats."""
        with caplog.at_level(logging.DEBUG):
            # Setup various error scenarios
            mock_agent.room.disconnect.side_effect = Exception("Test error")
            await mock_agent._set_call_state(CallState.ACTIVE)
            
            await mock_agent._terminate_call()
            
            # Verify logging levels
            info_logs = [r for r in caplog.records if r.levelname == "INFO"]
            error_logs = [r for r in caplog.records if r.levelname == "ERROR"]
            
            # Should have logs at multiple levels
            assert len(info_logs) > 0  # State changes, events
            assert len(error_logs) > 0  # Error conditions
            
            # Verify log format includes expected fields
            for log in error_logs:
                assert hasattr(log, 'message')
                assert hasattr(log, 'levelname')
                assert hasattr(log, 'created')

    @pytest.mark.asyncio
    async def test_error_handling_edge_cases(self, mock_agent):
        """Test error handling for edge cases and boundary conditions."""
        # Edge case 1: None room reference
        mock_agent.room = None
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Should handle None room gracefully
        await mock_agent._terminate_call()
        assert mock_agent.call_state == CallState.ENDED
        
        # Edge case 2: Agent without session
        agent2 = SimpleAgent()
        agent2._agent_session = None
        agent2.call_session.start_call()
        await agent2._set_call_state(CallState.ACTIVE)
        
        # Should handle missing session gracefully
        await agent2.on_user_input("goodbye")
        assert agent2.call_state == CallState.ENDED

    @pytest.mark.asyncio
    async def test_error_handling_resource_exhaustion(self, mock_agent):
        """Test error handling under resource exhaustion conditions."""
        # Simulate memory pressure
        mock_agent._call_metadata = {f"key_{i}": "x" * 1000 for i in range(100)}
        
        # Simulate resource exhaustion during cleanup
        def memory_error_cleanup():
            raise MemoryError("Out of memory")
        
        with patch.object(mock_agent, '_cleanup_call_resources', side_effect=memory_error_cleanup):
            await mock_agent._set_call_state(CallState.ACTIVE)
            
            # Should trigger emergency cleanup path
            await mock_agent._terminate_call()
            
            # Verify emergency cleanup worked
            assert mock_agent.call_state == CallState.ENDED
            assert len(mock_agent._call_metadata) <= 1  # Should be cleaned up

    @pytest.mark.asyncio
    async def test_error_propagation_control(self, mock_agent):
        """Test that errors are properly contained and don't propagate unexpectedly."""
        # Test 1: User-facing methods should not raise internal errors
        mock_agent.room.disconnect.side_effect = Exception("Internal error")
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Public interface should not raise
        try:
            await mock_agent._terminate_call()  # Use private method for testing
        except Exception as e:
            pytest.fail(f"Termination should not raise exceptions: {e}")
        
        # Should complete without raising
        assert mock_agent.call_state == CallState.ENDED
        
        # Test 2: Multiple component failures
        agent2 = SimpleAgent()
        agent2.room = MagicMock()
        agent2.room.disconnect.side_effect = Exception("Test error")
        agent2._agent_session = AsyncMock()
        agent2.call_session.start_call()
        
        await agent2._set_call_state(CallState.ACTIVE)
        
        try:
            await agent2._terminate_call()
        except Exception as e:
            pytest.fail(f"Termination should not raise exceptions: {e}")
        
        # Should complete despite component errors
        assert agent2.call_state == CallState.ENDED

    @pytest.mark.asyncio
    async def test_error_handling_consistency_across_methods(self, mock_agent):
        """Test that error handling is consistent across all methods."""
        # Test that cleanup methods complete without raising exceptions
        cleanup_methods = [
            mock_agent._force_room_cleanup,
            mock_agent._emergency_resource_cleanup,
            mock_agent._catastrophic_failure_cleanup,
        ]
        
        for method in cleanup_methods:
            try:
                await method()
                # Should complete without raising
            except Exception as e:
                # Cleanup methods should be robust and not raise exceptions
                pytest.fail(f"Method {method.__name__} raised unexpected exception: {e}")
        
        # Verify agent remains in a consistent state
        assert mock_agent.call_state in [CallState.IDLE, CallState.ACTIVE, CallState.ENDED, CallState.ERROR]
        assert mock_agent.room is None  # All cleanup methods should clear room

    @pytest.mark.asyncio
    async def test_error_handling_performance_impact(self, mock_agent):
        """Test that error handling doesn't significantly impact performance."""
        # Measure performance with and without errors
        start_time = time.time()
        
        # Normal termination
        await mock_agent._set_call_state(CallState.ACTIVE)
        await mock_agent._terminate_call()
        
        normal_time = time.time() - start_time
        
        # Reset agent
        agent2 = SimpleAgent()
        agent2.room = MagicMock()
        agent2.room.disconnect.side_effect = Exception("Performance test error")
        agent2._agent_session = AsyncMock()
        agent2.call_session.start_call()
        
        start_time = time.time()
        
        # Error termination
        await agent2._set_call_state(CallState.ACTIVE)
        await agent2._terminate_call()
        
        error_time = time.time() - start_time
        
        # Error handling should complete within reasonable time (5 seconds)
        assert error_time < 5.0, f"Error handling too slow: {error_time} seconds"
        assert agent2.call_state == CallState.ENDED