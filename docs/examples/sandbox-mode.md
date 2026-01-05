# Sandbox Mode

!!! hint "Recorded session"

    A [recorded session](../recordings/sandbox-mode/conversation.html) of this example is appended [below](#recording).


This example demonstrates running code execution in [sandbox mode](../sandbox.md) with a custom sandbox configuration. It does not cover [sandboxing MCP servers](../sandbox.md#mcp-servers).


Create a `sandbox-config.json` file in your working directory:

```json
--8<-- "examples/sandbox-config.json"
```

It allows network access only to `example.org` and protects the sandbox config file from being read or modified. The `allowLocalBinding` and write access to `~/Library/Jupyter/` and `~/.ipython/` are required for the sandboxed IPython kernel to operate on macOS.

Start the CLI with the custom configuration:

```bash
uv run freeact --sandbox --sandbox-config sandbox-config.json
```

The recording [below](#recording) demonstrates the sandbox in action. First, the agent can access the allowed domain:

> use requests to read from example.org, print status code only

This succeeds with status `200`. Access to other domains is blocked:

> now from google.com

This fails with a `403 Forbidden`. The sandbox also protects the config file:

> print the content of sandbox-config.json in a code action

This fails with a `PermissionError`.

[![Interactive mode](../recordings/sandbox-mode/conversation.svg)](../recordings/sandbox-mode/conversation.html){target="_blank" #recording}
