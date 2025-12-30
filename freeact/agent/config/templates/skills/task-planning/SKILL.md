---
name: task-planning
description: Structured task planning workflow with user feedback loops. Use when the user explicitly requests planning (e.g., "make a plan", "plan first", "create a plan"). Covers creating plans with actionable steps, iterating based on feedback, saving confirmed plans, and executing step-by-step with progress tracking.
---

# Task Planning

Structured workflow for planning and executing tasks when explicitly requested by the user.

## Planning Phase

### 1. Create Initial Plan

Draft a plan with clear, actionable steps using markdown checklist format:

```markdown
- [ ] Step 1: Description
- [ ] Step 2: Description
- [ ] Step 3: Description
```

### 2. Request Feedback

Present the plan to the user and ask for feedback. Do not proceed until feedback is received.

### 3. Iterate Until Confirmed

Revise the plan based on user feedback. Continue the proposal-feedback loop until the user confirms.

### 4. Save Confirmed Plan

Write the confirmed plan to `.freeact/plans/<task-name>.md` where:
- `<task-name>` is a descriptive kebab-case name
- Example: `.freeact/plans/add-user-authentication.md`
- The `.freeact/plans/` directory already exists

## Execution Phase

### 5. Execute Step-by-Step

Work through the plan sequentially:
- First unchecked item is the current task
- After completing each step, mark with checkmark: `- [x] Step description`
- Update the plan file to reflect progress

### 6. Revise as Needed

If execution reveals the need for plan adjustments:
- Update the plan file with revised steps
- Inform the user of significant changes

### 7. Request Feedback During Execution

If encountering uncertainty or needing user input during execution, ask for feedback before proceeding.

## Plan File Format

```markdown
# <Task Title>

## Steps

- [x] Completed step
- [ ] Pending step
- [ ] Another pending step

## Notes

Optional section for context, decisions made, or issues encountered.
```
