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

### Approval Prompt

Before executing code actions or tool calls, the agent requests approval:

```
Approve? [Y/n/a/s]
```

| Response       | Effect                                                   |
| -------------- | -------------------------------------------------------- |
| `Y` or `Enter` | Approve once                                             |
| `n`            | Reject once (ends the current agent turn)                |
| `a`            | Approve always (persists to `.freeact/permissions.json`) |
| `s`            | Approve for current session                              |

See [Permissions API](https://gradion-ai.github.io/freeact/sdk/#permissions-api) for details.
