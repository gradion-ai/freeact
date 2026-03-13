# CLI tool

The `freeact` or `freeact run` command starts the [interactive mode](#interactive-mode):

```
freeact
```

A `.freeact/` [configuration](https://gradion-ai.github.io/freeact/configuration/index.md) directory is created automatically if it does not exist yet. The `init` subcommand initializes the configuration directory without starting the interactive mode:

```
freeact init
```

## Options

| Option                  | Description                                                                                  |
| ----------------------- | -------------------------------------------------------------------------------------------- |
| `--sandbox`             | Run code execution in [sandbox mode](https://gradion-ai.github.io/freeact/sandbox/index.md). |
| `--sandbox-config PATH` | Path to sandbox configuration file.                                                          |
| `--session-id UUID`     | Resume a previous session by its UUID.                                                       |
| `--skip-permissions`    | Run tools without prompting for approval.                                                    |
| `--log-level LEVEL`     | Set logging level: `debug`, `info` (default), `warning`, `error`, `critical`.                |

## Examples

Running code execution in [sandbox mode](https://gradion-ai.github.io/freeact/sandbox/index.md):

```
freeact --sandbox
```

Running with a [custom sandbox configuration](https://gradion-ai.github.io/freeact/sandbox/#custom-configuration):

```
freeact --sandbox --sandbox-config sandbox-config.json
```

Resuming a previous [session](https://gradion-ai.github.io/freeact/sdk/#persistence):

```
freeact --session-id 550e8400-e29b-41d4-a716-446655440000
```

If `enable_persistence` is `false` in `.freeact/agent.json`, passing `--session-id` exits with an error.

## Interactive Mode

The interactive mode provides a conversation interface with the agent in a terminal window.

### User messages

| Key                                                | Action                             |
| -------------------------------------------------- | ---------------------------------- |
| `Enter`                                            | Send message                       |
| `Ctrl+J`                                           | Insert newline                     |
| `Option+Enter` (macOS) `Alt+Enter` (Linux/Windows) | Insert newline (`Ctrl+J` fallback) |
| `Escape`                                           | Cancel the current agent turn      |
| `Ctrl+Q`                                           | Quit                               |

### Clipboard

Clipboard behavior depends on terminal key forwarding.

- Paste into the prompt input: `Cmd+V` or `Ctrl+V`.
- Copy selected text from Freeact widgets: `Cmd+C` may not work in some terminals. Use `Ctrl+C` instead.
- Additional terminal fallbacks: `Ctrl+Shift+C` / `Ctrl+Insert` for copy, `Ctrl+Shift+V` / `Shift+Insert` for paste.

### Expand and Collapse

Use `Ctrl+O` to toggle all collapsible boxes between expanded and configured state.

The shortcut is configured in `.freeact/terminal.json` under `expand_all_toggle_key`.

### Image Attachments

Reference images using `@path` syntax:

```
@screenshot.png What does this show?
@images/ Describe these images
```

- Single file: `@path/to/image.png`
- Directory: `@path/to/dir/` includes all images in directory, non-recursive
- Supported formats: PNG, JPG, JPEG, GIF, WEBP
- Type `@` in the prompt to open a file picker.
- Select a file or directory to insert its path after `@`.

Images are automatically downscaled if larger than 1024 pixels in either dimension.

### Skill Invocation

The agent automatically uses skills when a request matches a skill's description. The `/skill-name` syntax is a shortcut to invoke a specific skill explicitly:

```
/plan my project requirements
/commit fix login bug
```

- Type `/` at the start of a prompt to open a skill picker.
- Select a skill to insert its name, then type arguments after it.
- Text after the skill name is passed as arguments to the skill.
- Skill locations: `.agents/skills/` (project) and `.freeact/skills/` (bundled).

### Cancellation

Press `Escape` during an active agent turn to cancel it. This interrupts the current operation (LLM streaming, code execution, or approval wait), stops the turn, and re-enables the prompt input.

### Approval Prompt

Before executing code actions or tool calls, the agent requests approval. The prompt displays a suggested pattern that summarizes the pending action:

```
Approve? [Y/n/a/s] git add *
```

| Key           | Action                                        |
| ------------- | --------------------------------------------- |
| `y` / `Enter` | Approve this invocation only                  |
| `n`           | Reject (ends the current agent turn)          |
| `a`           | Edit pattern, then save as always-allow rule  |
| `s`           | Edit pattern, then save as session-allow rule |

Pressing `a` or `s` opens the pattern for inline editing. The input is pre-filled with the suggested pattern. Edit the pattern to broaden or narrow the rule (e.g. change `filesystem_read_file src/main.py` to `filesystem_* src/**`), then press `Enter` to save the rule and approve. While editing, approval hotkeys are disabled so you can type freely.

Always-allow rules persist to `.freeact/permissions.json` across sessions. Session-allow rules are in-memory and cleared when the session ends. Future tool calls matching a saved rule are auto-approved without prompting.

The suggested pattern depends on the action type:

| Action               | Pattern format        | Example                             |
| -------------------- | --------------------- | ----------------------------------- |
| Shell command        | `command *` heuristic | `git add *`                         |
| Code action          | tool name             | `ipybox_execute_ipython_cell`       |
| File read/write/edit | tool name + path      | `filesystem_write_file src/main.py` |
| Other tool calls     | tool name             | `github_search_repositories`        |

See [Permissions](https://gradion-ai.github.io/freeact/configuration/#permissions) for the persisted format and pattern syntax.

Automatic approval

Use the [`--skip-permissions`](#options) CLI flag to run the agent with automatic approval for all tools and shell commands.
