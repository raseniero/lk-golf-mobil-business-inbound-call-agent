"""Test suite for enhanced call duration calculation functionality."""

import pytest
import time
from unittest.mock import patch, MagicMock
from agent import CallSession, SimpleAgent


class TestCallDurationCalculation:
    """Test cases for enhanced call duration calculation."""

    @pytest.fixture
    def call_session(self):
        """Create a CallSession instance for testing."""
        return CallSession()

    @pytest.fixture
    def agent(self):
        """Create a SimpleAgent instance for testing."""
        return SimpleAgent()

    def test_basic_duration_calculation(self, call_session):
        """Test basic duration calculation functionality."""
        call_session.start_call()
        start_time = call_session.start_time
        
        # Simulate some call duration
        time.sleep(0.01)
        call_session.end_call()
        
        duration = call_session.get_duration()
        
        assert duration is not None
        assert duration > 0
        assert duration >= 0.01
        assert isinstance(duration, float)

    def test_duration_without_start_time(self, call_session):
        """Test duration calculation when no start time is set."""
        call_session.end_call()
        duration = call_session.get_duration()
        
        assert duration is None

    def test_duration_without_end_time(self, call_session):
        """Test duration calculation when call hasn't ended."""
        call_session.start_call()
        duration = call_session.get_duration()
        
        assert duration is None

    def test_duration_formatting_seconds(self, call_session):
        """Test human-readable duration formatting for seconds."""
        # Mock specific duration
        call_session.start_time = 1000.0
        call_session.end_time = 1045.5  # 45.5 seconds
        
        formatted = call_session.get_duration_formatted()
        
        assert "45.5 seconds" in formatted

    def test_duration_formatting_minutes_seconds(self, call_session):
        """Test duration formatting for minutes and seconds."""
        # Mock duration of 2 minutes 30 seconds
        call_session.start_time = 1000.0
        call_session.end_time = 1150.0  # 150 seconds = 2:30
        
        formatted = call_session.get_duration_formatted()
        
        assert "2 minutes" in formatted
        assert "30 seconds" in formatted

    def test_duration_formatting_hours_minutes_seconds(self, call_session):
        """Test duration formatting for hours, minutes, and seconds."""
        # Mock duration of 1 hour 5 minutes 30 seconds
        call_session.start_time = 1000.0
        call_session.end_time = 4930.0  # 3930 seconds = 1:05:30
        
        formatted = call_session.get_duration_formatted()
        
        assert "1 hour" in formatted
        assert "5 minutes" in formatted
        assert "30 seconds" in formatted

    def test_duration_formatting_zero_duration(self, call_session):
        """Test duration formatting for zero or very small durations."""
        call_session.start_time = 1000.0
        call_session.end_time = 1000.0  # No duration
        
        formatted = call_session.get_duration_formatted()
        
        assert "0 seconds" in formatted

    def test_duration_formatting_none_duration(self, call_session):
        """Test duration formatting when duration is None."""
        formatted = call_session.get_duration_formatted()
        
        assert formatted == "unknown"

    def test_duration_in_minutes(self, call_session):
        """Test getting duration in minutes."""
        call_session.start_time = 1000.0
        call_session.end_time = 1180.0  # 180 seconds = 3 minutes
        
        duration_minutes = call_session.get_duration_minutes()
        
        assert duration_minutes == 3.0

    def test_duration_in_minutes_with_decimals(self, call_session):
        """Test getting duration in minutes with decimals."""
        call_session.start_time = 1000.0
        call_session.end_time = 1090.0  # 90 seconds = 1.5 minutes
        
        duration_minutes = call_session.get_duration_minutes()
        
        assert duration_minutes == 1.5

    def test_duration_in_minutes_none(self, call_session):
        """Test getting duration in minutes when duration is None."""
        duration_minutes = call_session.get_duration_minutes()
        
        assert duration_minutes is None

    def test_duration_validation(self, call_session):
        """Test duration validation for edge cases."""
        # Test negative duration (shouldn't happen but let's handle it)
        call_session.start_time = 1000.0
        call_session.end_time = 999.0  # End before start
        
        duration = call_session.get_duration()
        
        # Duration should be negative, but let's validate it
        assert duration == -1.0

    def test_duration_precision(self, call_session):
        """Test duration calculation precision."""
        call_session.start_time = 1000.123456
        call_session.end_time = 1001.654321
        
        duration = call_session.get_duration()
        expected = 1001.654321 - 1000.123456
        
        assert abs(duration - expected) < 0.000001  # High precision

    def test_multiple_call_sessions(self):
        """Test multiple call sessions with different durations."""
        sessions = []
        
        for i in range(3):
            session = CallSession()
            session.start_call()
            time.sleep(0.01 * (i + 1))  # Different durations
            session.end_call()
            sessions.append(session)
        
        durations = [s.get_duration() for s in sessions]
        
        # Each duration should be different and increasing
        assert len(durations) == 3
        assert all(d > 0 for d in durations)
        assert durations[0] < durations[1] < durations[2]

    def test_call_session_reset(self, call_session):
        """Test resetting call session for reuse."""
        # First call
        call_session.start_call()
        time.sleep(0.01)
        call_session.end_call()
        first_duration = call_session.get_duration()
        
        # Reset and second call
        call_session.reset()
        assert call_session.start_time is None
        assert call_session.end_time is None
        
        call_session.start_call()
        time.sleep(0.01)
        call_session.end_call()
        second_duration = call_session.get_duration()
        
        assert first_duration is not None
        assert second_duration is not None
        assert first_duration != second_duration

    def test_agent_duration_logging_integration(self, agent):
        """Test integration of enhanced duration calculation with agent logging."""
        agent.call_session.start_call()
        time.sleep(0.01)
        agent.call_session.end_call()
        
        with patch('agent.logger') as mock_logger:
            # Test the enhanced duration logging
            agent._log_call_duration_summary()
            
            # Should have logged duration information
            mock_logger.info.assert_called()
            log_message = str(mock_logger.info.call_args)
            
            assert "duration" in log_message.lower()

    def test_duration_statistics(self):
        """Test calculation of duration statistics across multiple sessions."""
        durations = []
        
        # Create multiple sessions with known durations
        for duration_seconds in [10, 20, 30, 40, 50]:
            session = CallSession()
            session.start_time = 1000.0
            session.end_time = 1000.0 + duration_seconds
            durations.append(session.get_duration())
        
        # Calculate statistics
        min_duration = min(durations)
        max_duration = max(durations)
        avg_duration = sum(durations) / len(durations)
        
        assert min_duration == 10.0
        assert max_duration == 50.0
        assert avg_duration == 30.0

    def test_duration_thresholds(self, call_session):
        """Test duration classification by thresholds."""
        # Test short call
        call_session.start_time = 1000.0
        call_session.end_time = 1015.0  # 15 seconds
        
        assert call_session.is_short_call()  # < 30 seconds
        assert not call_session.is_medium_call()
        assert not call_session.is_long_call()
        
        # Test medium call
        call_session.end_time = 1120.0  # 120 seconds (2 minutes)
        
        assert not call_session.is_short_call()
        assert call_session.is_medium_call()  # 30 seconds - 5 minutes
        assert not call_session.is_long_call()
        
        # Test long call
        call_session.end_time = 1400.0  # 400 seconds (6.67 minutes)
        
        assert not call_session.is_short_call()
        assert not call_session.is_medium_call()
        assert call_session.is_long_call()  # > 5 minutes

    def test_duration_export_data(self, call_session):
        """Test exporting duration data for analytics."""
        call_session.start_time = 1000.0
        call_session.end_time = 1150.0  # 150 seconds
        
        export_data = call_session.get_duration_export_data()
        
        expected_data = {
            'start_time': 1000.0,
            'end_time': 1150.0,
            'duration_seconds': 150.0,
            'duration_minutes': 2.5,
            'duration_formatted': '2 minutes 30 seconds',
            'call_classification': 'medium'
        }
        
        assert export_data == expected_data