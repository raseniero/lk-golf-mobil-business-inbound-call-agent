import unittest
import time
from agent import CallSession

class TestCallTermination(unittest.TestCase):
    def test_call_duration_tracking(self):
        """Test that call duration is tracked correctly from start to end."""
        # Simulate call start
        call_session = CallSession()
        call_session.start_call()
        start = call_session.start_time
        time.sleep(0.01)  # Simulate call duration
        call_session.end_call()
        end = call_session.end_time
        duration = call_session.get_duration()
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        self.assertGreater(duration, 0)
        self.assertAlmostEqual(duration, end - start, places=3)

if __name__ == '__main__':
    unittest.main()
