# Code actions

Freeact agents act by executing code rather than emitting one JSON tool call per LLM inference. A code action can contain any combination of Python code, shell commands, and programmatic MCP tool calls, generated in one LLM inference pass. This enables composition of tool calls, intermediate result processing, and control flow within a single action, reducing LLM roundtrips. For programmatic MCP tool calling ("code mode"[^1]), freeact generates typed Python APIs from MCP server schemas; the agent inspects generated APIs prior to execution and composes them based on available type information.

Code actions execute in an IPython kernel provided by [ipybox](https://github.com/gradion-ai/ipybox). A [unified execution interface](https://gradion-ai.github.io/ipybox/codeexec/) enables their combination within a single code action. Code actions, shell commands, and programmatic tool calls are subject to [approval](approvals.md) before execution.

## Python Code

Given a prompt like *"what is 17 raised to the power of 0.13"*, the agent generates and executes Python code directly:

```python
print(17 ** 0.13)
```
```
1.4453011884051326
```

## Shell Commands

Given a prompt like *"which .py files in tests/ contain ipybox"*, the agent uses a shell command with the `!` prefix:

```python
!grep -r "ipybox" tests/ --include="*.py" -l
```
```
tests/unit/test_agent.py
tests/conftest.py
tests/integration/test_agent.py
tests/integration/test_subagents.py
```

Each `!` line spawns a separate subprocess. Multi-line shell scripts can use the `%%bash` cell magic, which runs as a single subprocess:

```python
%%bash
cd /tmp
echo "Now in $(pwd)"
ls -la
```

Shell state (working directory, variables) does not persist across `!` lines but persists within a `%%bash` block. Neither carries state to the next cell execution. Their results can be stored in variables though.

## Programmatic Tool Calls

[Generated Python APIs](../guides/tool-servers.md#add-servers-for-programmatic-tool-calling) for MCP server tools can be imported and called like regular packages:

```python
from mcptools.google.web_search import run, Params

result = run(Params(query="python async tutorial"))
print(result)
```

## Combining Them

Python code, shell commands, and programmatic tool calls can be freely combined within a single code action:

```python
!pip install pandas
import pandas as pd
from mcptools.fetch.web_fetch import run, Params

result = run(Params(url="https://example.com/data.csv"))
df = pd.read_csv(result)
print(df.describe())
```

Shell output can be captured into Python variables:

```python
files = !ls /data/*.csv
print(f"Found {len(files)} CSV files")
```

Python variables can be interpolated into shell commands:

```python
filename = "report.pdf"
!cp /tmp/{filename} /output/
```

## Action Approval

Code actions, contained shell commands, and programmatic tool calls require approval before execution. Shell commands and programmatic tool calls are intercepted during code action execution for individual approval. [Approvals and permissions](approvals.md) explains the approval model; [Manage permissions](../guides/permissions.md) covers pre-approval with permission rules.

## Working Directory

The kernel starts in the agent's workspace directory. After each code action, the working directory is reset to this location. If code changes the directory via `os.chdir()` or `%cd`, the change is undone before the next execution and the kernel prints a `[ipybox] cwd reset to <path>` message.

[^1]: [Code Mode: the better way to use MCP](https://blog.cloudflare.com/code-mode/)
