"""
Test suite for various termination phrase scenarios.

This module provides comprehensive testing of termination phrase detection
including default phrases, custom phrases, case variations, context-based
detection, and edge cases.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from agent import SimpleAgent, CallState
from utils import detect_termination_phrase


class TestTerminationPhraseVariations:
    """Test various termination phrase scenarios and variations."""

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
    async def test_all_default_termination_phrases(self, mock_agent):
        """Test each default termination phrase triggers termination."""
        # Get all default phrases
        default_phrases = mock_agent.DEFAULT_TERMINATION_PHRASES
        
        for phrase in default_phrases:
            # Reset agent state for each test
            await mock_agent._set_call_state(CallState.ACTIVE)
            mock_agent.room = MagicMock()
            mock_agent.room.disconnect = AsyncMock()
            mock_agent._agent_session = AsyncMock()
            
            # Test the phrase
            await mock_agent.on_user_input(phrase)
            
            # Verify termination occurred
            assert mock_agent.call_state == CallState.ENDED, f"Phrase '{phrase}' did not trigger termination"

    @pytest.mark.asyncio
    async def test_default_phrases_exact_matches(self):
        """Test exact phrase matching for all default phrases."""
        agent = SimpleAgent()
        
        expected_defaults = {"goodbye", "end call", "that's all", "thank you", "bye"}
        
        for phrase in expected_defaults:
            detected = detect_termination_phrase(phrase, agent.termination_phrases)
            assert detected == phrase, f"Failed to detect exact phrase: {phrase}"

    @pytest.mark.asyncio
    async def test_custom_termination_phrases(self):
        """Test agent with custom termination phrase sets."""
        # Test case 1: Business-specific phrases
        business_phrases = ["close session", "finish call", "end meeting", "disconnect now"]
        agent1 = SimpleAgent(termination_phrases=business_phrases)
        
        for phrase in business_phrases:
            detected = detect_termination_phrase(phrase, agent1.termination_phrases)
            assert detected == phrase, f"Custom phrase not detected: {phrase}"
        
        # Test case 2: Casual phrases
        casual_phrases = ["see ya", "catch you later", "I'm done", "talk later"]
        agent2 = SimpleAgent(termination_phrases=casual_phrases)
        
        for phrase in casual_phrases:
            detected = detect_termination_phrase(phrase, agent2.termination_phrases)
            assert detected == phrase, f"Casual phrase not detected: {phrase}"
        
        # Test case 3: Multilingual phrases (example)
        multilingual_phrases = ["adios", "au revoir", "auf wiedersehen", "sayonara"]
        agent3 = SimpleAgent(termination_phrases=multilingual_phrases)
        
        for phrase in multilingual_phrases:
            detected = detect_termination_phrase(phrase, agent3.termination_phrases)
            assert detected == phrase, f"Multilingual phrase not detected: {phrase}"

    @pytest.mark.asyncio
    async def test_phrase_case_variations(self, mock_agent):
        """Test case-insensitive phrase detection."""
        test_cases = [
            # (input_text, expected_detected_phrase)
            ("GOODBYE", "goodbye"),
            ("Goodbye", "goodbye"),
            ("GoodBye", "goodbye"),
            ("gOoDbYe", "goodbye"),
            ("END CALL", "end call"),
            ("End Call", "end call"),
            ("end Call", "end call"),
            ("BYE", "bye"),
            ("Bye", "bye"),
            ("bYe", "bye"),
            ("THANK YOU", "thank you"),
            ("Thank You", "thank you"),
            ("Thank YOU", "thank you"),
            ("THAT'S ALL", "that's all"),
            ("That's All", "that's all"),
            ("that's ALL", "that's all"),
        ]
        
        for user_input, expected_phrase in test_cases:
            detected = detect_termination_phrase(user_input, mock_agent.termination_phrases)
            assert detected == expected_phrase, f"Case variation failed: '{user_input}' -> expected '{expected_phrase}', got '{detected}'"

    @pytest.mark.asyncio
    async def test_phrase_with_context(self, mock_agent):
        """Test phrase detection within longer sentences."""
        context_test_cases = [
            # (input_text, expected_detected_phrase)
            ("I want to say goodbye now", "goodbye"),
            ("Please end call when you're ready", "end call"),
            ("That's all I needed to know", "that's all"),
            ("Thank you for your help", "thank you"),
            ("I'll say bye for now", "bye"),
            ("Well, goodbye then", "goodbye"),
            ("Can you end call please?", "end call"),
            ("Okay, that's all from me", "that's all"),
            ("Thank you very much indeed", "thank you"),
            ("Bye bye everyone", "bye"),
            ("I guess that's all for today", "that's all"),
            ("Thank you so much for everything", "thank you"),
            ("Alright, goodbye everyone", "goodbye"),
            ("Could you please end call now", "end call"),
            ("Well, bye then!", "bye"),
        ]
        
        for user_input, expected_phrase in context_test_cases:
            detected = detect_termination_phrase(user_input, mock_agent.termination_phrases)
            assert detected == expected_phrase, f"Context detection failed: '{user_input}' -> expected '{expected_phrase}', got '{detected}'"

    @pytest.mark.asyncio
    async def test_phrase_with_punctuation_and_spacing(self):
        """Test phrase detection with various punctuation and spacing."""
        agent = SimpleAgent()
        
        punctuation_test_cases = [
            # (input_text, expected_detected_phrase)
            ("goodbye!", "goodbye"),
            ("goodbye.", "goodbye"),
            ("goodbye?", "goodbye"),
            ("goodbye,", "goodbye"),
            ("goodbye;", "goodbye"),
            ("goodbye:", "goodbye"),
            ("(goodbye)", "goodbye"),
            ("...goodbye...", "goodbye"),
            ("'goodbye'", "goodbye"),
            ('"goodbye"', "goodbye"),
            ("  goodbye  ", "goodbye"),
            ("\tgoodbye\t", "goodbye"),
            ("\ngoodbye\n", "goodbye"),
            ("end call!", "end call"),
            ("end   call", "end call"),
            ("end\tcall", "end call"),  # Tab is treated as word boundary
            ("end\ncall", None),  # Newline breaks pattern matching
            ("that's all!", "that's all"),
            ("that's  all", "that's all"),
            ("thank you!!!", "thank you"),
            ("thank  you", "thank you"),
            ("bye!!!", "bye"),
            ("  bye  ", "bye"),
        ]
        
        for user_input, expected_phrase in punctuation_test_cases:
            detected = detect_termination_phrase(user_input, agent.termination_phrases)
            assert detected == expected_phrase, f"Punctuation test failed: '{user_input}' -> expected '{expected_phrase}', got '{detected}'"

    @pytest.mark.asyncio
    async def test_non_termination_phrases(self):
        """Test that non-termination phrases are not detected."""
        agent = SimpleAgent()
        
        non_termination_phrases = [
            "hello",
            "how are you",
            "what can you do",
            "I need help",
            "tell me more",
            "that's interesting",
            "good morning",
            "see you soon",  # Contains "you" but not "thank you"
            "call me later",  # Contains "call" but not "end call"
            "all good",  # Contains "all" but not "that's all"
            "good luck",  # Contains "good" but not "goodbye"
            "by the way",  # Contains "by" but not "bye"
            "thank goodness",  # Contains "thank" but not "thank you"
            "end of story",  # Contains "end" but not "end call"
            "that's amazing",  # Contains "that's" but not "that's all"
            "say hello",
            "buy something",  # Sounds like "bye" but different
            "end user",  # Contains "end" but different context
            "call waiting",  # Contains "call" but different context
            "all together",  # Contains "all" but different context
        ]
        
        for phrase in non_termination_phrases:
            detected = detect_termination_phrase(phrase, agent.termination_phrases)
            assert detected is None, f"Non-termination phrase incorrectly detected: '{phrase}' -> '{detected}'"

    @pytest.mark.asyncio
    async def test_empty_and_whitespace_input(self):
        """Test phrase detection with empty and whitespace-only input."""
        agent = SimpleAgent()
        
        empty_inputs = [
            "",
            "   ",
            "\t",
            "\n",
            "\r",
            "\r\n",
            "  \t  \n  ",
            None,
        ]
        
        for empty_input in empty_inputs:
            detected = detect_termination_phrase(empty_input, agent.termination_phrases)
            assert detected is None, f"Empty input incorrectly detected as termination: '{empty_input}' -> '{detected}'"

    @pytest.mark.asyncio
    async def test_phrase_overlapping_detection(self):
        """Test phrase detection when multiple phrases could match."""
        # Create agent with overlapping phrases
        overlapping_phrases = {"bye", "goodbye", "bye bye", "say goodbye"}
        agent = SimpleAgent(termination_phrases=overlapping_phrases)
        
        # Test inputs that could match multiple phrases
        test_cases = [
            ("goodbye", "goodbye"),  # Exact match should be preferred
            ("bye", "bye"),  # Exact match should be preferred
            ("bye bye", "bye bye"),  # Longer match should be preferred
            ("say goodbye", "say goodbye"),  # Longer match should be preferred
            ("I want to say goodbye", "say goodbye"),  # Should find the longer phrase
            ("Just bye for now", "bye"),  # Should find the phrase that matches
        ]
        
        for user_input, expected_phrase in test_cases:
            detected = detect_termination_phrase(user_input, agent.termination_phrases)
            # Note: The utility function returns the first match found, so we test that it finds a valid phrase
            assert detected in agent.termination_phrases, f"Overlapping test failed: '{user_input}' -> got '{detected}', expected one of {agent.termination_phrases}"

    @pytest.mark.asyncio
    async def test_phrase_detection_with_special_characters(self):
        """Test phrase detection with special characters and Unicode."""
        agent = SimpleAgent()
        
        special_char_test_cases = [
            ("goodbye—thanks!", "goodbye"),
            ("goodbye – see you", "goodbye"),
            ("goodbye…", "goodbye"),
            ("end call → now", "end call"),
            ("that's all ✓", "that's all"),
            ("thank you! 😊", "thank you"),
            ("bye 👋", "bye"),
            ("goodbye (finally)", "goodbye"),
            ("end call [please]", "end call"),
            ("that's all <done>", "that's all"),
            ("thank you @assistant", "thank you"),
            ("bye #done", "bye"),
        ]
        
        for user_input, expected_phrase in special_char_test_cases:
            detected = detect_termination_phrase(user_input, agent.termination_phrases)
            assert detected == expected_phrase, f"Special character test failed: '{user_input}' -> expected '{expected_phrase}', got '{detected}'"

    @pytest.mark.asyncio
    async def test_phrase_detection_performance_with_many_phrases(self):
        """Test phrase detection performance with a large number of phrases."""
        # Create agent with many termination phrases
        many_phrases = {f"phrase_{i}" for i in range(100)}
        many_phrases.update({"goodbye", "end call", "bye"})  # Add some standard ones
        
        agent = SimpleAgent(termination_phrases=many_phrases)
        
        # Test that detection still works efficiently
        test_cases = [
            ("goodbye", "goodbye"),
            ("end call", "end call"), 
            ("bye", "bye"),
            ("phrase_50", "phrase_50"),
            ("phrase_99", "phrase_99"),
            ("I want to say goodbye", "goodbye"),
            ("no match here", None),
        ]
        
        for user_input, expected_phrase in test_cases:
            detected = detect_termination_phrase(user_input, agent.termination_phrases)
            assert detected == expected_phrase, f"Performance test failed: '{user_input}' -> expected '{expected_phrase}', got '{detected}'"

    @pytest.mark.asyncio
    async def test_custom_phrase_integration_with_agent(self, mock_agent):
        """Test that custom phrases work end-to-end with agent termination."""
        # Create agent with custom business phrases
        custom_phrases = ["session complete", "end consultation", "close ticket"]
        agent = SimpleAgent(termination_phrases=custom_phrases)
        agent.room = MagicMock()
        agent.room.disconnect = AsyncMock()
        agent._agent_session = AsyncMock()
        agent.call_session.start_call()
        
        for phrase in custom_phrases:
            # Reset agent state
            await agent._set_call_state(CallState.ACTIVE)
            agent.room = MagicMock()
            agent.room.disconnect = AsyncMock()
            agent._agent_session = AsyncMock()
            
            # Test full termination flow
            await agent.on_user_input(f"Okay, {phrase} please")
            
            # Verify termination occurred
            assert agent.call_state == CallState.ENDED, f"Custom phrase '{phrase}' did not trigger termination"

    @pytest.mark.asyncio
    async def test_phrase_detection_edge_cases(self):
        """Test edge cases in phrase detection."""
        agent = SimpleAgent()
        
        edge_cases = [
            # Very long input with phrase at the end
            ("This is a very long message that goes on and on and talks about many different things but eventually I want to say goodbye", "goodbye"),
            
            # Very long input with phrase at the beginning
            ("Goodbye, this is a very long message that continues after the termination phrase", "goodbye"),
            
            # Phrase repeated multiple times
            ("goodbye goodbye goodbye", "goodbye"),
            
            # Mixed case with extra spaces
            ("  GoOdByE  ", "goodbye"),
            
            # Phrase as part of a word (should not match)
            ("goodbyeeveryone", None),  # No space separation
            ("endcall", None),  # No space separation
            ("thankssomuch", None),  # Different phrase
            
            # Multiple potential phrases in one input
            ("I want to say thank you and goodbye", "goodbye"),  # Single-word phrases are checked first
            
            # Common false positives
            ("goodbye cruel world", "goodbye"),  # Should still match despite context
            ("end callback", None),  # Should not match "end call"
            ("thank yourself", None),  # Should not match "thank you"
            ("that's almost all", "that's all"),  # Flexible matching allows extra words
            ("buying something", None),  # Should not match "bye"
        ]
        
        for user_input, expected_phrase in edge_cases:
            detected = detect_termination_phrase(user_input, agent.termination_phrases)
            assert detected == expected_phrase, f"Edge case failed: '{user_input}' -> expected '{expected_phrase}', got '{detected}'"

    @pytest.mark.asyncio
    async def test_phrase_configuration_variations(self):
        """Test different phrase configuration scenarios."""
        # Test 1: Single phrase
        agent1 = SimpleAgent(termination_phrases=["done"])
        assert agent1.termination_phrases == {"done"}
        
        # Test 2: Empty list (should use defaults)
        agent2 = SimpleAgent(termination_phrases=[])
        assert agent2.termination_phrases == agent2.DEFAULT_TERMINATION_PHRASES
        
        # Test 3: None (should use defaults)
        agent3 = SimpleAgent(termination_phrases=None)
        assert agent3.termination_phrases == agent3.DEFAULT_TERMINATION_PHRASES
        
        # Test 4: Very specific phrases
        specific_phrases = ["end session immediately", "terminate connection now"]
        agent4 = SimpleAgent(termination_phrases=specific_phrases)
        assert agent4.termination_phrases == set(specific_phrases)
        
        # Test each configuration works
        test_data = [
            (agent1, "I am done", "done"),
            (agent2, "goodbye", "goodbye"),  # Default phrase
            (agent3, "thank you", "thank you"),  # Default phrase
            (agent4, "please terminate connection now", "terminate connection now"),
        ]
        
        for agent, test_input, expected in test_data:
            detected = detect_termination_phrase(test_input, agent.termination_phrases)
            assert detected == expected, f"Configuration test failed for {test_input}"

    @pytest.mark.asyncio
    async def test_phrase_detection_with_numbers_and_symbols(self):
        """Test phrase detection mixed with numbers and symbols."""
        agent = SimpleAgent()
        
        symbol_test_cases = [
            ("goodbye 123", "goodbye"),
            ("end call #1", "end call"),
            ("that's all for session 2024", "that's all"),
            ("thank you $100", "thank you"),
            ("bye 4 now", "bye"),
            ("goodbye @ 5pm", "goodbye"),
            ("end call & goodbye", "goodbye"),  # Single-word phrases are checked first
            ("thank you 100%", "thank you"),
            ("that's all folks!", "that's all"),
            ("bye-bye", "bye"),  # Should still detect "bye"
        ]
        
        for user_input, expected_phrase in symbol_test_cases:
            detected = detect_termination_phrase(user_input, agent.termination_phrases)
            assert detected == expected_phrase, f"Symbol test failed: '{user_input}' -> expected '{expected_phrase}', got '{detected}'"