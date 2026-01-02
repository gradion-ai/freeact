# Agent Skills

Agent skills are filesystem-based capability packages that extend freeact's behavior for specific domains. Skills provide domain-specific instructions, dependencies, and resources that the agent can discover and use as needed.

## Skill Structure

Each skill lives in a directory under `.freeact/skills/` with a `SKILL.md` file:

```
.freeact/skills/
└── pdf/
    ├── SKILL.md           # Skill definition with YAML frontmatter
    ├── resources/         # Optional resources (templates, examples)
    └── ...
```

The `SKILL.md` file contains YAML frontmatter with metadata followed by markdown instructions:

```markdown
---
name: pdf
description: Create and manipulate PDF documents
triggers:
  - pdf
  - document
dependencies:
  - pypdf
  - pdfplumber
---

# PDF Skill

Instructions for creating and manipulating PDFs...
```

## Installing a Skill

Skills from the [Anthropic skills repository](https://github.com/anthropics/skills) can be installed by copying them to `.freeact/skills/`:

```bash
# Clone the skills repository
git clone https://github.com/anthropics/skills.git /tmp/skills

# Copy the PDF skill
cp -r /tmp/skills/skills/pdf .freeact/skills/

# Install required dependencies
uv add pypdf pdfplumber
```

After installation, the agent can discover and use the skill when relevant tasks arise.

## Progressive Loading

Skills load progressively to minimize context usage:

1. **Startup**: Only skill names and descriptions are known
2. **Trigger matching**: When a task matches skill triggers, the skill summary loads
3. **Full activation**: Full skill instructions load only when the agent explicitly uses the skill

This means an agent with dozens of installed skills only loads the specific instructions it needs for the current task.

## Example Session

The following recording shows the agent using the PDF skill to perform a calculation and save the result as a PDF document:

[![Terminal session](../recordings/agent-skills/conversation.svg)](../recordings/agent-skills/conversation.html){target="_blank"}

Key steps in the recording:

1. **Task request**: User asks for a compound interest calculation with PDF output
2. **Skill discovery**: Agent identifies the PDF skill as relevant
3. **Calculation**: Agent performs the requested calculation
4. **PDF generation**: Agent uses skill instructions to create and save a PDF

## Creating Custom Skills

To create a custom skill:

1. Create a directory under `.freeact/skills/` with your skill name
2. Add a `SKILL.md` file with YAML frontmatter:
   - `name`: Skill identifier
   - `description`: Brief description for discovery
   - `triggers`: Keywords that activate the skill
   - `dependencies`: Required Python packages
3. Write instructions in markdown following the frontmatter
4. Optionally add resources in subdirectories

The agent will discover your skill on the next startup and use it when tasks match its triggers.
