"""
Performance testing with realistic call scenarios.

This module simulates realistic call patterns and usage scenarios
to ensure the system performs well under real-world conditions.
"""

import asyncio
import pytest
import random
import time
import logging
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

from agent import SimpleAgent, CallState


class TestPerformanceRealisticScenarios:
    """Performance tests simulating realistic call scenarios."""

    @pytest.fixture
    def create_realistic_agent(self):
        """Factory to create agents with realistic configurations."""
        def _create():
            agent = SimpleAgent()
            agent._agent_session = AsyncMock()
            agent.room = MagicMock()
            agent.room.disconnect = AsyncMock()
            
            # Add realistic delays to simulate network/processing
            async def delayed_disconnect():
                await asyncio.sleep(random.uniform(0.01, 0.05))
            agent.room.disconnect = delayed_disconnect
            
            agent.call_session.start_call()
            return agent
        return _create

    @pytest.mark.asyncio
    async def test_realistic_call_duration_distribution(self, create_realistic_agent):
        """Test with realistic call duration distribution."""
        # Simulate call durations based on typical patterns:
        # - 20% very short calls (< 30 seconds)
        # - 50% medium calls (30 seconds - 2 minutes)
        # - 25% long calls (2-5 minutes)
        # - 5% very long calls (> 5 minutes)
        
        num_calls = 20
        call_durations = []
        
        for i in range(num_calls):
            agent = create_realistic_agent()
            await agent._set_call_state(CallState.ACTIVE)
            
            # Determine call duration category
            rand = random.random()
            if rand < 0.2:
                # Very short call
                duration = random.uniform(0.01, 0.03)
            elif rand < 0.7:
                # Medium call
                duration = random.uniform(0.03, 0.12)
            elif rand < 0.95:
                # Long call
                duration = random.uniform(0.12, 0.3)
            else:
                # Very long call
                duration = random.uniform(0.3, 0.5)
            
            # Simulate call activity
            start_time = time.time()
            await asyncio.sleep(duration)
            
            # Terminate call
            await agent.on_user_input("goodbye")
            
            actual_duration = time.time() - start_time
            call_durations.append(actual_duration)
            
            assert agent.call_state == CallState.ENDED
            assert agent.room is None
        
        # Verify performance metrics
        avg_duration = sum(call_durations) / len(call_durations)
        assert avg_duration < 0.2, f"Average call duration too high: {avg_duration}s"

    @pytest.mark.asyncio
    async def test_peak_hour_simulation(self, create_realistic_agent):
        """Simulate peak hour call patterns."""
        # Simulate a burst of calls during peak hours
        peak_calls = 15
        off_peak_calls = 5
        
        async def handle_call_burst(num_calls, delay_range):
            """Handle a burst of calls with random delays."""
            tasks = []
            
            for _ in range(num_calls):
                async def single_call():
                    agent = create_realistic_agent()
                    await agent._set_call_state(CallState.ACTIVE)
                    
                    # Random delay between calls
                    await asyncio.sleep(random.uniform(*delay_range))
                    
                    # Simulate conversation
                    messages = ["Hello", "I need help", "Can you assist?", "goodbye"]
                    for msg in messages:
                        await agent.on_user_input(msg)
                        await asyncio.sleep(0.01)
                    
                    return agent
                
                tasks.append(single_call())
            
            agents = await asyncio.gather(*tasks)
            
            # Verify all calls completed
            for agent in agents:
                assert agent.call_state == CallState.ENDED
            
            return len(agents)
        
        # Simulate peak hour
        start_time = time.time()
        peak_handled = await handle_call_burst(peak_calls, (0.01, 0.05))
        peak_time = time.time() - start_time
        
        # Simulate off-peak
        off_peak_handled = await handle_call_burst(off_peak_calls, (0.1, 0.2))
        
        assert peak_handled == peak_calls
        assert off_peak_handled == off_peak_calls
        assert peak_time < 5.0, f"Peak hour handling too slow: {peak_time}s"

    @pytest.mark.asyncio
    async def test_mixed_call_patterns(self, create_realistic_agent):
        """Test with mixed call patterns (new, active, terminating)."""
        num_agents = 12
        agents = []
        
        # Create agents in different states
        for i in range(num_agents):
            agent = create_realistic_agent()
            agents.append(agent)
            
            if i < 4:
                # New calls
                await agent._set_call_state(CallState.IDLE)
            elif i < 8:
                # Active calls
                await agent._set_call_state(CallState.ACTIVE)
            else:
                # Calls ready to terminate
                await agent._set_call_state(CallState.ACTIVE)
        
        # Simulate concurrent operations
        tasks = []
        
        for i, agent in enumerate(agents):
            if i < 4:
                # Activate new calls
                tasks.append(agent._set_call_state(CallState.ACTIVE))
            elif i < 8:
                # Send messages to active calls
                tasks.append(agent.on_user_input(f"Message from agent {i}"))
            else:
                # Terminate remaining calls
                tasks.append(agent.on_user_input("goodbye"))
        
        # Execute all operations concurrently
        await asyncio.gather(*tasks)
        
        # Verify states
        for i, agent in enumerate(agents):
            if i < 8:
                assert agent.call_state == CallState.ACTIVE
            else:
                assert agent.call_state == CallState.ENDED

    @pytest.mark.asyncio
    async def test_call_abandonment_scenarios(self, create_realistic_agent):
        """Test handling of abandoned calls."""
        num_calls = 10
        abandoned_calls = []
        completed_calls = []
        
        for i in range(num_calls):
            agent = create_realistic_agent()
            await agent._set_call_state(CallState.ACTIVE)
            
            if i % 3 == 0:
                # Simulate abandoned call (no goodbye)
                await agent._terminate_call()
                abandoned_calls.append(agent)
            else:
                # Normal termination
                await agent.on_user_input("goodbye")
                completed_calls.append(agent)
        
        # Verify all calls are properly cleaned up
        for agent in abandoned_calls + completed_calls:
            assert agent.call_state == CallState.ENDED
            assert agent.room is None
        
        assert len(abandoned_calls) + len(completed_calls) == num_calls

    @pytest.mark.asyncio
    async def test_conversation_complexity_impact(self, create_realistic_agent):
        """Test performance with varying conversation complexity."""
        complexities = {
            'simple': ['hello', 'goodbye'],
            'moderate': ['hello', 'how are you', 'what services do you offer', 'thank you', 'goodbye'],
            'complex': [
                'hello', 'I need help with multiple things',
                'first, can you explain your services',
                'second, what are your hours',
                'third, how do I make an appointment',
                'also, what about pricing',
                'one more question about location',
                'that sounds good, thank you',
                'goodbye'
            ]
        }
        
        performance_metrics = {}
        
        for complexity_name, messages in complexities.items():
            agents = []
            start_time = time.time()
            
            # Run 5 calls of each complexity
            for _ in range(5):
                agent = create_realistic_agent()
                await agent._set_call_state(CallState.ACTIVE)
                
                for msg in messages:
                    await agent.on_user_input(msg)
                
                agents.append(agent)
            
            end_time = time.time()
            performance_metrics[complexity_name] = {
                'total_time': end_time - start_time,
                'avg_time': (end_time - start_time) / 5,
                'messages_per_call': len(messages)
            }
            
            # Verify all calls completed
            for agent in agents:
                assert agent.call_state == CallState.ENDED
        
        # Complex calls should not take disproportionately longer
        simple_avg = performance_metrics['simple']['avg_time']
        complex_avg = performance_metrics['complex']['avg_time']
        
        # Complex calls have more messages but should still be efficient
        efficiency_ratio = complex_avg / simple_avg
        messages_ratio = performance_metrics['complex']['messages_per_call'] / performance_metrics['simple']['messages_per_call']
        
        # Performance should scale sub-linearly with message count
        assert efficiency_ratio < messages_ratio, \
            f"Performance scaling poorly: {efficiency_ratio}x time for {messages_ratio}x messages"

    @pytest.mark.asyncio
    async def test_sustained_load_performance(self, create_realistic_agent):
        """Test sustained load over extended period."""
        duration_seconds = 2.0  # Shortened for test speed
        calls_per_second = 5
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        total_calls = 0
        successful_calls = 0
        failed_calls = 0
        
        while time.time() < end_time:
            batch_start = time.time()
            
            # Create batch of calls
            tasks = []
            for _ in range(calls_per_second):
                async def single_call():
                    try:
                        agent = create_realistic_agent()
                        await agent._set_call_state(CallState.ACTIVE)
                        await agent.on_user_input("quick question")
                        await agent.on_user_input("thanks bye")
                        return True
                    except Exception:
                        return False
                
                tasks.append(single_call())
            
            results = await asyncio.gather(*tasks)
            
            successful_calls += sum(1 for r in results if r)
            failed_calls += sum(1 for r in results if not r)
            total_calls += len(results)
            
            # Wait for next second
            elapsed = time.time() - batch_start
            if elapsed < 1.0:
                await asyncio.sleep(1.0 - elapsed)
        
        # Verify performance
        success_rate = successful_calls / total_calls if total_calls > 0 else 0
        assert success_rate > 0.95, f"Success rate too low: {success_rate}"
        assert total_calls >= duration_seconds * calls_per_second * 0.8, \
            f"Could not maintain target call rate: {total_calls} calls in {duration_seconds}s"

    @pytest.mark.asyncio
    async def test_performance_degradation_detection(self, create_realistic_agent):
        """Test that performance doesn't degrade over time."""
        batches = 5
        calls_per_batch = 10
        batch_times = []
        
        for batch in range(batches):
            batch_start = time.time()
            
            # Process batch of calls
            tasks = []
            for _ in range(calls_per_batch):
                async def process_call():
                    agent = create_realistic_agent()
                    await agent._set_call_state(CallState.ACTIVE)
                    await agent.on_user_input("hello")
                    await agent.on_user_input("goodbye")
                
                tasks.append(process_call())
            
            await asyncio.gather(*tasks)
            
            batch_time = time.time() - batch_start
            batch_times.append(batch_time)
            
            # Small delay between batches
            await asyncio.sleep(0.1)
        
        # Check for performance degradation
        # Later batches should not be significantly slower than earlier ones
        first_batch_avg = sum(batch_times[:2]) / 2
        last_batch_avg = sum(batch_times[-2:]) / 2
        
        degradation = (last_batch_avg - first_batch_avg) / first_batch_avg
        assert degradation < 0.2, f"Performance degraded by {degradation * 100:.1f}%"