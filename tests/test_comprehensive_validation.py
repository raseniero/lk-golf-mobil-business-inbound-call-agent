"""
Comprehensive validation test suite.

This module performs a final comprehensive validation of all implemented
features including call termination, error handling, logging, and state
management.
"""

import asyncio
import pytest
import logging
from unittest.mock import AsyncMock, MagicMock, patch
import time

from agent import SimpleAgent, CallState
from utils import detect_termination_phrase


class TestComprehensiveValidation:
    """Comprehensive validation of all implemented features."""

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
    async def test_complete_call_lifecycle(self, mock_agent):
        """Test a complete call lifecycle from start to end."""
        # Start call
        await mock_agent._set_call_state(CallState.IDLE)
        assert mock_agent.call_state == CallState.IDLE
        
        # Answer call
        await mock_agent._set_call_state(CallState.ACTIVE)
        assert mock_agent.call_state == CallState.ACTIVE
        assert mock_agent.call_session.start_time is not None
        
        # Process user input
        await mock_agent.on_user_input("Hello, how are you?")
        assert mock_agent.call_state == CallState.ACTIVE
        
        # Terminate call with phrase
        await mock_agent.on_user_input("goodbye")
        assert mock_agent.call_state == CallState.ENDED
        assert mock_agent.call_session.end_time is not None
        assert mock_agent.room is None

    @pytest.mark.asyncio
    async def test_error_recovery_comprehensive(self, mock_agent):
        """Test comprehensive error recovery across all failure modes."""
        # Setup multiple failure points
        mock_agent.room.disconnect.side_effect = Exception("Room disconnect failed")
        mock_agent.call_session.end_call = MagicMock(side_effect=Exception("Session end failed"))
        
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Execute termination with multiple failures
        await mock_agent._terminate_call()
        
        # Verify recovery was successful
        assert mock_agent.call_state == CallState.ENDED
        assert mock_agent.room is None
        warnings = mock_agent.call_metadata.get("warnings", {})
        assert len(warnings) >= 2  # At least 2 warnings for 2 failures

    @pytest.mark.asyncio
    async def test_logging_completeness(self, mock_agent, caplog):
        """Test that all critical events are logged correctly."""
        with caplog.at_level(logging.INFO):
            # Complete call flow
            await mock_agent._set_call_state(CallState.ACTIVE)
            await mock_agent.on_user_input("goodbye")
            
            # Verify all key events were logged
            log_messages = [record.message for record in caplog.records]
            
            # Check for key log events
            assert any("Call state changed" in msg for msg in log_messages)
            assert any("PHRASE_DETECTED" in msg for msg in log_messages)
            assert any("TERMINATION_INITIATED" in msg for msg in log_messages)
            assert any("CALL_TERMINATION" in msg for msg in log_messages)
            assert any("CALL_TERMINATED" in msg for msg in log_messages)

    @pytest.mark.asyncio
    async def test_state_consistency_under_stress(self, mock_agent):
        """Test state consistency under concurrent operations."""
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Simulate concurrent operations
        tasks = []
        for i in range(10):
            if i % 3 == 0:
                tasks.append(mock_agent.on_user_input(f"message {i}"))
            elif i % 3 == 1:
                tasks.append(mock_agent._set_call_state(CallState.ACTIVE))
            else:
                tasks.append(mock_agent.on_user_input("goodbye"))
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify final state is consistent
        assert mock_agent.call_state in [CallState.ENDED, CallState.ACTIVE]
        
        # If ended, verify proper cleanup
        if mock_agent.call_state == CallState.ENDED:
            assert mock_agent.room is None

    @pytest.mark.asyncio
    async def test_phrase_detection_accuracy(self, mock_agent):
        """Test phrase detection accuracy across various inputs."""
        # Test cases with expected results
        test_cases = [
            ("goodbye", True),
            ("thank you", True),
            ("bye", True),
            ("thanks", False),  # Not in default phrases
            ("Good bye", True),
            ("GOODBYE", True),
            ("hello goodbye", True),
            ("goodbye friend", True),
            ("hello", False),
            ("good morning", False),
            ("", False),
        ]
        
        for phrase, expected in test_cases:
            result = detect_termination_phrase(phrase, mock_agent.termination_phrases)
            # detect_termination_phrase returns the phrase if found, None otherwise
            actual = result is not None
            assert actual == expected, f"Failed for phrase: '{phrase}' - got {result}"

    @pytest.mark.asyncio
    async def test_resource_cleanup_verification(self, mock_agent):
        """Verify all resources are properly cleaned up."""
        # Setup agent with resources
        mock_agent._call_metadata = {"test": "data", "more": "data"}
        mock_agent.room = MagicMock()
        mock_agent._agent_session = AsyncMock()
        
        await mock_agent._set_call_state(CallState.ACTIVE)
        
        # Terminate and verify cleanup
        await mock_agent._terminate_call()
        
        # Verify resources are cleaned
        assert mock_agent.room is None
        # Agent session is cleared in emergency cleanup
        assert len(mock_agent._call_metadata) <= 1  # Only warnings if any

    @pytest.mark.asyncio
    async def test_performance_benchmarks(self, mock_agent):
        """Test performance benchmarks for critical operations."""
        # Benchmark 1: State transition speed
        start = time.time()
        for _ in range(100):
            await mock_agent._set_call_state(CallState.ACTIVE)
        state_time = time.time() - start
        assert state_time < 0.1, f"State transitions too slow: {state_time}s for 100 transitions"
        
        # Benchmark 2: Phrase detection speed
        start = time.time()
        for _ in range(1000):
            detect_termination_phrase("hello goodbye thank you", mock_agent.termination_phrases)
        detect_time = time.time() - start
        assert detect_time < 0.1, f"Phrase detection too slow: {detect_time}s for 1000 checks"
        
        # Benchmark 3: Termination speed
        start = time.time()
        await mock_agent._terminate_call()
        term_time = time.time() - start
        assert term_time < 1.0, f"Termination too slow: {term_time}s"

    @pytest.mark.asyncio
    async def test_edge_case_handling(self, mock_agent):
        """Test handling of various edge cases."""
        # Edge case 1: Double termination
        await mock_agent._set_call_state(CallState.ACTIVE)
        await mock_agent._terminate_call()
        
        # Second termination should be handled gracefully
        await mock_agent._terminate_call()
        assert mock_agent.call_state == CallState.ENDED
        
        # Edge case 2: Termination from non-active state
        agent2 = SimpleAgent()
        await agent2._terminate_call()
        assert agent2.call_state == CallState.ENDED
        
        # Edge case 3: User input on ended call
        await mock_agent.on_user_input("hello")
        assert mock_agent.call_state == CallState.ENDED

    @pytest.mark.asyncio
    async def test_integration_with_all_components(self, mock_agent):
        """Test integration between all components."""
        # Setup comprehensive mocking
        with patch('agent.logger') as mock_logger:
            # Execute full call flow
            await mock_agent._set_call_state(CallState.ACTIVE)
            
            # Simulate various user inputs
            await mock_agent.on_user_input("Hello")
            await mock_agent.on_user_input("How are you?")
            await mock_agent.on_user_input("Thank you, goodbye")
            
            # Verify complete integration
            assert mock_agent.call_state == CallState.ENDED
            assert mock_agent.room is None
            assert mock_logger.info.called
            
            # Verify proper event sequence in logs
            call_args = [call[0][0] for call in mock_logger.info.call_args_list]
            assert any("PHRASE_DETECTED" in str(arg) for arg in call_args)
            assert any("CALL_TERMINATED" in str(arg) for arg in call_args)

    @pytest.mark.asyncio
    async def test_final_validation_checklist(self, mock_agent):
        """Final validation checklist for all requirements."""
        # ✓ Call state management
        assert hasattr(mock_agent, 'call_state')
        assert hasattr(mock_agent, '_set_call_state')
        
        # ✓ Error handling methods
        assert hasattr(mock_agent, '_force_room_cleanup')
        assert hasattr(mock_agent, '_emergency_resource_cleanup')
        assert hasattr(mock_agent, '_catastrophic_failure_cleanup')
        
        # ✓ Termination functionality
        assert hasattr(mock_agent, '_terminate_call')
        assert hasattr(mock_agent, 'on_user_input')
        
        # ✓ Call session tracking
        assert hasattr(mock_agent.call_session, 'start_call')
        assert hasattr(mock_agent.call_session, 'end_call')
        assert hasattr(mock_agent.call_session, 'get_duration')
        
        # ✓ Phrase detection utility
        # detect_termination_phrase returns the phrase if found, None otherwise
        result = detect_termination_phrase("goodbye", mock_agent.termination_phrases)
        assert result is not None
        
        # Execute final comprehensive test
        await mock_agent._set_call_state(CallState.ACTIVE)
        await mock_agent.on_user_input("Thank you and goodbye!")
        
        # Final assertions
        assert mock_agent.call_state == CallState.ENDED
        assert mock_agent.room is None
        assert mock_agent.call_session.end_time is not None
        duration = mock_agent.call_session.get_duration()
        assert duration >= 0