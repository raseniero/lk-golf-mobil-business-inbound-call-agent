---
trigger: manual
---

---
description: Instructions for making code changes.
globs:
alwaysApply: false
---

# Rule: Instructions for making code changes.

This is a guidelines to the AI Assistant for making code changes.

## Goal

The goal is to write code that is modular and testable.

## Process

### Before making code changes

1. Grab the latest code from the `main` branch
2. Create a new branch
3. Switch to the newly created branch, and perform code changes there
4. Use a python virtual environment 

### While making code changes

1. Write unit tests to satisfy the task requirement
2. Write code until all unit tests passes

### After making code changes

1. Commit code changes to local repo
2. Push changes to Github.com using `gh` command or the Github plugin
3. Create a PR from the newly create branch to the `main` branch
4. Assign the new PR to `raseniero`
