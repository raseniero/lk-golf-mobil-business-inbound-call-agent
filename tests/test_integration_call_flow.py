"""
Integration tests for complete call flow functionality.

This module tests end-to-end call scenarios including initialization,
state transitions, termination, and error recovery flows.
"""

import asyncio
import pytest
import logging
from unittest.mock import AsyncMock, MagicMock, patch
import time

from agent import SimpleAgent, CallState, CallSession
from utils import detect_termination_phrase


class TestIntegrationCallFlow:
    """Integration tests for complete call flow scenarios."""

    @pytest.fixture
    def mock_livekit_components(self):
        """Create mock LiveKit components for integration testing."""
        mock_room = MagicMock()
        mock_room.disconnect = AsyncMock()
        mock_room.remote_participants = []
        
        mock_session = AsyncMock()
        mock_session.generate_reply = AsyncMock()
        mock_session.say = AsyncMock()
        
        return {
            "room": mock_room,
            "session": mock_session
        }

    @pytest.mark.asyncio
    async def test_complete_call_lifecycle(self, mock_livekit_components):
        """Test complete call lifecycle from start to termination."""
        agent = SimpleAgent()
        agent.room = mock_livekit_components["room"]
        
        # Test 1: Initial state
        assert agent.call_state == CallState.IDLE
        assert agent.call_session.get_duration() is None
        
        # Test 2: Call start (simulate on_enter)
        await agent._set_call_state(CallState.RINGING)
        agent.call_session.start_call()
        agent._agent_session = mock_livekit_components["session"]
        await agent._set_call_state(CallState.ACTIVE)
        
        assert agent.call_state == CallState.ACTIVE
        assert agent.call_session.start_time is not None
        
        # Test 3: Process normal user input
        await agent.on_user_input("Hello, I need help with something")
        mock_livekit_components["session"].generate_reply.assert_called()
        
        # Test 4: Process termination phrase
        await agent.on_user_input("goodbye")
        
        # Verify termination sequence
        mock_livekit_components["session"].say.assert_called()  # Immediate response
        assert agent.call_state == CallState.ENDED
        assert agent.call_session.get_duration() is not None
        assert agent.room is None

    @pytest.mark.asyncio
    async def test_call_flow_with_multiple_participants(self, mock_livekit_components):
        """Test call flow when multiple participants are present."""
        agent = SimpleAgent()
        
        # Setup room with multiple participants
        mock_participants = [MagicMock(), MagicMock(), MagicMock()]
        mock_livekit_components["room"].remote_participants = mock_participants
        agent.room = mock_livekit_components["room"]
        
        # Start call
        agent.call_session.start_call()
        await agent._set_call_state(CallState.ACTIVE)
        agent._agent_session = mock_livekit_components["session"]
        
        # Terminate call
        await agent.on_user_input("end call")
        
        # Verify proper handling with multiple participants
        assert agent.call_state == CallState.ENDED
        assert agent.room is None
        mock_livekit_components["room"].disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_flow_error_recovery(self, mock_livekit_components):
        """Test call flow error recovery scenarios."""
        agent = SimpleAgent()
        agent.room = mock_livekit_components["room"]
        agent._agent_session = mock_livekit_components["session"]
        
        # Start call
        agent.call_session.start_call()
        await agent._set_call_state(CallState.ACTIVE)
        
        # Simulate room disconnect error
        mock_livekit_components["room"].disconnect.side_effect = Exception("Connection failed")
        
        # Attempt termination
        await agent.on_user_input("goodbye")
        
        # Verify error recovery
        assert agent.call_state == CallState.ENDED  # Should still complete
        assert agent.room is None  # Room should be cleared despite error
        warnings = agent.call_metadata.get("warnings", {})
        assert "room_disconnect" in warnings

    @pytest.mark.asyncio
    async def test_state_transitions_integration(self, mock_livekit_components):
        """Test complete state transition flow."""
        agent = SimpleAgent()
        agent.room = mock_livekit_components["room"]
        
        # Track state changes
        state_history = []
        
        original_set_state = agent._set_call_state
        async def track_state_change(new_state, **metadata):
            state_history.append((new_state, metadata))
            await original_set_state(new_state, **metadata)
        
        agent._set_call_state = track_state_change
        
        # Execute full call flow
        await agent._set_call_state(CallState.RINGING)
        agent.call_session.start_call()
        await agent._set_call_state(CallState.ACTIVE)
        agent._agent_session = mock_livekit_components["session"]
        
        # Process termination
        await agent.on_user_input("that's all")
        
        # Verify state progression
        expected_states = [CallState.RINGING, CallState.ACTIVE, CallState.TERMINATING, CallState.ENDED]
        actual_states = [state for state, _ in state_history]
        
        assert CallState.RINGING in actual_states
        assert CallState.ACTIVE in actual_states
        assert CallState.TERMINATING in actual_states
        assert CallState.ENDED in actual_states

    @pytest.mark.asyncio
    async def test_call_flow_with_session_errors(self, mock_livekit_components):
        """Test call flow when session operations fail."""
        agent = SimpleAgent()
        agent.room = mock_livekit_components["room"]
        
        # Setup session with errors
        mock_session = mock_livekit_components["session"]
        mock_session.say.side_effect = Exception("TTS failed")
        mock_session.generate_reply.side_effect = Exception("LLM failed")
        
        agent._agent_session = mock_session
        agent.call_session.start_call()
        await agent._set_call_state(CallState.ACTIVE)
        
        # Test normal input with session error
        await agent.on_user_input("Hello")
        # Should handle gracefully despite LLM error
        
        # Test termination with session error
        await agent.on_user_input("goodbye")
        # Should still terminate despite TTS error
        
        assert agent.call_state == CallState.ENDED

    @pytest.mark.asyncio
    async def test_call_flow_timing_and_duration(self, mock_livekit_components):
        """Test call flow timing and duration tracking."""
        agent = SimpleAgent()
        agent.room = mock_livekit_components["room"]
        agent._agent_session = mock_livekit_components["session"]
        
        # Start call and record time
        start_time = time.time()
        agent.call_session.start_call()
        await agent._set_call_state(CallState.ACTIVE)
        
        # Simulate some call activity
        await asyncio.sleep(0.1)  # Small delay to ensure measurable duration
        await agent.on_user_input("How are you?")
        await asyncio.sleep(0.1)
        
        # Terminate call
        await agent.on_user_input("bye")
        end_time = time.time()
        
        # Verify timing
        duration = agent.call_session.get_duration()
        assert duration is not None
        assert duration > 0
        assert duration <= (end_time - start_time)
        
        # Verify duration classification
        classification = agent.call_session.get_call_classification()
        assert classification == "short"  # Should be less than 30 seconds

    @pytest.mark.asyncio
    async def test_call_flow_state_consistency(self, mock_livekit_components):
        """Test state consistency throughout call flow."""
        agent = SimpleAgent()
        agent.room = mock_livekit_components["room"]
        agent._agent_session = mock_livekit_components["session"]
        
        # Start call
        agent.call_session.start_call()
        await agent._set_call_state(CallState.ACTIVE)
        
        # Verify initial active state
        assert agent.call_state == CallState.ACTIVE
        assert agent.room is not None
        assert agent._agent_session is not None
        
        # Process multiple inputs
        inputs = ["Hello", "How can you help me?", "What services do you offer?"]
        for user_input in inputs:
            await agent.on_user_input(user_input)
            # State should remain active
            assert agent.call_state == CallState.ACTIVE
        
        # Terminate call
        await agent.on_user_input("thank you")
        
        # Verify final state consistency
        assert agent.call_state == CallState.ENDED
        assert agent.room is None
        assert agent.is_speaking is False
        assert agent.is_listening is False

    @pytest.mark.asyncio
    async def test_call_flow_cleanup_verification(self, mock_livekit_components):
        """Test that call flow properly cleans up resources."""
        agent = SimpleAgent()
        agent.room = mock_livekit_components["room"]
        agent._agent_session = mock_livekit_components["session"]
        
        # Set up call with various resources
        agent.call_session.start_call()
        await agent._set_call_state(CallState.ACTIVE)
        agent.is_speaking = True
        agent.is_listening = True
        agent._call_metadata = {"test_data": "value"}
        
        # Store references for verification
        original_room = agent.room
        original_session = agent._agent_session
        
        # Terminate call
        await agent.on_user_input("goodbye")
        
        # Verify comprehensive cleanup
        assert agent.room is None
        # Note: _agent_session is not cleared in normal termination, only in emergency cleanup
        assert agent.is_speaking is False
        assert agent.is_listening is False
        assert agent._call_metadata == {}
        assert agent.call_state == CallState.ENDED
        
        # Verify disconnect was called on original room
        original_room.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_flow_with_non_termination_input(self, mock_livekit_components):
        """Test call flow continues normally with non-termination input."""
        agent = SimpleAgent()
        agent.room = mock_livekit_components["room"]
        agent._agent_session = mock_livekit_components["session"]
        
        # Start call
        agent.call_session.start_call()
        await agent._set_call_state(CallState.ACTIVE)
        
        # Process various non-termination inputs
        non_termination_inputs = [
            "Hello there",
            "I need help",
            "What can you do?",
            "Tell me about your services",
            "How much does it cost?",
            "When are you available?"
        ]
        
        for user_input in non_termination_inputs:
            await agent.on_user_input(user_input)
            
            # Verify call continues
            assert agent.call_state == CallState.ACTIVE
            assert agent.room is not None
            assert agent._agent_session is not None
            
            # Verify generate_reply was called
            mock_livekit_components["session"].generate_reply.assert_called()

    @pytest.mark.asyncio
    async def test_call_flow_with_empty_input(self, mock_livekit_components):
        """Test call flow handles empty or whitespace input gracefully."""
        agent = SimpleAgent()
        agent.room = mock_livekit_components["room"]
        agent._agent_session = mock_livekit_components["session"]
        
        # Start call
        agent.call_session.start_call()
        await agent._set_call_state(CallState.ACTIVE)
        
        # Reset mock call count
        mock_livekit_components["session"].generate_reply.reset_mock()
        
        # Process empty/whitespace inputs
        empty_inputs = ["", "   ", "\n", "\t", None]
        
        for user_input in empty_inputs:
            await agent.on_user_input(user_input)
            
            # Verify call state unchanged
            assert agent.call_state == CallState.ACTIVE
        
        # Verify generate_reply was not called for empty inputs
        mock_livekit_components["session"].generate_reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_call_flow_integration_with_phrase_detection(self, mock_livekit_components):
        """Test integration between call flow and phrase detection utility."""
        agent = SimpleAgent()
        agent.room = mock_livekit_components["room"]
        agent._agent_session = mock_livekit_components["session"]
        
        # Start call
        agent.call_session.start_call()
        await agent._set_call_state(CallState.ACTIVE)
        
        # Test phrase detection integration
        test_cases = [
            ("I want to say goodbye now", "goodbye"),
            ("Please end call", "end call"),
            ("That's all for today", "that's all"),
            ("Thank you very much", "thank you"),
            ("bye bye", "bye")
        ]
        
        for user_input, expected_phrase in test_cases:
            # Reset agent state
            await agent._set_call_state(CallState.ACTIVE)
            agent.room = mock_livekit_components["room"]
            agent._agent_session = mock_livekit_components["session"]
            
            # Test phrase detection
            detected = detect_termination_phrase(user_input, agent.termination_phrases)
            assert detected == expected_phrase
            
            # Test full flow
            await agent.on_user_input(user_input)
            assert agent.call_state == CallState.ENDED

    @pytest.mark.asyncio
    async def test_call_flow_error_logging_integration(self, mock_livekit_components, caplog):
        """Test integration of error logging throughout call flow."""
        with caplog.at_level(logging.INFO):
            agent = SimpleAgent()
            agent.room = mock_livekit_components["room"]
            agent._agent_session = mock_livekit_components["session"]
            
            # Make room disconnect fail to trigger error logging
            mock_livekit_components["room"].disconnect.side_effect = Exception("Test error")
            
            # Execute call flow
            agent.call_session.start_call()
            await agent._set_call_state(CallState.ACTIVE)
            await agent.on_user_input("goodbye")
            
            # Verify comprehensive logging
            log_messages = [record.message for record in caplog.records]
            
            # Should have state change logs
            assert any("Call state changed" in msg for msg in log_messages)
            
            # Should have termination event logs
            assert any("PHRASE_DETECTED" in msg for msg in log_messages)
            assert any("CALL_TERMINATION" in msg for msg in log_messages)
            
            # Should have error logs
            error_logs = [record for record in caplog.records if record.levelname == "ERROR"]
            assert len(error_logs) > 0

    @pytest.mark.asyncio
    async def test_concurrent_call_operations(self, mock_livekit_components):
        """Test concurrent operations during call flow."""
        agent = SimpleAgent()
        agent.room = mock_livekit_components["room"]
        agent._agent_session = mock_livekit_components["session"]
        
        # Start call
        agent.call_session.start_call()
        await agent._set_call_state(CallState.ACTIVE)
        
        # Execute concurrent user inputs (should be handled sequentially)
        inputs = ["Hello", "How are you?", "What services?", "goodbye"]
        
        # Execute inputs concurrently
        tasks = [agent.on_user_input(user_input) for user_input in inputs]
        await asyncio.gather(*tasks)
        
        # Verify final state is consistent
        assert agent.call_state == CallState.ENDED
        assert agent.room is None

    @pytest.mark.asyncio
    async def test_call_flow_memory_management(self, mock_livekit_components):
        """Test memory management throughout call flow."""
        agent = SimpleAgent()
        agent.room = mock_livekit_components["room"]
        agent._agent_session = mock_livekit_components["session"]
        
        # Start call and add metadata
        agent.call_session.start_call()
        await agent._set_call_state(CallState.ACTIVE)
        
        # Simulate accumulating call data
        for i in range(10):
            agent._call_metadata[f"data_{i}"] = f"value_{i}" * 100  # Some data
            await agent.on_user_input(f"Message {i}")
        
        # Verify data accumulation
        assert len(agent._call_metadata) > 0
        
        # Terminate call
        await agent.on_user_input("goodbye")
        
        # Verify memory cleanup
        assert agent._call_metadata == {}
        assert agent.room is None
        # Note: _agent_session is preserved in normal termination