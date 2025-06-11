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
    
    # Compile a regex pattern for all termination phrases
    pattern = re.compile(r'\b(?:' + '|'.join(re.escape(phrase) for phrase in termination_phrases) + r')\b', re.IGNORECASE)
    
    # Search for a match in the input text
    match = pattern.search(text)
    if match:
        # Return the matched phrase in its original case
        return next((phrase for phrase in termination_phrases if phrase.lower() == match.group(0).lower()), None)
    
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
