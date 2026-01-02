# Agent Skills

Agent skills are filesystem-based capability packages that extend freeact's behavior for specific domains. Skills provide domain-specific instructions and resources that the agent can discover and use as needed.

For the official Agent Skills specification, see [agentskills.io](https://agentskills.io/).

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
description: Create and manipulate PDF documents. Use when working with PDF files or when the user mentions PDFs, forms, or document extraction.
---

# PDF Skill

Instructions for creating and manipulating PDFs...
```

**Required fields:**

- `name`: Skill identifier (max 64 characters, lowercase letters, numbers, and hyphens only)
- `description`: Explains what the skill does and when to use it (max 1024 characters). The description is used by the agent to determine when a skill is relevant.

**Optional fields:**

- `license`: License name or bundled file reference
- `compatibility`: Environment requirements (max 500 characters)
- `metadata`: Custom key-value pairs

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

Skills load progressively to minimize context usage. The official specification defines three loading levels:

| Level | When Loaded | Token Cost | Content |
|-------|-------------|------------|---------|
| **Level 1: Metadata** | At startup | ~100 tokens per skill | `name` and `description` from YAML frontmatter |
| **Level 2: Instructions** | When skill is relevant | <5k tokens recommended | Full SKILL.md body with instructions and guidance |
| **Level 3: Resources** | As needed | Varies | Bundled files (scripts, references, templates) accessed on demand |

This means an agent with dozens of installed skills only loads the specific instructions it needs for the current task. When the agent determines a skill is relevant based on its description, it reads the full SKILL.md instructions. Additional resources are loaded only when referenced.

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

1. Create a directory under `.freeact/skills/` with your skill name (lowercase, hyphens allowed)
2. Add a `SKILL.md` file with YAML frontmatter:
   - `name`: Skill identifier (must match directory name)
   - `description`: Explains what the skill does and when to use it
3. Write instructions in markdown following the frontmatter
4. Optionally add resources in subdirectories (`scripts/`, `references/`, `assets/`)

The agent will discover your skill on the next startup and use it when tasks match its description.
