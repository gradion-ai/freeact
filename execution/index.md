# Code Execution

Freeact executes Python code, shell commands, and programmatic MCP tool calls in an IPython kernel provided by [ipybox](https://github.com/gradion-ai/ipybox). A [unified execution interface](https://gradion-ai.github.io/ipybox/codeexec/) enables their combination within a single code action. Code actions, shell commands, and programmatic tool calls are subject to [action approval](#action-approval) before execution.

## Python Code

Given a prompt like *"what is 17 raised to the power of 0.13"*, the agent generates and executes Python code directly:

```
print(17 ** 0.13)
```

```
1.4453011884051326
```

## Shell Commands

Given a prompt like *"which .py files in tests/ contain ipybox"*, the agent uses a shell command with the `!` prefix:

```
!grep -r "ipybox" tests/ --include="*.py" -l
```

```
tests/unit/test_agent.py
tests/conftest.py
tests/integration/test_agent.py
tests/integration/test_subagents.py
```

Each `!` line spawns a separate subprocess. Multi-line shell scripts can use the `%%bash` cell magic, which runs as a single subprocess:

```
%%bash
cd /tmp
echo "Now in $(pwd)"
ls -la
```

Shell state (working directory, variables) does not persist across `!` lines but persists within a `%%bash` block. Neither carries state to the next cell execution. Their results can be stored in variables though.

`%%bash` approval

Approval support for `%%bash` cell magic is not implemented yet (coming soon).

## Programmatic Tool Calls

[Generated Python APIs](https://gradion-ai.github.io/freeact/sdk/#generation-api) for MCP server tools can be imported and called like regular packages:

```
from mcptools.google.web_search import run, Params

result = run(Params(query="python async tutorial"))
print(result)
```

## Combining Them

Python code, shell commands, and programmatic tool calls can be freely combined within a single code action:

```
!pip install pandas
import pandas as pd
from mcptools.fetch.web_fetch import run, Params

result = run(Params(url="https://example.com/data.csv"))
df = pd.read_csv(result)
print(df.describe())
```

Shell output can be captured into Python variables:

```
files = !ls /data/*.csv
print(f"Found {len(files)} CSV files")
```

Python variables can be interpolated into shell commands:

```
filename = "report.pdf"
!cp /tmp/{filename} /output/
```

## Action Approval

Code actions, contained shell commands, and programmatic tool calls require approval before execution. Shell commands and programmatic tool calls are intercepted during code action execution for individual approval.

Composite shell commands (using `&&`, `||`, `|`, `;`) are decomposed into individual sub-commands, each approved separately. Python variables in shell commands are resolved before the approval request, so the approval request shows actual values.

See the Agent SDK for programmatic [approval](https://gradion-ai.github.io/freeact/sdk/#approval) control, [permission configuration](https://gradion-ai.github.io/freeact/configuration/#permissions) for action pre-approval, and the CLI tool for the interactive [approval prompt](https://gradion-ai.github.io/freeact/cli/#approval-prompt).

## Working Directory

The kernel starts in the agent's workspace directory. After each code action, the working directory is reset to this location. If code changes the directory via `os.chdir()` or `%cd`, the change is undone before the next execution and the kernel prints a `[ipybox] cwd reset to <path>` message.
