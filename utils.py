import os
import re
import yaml
from typing import Set, Optional, Dict, Tuple

# Global pattern cache for performance optimization
_PATTERN_CACHE: Dict[str, re.Pattern] = {}
_COMBINED_PATTERN_CACHE: Dict[frozenset, Tuple[re.Pattern, Dict[str, str]]] = {}


def _get_or_create_single_pattern(phrase: str) -> re.Pattern:
    """Get or create a cached regex pattern for a single phrase."""
    if phrase not in _PATTERN_CACHE:
        phrase_lower = phrase.lower()
        pattern = r"\b" + re.escape(phrase_lower) + r"\b"
        _PATTERN_CACHE[phrase] = re.compile(pattern, re.IGNORECASE)
    return _PATTERN_CACHE[phrase]


def _get_or_create_multi_pattern(phrase: str) -> re.Pattern:
    """Get or create a cached regex pattern for a multi-word phrase."""
    cache_key = f"multi_{phrase}"
    if cache_key not in _PATTERN_CACHE:
        phrase_lower = phrase.lower()
        words = phrase_lower.split()
        escaped_words = [re.escape(word) for word in words]
        flexible_pattern = r"\b" + r"\b.*?\b".join(escaped_words) + r"\b"
        _PATTERN_CACHE[cache_key] = re.compile(flexible_pattern, re.IGNORECASE)
    return _PATTERN_CACHE[cache_key]


def _get_or_create_combined_patterns(
    termination_phrases: Set[str],
) -> Tuple[re.Pattern, Dict[str, str], re.Pattern, Dict[str, str]]:
    """Get or create combined regex patterns for single and multi-word phrases."""
    phrases_key = frozenset(termination_phrases)

    if phrases_key not in _COMBINED_PATTERN_CACHE:
        single_word_phrases = []
        multi_word_phrases = []

        # Separate single and multi-word phrases
        for phrase in termination_phrases:
            if " " in phrase:
                multi_word_phrases.append(phrase)
            else:
                single_word_phrases.append(phrase)

        # Create combined pattern for single-word phrases
        single_pattern = None
        single_map = {}
        if single_word_phrases:
            escaped_singles = [
                re.escape(phrase.lower()) for phrase in single_word_phrases
            ]
            single_pattern_str = r"\b(?:" + "|".join(escaped_singles) + r")\b"
            single_pattern = re.compile(single_pattern_str, re.IGNORECASE)
            single_map = {phrase.lower(): phrase for phrase in single_word_phrases}

        # Create individual patterns for multi-word phrases (they need flexible matching)
        multi_pattern = None
        multi_map = {}
        if multi_word_phrases:
            # For multi-word, we'll use the original approach since they need flexible matching
            multi_map = {phrase.lower(): phrase for phrase in multi_word_phrases}

        _COMBINED_PATTERN_CACHE[phrases_key] = (
            single_pattern,
            single_map,
            multi_pattern,
            multi_map,
        )

    return _COMBINED_PATTERN_CACHE[phrases_key]


def detect_termination_phrase(
    text: str, termination_phrases: Set[str]
) -> Optional[str]:
    """
    Detect if any termination phrase is present in the given text.

    This function performs case-insensitive matching and handles partial matches
    within sentences, including phrases followed by punctuation. It uses word
    boundary detection to avoid false positives from partial word matches.

    For multi-word phrases, it allows extra words between the key terms while
    maintaining word order (e.g., "end call" matches "end the call" but not "call end").

    Performance optimizations:
    - Cached compiled regex patterns for reuse
    - Combined regex for single-word phrases
    - Early exit when match found
    - Separate handling of single vs multi-word phrases

    Args:
        text: The input text to search for termination phrases.
              Can be None or empty string.
        termination_phrases: Set of termination phrases to match against.
                           Phrases should be in lowercase for consistency.

    Returns:
        The matched termination phrase (in original case from the set) if found,
        None otherwise.

    Examples:
        >>> phrases = {"goodbye", "end call", "bye"}
        >>> detect_termination_phrase("Goodbye everyone", phrases)
        'goodbye'
        >>> detect_termination_phrase("Please end the call", phrases)
        'end call'
        >>> detect_termination_phrase("hello there", phrases)
        None
    """
    if not text or not text.strip() or not termination_phrases:
        return None

    # Get cached patterns for this phrase set
    single_pattern, single_map, _, multi_map = _get_or_create_combined_patterns(
        termination_phrases
    )

    # Fast path: Check all single-word phrases with one combined regex
    if single_pattern:
        match = single_pattern.search(text)
        if match:
            matched_text = match.group(0).lower()
            return single_map.get(matched_text)

    # Slower path: Check multi-word phrases individually (they need flexible matching)
    if multi_map:
        text_lower = text.lower()
        for phrase_lower, original_phrase in multi_map.items():
            pattern = _get_or_create_multi_pattern(original_phrase)
            if pattern.search(text_lower):
                return original_phrase

    return None


def load_prompt(filename):
    """Load a prompt from a YAML file."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(script_dir, "prompts", filename)

    try:
        with open(prompt_path, "r") as file:
            prompt_data = yaml.safe_load(file)
            return prompt_data.get("instructions", "")
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(f"Error loading prompt file {filename}: {e}")
        return ""


def load_prompt_markdown(filename):
    """Load a prompt from a Markdown (.md) file as plain text."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(script_dir, "prompts", filename)

    try:
        with open(prompt_path, "r") as file:
            return file.read()
    except FileNotFoundError as e:
        print(f"Error loading markdown file {filename}: {e}")
        return ""
