# Agent Skills

Agent skills are filesystem-based capability packages that extend freeact's behavior for specific domains. See [agentskills.io](https://agentskills.io/) for the official specification.

## Example: PDF Generation

Install the PDF skill from the [Anthropic skills repository](https://github.com/anthropics/skills):

```bash
git clone https://github.com/anthropics/skills.git /tmp/skills
cp -r /tmp/skills/skills/pdf .freeact/skills/
```

Install the required package:

```bash
uv pip install reportlab
```

The following recording shows the agent using the PDF skill to perform a calculation and save the result as a PDF document:

[![Terminal session](../recordings/agent-skills/conversation.svg)](../recordings/agent-skills/conversation.html){target="_blank"}

The agent identifies the PDF skill as relevant, performs the calculation, and generates a PDF using the skill's instructions.
