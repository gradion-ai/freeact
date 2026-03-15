# Rerunning Documentation Examples

Instructions for a Claude Code session to reproduce all freeact documentation examples as live tmux sessions with widgets expanded to match `docs/screenshots/`.

The goal is 6 tmux sessions, each running a freeact instance showing the final state of one example. Use the `freeact-interaction` skill for tmux/Textual interaction patterns.

## API Keys

Every workspace needs the project `.env` file. Copy it from the project root:

```bash
cp /path/to/freeact/.env /tmp/workspace-dir/
```

## Workspace Setup Patterns

**Minimal** (quickstart, sandbox): just create a directory and copy `.env`.

**With virtual environment** (agent-skills, python-packages): create a directory, then:

```bash
cd /tmp/workspace-dir
uv init --bare --python 3.13
uv add freeact
uv pip install <extra-packages>
```

**Important**: All package installations (`uv add`, `uv pip install`) must complete *before* launching freeact. Freeact's IPython kernel inherits the virtual environment at startup, so packages installed after launch will not be available in code actions. Verify with `uv run python -c "import <package>"` before proceeding.

**With config init** (output-parser): create a directory, copy `.env`, then run `uvx freeact init` to generate `.freeact/agent.json`.

## tmux + Textual Interaction

Follow the `freeact-interaction` skill for all tmux interaction. Key points:

- Session size: 120x50
- Separate tool calls for `send-keys` and `capture-pane` (never chain them)
- Wait 12+ seconds after starting freeact for MCP server initialization
- Launch freeact with `--skip-permissions` to avoid approval prompts

### Expanding Widgets

After the agent responds, widgets auto-collapse per config. To selectively expand widgets to match a screenshot:

1. Disable tmux mouse: `tmux set-option -t SESSION mouse off`
2. Capture pane with line numbers: `tmux capture-pane -t SESSION -p | cat -n`
3. Click on a collapsed widget row (1-indexed, column 5 hits the toggle):
   ```bash
   tmux send-keys -t SESSION Escape '[<0;5;ROW_NUM_HERE M' Escape '[<0;5;ROW_NUM_HEREm'
   ```
   (No space before M -- it is literal `M` for press, literal `m` for release.)
4. Expand from bottom to top so row numbers of items above do not shift.
5. If the target has scrolled off-screen, scroll up first:
   ```bash
   for i in $(seq 1 20); do tmux send-keys -t SESSION Escape '[<64;60;25M' Escape '[<64;60;25m'; done
   ```
6. Re-capture and verify after each expansion.

### Retrying

If the agent produces unexpected results, quit (`ctrl+q`), wait 3 seconds, restart freeact, and re-send the query.

## Parallel Execution Strategy

Five examples are independent and should run as parallel subagents, each in its own temp directory and tmux session. The sixth (saving-codeacts) depends on output-parser and runs after it completes.

**Parallel batch** (launch as 5 simultaneous subagents):

| Session | Workspace |
|---|---|
| `ex-quickstart` | `/tmp/freeact-ex-quickstart` |
| `ex-agent-skills` | `/tmp/freeact-ex-agent-skills` |
| `ex-python-packages` | `/tmp/freeact-ex-python-packages` |
| `ex-sandbox` | `/tmp/freeact-ex-sandbox` |
| `ex-output-parser` | `/tmp/freeact-ex-output-parser` |

**Sequential** (after `ex-output-parser` completes):

| Session | Workspace |
|---|---|
| `ex-saving-codeacts` | `/tmp/freeact-ex-output-parser` (reuses workspace) |

Each subagent should: set up the workspace, start the tmux session, launch freeact, send queries, wait for completion, expand widgets to match the screenshot, and leave the session running.

## Examples

### 1. Quickstart

- **Source**: `docs/quickstart.md`
- **Screenshot**: `docs/screenshots/quickstart.png`
- **Session**: `ex-quickstart`
- **Setup**: minimal (copy `.env` only)
- **Launch**: `uvx freeact --skip-permissions`

**Query**:
> who is F1 world champion 2025?

**Widget state**:

| Widget | State |
|---|---|
| User Input | expanded |
| Thinking | collapsed |
| Tool Call: pytools_list_categories | collapsed |
| Tool Output (list_categories) | collapsed |
| Tool Call: pytools_list_tools | **expanded** |
| Tool Output (list_tools) | **expanded** |
| Read Action: web_search.py | collapsed |
| Tool Output (read) | collapsed |
| Code Action | **expanded** |
| PTC: google_web_search | **expanded** |
| Execution Output | **expanded** |
| Response | expanded |

---

### 2. Agent Skills

- **Source**: `docs/examples/agent-skills.md`
- **Screenshot**: `docs/screenshots/agent-skills.png`
- **Session**: `ex-agent-skills`
- **Setup**: virtual environment with `reportlab`, plus PDF skill

```bash
mkdir -p /tmp/freeact-ex-agent-skills && cd /tmp/freeact-ex-agent-skills
cp /path/to/freeact/.env .
uv init --bare --python 3.13
uv add freeact
uv pip install reportlab
git clone https://github.com/anthropics/skills.git /tmp/skills-repo 2>/dev/null || true
mkdir -p .agents/skills
cp -r /tmp/skills-repo/skills/pdf .agents/skills/
```

- **Launch**: `uv run freeact --skip-permissions`

**Query**:
> calculate compound interest for $10,000 at 5% for 10 years, save result to output/compound_interest.pdf

**Widget state**:

| Widget | State |
|---|---|
| User Input | expanded |
| Thinking | collapsed |
| Tool Call: pytools_list_categories | collapsed |
| Tool Output | collapsed |
| Read Action: SKILL.md | **expanded** (highlighted/selected) |
| Tool Output (path) | collapsed |
| Tool Output (content) | collapsed |
| Thinking | collapsed |
| Code Action (pip install) | collapsed |
| Execution Output | collapsed |
| Code Action / Execution Output (intermediate steps) | collapsed |
| Thinking | collapsed |
| Code Action (`ls -l output/...`) | **expanded** |
| Execution Output (ls output) | **expanded** |
| Response | expanded |

---

### 3. Data Analysis (Python Packages)

- **Source**: `docs/examples/python-packages.md`
- **Screenshot**: `docs/screenshots/python-packages.png`
- **Session**: `ex-python-packages`
- **Setup**: virtual environment with `scikit-learn matplotlib`

```bash
mkdir -p /tmp/freeact-ex-python-packages && cd /tmp/freeact-ex-python-packages
cp /path/to/freeact/.env .
uv init --bare --python 3.13
uv add freeact
uv pip install scikit-learn matplotlib
```

- **Launch**: `uv run freeact --skip-permissions`

**Query**:
> Generate 30 noisy samples from a sine function and fit a Gaussian process regressor to the data. Save the result as a plot with uncertainty bounds to output/gpr_sine.png.

**Widget state**:

| Widget | State |
|---|---|
| User Input | expanded |
| Thinking | collapsed |
| Code Action (mkdir -p output) | collapsed |
| Thinking | collapsed |
| Code Action (main GPR code) | **expanded** |
| Execution Output | collapsed |
| Response | expanded |

---

### 4. Sandbox Mode

- **Source**: `docs/examples/sandbox-mode.md`
- **Screenshot**: `docs/screenshots/sandbox-mode.png`
- **Session**: `ex-sandbox`
- **Setup**: minimal, plus `sandbox-config.json`

```bash
mkdir -p /tmp/freeact-ex-sandbox
cp /path/to/freeact/.env /tmp/freeact-ex-sandbox/
cp /path/to/freeact/examples/sandbox-config.json /tmp/freeact-ex-sandbox/
```

- **Launch**: `uvx freeact --skip-permissions --sandbox --sandbox-config sandbox-config.json`

**Three sequential queries** (wait for each response before sending the next):

1. > use requests to read from example.org, print status code only
2. > now from google.com
3. > print the content of sandbox-config.json in a code action

**Widget state** (all three query blocks visible):

Query 1 and 2 blocks:

| Widget | State |
|---|---|
| User Input | expanded |
| Code Action | **expanded** |
| Execution Output | collapsed |
| Response | expanded |

Query 3 block:

| Widget | State |
|---|---|
| User Input | expanded |
| Code Action | **expanded** |
| Execution Output | **expanded** |

---

### 5. Output Parser (Enhancing Tools)

- **Source**: `docs/examples/output-parser.md`
- **Screenshot**: `docs/screenshots/output-parser.png`
- **Session**: `ex-output-parser`
- **Setup**: config init, then add GitHub MCP server to `ptc_servers`

```bash
mkdir -p /tmp/freeact-ex-output-parser && cd /tmp/freeact-ex-output-parser
cp /path/to/freeact/.env .
uvx freeact init
python3 -c "
import json
with open('.freeact/agent.json') as f:
    config = json.load(f)
config.setdefault('ptc_servers', {})['github'] = {
    'url': 'https://api.githubcopilot.com/mcp/',
    'headers': {'Authorization': 'Bearer \${GITHUB_API_KEY}'}
}
with open('.freeact/agent.json', 'w') as f:
    json.dump(config, f, indent=2)
"
```

- **Launch**: `uvx freeact --skip-permissions`

**Query**:
> create an output parser for search_repositories

**Widget state**:

| Widget | State |
|---|---|
| User Input | expanded |
| Tool Call: pytools_list_categories | collapsed |
| Tool Output | collapsed |
| Tool Call: pytools_list_tools | collapsed |
| Tool Output | collapsed |
| Read Action: SKILL.md | collapsed |
| Tool Output | collapsed |
| Read Action: search_repositories.py | collapsed |
| Tool Output | collapsed |
| Code Action (test with run) | **expanded** |
| PTC: github_search_repositories (x2) | collapsed |
| Execution Output | collapsed |
| Thinking | collapsed |
| Read Action: search_repositories.py | collapsed |
| Tool Output | collapsed |
| Code Action (mkdir/ls) | **expanded** |
| Execution Output | **expanded** |
| Thinking | collapsed |
| Edit/Write Actions + Tool Outputs | collapsed |
| Tool Call: ipybox_reset | collapsed |
| Tool Output | collapsed |
| Code Action (test with run_parsed) | **expanded** |
| PTC calls | collapsed |
| Execution Output | collapsed |
| Response | expanded |

---

### 6. Code Action Reuse (Saving Codeacts)

- **Source**: `docs/examples/saving-codeacts.md`
- **Screenshots**: `docs/screenshots/saving-codeacts-1.png`, `docs/screenshots/saving-codeacts-2.png`
- **Session**: `ex-saving-codeacts`
- **Workspace**: `/tmp/freeact-ex-output-parser` (same as output-parser, must run after it completes)
- **Launch**: `uvx freeact --skip-permissions`

This example requires two freeact sessions in the same workspace and tmux session.

#### Part 1: Compose and Save

**Query 1**:
> get the latest 5 commits of the 3 github repos of torvalds with the most stars. For each repo, output name, stars and the first line of commit messages, and the link to the commit

Wait for the response, then send:

**Query 2**:
> save this as tool under category github, with username, top_n_repos, top_n_commits as parameter

**Widget state for `saving-codeacts-1.png`** (shows query 2 and its response):

| Widget | State |
|---|---|
| User Input (save query) | expanded |
| Thinking | collapsed |
| Read Action: SKILL.md | collapsed |
| Tool Output | collapsed |
| Thinking | collapsed |
| Code Action (mkdir, touch) | **expanded** |
| Write Actions + Tool Outputs | collapsed |
| Code Action (test run) | **expanded** |
| PTC calls | collapsed |
| Execution Output | collapsed |
| Response | expanded |

#### Part 2: Discover and Reuse

Quit freeact (`ctrl+q`), wait 3 seconds, start a new freeact session in the same workspace.

**Query**:
> get the latest 3 commits of the 2 github repos of torvalds with the most stars. For each repo, output name, stars and the first line of commit messages, and the link to the commit

**Widget state for `saving-codeacts-2.png`**:

| Widget | State |
|---|---|
| User Input | expanded |
| Tool Call: pytools_list_categories | collapsed |
| Tool Output | collapsed |
| Tool Call: pytools_list_tools | collapsed |
| Tool Output | collapsed |
| Thinking | collapsed |
| Read Action: 2 files | collapsed |
| Tool Output | collapsed |
| Thinking | collapsed |
| Code Action | **expanded** |
| PTC calls | collapsed |
| Execution Output | collapsed |
| Response | expanded |

## After Completion

All 6 tmux sessions should remain running. To list them:

```bash
tmux list-sessions
```

To attach and visually inspect any session:

```bash
tmux attach -t ex-quickstart  # or any other session name
```

Detach without stopping: `ctrl+b d`.
