# Task Planning

Freeact includes a task planning skill that enables structured planning workflows with user feedback loops and progress tracking.

## When to Use Planning

The planning skill activates when you explicitly request planning:

- "Make a plan"
- "Plan first"
- "Create a plan before starting"

For multi-step tasks involving research, tool discovery, and execution, planning helps break down complexity and track progress.

## Planning Workflow

The planning workflow consists of three phases:

### 1. Plan Creation

When you request planning, the agent:

- Analyzes the task requirements
- Identifies required tools and information sources
- Creates a step-by-step plan with actionable items
- Presents the plan for your approval

### 2. Plan Confirmation

Before execution, you can:

- Approve the plan as-is
- Request modifications
- Add or remove steps
- Clarify requirements

The plan is saved to `.freeact/plans/` for reference and progress tracking.

### 3. Step-by-Step Execution

Once confirmed, the agent:

- Executes each step sequentially
- Updates the plan file to mark completed steps
- Reports progress after each step
- Handles errors and adjusts as needed

## Example Session

The following recording shows the agent creating and executing a plan to find repository commits:

[![Terminal session](../recordings/planning/conversation.svg)](../recordings/planning/conversation.html){target="_blank"}

Key elements in the recording:

1. **Plan creation**: Agent reads the task-planning skill and creates a 5-step plan
2. **User confirmation**: User approves the plan with "yes, proceed"
3. **Plan persistence**: Agent saves the plan to `.freeact/plans/deepseek-r1-author-commits.md`
4. **Tool usage**: Agent uses `mcptools.google.web_search` and `mcptools.github` tools
5. **Progress tracking**: Agent updates the plan file, marking steps `[x]` as completed
6. **Final report**: Agent summarizes findings after completing all steps

## Plan File Format

Plans are saved as Markdown files in `.freeact/plans/`:

```markdown
# Task Name Plan

## Steps

- [x] Step 1: Completed step description
- [x] Step 2: Another completed step
- [ ] Step 3: Pending step
- [ ] Step 4: Final step
```

The checkbox format (`[ ]` / `[x]`) provides visual progress tracking that persists across sessions.

## Integration with Code Actions

Planning integrates with programmatic tool calling:

- Plans identify which tools are needed before execution
- Each step can involve multiple tool calls within a single code action
- The agent reads tool APIs (`mcptools/`) to understand available parameters
- Results from earlier steps inform later steps

## Cross-Session Memory

Plans stored in `.freeact/plans/` persist across sessions:

- Resume interrupted tasks by referencing the plan file
- Review completed plans for audit trails
- Reuse successful plans as templates for similar tasks

See [Reusable Code Actions](reusable-codeacts.md) for additional memory management capabilities.
