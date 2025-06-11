"""Performance tests for phrase detection optimization."""

import time
import pytest
from utils import detect_termination_phrase


class TestPhraseDetectionPerformance:
    """Test cases for phrase detection performance optimization."""

    def setup_method(self):
        """Set up test data with a larger phrase set."""
        self.small_phrase_set = {
            "goodbye",
            "end call",
            "that's all",
            "thank you",
            "bye",
        }

        self.large_phrase_set = {
            "goodbye",
            "end call",
            "that's all",
            "thank you",
            "bye",
            "see you later",
            "have a good day",
            "take care",
            "farewell",
            "so long",
            "until next time",
            "call me back",
            "talk soon",
            "catch you later",
            "peace out",
            "signing off",
            "gotta go",
            "wrap up",
            "finish up",
            "done here",
            "all done",
            "complete",
            "end session",
            "close call",
            "hang up",
            "disconnect",
            "talk later",
            "until tomorrow",
            "see you soon",
            "good night",
            "good morning",
            "have a nice day",
            "take it easy",
            "be well",
        }

        self.test_inputs = [
            "I think we should probably wrap up this call now",
            "please end the call",
            "goodbye everyone and have a good day",
            "thank you very much for your time",
            "I think that's all for today",
            "let's finish up our conversation",
            "this is just a regular conversation with no termination phrases",
            "can you help me with something else instead",
        ]

    def test_single_call_performance(self):
        """Test performance of a single function call."""
        start_time = time.time()
        result = detect_termination_phrase("please end the call", self.large_phrase_set)
        end_time = time.time()

        assert result == "end call"
        # Should complete in under 1ms
        assert (end_time - start_time) < 0.001

    def test_multiple_calls_performance(self):
        """Test performance of multiple function calls."""
        num_iterations = 1000

        start_time = time.time()
        for _ in range(num_iterations):
            for test_input in self.test_inputs:
                detect_termination_phrase(test_input, self.large_phrase_set)
        end_time = time.time()

        total_time = end_time - start_time
        average_time = total_time / (num_iterations * len(self.test_inputs))

        # Should average less than 0.5ms per call with large phrase set
        assert average_time < 0.0005

        print(f"\nPerformance results:")
        print(f"Total calls: {num_iterations * len(self.test_inputs)}")
        print(f"Total time: {total_time*1000:.2f}ms")
        print(f"Average per call: {average_time*1000:.4f}ms")
        print(f"Phrases in set: {len(self.large_phrase_set)}")

    def test_worst_case_performance(self):
        """Test performance when no match is found (worst case)."""
        non_matching_text = "this text contains no termination phrases at all and should not match anything"

        start_time = time.time()
        for _ in range(1000):
            result = detect_termination_phrase(non_matching_text, self.large_phrase_set)
        end_time = time.time()

        assert result is None
        average_time = (end_time - start_time) / 1000

        # Even worst case should be under 0.5ms
        assert average_time < 0.0005

    def test_early_match_performance(self):
        """Test performance when match is found early."""
        early_match_text = "goodbye everyone"  # Should match first phrase

        start_time = time.time()
        for _ in range(1000):
            result = detect_termination_phrase(early_match_text, self.large_phrase_set)
        end_time = time.time()

        assert result == "goodbye"
        average_time = (end_time - start_time) / 1000

        # Early match should be very fast
        assert average_time < 0.0003

    def test_cache_effectiveness(self):
        """Test that pattern caching improves performance on repeated calls."""
        from utils import _PATTERN_CACHE, _COMBINED_PATTERN_CACHE

        # Clear caches to start fresh
        _PATTERN_CACHE.clear()
        _COMBINED_PATTERN_CACHE.clear()

        # First call should populate cache
        result1 = detect_termination_phrase("goodbye", self.large_phrase_set)
        assert len(_COMBINED_PATTERN_CACHE) == 1  # Should have cached the phrase set

        # Second call with same phrase set should reuse cache
        cache_size_before = len(_PATTERN_CACHE)
        result2 = detect_termination_phrase("bye", self.large_phrase_set)
        cache_size_after = len(_PATTERN_CACHE)

        assert result1 == "goodbye"
        assert result2 == "bye"
        # Cache should not grow significantly for same phrase set
        assert (
            cache_size_after <= cache_size_before + 5
        )  # Allow some growth for multi-word patterns
