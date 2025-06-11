import os
import re
import yaml
from typing import Set, Optional


def detect_termination_phrase(text: str, termination_phrases: Set[str]) -> Optional[str]:
    """
    Detect if any termination phrase is present in the given text.
    
    This function performs case-insensitive matching and handles partial matches
    within sentences, including phrases followed by punctuation. It uses word
    boundary detection to avoid false positives from partial word matches.
    
    For multi-word phrases, it allows extra words between the key terms while
    maintaining word order (e.g., "end call" matches "end the call" but not "call end").
    
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
    
    text_lower = text.lower()
    
    # Check each termination phrase
    for phrase in termination_phrases:
        phrase_lower = phrase.lower()
        words = phrase_lower.split()
        
        if len(words) == 1:
            # Single word - use exact word boundary matching
            pattern = re.compile(r'\b' + re.escape(phrase_lower) + r'\b')
            if pattern.search(text_lower):
                return phrase
        else:
            # Multi-word phrase - allow extra words between terms but maintain order
            # Create a flexible pattern: word1 (any characters) word2 (any characters) word3...
            escaped_words = [re.escape(word) for word in words]
            # Use word boundaries and non-greedy matching
            flexible_pattern = r'\b' + r'\b.*?\b'.join(escaped_words) + r'\b'
            pattern = re.compile(flexible_pattern)
            if pattern.search(text_lower):
                return phrase
    
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
