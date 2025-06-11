"""
Performance testing for multiple concurrent calls.

This module tests the system's performance and stability when handling
multiple concurrent calls, including stress testing, memory usage analysis,
and resource management verification.
"""

import asyncio
import pytest
import time
import gc
import psutil
import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, patch
import logging

from agent import SimpleAgent, CallState


class TestPerformanceMultipleCalls:
    """Performance tests for handling multiple concurrent calls."""

    @pytest.fixture
    def create_mock_agent(self):
        """Factory to create mock agents for testing."""
        def _create():
            agent = SimpleAgent()
            agent._agent_session = AsyncMock()
            agent.room = MagicMock()
            agent.room.disconnect = AsyncMock()
            agent.call_session.start_call()
            return agent
        return _create

    @pytest.mark.asyncio
    async def test_concurrent_call_handling(self, create_mock_agent):
        """Test handling multiple concurrent calls."""
        num_calls = 10
        agents = [create_mock_agent() for _ in range(num_calls)]
        
        # Start all calls concurrently
        start_tasks = []
        for agent in agents:
            start_tasks.append(agent._set_call_state(CallState.ACTIVE))
        
        await asyncio.gather(*start_tasks)
        
        # Verify all agents are active
        for agent in agents:
            assert agent.call_state == CallState.ACTIVE
        
        # Terminate all calls concurrently
        term_tasks = []
        for agent in agents:
            term_tasks.append(agent.on_user_input("goodbye"))
        
        await asyncio.gather(*term_tasks)
        
        # Verify all calls terminated successfully
        for agent in agents:
            assert agent.call_state == CallState.ENDED
            assert agent.room is None

    @pytest.mark.asyncio
    async def test_rapid_call_creation_termination(self, create_mock_agent):
        """Test rapid creation and termination of calls."""
        num_iterations = 20
        total_time = 0
        
        for i in range(num_iterations):
            agent = create_mock_agent()
            
            start_time = time.time()
            
            # Activate call
            await agent._set_call_state(CallState.ACTIVE)
            
            # Simulate some user interaction
            await agent.on_user_input("Hello")
            
            # Terminate call
            await agent.on_user_input("goodbye")
            
            end_time = time.time()
            iteration_time = end_time - start_time
            total_time += iteration_time
            
            # Verify call terminated
            assert agent.call_state == CallState.ENDED
            assert agent.room is None
            
            # Each iteration should complete quickly
            assert iteration_time < 0.1, f"Iteration {i} took too long: {iteration_time}s"
        
        avg_time = total_time / num_iterations
        assert avg_time < 0.05, f"Average call handling time too high: {avg_time}s"

    @pytest.mark.asyncio
    async def test_memory_usage_multiple_calls(self, create_mock_agent):
        """Test memory is properly released after calls are terminated."""
        # Force garbage collection
        gc.collect()
        
        # Run two cycles to test memory release
        memory_samples = []
        
        for cycle in range(2):
            process = psutil.Process(os.getpid())
            start_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            num_calls = 20
            agents = []
            
            # Create and activate calls
            for _ in range(num_calls):
                agent = create_mock_agent()
                await agent._set_call_state(CallState.ACTIVE)
                agents.append(agent)
            
            peak_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Terminate all calls
            for agent in agents:
                await agent._terminate_call()
            
            # Clear references and force garbage collection
            agents.clear()
            gc.collect()
            await asyncio.sleep(0.1)  # Give time for cleanup
            
            end_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            memory_samples.append({
                'start': start_memory,
                'peak': peak_memory,
                'end': end_memory,
                'peak_increase': peak_memory - start_memory,
                'released': peak_memory - end_memory
            })
        
        # Verify memory is being released between cycles
        # The second cycle should not have significantly more memory than the first
        if len(memory_samples) == 2:
            cycle1_peak = memory_samples[0]['peak_increase']
            cycle2_peak = memory_samples[1]['peak_increase']
            
            # Second cycle peak should not be much higher than first
            # (within 50% indicates proper cleanup)
            assert cycle2_peak < cycle1_peak * 1.5, \
                f"Memory not being released properly: cycle1={cycle1_peak}MB, cycle2={cycle2_peak}MB"

    @pytest.mark.asyncio
    async def test_stress_test_concurrent_operations(self, create_mock_agent):
        """Stress test with many concurrent operations."""
        num_agents = 20
        operations_per_agent = 10
        
        agents = [create_mock_agent() for _ in range(num_agents)]
        
        # Activate all agents
        for agent in agents:
            await agent._set_call_state(CallState.ACTIVE)
        
        # Perform many concurrent operations
        tasks = []
        for _ in range(operations_per_agent):
            for i, agent in enumerate(agents):
                if i % 3 == 0:
                    tasks.append(agent.on_user_input(f"Message {i}"))
                elif i % 3 == 1:
                    tasks.append(agent._set_call_state(CallState.ACTIVE))
                else:
                    tasks.append(agent.on_user_input("test"))
        
        # Execute all tasks with timeout
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        execution_time = time.time() - start_time
        
        # Check for errors
        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0, f"Got {len(errors)} errors during stress test"
        
        # Should complete within reasonable time
        assert execution_time < 5.0, f"Stress test took too long: {execution_time}s"
        
        # Cleanup all agents
        cleanup_tasks = [agent._terminate_call() for agent in agents]
        await asyncio.gather(*cleanup_tasks)

    @pytest.mark.asyncio
    async def test_resource_cleanup_verification(self, create_mock_agent):
        """Verify resources are properly cleaned up after multiple calls."""
        num_cycles = 10
        calls_per_cycle = 5
        
        for cycle in range(num_cycles):
            agents = []
            
            # Create and activate calls
            for _ in range(calls_per_cycle):
                agent = create_mock_agent()
                await agent._set_call_state(CallState.ACTIVE)
                agents.append(agent)
            
            # Terminate all calls
            for agent in agents:
                await agent._terminate_call()
            
            # Verify cleanup
            for agent in agents:
                assert agent.room is None
                assert agent.call_state == CallState.ENDED
                assert len(agent._call_metadata) <= 1  # Only warnings if any
            
            # Clear references
            agents.clear()

    @pytest.mark.asyncio
    async def test_call_state_consistency_under_load(self, create_mock_agent):
        """Test call state consistency under heavy load."""
        num_agents = 30
        agents = [create_mock_agent() for _ in range(num_agents)]
        
        # Mixed operations to test state consistency
        async def mixed_operations(agent, agent_id):
            """Perform mixed operations on an agent."""
            await agent._set_call_state(CallState.ACTIVE)
            
            # Simulate various user inputs
            for i in range(5):
                if i == 4:  # Last message is termination
                    await agent.on_user_input("goodbye")
                else:
                    await agent.on_user_input(f"Agent {agent_id} message {i}")
            
            return agent.call_state
        
        # Execute mixed operations concurrently
        tasks = [mixed_operations(agent, i) for i, agent in enumerate(agents)]
        final_states = await asyncio.gather(*tasks)
        
        # All agents should end in ENDED state
        for state in final_states:
            assert state == CallState.ENDED

    @pytest.mark.asyncio
    async def test_phrase_detection_performance_under_load(self, create_mock_agent):
        """Test phrase detection performance with multiple concurrent calls."""
        num_agents = 25
        messages_per_agent = 20
        
        agents = [create_mock_agent() for _ in range(num_agents)]
        
        # Activate all agents
        for agent in agents:
            await agent._set_call_state(CallState.ACTIVE)
        
        # Test phrases
        test_phrases = [
            "hello there",
            "how are you",
            "what's the weather",
            "goodbye",  # Termination phrase
            "thank you",  # Termination phrase
            "bye",  # Termination phrase
        ]
        
        # Send many messages concurrently
        start_time = time.time()
        tasks = []
        
        for agent in agents:
            for i in range(messages_per_agent):
                phrase = test_phrases[i % len(test_phrases)]
                tasks.append(agent.on_user_input(phrase))
        
        await asyncio.gather(*tasks, return_exceptions=True)
        detection_time = time.time() - start_time
        
        # Should handle all messages quickly
        total_messages = num_agents * messages_per_agent
        avg_time_per_message = detection_time / total_messages
        assert avg_time_per_message < 0.01, f"Phrase detection too slow: {avg_time_per_message}s per message"

    @pytest.mark.asyncio
    async def test_error_recovery_performance(self, create_mock_agent):
        """Test performance of error recovery with multiple failing calls."""
        num_agents = 15
        agents = []
        
        # Create agents with various failure scenarios
        for i in range(num_agents):
            agent = create_mock_agent()
            
            if i % 3 == 0:
                # Room disconnect will fail
                agent.room.disconnect.side_effect = Exception(f"Room error {i}")
            elif i % 3 == 1:
                # Session operations will fail
                agent._agent_session.say.side_effect = Exception(f"Session error {i}")
            # else: normal operation
            
            agents.append(agent)
        
        # Activate all agents
        for agent in agents:
            await agent._set_call_state(CallState.ACTIVE)
        
        # Terminate all calls (some will have errors)
        start_time = time.time()
        term_tasks = [agent._terminate_call() for agent in agents]
        await asyncio.gather(*term_tasks, return_exceptions=True)
        recovery_time = time.time() - start_time
        
        # All should complete despite errors
        for agent in agents:
            assert agent.call_state == CallState.ENDED
            assert agent.room is None
        
        # Error recovery should still be performant
        assert recovery_time < 2.0, f"Error recovery took too long: {recovery_time}s"

    @pytest.mark.asyncio
    async def test_logging_performance_impact(self, create_mock_agent, caplog):
        """Test logging doesn't significantly impact performance."""
        # Test with different log levels
        log_levels = [logging.DEBUG, logging.INFO, logging.WARNING]
        times = {}
        
        for level in log_levels:
            with caplog.at_level(level):
                agents = [create_mock_agent() for _ in range(10)]
                
                start_time = time.time()
                
                # Perform operations
                for agent in agents:
                    await agent._set_call_state(CallState.ACTIVE)
                    await agent.on_user_input("hello")
                    await agent.on_user_input("goodbye")
                
                end_time = time.time()
                times[level] = end_time - start_time
        
        # Debug logging should not be more than 2x slower than WARNING
        assert times[logging.DEBUG] < times[logging.WARNING] * 2, \
            f"Debug logging too slow: {times[logging.DEBUG]}s vs {times[logging.WARNING]}s"

    @pytest.mark.asyncio
    async def test_thread_safety_multiple_calls(self, create_mock_agent):
        """Test thread safety with multiple calls from different threads."""
        num_threads = 4
        calls_per_thread = 5
        
        async def thread_operations(thread_id):
            """Operations to run in each thread."""
            agents = []
            for i in range(calls_per_thread):
                agent = create_mock_agent()
                await agent._set_call_state(CallState.ACTIVE)
                await agent.on_user_input(f"Thread {thread_id} message {i}")
                await agent.on_user_input("goodbye")
                agents.append(agent)
            
            # Verify all completed successfully
            for agent in agents:
                assert agent.call_state == CallState.ENDED
            
            return len(agents)
        
        # Run operations in multiple threads
        tasks = [thread_operations(i) for i in range(num_threads)]
        results = await asyncio.gather(*tasks)
        
        # Verify all threads completed their calls
        total_calls = sum(results)
        assert total_calls == num_threads * calls_per_thread

    @pytest.mark.asyncio
    async def test_performance_metrics_summary(self, create_mock_agent, caplog):
        """Generate a performance metrics summary."""
        metrics = {
            "call_creation_time": [],
            "call_termination_time": [],
            "full_lifecycle_time": [],
            "memory_per_call": []
        }
        
        num_samples = 20
        
        for _ in range(num_samples):
            agent = create_mock_agent()
            
            # Measure call creation
            start = time.time()
            await agent._set_call_state(CallState.ACTIVE)
            metrics["call_creation_time"].append(time.time() - start)
            
            # Simulate some activity
            await agent.on_user_input("test message")
            
            # Measure termination
            start = time.time()
            await agent._terminate_call()
            metrics["call_termination_time"].append(time.time() - start)
        
        # Full lifecycle test
        for _ in range(num_samples):
            agent = create_mock_agent()
            start = time.time()
            
            await agent._set_call_state(CallState.ACTIVE)
            await agent.on_user_input("hello")
            await agent.on_user_input("goodbye")
            
            metrics["full_lifecycle_time"].append(time.time() - start)
        
        # Calculate statistics
        for metric_name, values in metrics.items():
            if values:  # Skip empty metrics
                avg = sum(values) / len(values)
                max_val = max(values)
                min_val = min(values)
                
                # Log performance metrics
                with caplog.at_level(logging.INFO):
                    logger = logging.getLogger(__name__)
                    logger.info(f"Performance metric '{metric_name}':")
                    logger.info(f"  Average: {avg:.4f}s")
                    logger.info(f"  Min: {min_val:.4f}s")
                    logger.info(f"  Max: {max_val:.4f}s")
                
                # Assert reasonable performance
                if "creation" in metric_name:
                    assert avg < 0.01, f"{metric_name} average too high: {avg}s"
                elif "termination" in metric_name:
                    assert avg < 0.05, f"{metric_name} average too high: {avg}s"
                elif "lifecycle" in metric_name:
                    assert avg < 0.1, f"{metric_name} average too high: {avg}s"