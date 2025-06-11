"""Test suite for call termination logic implementation."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from agent import SimpleAgent, CallState


class TestCallTerminationLogic:
    """Test cases for call termination logic implementation."""
    
    def setup_method(self):
        """Set up test data and mock agent."""
        self.agent = SimpleAgent()
        
        # Mock the session and room
        self.mock_session = MagicMock()
        self.mock_session.generate_reply = AsyncMock()
        self.mock_session.say = AsyncMock()
        
        self.mock_room = MagicMock()
        self.mock_room.disconnect = AsyncMock()
        
        # Set up agent state
        self.agent._agent_session = self.mock_session
        self.agent.room = self.mock_room
    
    @pytest.mark.asyncio
    async def test_terminate_call_method_exists(self):
        """Test that _terminate_call method exists."""
        assert hasattr(self.agent, '_terminate_call')
        assert callable(getattr(self.agent, '_terminate_call'))
    
    @pytest.mark.asyncio
    async def test_terminate_call_basic_flow(self):
        """Test basic _terminate_call method flow."""
        # Set up initial state
        self.agent._call_state = CallState.ACTIVE
        self.agent.call_session.start_call()  # Start timing first
        
        # Call the method
        await self.agent._terminate_call()
        
        # Verify state changes
        assert self.agent._call_state == CallState.ENDED
        
        # Verify call session ended
        assert self.agent.call_session.end_time is not None
    
    @pytest.mark.asyncio
    async def test_terminate_call_already_ended(self):
        """Test _terminate_call when call is already ended."""
        # Set state to already ended
        self.agent._call_state = CallState.ENDED
        
        # Should not raise exception and return early
        await self.agent._terminate_call()
        
        # State should remain ended
        assert self.agent._call_state == CallState.ENDED
    
    @pytest.mark.asyncio
    async def test_terminate_call_sets_terminating_state(self):
        """Test that _terminate_call sets TERMINATING state during process."""
        self.agent._call_state = CallState.ACTIVE
        
        # Track state changes
        state_changes = []
        original_set_state = self.agent._set_call_state
        
        async def track_state_changes(new_state, **kwargs):
            state_changes.append(new_state)
            await original_set_state(new_state, **kwargs)
        
        self.agent._set_call_state = track_state_changes
        
        await self.agent._terminate_call()
        
        # Should transition through TERMINATING to ENDED
        assert CallState.TERMINATING in state_changes
        assert CallState.ENDED in state_changes
    
    @pytest.mark.asyncio
    async def test_terminate_call_error_handling(self):
        """Test error handling in _terminate_call method."""
        self.agent._call_state = CallState.ACTIVE
        
        # Mock an error during termination
        self.mock_room.disconnect = AsyncMock(side_effect=Exception("Disconnect failed"))
        
        # Should handle error gracefully
        await self.agent._terminate_call()
        
        # Should still end up in ENDED state despite error
        assert self.agent._call_state == CallState.ENDED
    
    @pytest.mark.asyncio
    async def test_terminate_call_cleanup_resources(self):
        """Test that _terminate_call properly cleans up resources."""
        self.agent._call_state = CallState.ACTIVE
        self.agent.is_speaking = True
        self.agent.is_listening = True
        
        await self.agent._terminate_call()
        
        # Verify cleanup occurred
        assert not self.agent.is_speaking
        assert not self.agent.is_listening
    
    @pytest.mark.asyncio
    async def test_terminate_call_logs_duration(self):
        """Test that _terminate_call logs call duration."""
        self.agent._call_state = CallState.ACTIVE
        self.agent.call_session.start_call()  # Start timing
        
        with patch('agent.logger') as mock_logger:
            await self.agent._terminate_call()
            
            # Verify duration was logged
            assert any('duration' in str(call) for call in mock_logger.info.call_args_list)
    
    @pytest.mark.asyncio
    async def test_terminate_call_room_disconnect(self):
        """Test that _terminate_call disconnects from room."""
        self.agent._call_state = CallState.ACTIVE
        
        await self.agent._terminate_call()
        
        # Verify room disconnect was called
        self.mock_room.disconnect.assert_called_once()
    
    @pytest.mark.asyncio 
    async def test_terminate_call_no_room(self):
        """Test _terminate_call when no room is available."""
        self.agent._call_state = CallState.ACTIVE
        self.agent.room = None
        
        # Should not raise exception
        await self.agent._terminate_call()
        
        # Should still transition to ENDED
        assert self.agent._call_state == CallState.ENDED


class TestCallDisconnectionLogic:
    """Test cases specifically for call disconnection logic."""
    
    def setup_method(self):
        """Set up test data and mock agent."""
        self.agent = SimpleAgent()
        
        # Mock the session and room
        self.mock_session = MagicMock()
        self.mock_session.generate_reply = AsyncMock()
        self.mock_session.say = AsyncMock()
        
        self.mock_room = MagicMock()
        self.mock_room.disconnect = AsyncMock()
        self.mock_room.local_participant = MagicMock()
        
        # Set up agent state
        self.agent._agent_session = self.mock_session
        self.agent.room = self.mock_room
    
    @pytest.mark.asyncio
    async def test_disconnect_with_participants(self):
        """Test disconnection when other participants are present."""
        self.agent._call_state = CallState.ACTIVE
        self.agent.call_session.start_call()
        
        # Mock participants
        mock_participant1 = MagicMock()
        mock_participant1.identity = "user1"
        mock_participant2 = MagicMock() 
        mock_participant2.identity = "user2"
        
        self.mock_room.remote_participants = {
            "user1": mock_participant1,
            "user2": mock_participant2
        }
        
        await self.agent._terminate_call()
        
        # Verify room disconnect was called
        self.mock_room.disconnect.assert_called_once()
        assert self.agent._call_state == CallState.ENDED
    
    @pytest.mark.asyncio
    async def test_disconnect_timeout_handling(self):
        """Test handling of disconnect timeout."""
        self.agent._call_state = CallState.ACTIVE
        self.agent.call_session.start_call()
        
        # Mock disconnect taking too long
        async def slow_disconnect():
            await asyncio.sleep(0.1)  # Simulate slow disconnect
            
        self.mock_room.disconnect = slow_disconnect
        
        # Should still complete successfully
        await self.agent._terminate_call()
        
        assert self.agent._call_state == CallState.ENDED
    
    @pytest.mark.asyncio
    async def test_disconnect_failure_recovery(self):
        """Test graceful handling when disconnect fails."""
        self.agent._call_state = CallState.ACTIVE
        self.agent.call_session.start_call()
        
        # Mock disconnect failure
        self.mock_room.disconnect = AsyncMock(side_effect=Exception("Connection lost"))
        
        # Should handle gracefully and still clean up
        await self.agent._terminate_call()
        
        # Should still end in ENDED state despite disconnect failure
        assert self.agent._call_state == CallState.ENDED
    
    @pytest.mark.asyncio
    async def test_multiple_disconnect_calls(self):
        """Test that multiple disconnect calls are handled gracefully."""
        self.agent._call_state = CallState.ACTIVE
        self.agent.call_session.start_call()
        
        # Call disconnect multiple times
        await self.agent._terminate_call()
        first_state = self.agent._call_state
        
        # Second call should be ignored
        await self.agent._terminate_call() 
        second_state = self.agent._call_state
        
        assert first_state == CallState.ENDED
        assert second_state == CallState.ENDED
        # Room disconnect should only be called once from first termination
        self.mock_room.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_disconnect_cleans_session_references(self):
        """Test that disconnection cleans up session references."""
        self.agent._call_state = CallState.ACTIVE
        self.agent.call_session.start_call()
        self.agent._agent_session = self.mock_session
        
        await self.agent._terminate_call()
        
        # Verify cleanup occurred
        assert not self.agent.is_speaking
        assert not self.agent.is_listening
        # Session reference should still exist for proper cleanup
        assert self.agent._agent_session is not None


class TestImmediateTerminationResponse:
    """Test cases for immediate response to termination phrases."""
    
    def setup_method(self):
        """Set up test data and mock agent."""
        self.agent = SimpleAgent()
        
        # Mock the session and room
        self.mock_session = MagicMock()
        self.mock_session.generate_reply = AsyncMock()
        self.mock_session.say = AsyncMock()
        
        self.mock_room = MagicMock()
        self.mock_room.disconnect = AsyncMock()
        
        # Set up agent state
        self.agent._agent_session = self.mock_session
        self.agent.room = self.mock_room
        self.agent._call_state = CallState.ACTIVE
    
    @pytest.mark.asyncio
    async def test_immediate_acknowledgment_on_termination(self):
        """Test that agent immediately acknowledges termination phrases."""
        self.agent.call_session.start_call()
        
        # Process a termination phrase
        await self.agent.on_user_input("goodbye everyone")
        
        # Verify immediate response was triggered
        self.mock_session.say.assert_called_once()
        
        # Verify the response was appropriate (should contain acknowledgment)
        call_args = self.mock_session.say.call_args[0][0]
        assert "goodbye" in call_args.lower() or "bye" in call_args.lower()
    
    @pytest.mark.asyncio
    async def test_different_termination_phrases_get_appropriate_responses(self):
        """Test that different termination phrases get contextual responses."""
        test_cases = [
            ("thank you for your help", "welcome"),  # "You're welcome!"
            ("that's all I need", "understood"),     # "Understood"
            ("end call please", "ending"),           # "Ending the call"
            ("goodbye", "goodbye")                   # "Goodbye!"
        ]
        
        for input_phrase, expected_word in test_cases:
            # Reset mocks
            self.mock_session.say.reset_mock()
            self.agent._call_state = CallState.ACTIVE
            self.agent.call_session.start_call()
            
            # Process termination phrase
            await self.agent.on_user_input(input_phrase)
            
            # Verify response was given
            self.mock_session.say.assert_called_once()
            
            # Verify response is contextual
            response = self.mock_session.say.call_args[0][0].lower()
            assert expected_word in response or "goodbye" in response
    
    @pytest.mark.asyncio
    async def test_immediate_response_before_termination(self):
        """Test that immediate response happens before call termination."""
        self.agent.call_session.start_call()
        
        # Track the order of operations
        operations = []
        
        # Mock say to track when it's called
        async def track_say(message):
            operations.append("say_response")
            
        # Mock disconnect to track when termination starts
        async def track_disconnect():
            operations.append("disconnect")
            
        self.mock_session.say = track_say
        self.mock_room.disconnect = track_disconnect
        
        # Process termination phrase
        await self.agent.on_user_input("goodbye")
        
        # Verify say happened before disconnect
        assert "say_response" in operations
        assert "disconnect" in operations
        assert operations.index("say_response") < operations.index("disconnect")
    
    @pytest.mark.asyncio
    async def test_no_immediate_response_for_non_termination_phrases(self):
        """Test that non-termination phrases don't trigger immediate responses."""
        # Process a regular phrase
        await self.agent.on_user_input("hello there")
        
        # Verify no immediate response (say) was called
        self.mock_session.say.assert_not_called()
        
        # But generate_reply should still be called for regular processing
        self.mock_session.generate_reply.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_immediate_response_error_handling(self):
        """Test error handling in immediate response generation."""
        self.agent.call_session.start_call()
        
        # Mock say to raise an error
        self.mock_session.say = AsyncMock(side_effect=Exception("TTS error"))
        
        # Should not crash even if immediate response fails
        await self.agent.on_user_input("goodbye")
        
        # Verify termination still proceeded
        assert self.agent._call_state == CallState.ENDED
    
    @pytest.mark.asyncio
    async def test_immediate_response_timing(self):
        """Test that immediate response is fast and doesn't delay termination."""
        import time
        self.agent.call_session.start_call()
        
        start_time = time.time()
        await self.agent.on_user_input("goodbye")
        end_time = time.time()
        
        # Entire process should complete quickly (under 1 second in tests)
        total_time = end_time - start_time
        assert total_time < 1.0
        
        # Verify both response and termination happened
        self.mock_session.say.assert_called_once()
        assert self.agent._call_state == CallState.ENDED


class TestCallTerminationFlow:
    """Test cases for end-to-end call termination flow integration."""
    
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
    async def test_complete_termination_flow_with_goodbye(self):
        """Test complete termination flow from phrase detection to disconnection."""
        self.agent.call_session.start_call()
        
        # Track all operations in order
        operations = []
        
        async def track_say(message):
            operations.append(f"say: {message}")
            
        async def track_disconnect():
            operations.append("disconnect")
            
        def track_state_change(new_state, **kwargs):
            operations.append(f"state: {new_state.name}")
            
        self.mock_session.say = track_say
        self.mock_room.disconnect = track_disconnect
        
        # Monkey patch state change tracking
        original_set_state = self.agent._set_call_state
        
        async def tracked_set_state(new_state, **kwargs):
            track_state_change(new_state, **kwargs)
            await original_set_state(new_state, **kwargs)
            
        self.agent._set_call_state = tracked_set_state
        
        # Execute complete flow
        await self.agent.on_user_input("goodbye everyone")
        
        # Verify complete flow happened in correct order
        assert len(operations) >= 4
        
        # Should start with immediate response
        assert operations[0].startswith("say:")
        assert "goodbye" in operations[0].lower()
        
        # Should transition through states
        assert "state: TERMINATING" in operations
        assert "state: ENDED" in operations
        
        # Should disconnect from room
        assert "disconnect" in operations
        
        # Verify final state
        assert self.agent._call_state == CallState.ENDED
    
    @pytest.mark.asyncio
    async def test_termination_flow_with_multiple_participants(self):
        """Test termination flow when other participants are in the call."""
        self.agent.call_session.start_call()
        
        # Mock multiple participants
        self.mock_room.remote_participants = {
            "user1": MagicMock(identity="user1"),
            "user2": MagicMock(identity="user2")
        }
        
        # Execute termination
        await self.agent.on_user_input("that's all for today")
        
        # Verify immediate response
        self.mock_session.say.assert_called_once()
        response = self.mock_session.say.call_args[0][0]
        assert "understood" in response.lower()
        
        # Verify disconnect happened
        self.mock_room.disconnect.assert_called_once()
        
        # Verify final state
        assert self.agent._call_state == CallState.ENDED
    
    @pytest.mark.asyncio
    async def test_termination_flow_error_recovery(self):
        """Test termination flow handles errors gracefully."""
        self.agent.call_session.start_call()
        
        # Mock various errors
        self.mock_session.say = AsyncMock(side_effect=Exception("TTS failed"))
        self.mock_room.disconnect = AsyncMock(side_effect=Exception("Disconnect failed"))
        
        # Should handle errors gracefully
        await self.agent.on_user_input("end call")
        
        # Should still reach ENDED state despite errors
        assert self.agent._call_state == CallState.ENDED
        
        # Should still attempt both operations
        self.mock_session.say.assert_called_once()
        self.mock_room.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_termination_flow_timing_and_duration(self):
        """Test that termination flow properly tracks call duration."""
        import time
        
        # Start call with some delay
        self.agent.call_session.start_call()
        await asyncio.sleep(0.01)  # Small delay to ensure measurable duration
        
        start_time = time.time()
        await self.agent.on_user_input("thank you")
        end_time = time.time()
        
        # Verify duration was calculated
        duration = self.agent.call_session.get_duration()
        assert duration is not None
        assert duration > 0
        
        # Verify termination was reasonably fast
        termination_time = end_time - start_time
        assert termination_time < 0.5  # Should complete in under 500ms
        
        # Verify final state
        assert self.agent._call_state == CallState.ENDED
    
    @pytest.mark.asyncio
    async def test_termination_flow_state_consistency(self):
        """Test that termination flow maintains consistent state throughout."""
        self.agent.call_session.start_call()
        
        # Track state changes
        states = []
        original_set_state = self.agent._set_call_state
        
        async def track_states(new_state, **kwargs):
            states.append(new_state)
            await original_set_state(new_state, **kwargs)
            
        self.agent._set_call_state = track_states
        
        # Execute termination
        await self.agent.on_user_input("bye")
        
        # Verify state progression
        assert CallState.TERMINATING in states
        assert CallState.ENDED in states
        
        # Verify no duplicate states
        terminating_count = states.count(CallState.TERMINATING)
        ended_count = states.count(CallState.ENDED)
        assert terminating_count == 1
        assert ended_count == 1
        
        # Verify final state
        assert self.agent._call_state == CallState.ENDED
    
    @pytest.mark.asyncio
    async def test_termination_flow_cleanup_verification(self):
        """Test that termination flow properly cleans up all resources."""
        self.agent.call_session.start_call()
        
        # Set up some state to be cleaned
        self.agent.is_speaking = True
        self.agent.is_listening = True
        self.agent._call_metadata["test_data"] = "should_be_cleared"
        
        # Execute termination
        await self.agent.on_user_input("goodbye")
        
        # Verify cleanup occurred
        assert not self.agent.is_speaking
        assert not self.agent.is_listening
        assert len(self.agent._call_metadata) == 0  # All metadata cleared by cleanup
        
        # Verify room reference is cleared
        assert self.agent.room is None
        
        # Verify final state
        assert self.agent._call_state == CallState.ENDED
    
    @pytest.mark.asyncio
    async def test_termination_flow_with_non_termination_input(self):
        """Test that non-termination input doesn't trigger termination flow."""
        initial_state = self.agent._call_state
        
        # Process non-termination input
        await self.agent.on_user_input("hello there, how are you?")
        
        # Verify no termination occurred
        assert self.agent._call_state == initial_state
        self.mock_session.say.assert_not_called()
        self.mock_room.disconnect.assert_not_called()
        
        # But normal processing should occur
        self.mock_session.generate_reply.assert_called_once()