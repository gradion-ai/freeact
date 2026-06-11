# Approvals and permissions

Every code action, shell command, and tool call requires approval before execution, unless a permission rule pre-approves it. This page explains the approval model: what gets approved, who decides, and why permission matching works the way it does.

## The approval model

A code action is approved as a whole before it runs. Shell commands and programmatic tool calls inside it are then intercepted during execution and approved individually. This two-level model means a single approved code action does not grant blanket permission to everything it does: each side effect surfaces as its own decision point.

Interception happens with full runtime information. Python variables in shell commands are resolved before the approval request, so the user approves the actual command values, not templates. Composite shell commands joined with `&&`, `||`, `|`, or `;` are decomposed into individual sub-commands, each approved separately, so a harmless prefix cannot smuggle in a destructive suffix. `%%bash` scripts are approved as a whole.

The `tool_call` type of an ApprovalRequest determines what is being approved:

| `tool_call` type              | Trigger                                                                                    |
| ----------------------------- | ------------------------------------------------------------------------------------------ |
| CodeAction                    | Code action containing Python code and shell commands to execute                           |
| ShellAction                   | Shell command (`!cmd`) or shell script (`%%bash`) intercepted during code action execution |
| GenericCall                   | Programmatic tool call (intercepted during code action execution) or JSON tool call        |
| FileRead, FileWrite, FileEdit | Filesystem operation via built-in MCP server                                               |

`GenericCall` covers both call styles; its `ptc` field is `True` for programmatic tool calls, so applications can match `GenericCall(ptc=True)` to treat them differently from JSON tool calls.

## Who decides

The agent itself is policy-free. It yields ApprovalRequest events from its [event stream](https://gradion-ai.github.io/freeact/concepts/runtime/#events) and suspends execution until the application calls `approve()`. Calling `approve(True)` executes the action; `approve(False)` rejects it and ends the current agent turn. A rejection is signaled structurally: the final CodeExecutionOutput has `approval_rejected=True`.

The embedding application decides how requests are resolved. The CLI prompts the user interactively. The [SDK tutorial](https://gradion-ai.github.io/freeact/getting-started/sdk-tutorial/index.md) auto-approves everything. Applications that want stored rules use PermissionManager, the same utility the CLI uses internally; the agent never reads `permissions.toml` itself. See [Manage permissions](https://gradion-ai.github.io/freeact/guides/permissions/index.md) for both the interactive and the programmatic workflow.

Two safeguards prevent approval requests from hanging forever: if the consumer abandons the stream while an approval is pending, the request is resolved as rejected, and with a configured `approval_timeout`, an unresolved request is rejected when the timeout expires.

Subagent actions go through the same mechanism. Events from subagents flow through the parent agent's stream, with `agent_id` identifying the source, so the application applies one approval policy to the whole agent tree.

## Why two tiers

Permission rules are organized into `allow` and `ask` tiers, evaluated **ask then allow**: if a rule matches both tiers, the user is prompted. This order makes `ask` rules a safety net. A broad convenience rule like `allow git *` cannot silently cover a pattern the user wants to always confirm, such as `ask rm *`. Each tier supports an **always** scope (persisted to `permissions.toml`) and a **session** scope (in-memory, cleared when the session ends), separating durable policy from one-off trust.

## The path matching model

Rules for filesystem operations match on paths, and the matching is designed around the working directory as the trust boundary. Paths are normalized before matching: absolute paths under the working directory become relative, paths outside stay absolute. A relative pattern like `src/**` can therefore only ever match files inside the workspace, regardless of how the agent spells the path. Granting access outside the workspace requires an explicit absolute pattern with a leading `/`. Within patterns, `*` stays inside a single directory while `**` crosses directory boundaries, so a rule scoped to one directory does not silently extend to its subtree. See [Permission rules](https://gradion-ai.github.io/freeact/reference/permission-rules/index.md) for the exact syntax.
