# Task List Management and Coding Changes

Guidelines for managing task lists in markdown files to track progress on completing a PRD. And guidelines for making code changes.

## Task List Implementation

- **One sub-task at a time:** Do **NOT** start the next sub‑task until you ask the user for permission and they say “yes” or "y"
- **Completion protocol:**  
  1. When you finish a **sub‑task**, immediately mark it as completed by changing `[ ]` to `[x]`.  
  2. If **all** subtasks underneath a parent task are now `[x]`, also mark the **parent task** as completed.  
- Stop after each sub‑task and wait for the user’s go‑ahead.

## Task List Maintenance

1. **Update the task list as you work:**
   - Mark tasks and subtasks as completed (`[x]`) per the protocol above.
   - Add new tasks as they emerge.

2. **Maintain the “Relevant Files” section:**
   - List every file created or modified.
   - Give each file a one‑line description of its purpose.

## AI Instructions

When working with task lists, the AI must:

1. Regularly update the task list file after finishing any significant work.
2. Follow the completion protocol:
   - Mark each finished **sub‑task** `[x]`.
   - Mark the **parent task** `[x]` once **all** its subtasks are `[x]`.
3. Add newly discovered tasks.
4. Keep “Relevant Files” accurate and up to date.
5. Before starting work, check which sub‑task is next.
6. After implementing a sub‑task, update the file and then pause for user approval.

## Instructions for Making Code Changes

This is a set of instructions to the AI Assistant for making code changes. The goal is to write code that is modular and testable.

1. Before making code changes
1.1. Grab the latest code from the `main` branch
1.2. Create a new branch
1.3. Switch to the newly created branch, and perform code changes here
1.4. Create and activate a python virtual environment
2. While making code changes
2.1. Write unit test to satisfy the requirement
2.2. Write code, until all unit tests pass
3. Completing making code changes
3.1. Commit all changes to local repo
3.2. Push changes to Github.com
3.3. Create a PR from the newly create branch to the `main` branch
3.4. Assign the new PR to `raseniero`