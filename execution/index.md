# Code Execution

Freeact executes Python code and shell commands in an IPython kernel provided by [ipybox](https://github.com/gradion-ai/ipybox). Both run through the same `ipybox_execute_ipython_cell` [internal tool](https://gradion-ai.github.io/freeact/sdk/#internal-tools), and the kernel is stateful: variables, imports, and function definitions persist across executions within a session.

Python code and shell commands share the same kernel, but shell commands use the `!` prefix (e.g., `!ls`, `!git status`, `!uv pip install`). The bundled [system prompts](https://github.com/gradion-ai/freeact/tree/main/freeact/agent/config/prompts) provide initial guidance on when to use shell commands versus Python code. More detailed guidance can be given in custom [agent skills](https://gradion-ai.github.io/freeact/configuration/#skills).

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

Shell state (working directory, variables) does not persist across `!` lines but persists within a `%%bash` block. Neither carries state to the next cell execution.

## Mixing Both

Python and shell commands can be freely combined within a single code action. A common pattern is installing a package and using it immediately:

```
!uv pip install pandas
import pandas as pd

df = pd.read_csv("data.csv")
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
