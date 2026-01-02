# Freeact Documentation Plan

## Overview

Create concise, LLM-friendly documentation for freeact with self-contained examples. Documentation will use Material for MkDocs with mkdocstrings for API docs.

## Documentation Structure

```
docs/
├── index.md                    # Overview (existing, update links)
├── installation.md             # Workspace setup and installation
├── quickstart.md               # Minimal terminal + Python API example
├── features/
│   ├── programmatic-tools.md   # PTC on MCP servers
│   ├── reusable-codeacts.md    # Code actions as tools (3 terminal sessions)
│   ├── agent-skills.md         # agentskills.io extensions
│   ├── sandbox.md              # Sandboxed code execution
│   ├── planning.md             # Task planning and memory
│   ├── python-packages.md      # Using matplotlib, sklearn, etc.
│   └── approval.md             # Unified approval mechanism
├── python-api.md               # Python API intro guide (NEW)
├── api/
│   ├── agent.md                # Agent API (existing, no changes)
│   └── config.md               # Config API (existing, no changes)
├── configuration.md            # Configuration reference
└── recordings/                 # Terminal session HTML recordings
    └── *.html

examples/
├── __init__.py
├── basic_agent.py              # Minimal agent example
├── custom_config.py            # Loading and using Config
└── generate_mcptools.py        # mcptools generation example
```

---

## Task Checklist

### Setup Tasks
- [x] Create `docs/features/` directory
- [x] Create `docs/recordings/` directory
- [x] Create `examples/` directory with `__init__.py`

### Documentation Files

#### Installation (`docs/installation.md`)
- [x] Write workspace setup with `uv init --bare --python 3.13`
- [x] Document `uv add freeact`
- [x] Document `freeact init` for initial configuration
- [x] Describe default config: 2 MCP servers for filesystem search, 1 for web search (Gemini)
- [x] Mention future extensions (bash tool, web fetch, hybrid search for PTC)
- [x] Document sandbox-runtime installation (required for `--sandbox` mode):
  - [x] `npm install -g @anthropic-ai/sandbox-runtime@0.0.21` (provides `srt` command)
  - [x] macOS: `brew install ripgrep` (uses native `sandbox-exec`)
  - [x] Linux: `apt-get install bubblewrap socat ripgrep` (note: Linux sandboxing WIP)
  - [x] Reference: https://gradion-ai.github.io/ipybox/installation/index.md

#### Quickstart (`docs/quickstart.md`)
- [x] Create minimal terminal session recording
- [x] Embed Python API example from `examples/basic_agent.py`

#### Feature: Programmatic Tool Calling (`docs/features/programmatic-tools.md`)
- [x] Write setup instructions for GitHub MCP server in `ptc-servers`
- [x] Create terminal recording with query: "get the top 3 github repos of torvalds, sorted by stars desc."
- [x] Document `mcptools/` generation
- [x] Explain progressive loading and limitations

#### Feature: Reusable Code Actions (`docs/features/reusable-codeacts.md`)
The raw recording for this feature already exists in
- docs/recordings/reusable-codeacts-1/
- docs/recordings/reusable-codeacts-2/
- docs/recordings/reusable-codeacts-3/

- [x] Create terminal recording 1: Generate output parser for search_repositories
- [x] Create terminal recording 2: Compose search_repositories + list_commits, save as tool
- [x] Create terminal recording 3: Rerun task showing tool discovery and usage

#### Feature: Agent Skills (`docs/features/agent-skills.md`)
- [x] Write shell instructions: clone skills repo, copy pdf skill to `.freeact/skills`, install deps
- [x] Create terminal recording: calculation + save as PDF
- [x] Document progressive skill loading

#### Feature: Sandboxing (`docs/features/sandbox.md`)
- [x] Write brief intro to ipybox sandboxing (sandbox-runtime)
- [x] Document `--sandbox` and `--sandbox-config` CLI options
- [x] Create terminal recording 1: Custom sandbox allowing example.org, blocking others
- [x] Create terminal recording 2: MCP server sandboxing (documented with config examples, linked to ipybox docs)

#### Feature: Task Planning (`docs/features/planning.md`)
- [x] Create terminal recording with query: "what are the latest 3 commit of the top github repo (w.r.t stars) of the author of DeepSeek-R1 agents with code actions? Make a plan"
- [x] Describe planning skill and workflow
- [x] Reference reusable-codeacts for memory management

#### Feature: Python Packages (`docs/features/python-packages.md`)
- [x] Document `uv add matplotlib scikit-learn`
- [x] Create terminal recording: sine function + GP regressor fitting
- [x] Include generated image in docs

#### Feature: Unified Approval (`docs/features/approval.md`)
- [x] Write explanation of Y/n/a/s options
- [x] Document `permissions.json` mechanism and format
- [x] Note: No separate recording needed (approvals shown in all other recordings)

#### Python API (`docs/python-api.md`)
- [x] Write narrative introduction explaining CLI/terminal use Python API internally
- [x] Document Config API: loading config, accessing skills_metadata, system_prompt, servers
- [x] Document Agent API: async context manager, streaming events, handling ApprovalRequest
- [x] Document mcptools generation: `generate_mcp_sources()` for PTC servers
- [x] Add cross-references to API reference (api/agent.md, api/config.md)

#### Configuration Reference (`docs/configuration.md`)
- [x] Document `.freeact/` directory structure
- [x] Document `servers.json` format (mcp-servers, ptc-servers)
- [x] Document `prompts/system.md` placeholders ({working_dir}, {skills})
- [x] Document Skills structure (`SKILL.md` format with YAML frontmatter)
- [x] Document `permissions.json` format

#### Example Files
- [x] Create `examples/basic_agent.py`
- [x] Create `examples/custom_config.py`
- [x] Create `examples/generate_mcptools.py`

### Update Existing Files

#### Update `docs/index.md`
- [ ] Add links from feature table to corresponding feature pages

#### Update `mkdocs.yml`
- [x] Add new pages to navigation
- [x] Update llmstxt plugin configuration

---

## Recording Details

### Recording Format

Use SVG preview with clickable link to HTML:

```markdown
[![Terminal session](recordings/feature-name/conversation.svg)](recordings/feature-name/conversation.html){target="_blank"}
```

### Recording Commands

Use `freeact-interaction` skill via tmux:

```bash
# Start session with recording
tmux new-session -d -s agent -x 120 -y 50
tmux send-keys -t agent 'uv run freeact --record --record-dir docs/recordings/FEATURE_NAME --record-title "TITLE"' Enter

# Send queries and approvals
tmux send-keys -t agent 'YOUR QUERY HERE' Enter
sleep N
tmux send-keys -t agent 'Y' Enter  # or 'a' for always

# Quit and cleanup
tmux send-keys -t agent 'q' Enter
tmux kill-session -t agent
```

### Recording Directories

```
docs/recordings/
├── quickstart/
├── programmatic-tools/
├── reusable-codeacts-1/
├── reusable-codeacts-2/
├── reusable-codeacts-3/
├── agent-skills/
├── sandbox-custom/
├── sandbox-mcp/
├── planning/
└── python-packages/
```

---

## Specific Scenarios and Queries

### Programmatic Tool Calling

1. Add to `.freeact/servers.json` under `ptc-servers`:
```json
"github": {
  "url": "https://api.githubcopilot.com/mcp/",
  "headers": {"Authorization": "Bearer ${GITHUB_API_KEY}"}
}
```

2. Query: "get the top 3 github repos of torvalds, sorted by stars desc."

### Reusable Code Actions (3 sessions)

Based on ipybox ccplugin scenario (https://gradion-ai.github.io/ipybox/ccplugin/index.md):

**Session 1**: Generate output parser
- Use GitHub search_repositories tool
- Agent should infer output structure and create parser

**Session 2**: Compose and save
- Use augmented search_repositories (with parser)
- Compose with list_commits
- Save composite as tool

**Session 3**: Tool discovery
- Run similar task
- Agent should discover and use saved tool

### Agent Skills (PDF example)

Setup:
```bash
git clone https://github.com/anthropics/skills.git /tmp/skills
cp -r /tmp/skills/skills/pdf .freeact/skills/
uv pip install pypdf pdfplumber
```

Query: Ask for a calculation (e.g., compound interest), generate text around result, save as PDF.

### Sandboxing

**Custom sandbox config** (save as `sandbox-config.json`):
```json
{
  "network": {
    "allowedDomains": ["example.org"],
    "deniedDomains": [],
    "allowLocalBinding": true
  },
  "filesystem": {
    "denyRead": ["sandbox-config.json"],
    "allowWrite": ["."],
    "denyWrite": ["sandbox-config.json"]
  }
}
```

Reference: https://github.com/anthropic-experimental/sandbox-runtime

Available fields:
- `network.allowedDomains`: Permitted hosts (supports wildcards like `*.example.com`)
- `network.deniedDomains`: Explicitly blocked domains (takes precedence)
- `network.allowUnixSockets`: Socket paths allowed (macOS only)
- `network.allowLocalBinding`: Boolean for local port binding
- `filesystem.denyRead`: Paths blocked from reading
- `filesystem.allowWrite`: Paths permitted for writing
- `filesystem.denyWrite`: Exceptions within allowed write paths

Run with: `freeact --sandbox --sandbox-config sandbox-config.json`

Test queries (use explicit code for reproducibility):
- "Run: `import requests; print(requests.get('https://example.org').status_code)`" (should pass with 200)
- "Run: `import requests; print(requests.get('https://google.com').status_code)`" (should fail - network blocked)
- "Run: `open('sandbox-config.json').read()`" (should fail - read denied)

**MCP server sandboxing**: Adapt examples from https://gradion-ai.github.io/ipybox/sandbox/index.md

### Planning

Query: "what are the latest 3 commit of the top github repo (w.r.t stars) of the author of DeepSeek-R1 agents with code actions? Make a plan"

### Python Packages (matplotlib + sklearn)

Setup: `uv add matplotlib scikit-learn`

Query: "Generate 30 noisy samples from a sine function and fit a Gaussian process regressor to the data. Show the result as a plot."

Image will be saved to `images/` directory (configurable).

---

## llms.txt Configuration

Update `mkdocs.yml`:

```yaml
plugins:
  - llmstxt:
      markdown_description: |
        Freeact is a lightweight, general-purpose agent that acts via code actions rather than JSON tool calls.
        It writes executable Python code that can call multiple tools, process intermediate results, and branch
        on conditions. Tasks that would otherwise require many inference rounds with JSON tool calling can be
        completed in a single pass.

        The agent auto-generates typed Python modules from MCP tool schemas, enabling programmatic tool calling
        within code actions. Successful code actions can be saved as discoverable tools with clean interfaces,
        building tool libraries that evolve as the agent works. Agent skills provide filesystem-based capability
        packages that extend behavior for specific domains.

        All code executes locally in a sandboxed IPython kernel via ipybox, with configurable filesystem and
        network restrictions. Tool and skill information loads progressively as needed rather than consuming
        context upfront. A unified approval mechanism gates all tool executions regardless of origin.
      full_output: llms-full.txt
      sections:
        User Guide:
          - index.md: Overview and features
          - installation.md: Setup and installation
          - quickstart.md: Getting started
        Features:
          - features/programmatic-tools.md: MCP programmatic tool calling
          - features/reusable-codeacts.md: Code actions as tools
          - features/agent-skills.md: agentskills.io extensions
          - features/sandbox.md: Sandboxed execution
          - features/planning.md: Task planning
          - features/python-packages.md: Python package usage
          - features/approval.md: Approval mechanism
        Python API:
          - python-api.md: Python API introduction and examples
        API Reference:
          - api/agent.md: Agent API
          - api/config.md: Config API
        Reference:
          - configuration.md: Configuration reference
```

---

## Key Reference Files

### Freeact Source Files
- `freeact/cli.py` - CLI options (--sandbox, --record, etc.)
- `freeact/agent/core.py` - Agent class and event types
- `freeact/agent/config/config.py` - Config class
- `freeact/agent/config/init.py` - Config initialization
- `freeact/agent/config/templates/` - Default templates
- `freeact/permissions.py` - Permission system

### External References
- ipybox sandbox docs: https://gradion-ai.github.io/ipybox/sandbox/index.md
- ipybox ccplugin docs: https://gradion-ai.github.io/ipybox/ccplugin/index.md
- Anthropic skills repo: https://github.com/anthropics/skills

### Skills
- Use `freeact-interaction` skill for terminal session recordings
- Use `mkdocs-formatter` skill for documentation formatting

---

## Decisions Made

- **Recording format**: SVG preview with link to HTML (same pattern as older freeact quickstart)
- **Python API**: Add intro guide (docs/python-api.md) with embedded examples; existing mkdocstrings autodocs unchanged
- **Index.md**: Add links from feature table to corresponding feature pages
- **Unified approval**: Documentation-only section (approvals shown in all other recordings)
- **Progressive disclosure**: No separate example (covered by programmatic-tools and agent-skills examples)
