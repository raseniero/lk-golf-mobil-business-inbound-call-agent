"""Test suite for phrase detection utility function."""

import pytest
from utils import detect_termination_phrase


class TestPhraseDetection:
    """Test cases for the phrase detection utility function."""
    
    def setup_method(self):
        """Set up test data."""
        self.termination_phrases = {
            "goodbye",
            "end call", 
            "that's all",
            "thank you",
            "bye"
        }
    
    def test_exact_match_detection(self):
        """Test exact phrase match detection."""
        result = detect_termination_phrase("goodbye", self.termination_phrases)
        assert result == "goodbye"
        
        result = detect_termination_phrase("end call", self.termination_phrases)
        assert result == "end call"
    
    def test_case_insensitive_detection(self):
        """Test case-insensitive phrase matching."""
        result = detect_termination_phrase("GOODBYE", self.termination_phrases)
        assert result == "goodbye"
        
        result = detect_termination_phrase("Thank You", self.termination_phrases)
        assert result == "thank you"
        
        result = detect_termination_phrase("END CALL", self.termination_phrases)
        assert result == "end call"
    
    def test_phrase_in_sentence(self):
        """Test detection of phrases within sentences."""
        result = detect_termination_phrase("Well, goodbye everyone", self.termination_phrases)
        assert result == "goodbye"
        
        result = detect_termination_phrase("I think that's all for now", self.termination_phrases)
        assert result == "that's all"
        
        result = detect_termination_phrase("Please end call now", self.termination_phrases)
        assert result == "end call"
    
    def test_phrase_with_punctuation(self):
        """Test detection of phrases followed by punctuation."""
        result = detect_termination_phrase("goodbye!", self.termination_phrases)
        assert result == "goodbye"
        
        result = detect_termination_phrase("that's all.", self.termination_phrases)
        assert result == "that's all"
        
        result = detect_termination_phrase("thank you,", self.termination_phrases)
        assert result == "thank you"
    
    def test_no_match_detection(self):
        """Test that non-matching input returns None."""
        result = detect_termination_phrase("hello there", self.termination_phrases)
        assert result is None
        
        result = detect_termination_phrase("how are you", self.termination_phrases)
        assert result is None
        
        result = detect_termination_phrase("continue talking", self.termination_phrases)
        assert result is None
    
    def test_empty_input_handling(self):
        """Test handling of empty or None input."""
        result = detect_termination_phrase("", self.termination_phrases)
        assert result is None
        
        result = detect_termination_phrase(None, self.termination_phrases)
        assert result is None
        
        result = detect_termination_phrase("   ", self.termination_phrases)
        assert result is None
    
    def test_partial_word_no_match(self):
        """Test that partial word matches don't trigger false positives."""
        result = detect_termination_phrase("bygone", self.termination_phrases)
        assert result is None
        
        result = detect_termination_phrase("antibody", self.termination_phrases)
        assert result is None
    
    def test_empty_phrase_set(self):
        """Test behavior with empty phrase set."""
        result = detect_termination_phrase("goodbye", set())
        assert result is None
    
    def test_single_word_phrases(self):
        """Test detection of single word phrases."""
        result = detect_termination_phrase("bye", self.termination_phrases)
        assert result == "bye"
        
        result = detect_termination_phrase("Bye there", self.termination_phrases)
        assert result == "bye"
    
    def test_multi_word_phrases(self):
        """Test detection of multi-word phrases."""
        result = detect_termination_phrase("I want to end call", self.termination_phrases)
        assert result == "end call"
        
        result = detect_termination_phrase("that's all I need", self.termination_phrases)
        assert result == "that's all"
    
    def test_partial_matches_with_extra_words(self):
        """Test detection of phrases with extra words in between."""
        # Multi-word phrases with extra words
        result = detect_termination_phrase("please end the call", self.termination_phrases)
        assert result == "end call"
        
        result = detect_termination_phrase("I think that's really all", self.termination_phrases)
        assert result == "that's all"
        
        result = detect_termination_phrase("can you end this call", self.termination_phrases)
        assert result == "end call"
        
        result = detect_termination_phrase("well that's definitely all for today", self.termination_phrases)
        assert result == "that's all"
    
    def test_flexible_word_order_should_not_match(self):
        """Test that reversed word order does not match."""
        # These should NOT match because word order matters
        result = detect_termination_phrase("call end", self.termination_phrases)
        assert result is None
        
        result = detect_termination_phrase("all that's", self.termination_phrases)
        assert result is None
    
    def test_exact_word_matching_required(self):
        """Test that exact words are required (e.g., 'that is' != 'that's')."""
        # "that is" should NOT match "that's all" because the words are different
        result = detect_termination_phrase("that is really all for today", self.termination_phrases)
        assert result is None
        
        # But "that's" with extra words should still match
        result = detect_termination_phrase("I think that's definitely all", self.termination_phrases)
        assert result == "that's all"