# PRD: Call Termination Feature for Golf Club Repair Voice AI

## 1. Introduction/Overview

This PRD outlines the implementation of a call termination feature for the Golf Club Repair Voice AI Agent. The feature will allow the agent to gracefully end calls when specific termination phrases are detected from the caller, improving the overall user experience by providing a natural way to conclude conversations.

## 2. Goals

- Enable the agent to detect when a caller wants to end the conversation
- Provide a polite and professional call termination experience
- Log call terminations for analytics and quality assurance
- Implement proper error handling for call termination

## 3. User Stories

- As a customer, I want to end the call naturally by saying "goodbye" or similar phrases, so I don't have to wait for the agent to finish speaking.
- As a business owner, I want calls to be logged when they end naturally, so I can track call duration and termination patterns.
- As a developer, I want proper error handling for call termination, so any issues can be quickly identified and resolved.

## 4. Functional Requirements

1. The agent must detect the following termination phrases (case-insensitive):
   - "goodbye"
   - "bye"
   - "that's all, thank you"
   - "i'm done"
   - "end call"
   - "that's all for now"
   - "thanks, that's all"

2. Upon detecting a termination phrase, the agent must:
   - Respond with "Goodbye"
   - Immediately terminate the call
   - Log the call termination event with timestamp and call details

3. The system must log the following information for each terminated call:
   - Call start and end timestamps
   - Call duration
   - Termination phrase detected
   - Any error that occurred during termination

4. Error Handling:
   - If call termination fails, log the error with details
   - Implement a fallback mechanism to ensure calls don't remain open indefinitely
   - Include error codes and messages for common failure scenarios

## 5. Non-Goals (Out of Scope)

- Adding additional conversation context analysis for termination
- Customizable termination phrases (will be hardcoded for now)
- Call transfer functionality
- Post-call surveys or feedback collection

## 6. Design Considerations

- The termination should feel natural and not abrupt
- The "Goodbye" response should be clear but concise
- Logs should be structured for easy analysis
- Error messages should be descriptive enough for debugging

## 7. Technical Considerations

- Need to integrate with LiveKit's call termination API
- Should use existing logging infrastructure
- Consider rate limiting for termination attempts
- Ensure thread safety when terminating calls

## 8. Success Metrics

- 95% of calls with termination phrases are properly terminated
- Less than 1% of calls experience termination errors
- Call logs are properly captured for 100% of terminated calls

## 9. Open Questions

- Should we add more termination phrases?
- Is there a need for different termination responses based on context?
- Should we implement a confirmation step before terminating calls?

## Implementation Notes

- The feature will be implemented in the `SimpleAgent` class in `agent.py`
- Will need to extend the agent's message handling to check for termination phrases
- Should integrate with the existing logging setup
- Will require testing with actual call scenarios to ensure smooth termination
