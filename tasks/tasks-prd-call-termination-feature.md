# Task List: Call Termination Feature Implementation

## Relevant Files

- `agent.py` - Main agent implementation where call termination logic will be added
- `utils.py` - Contains utility functions that might need updates
- `requirements.txt` - May need updates if new dependencies are required
- `prompts/basic_prompt.md` - Contains agent instructions that might need updates
- `tests/test_call_termination.py` - New test file for call termination feature

## Tasks

### 1.0 Set Up Call Termination Infrastructure
- [x] 1.1 Add new event handlers for call lifecycle events
- [x] 1.2 Create a call state management system
- [x] 1.3 Set up call duration tracking
- [x] 1.4 Initialize termination phrase set in agent's `__init__`
  ### Before Starting
  - [ ] Ensure you're on the latest `main` branch
  - [ ] Create a new branch: `feature/termination-phrase-init`
  - [ ] Set up Python virtual environment if not already active

  ### Implementation Steps
  1. **Add Default Phrases Constant**
     - Add to `agent.py`:
       ```python
       DEFAULT_TERMINATION_PHRASES = {
           "goodbye",
           "end call",
           "that's all",
           "thank you",
           "bye"
       }
       ```

  2. **Update `__init__` Method**
     - Add parameter: `termination_phrases: Optional[Iterable[str]] = None`
     - Initialize instance variable: `self.termination_phrases: Set[str]`
     - Use provided phrases or default: `self.termination_phrases = set(termination_phrases or self.DEFAULT_TERMINATION_PHRASES)`

  3. **Add Type Hints**
     - Import required types: `from typing import Iterable, Set, Optional`

  ### Testing Requirements
  - [ ] Create test file: `tests/test_termination_phrases.py`
  - Test cases:
    1. Initialize with default phrases
    2. Initialize with custom phrases
    3. Initialize with empty list (should use defaults)
    4. Verify phrases are stored as a set

  ### Documentation
  - [ ] Update `__init__` docstring with new parameter
  - [ ] Add type hints for better code clarity
  - [ ] Include example usage in docstring

  ### After Implementation
  - [ ] Run all tests: `python -m pytest -v`
  - [ ] Commit changes with message: "feat: Initialize termination phrases in agent"
  - [ ] Push branch and create PR to `main`
  - [ ] Assign PR to `raseniero`
- [ ] 1.5 Add test stubs for new functionality

### 2.0 Implement Termination Phrase Detection
- [ ] 2.1 Create phrase detection utility function
- [ ] 2.2 Add case-insensitive phrase matching
- [ ] 2.3 Handle partial matches in user input
- [ ] 2.4 Add tests for phrase detection
- [ ] 2.5 Optimize phrase lookup performance

### 3.0 Add Call Termination Logic
- [ ] 3.1 Implement `_terminate_call` method
- [ ] 3.2 Add call disconnection logic
- [ ] 3.3 Implement immediate response to termination phrases
- [ ] 3.4 Add "Goodbye" response before termination
- [ ] 3.5 Add tests for call termination flow

### 4.0 Implement Logging System
- [ ] 4.1 Define log message format for call termination
- [ ] 4.2 Add call start/end timestamp logging
- [ ] 4.3 Log detected termination phrases
- [ ] 4.4 Add call duration calculation
- [ ] 4.5 Configure log levels appropriately

### 5.0 Add Error Handling and Recovery
- [ ] 5.1 Implement error handling for termination process
- [ ] 5.2 Add fallback disconnection mechanism
- [ ] 5.3 Create error codes and messages
- [ ] 5.4 Add error logging with stack traces
- [ ] 5.5 Test error scenarios

### 6.0 Testing and Validation
- [ ] 6.1 Unit tests for all new functions
- [ ] 6.2 Integration tests for call flow
- [ ] 6.3 Test with various termination phrases
- [ ] 6.4 Verify error handling behavior
- [ ] 6.5 Performance testing with multiple calls
- [ ] 6.6 Update documentation

## Notes

- All new code should follow the project's existing style guidelines
- Log messages should be clear and actionable
- Error messages should be descriptive and include relevant context
- Tests should cover both success and error cases
- Consider thread safety for all shared resources
- Document any new configuration options
- Update README with new feature information if needed

## Testing Commands

Run unit tests:
```bash
python -m pytest tests/test_call_termination.py -v
```

Run all tests:
```bash
python -m pytest
```

Run with logging:
```bash
LOG_LEVEL=DEBUG python -m pytest tests/test_call_termination.py -v -s
```
