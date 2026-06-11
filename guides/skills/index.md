# Create agent skills

Skills are filesystem-based capability packages that specialize agent behavior. A skill is a directory containing a `SKILL.md` file with metadata in YAML frontmatter, and optionally further skill resources. Skills follow the [agentskills.io](https://agentskills.io/specification/) specification, a lightweight format for extending agent capabilities with specialized knowledge and workflows. Skills that guide code execution are particularly well-suited for freeact's code action approach. Skills are loaded on demand: only metadata is in context initially, full instructions load when relevant.

## Add a custom skill

Custom skills are loaded from `.agents/skills/` in the working directory. Each subdirectory containing a `SKILL.md` file is registered as a skill:

```
.agents/skills/
└── <skill-name>/
    ├── SKILL.md    # Skill metadata and instructions
    └── ...         # Further skill resources
```

Metadata of custom skills appears in the system prompt after [bundled skills](#bundled-skills). The `.agents/skills/` directory is not managed by freeact and is not auto-created.

## Example: PDF generation

This example uses the PDF skill from the [Anthropic skills repository](https://github.com/anthropics/skills), a collection of production-quality skills maintained by Anthropic.

Create a [workspace with a virtual environment](https://gradion-ai.github.io/freeact/getting-started/installation/#option-2-with-virtual-environment) and install the required dependencies for this example:

```
uv pip install reportlab
```

Install the PDF skill:

```
git clone https://github.com/anthropics/skills.git /tmp/skills
mkdir -p .agents/skills
cp -r /tmp/skills/skills/pdf .agents/skills/
```

Start the [CLI tool](https://gradion-ai.github.io/freeact/reference/cli/index.md):

```
uv run freeact
```

When asked to

> calculate compound interest for $10,000 at 5% for 10 years, save result to output/compound_interest.pdf

the agent:

1. Identifies the PDF skill as relevant based on the request to create a PDF document
1. Loads the skill instructions by reading the `pdf/SKILL.md` file
1. Performs the calculation and generates a PDF following the skill's guidance

## Invoke skills

The agent autonomously selects a skill when the request matches the skill's description. Skills can also be invoked explicitly:

- In the [CLI tool](https://gradion-ai.github.io/freeact/reference/cli/#skill-invocation), `/skill-name args` invokes a skill by name.
- In SDK applications, prompts passed to `stream()` may contain skill tags that the agent processes:

```
<skill name="review">the auth module</skill>
```

The CLI generates these tags from the `/skill-name` syntax. Skills are discovered from `.freeact/skills/` and `.agents/skills/` directories.

## Bundled skills

Freeact contributes three bundled skills to `.freeact/skills/`:

| Skill                                                                                                              | Description                                                            |
| ------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| [output-parsers](https://github.com/gradion-ai/freeact/tree/main/freeact/config/templates/skills/output-parsers)   | Generate output parsers for `mcptools/` with unstructured return types |
| [saving-codeacts](https://github.com/gradion-ai/freeact/tree/main/freeact/config/templates/skills/saving-codeacts) | Save generated code actions as reusable tools in `gentools/`           |
| [task-planning](https://github.com/gradion-ai/freeact/tree/main/freeact/config/templates/skills/task-planning)     | Basic task planning and tracking workflows                             |

Bundled skills are auto-created from templates on [initialization](https://gradion-ai.github.io/freeact/reference/configuration/#initialization). User modifications persist across restarts.

Tool authoring

The `output-parsers` and `saving-codeacts` skills enable tool authoring. See [Enhance generated tools](https://gradion-ai.github.io/freeact/guides/enhancing-tools/index.md) and [Save code actions as tools](https://gradion-ai.github.io/freeact/guides/saving-tools/index.md) for walkthroughs.
