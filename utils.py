import os
import yaml
from typing import Set, Optional


def detect_termination_phrase(text: str, termination_phrases: Set[str]) -> Optional[str]:
    """
    Detect if any termination phrase is present in the given text.
    
    This function performs case-insensitive matching and handles partial matches
    within sentences, including phrases followed by punctuation. It uses word
    boundary detection to avoid false positives from partial word matches.
    
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
        >>> detect_termination_phrase("Please end call now", phrases)
        'end call'
        >>> detect_termination_phrase("hello there", phrases)
        None
    """
    if not text or not text.strip() or not termination_phrases:
        return None
    
    # Normalize the input for case-insensitive matching
    normalized_input = text.lower().strip()
    
    # Split the input into words for more precise matching
    words = normalized_input.split()
    
    # Check each termination phrase
    for phrase in termination_phrases:
        # Normalize the phrase for matching
        normalized_phrase = phrase.lower()
        
        # Check for exact match first
        if normalized_input == normalized_phrase:
            return phrase
            
        # Check if the phrase is a complete word in the input
        if normalized_phrase in words:
            return phrase
        
        # Check for phrase at the start of the input with word boundary
        if normalized_input.startswith(normalized_phrase):
            # Check if it's followed by a non-word character or end of string
            next_char_pos = len(normalized_phrase)
            if next_char_pos >= len(normalized_input):
                return phrase
            elif not normalized_input[next_char_pos].isalnum():
                return phrase
        
        # Check for phrase at the end of the input with word boundary
        if normalized_input.endswith(normalized_phrase):
            # Check if it's preceded by a non-word character or start of string
            prev_char_pos = len(normalized_input) - len(normalized_phrase) - 1
            if prev_char_pos < 0:
                return phrase
            elif not normalized_input[prev_char_pos].isalnum():
                return phrase
        
        # Check for phrase in the middle of the input with word boundaries
        if f' {normalized_phrase} ' in f' {normalized_input} ':
            return phrase
            
        # Check for phrase followed by punctuation
        for punct in ['.', ',', '!', '?']:
            if f' {normalized_phrase}{punct}' in f' {normalized_input} ':
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
