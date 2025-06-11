import unittest
from agent import SimpleAgent, CallState


class TestTerminationPhrases(unittest.TestCase):
    def test_default_phrases_initialization(self):
        """Test that default phrases are initialized correctly."""
        agent = SimpleAgent()
        self.assertIsNotNone(agent.termination_phrases)
        self.assertGreater(len(agent.termination_phrases), 0)
        self.assertIn("goodbye", agent.termination_phrases)
        self.assertIn("end call", agent.termination_phrases)
        self.assertIn("thank you", agent.termination_phrases)

    def test_custom_phrases_initialization(self):
        """Test initialization with custom phrases."""
        custom_phrases = ["adios", "hasta luego", "chao"]
        agent = SimpleAgent(termination_phrases=custom_phrases)

        self.assertEqual(len(agent.termination_phrases), 3)
        self.assertIn("adios", agent.termination_phrases)
        self.assertIn("hasta luego", agent.termination_phrases)
        self.assertIn("chao", agent.termination_phrases)
        # Verify default phrases are not included
        self.assertNotIn("goodbye", agent.termination_phrases)

    def test_empty_phrases_initialization(self):
        """Test initialization with empty list uses default phrases."""
        agent = SimpleAgent(termination_phrases=[])
        self.assertGreater(len(agent.termination_phrases), 0)
        self.assertIn("goodbye", agent.termination_phrases)

    def test_phrases_stored_as_set(self):
        """Test that phrases are stored as a set for O(1) lookups."""
        agent = SimpleAgent()
        self.assertIsInstance(agent.termination_phrases, set)

        # Test O(1) lookup
        self.assertIn("goodbye", agent.termination_phrases)
        self.assertNotIn("nonexistent_phrase", agent.termination_phrases)


if __name__ == "__main__":
    unittest.main()
