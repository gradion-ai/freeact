# Behavior Inventory

Functional contract for the greenfield rewrite (branch `wip-rewrite`). Triangulated from
three sources: the pre-rewrite test suite, the user and architecture docs, and a sweep of
the package source for behaviors that are implemented but neither tested nor documented.
The rewrite must preserve every behavior listed here unless explicitly listed under
"Consciously dropped". Test code itself is NOT the contract; this document is. Evidence
references point at the pre-rewrite tree (reachable on `main`).

Legend: `[U]` tests/unit, `[I]` tests/integration, `[D]` docs; bare `file.py` references
mean source-derived (no test or doc coverage pre-rewrite). Statements are
implementation-independent unless marked INVARIANT (property that must hold regardless of
mechanism) or PORT (module is ported, contract pinned by existing tests).

## 1. Agent SDK: lifecycle & public API

- Agent is constructed with config plus optional `agent_id`, `session_id`, `sandbox`, `sandbox_config`. [D sdk.md]
- Agent works as an async context manager; `start()`/`stop()` manage kernel and MCP server lifecycle explicitly. [D sdk.md]
- Default main agent id is `main`. [I test_subagents::test_agent_has_default_id]
- `stream(prompt, max_turns=None)` yields events for one turn; the turn ends when the model responds without tool calls (no implicit turn limit). [I test_agent::test_no_max_turns_completes_normally]
- `max_turns` limits tool-execution rounds for the agent it is passed to. [I test_subagents::test_max_turns_limits_parent]
- `cancel()` interrupts the current turn at the next phase boundary. [D sdk.md]
- `session_id` property returns the session id, or None when persistence is disabled. [D sdk.md]
- A session id is generated when persistence is enabled and none is provided; a provided session id is used as-is. [U test_agent::TestSessionPersistenceConfig]
- Providing a session id while persistence is disabled is an error (ValueError). [U test_agent::test_agent_rejects_session_id_when_persistence_disabled; U test_cli]
- `tool_names` lists all registered tool names; `agent_id`, `model`, and `model_settings` are readable on the agent instance. [D sdk.md; core.py]
- `.env` in the working directory is auto-loaded at CLI startup. [cli.py main]

## 2. Event model

- Event types: `ThoughtsChunk`/`Thoughts`, `ResponseChunk`/`Response`, `CodeExecutionOutputChunk`/`CodeExecutionOutput`, `ToolOutput`, `ApprovalRequest`, `Cancelled`. [D sdk.md]
- Chunk events stream deltas; a final non-chunk event carries the consolidated content. [I test_agent::test_text_deltas_yielded, test_thinking_parts_yielded]
- INVARIANT: every event carries the originating agent's id; subagent events are distinguishable from main-agent events. [I test_subagents::test_events_carry_agent_id]
- INVARIANT: tool-related events carry a correlation id; subagent events carry their own correlation ids plus a reference to the parent task's correlation id (enables nested rendering and parallel-task routing). [I test_subagents::test_subagent_events_keep_subagent_corr_ids, test_parallel_subagent_events_keep_parent_task_corr_ids]
- None deltas in thinking streams are ignored without error. [I test_agent::test_thinking_none_content_ignored]
- `CodeExecutionOutput` formats as its text plus markdown image references for produced images; empty output formats as empty string; it carries a `truncated` flag indicating truncated output. [U test_agent::TestCodeExecutionOutput; events.py]

## 3. Code execution (ipybox)

- Python code executes in a stateful IPython kernel; output streams back as chunk events followed by a final output event. [I test_agent::test_real_code_execution]
- Working directory is reset to the workspace directory after each code action (even if code chdir'd away). [I test_agent::test_working_dir_reset_after_chdir; D execution.md]
- Code execution exceptions are caught and returned as error text in the output event (turn continues). [I test_agent::test_code_execution_exception_yields_error]
- `execution_timeout` (default 300s, None disables) bounds code execution; timeout produces an interrupted/empty result, not a crash. [I test_agent::test_execution_timeout_exceeded]
- INVARIANT: time spent waiting for approvals does NOT count toward the execution timeout. [I test_agent::test_execution_timeout_excludes_ptc_approval_wait]
- A kernel-reset tool exists; success returns a confirmation, failure returns an error message. [I test_agent::test_ipybox_reset_success, test_ipybox_reset_exception]
- Generated images are saved under the configured images directory and referenced from output events. [D configuration.md]
- Kernel env: user-provided `kernel_env` is resolved with `${VAR}` substitution; `HOME` is inherited from the host env unless the user sets it; the generated-tools dir is always on `PYTHONPATH`. [U test_agent::TestKernelEnvHome; U test_config]

## 4. Shell command interception

- `!command` lines inside code actions are intercepted and surfaced as shell approvals (tool name `bash`); `%%bash` cell magic surfaces as a distinct shell approval (tool name `shell_magic`). [U test_agent_shell::test_shell_command_yields_shell_approval]
- Composite shell commands (`&&`, `||`, `|`, `;`) are split into one approval per sub-command; operators inside quotes do not split. [U test_agent_shell, U test_shell::test_split_composite_command]
- Rejecting any sub-command of a composite rejects the whole command. [U test_agent_shell::test_composite_partial_rejection_rejects_ipybox_approval]
- Python variables in shell commands are resolved before the approval is requested (the user approves the concrete command). [D execution.md]
- Shell state persists within a `%%bash` block but not across separate `!` lines. [D execution.md]
- Pattern suggestion generalizes a concrete shell command to a glob pattern (e.g. `git add /path/file.py` suggests `git add *`); multiline commands escape newlines in the pattern. [U test_shell::test_suggest_shell_pattern, U test_call::test_suggest_pattern]

## 5. Approvals

- Every code action, shell command, programmatic tool call (PTC), JSON MCP tool call, and subagent task requires approval before execution (unless pre-approved by permission rules or `--skip-permissions`). [I test_agent; D index.md]
- `ApprovalRequest` carries a typed tool call; `approve(bool)` resolves it; `approved()` awaits the decision. Resolving twice is a safe no-op. [D sdk.md; U test_agent::test_approve_after_future_resolved_is_noop]
- INVARIANT: rejection of any approval ends the agent turn with a "Tool call rejected" response; nothing after the rejected action executes. [U+I many tests]
- Rejected PTCs surface an ApprovalRejectedError in the code output so the model can see the rejection. [U test_agent::test_ptc_approval_rejected]
- PTC approvals during code execution surface as nested approvals (correlated to the running code action). [U test_agent::test_ptc_approval_accepted]
- Non-shell PTC approvals surface as GenericCall with `ptc=True` and tool name `<server>_<tool>`. [U test_agent_shell::test_non_shell_ptc_uses_generic_call]
- INVARIANT: abandoning the event stream (consumer closes the generator) while an approval is pending rejects that approval exactly once; nothing hangs. [U test_agent::TestGeneratorExitRejectsIpyboxApproval]
- Unknown tool names return an error to the model without requesting approval. [I test_agent::test_unknown_tool_returns_error_without_approval]
- `approval_timeout` (default None = wait forever) is configurable and bounds PTC approval waits. [U test_agent::TestTimeoutParameters; D configuration.md]

## 6. Cancellation

Documented semantics: docs/internal/architecture/cancellation.md (pre-rewrite). Phases: `between_turns`, `llm_streaming`, `tool_execution`.

- Cancelling yields a `Cancelled` event carrying the phase where cancellation took effect. [U test_agent::TestCancellation]
- Cancel during LLM streaming preserves the partial response. [U test_agent::test_cancel_during_llm_streaming]
- Cancel during code execution preserves output produced so far. [U test_agent::test_cancel_during_tool_execution]
- Cancel while an approval is pending rejects/abandons it and produces an interrupted tool return. [U test_agent::test_cancel_during_approval_wait]
- INVARIANT: after cancellation, every tool call the model issued has a tool return in history ("Interrupted by user" synthetic returns for unfinished ones), so the persisted history remains valid for resumption. [U test_agent::test_cancel_produces_synthetic_returns_for_orphaned_calls]
- A stream that is never cancelled behaves identically with or without cancellation support (no spurious events). [U test_agent::test_stream_without_cancel_unchanged]
- Parent cancellation propagates to running subagents (and their code executors). [U test_agent::test_cancel_propagates_to_subagent_code_executor]

## 7. MCP tool calls (JSON mode)

- Configured MCP servers' tools are registered and callable; results surface as `ToolOutput` events. [I test_agent::test_mcp_tool_approval_accepted]
- MCP tool exceptions are converted to error text in the tool return ("MCP tool call failed: ..."), the turn continues. [I test_agent::test_mcp_tool_exception_returns_error]
- Binary MCP content is supported in tool results. [core.py; U media handling]
- Specific tools can be excluded per server via config. [U test_config]

## 8. Tool result overflow

- Tool results and code outputs up to `tool_result_inline_max_bytes` (default 32768) stay inline; larger results are written to a session-scoped file and replaced in history by a notice containing the threshold, a preview (`tool_result_preview_chars`, default 2048, string results only), and the file path. [U test_tool_result_overflow; I test_agent::test_mcp_tool_result_overflow_is_saved_to_file]
- Structured (JSON) results are saved as JSON without preview; binary results without preview, with extension matching media type. [U test_tool_result_overflow]
- Streamed chunks plus final output produce exactly one overflow file. [I test_agent::test_code_execution_chunk_does_not_create_duplicate_overflow_file]
- INVARIANT: if saving the overflow file fails, the result stays inline (no data loss). [U test_tool_result_overflow::test_large_result_stays_inline_when_store_write_fails]
- INVARIANT: file extensions for saved results are sanitized (no path traversal via media-type-derived extension). [U test_session::test_save_tool_result_sanitizes_extension]
- The system prompt tells the model about overflow files so it can read them on demand. [U test_config::test_system_prompt_mentions_overflow_file_guidance]

## 9. Subagents

- `subagent_task` tool (present when `enable_subagents`, default true) delegates a prompt to a child agent with its own kernel and MCP connections; the child's final response returns as the parent's `ToolOutput`. [I test_subagents]
- Subagent ids use a `sub-` prefix; subagent events stream through the parent's event stream, including approvals. [I test_subagents]
- Subagents cannot nest (no `subagent_task` tool in subagents). [I test_subagents::test_subagent_has_no_task_tool]
- Subagent kernels are independent of the parent kernel (no shared state). [I test_subagents::test_subagent_kernel_is_independent]
- Subagent default `max_turns` is 100; concurrency is bounded by `max_subagents` (default 5). [U test_agent; D configuration.md]
- Subagents inherit parent settings (model, system prompt, kernel env [deep copy], images dir, timeouts, sandbox settings, session id) but always have subagents disabled; in hybrid-search mode subagents do not sync/watch the index. [U test_agent::TestSubagentConfigPropagation; U test_config::test_for_subagent_disables_subagents_and_sync_watch]
- Subagent failure returns an error-text ToolOutput to the parent ("Subagent error..."), not a crash. [I test_subagents::test_subagent_exception_returns_error_in_tool_output]
- Parallel subagent tasks run concurrently with separate ToolOutputs and correctly correlated event streams. [I test_subagents::test_parallel_task_execution]
- Rejecting the `subagent_task` approval prevents the subagent from running. [I test_subagents::test_task_approval_rejected]

## 10. Session persistence & resume

- With persistence enabled, message history is persisted incrementally (after every history mutation, not just at turn end) under `.freeact/sessions/<session-id>/`. [I test_session_persistence]
- Main agent history and each subagent's history are persisted separately; resume rehydrates only the main history (subagent files are an audit record). [I test_session_persistence::test_resume_loads_only_main_history]
- Resuming with an existing session id continues the conversation; a new id creates a fresh session. [D sdk.md]
- Overflowed tool results live in a `tool-results/` directory inside the session directory. [I test_session_persistence]
- INVARIANT: a partially written (crashed mid-write) trailing record is tolerated on load (valid prefix is used); corruption elsewhere is an error. [U test_session::test_load_ignores_malformed_trailing_line, test_load_raises_on_non_tail_malformed_line]
- INVARIANT: persisted history round-trips with full fidelity (pydantic-ai ModelMessage parity). [U test_session::test_append_load_round_trip_model_messages]
- History rollback (e.g. on cancellation) is reflected in the persisted record, not only in memory. [U test_session::test_delete_last_messages_truncates_persisted_tail]
- Storage format (JSONL envelopes, one message per line, versioned, timestamped) is an implementation choice the rewrite may change, but incremental-append, crash tolerance, and fidelity are contract.

## 11. Permissions (security-critical; semantics must be preserved exactly)

Rule model: two tiers (session-only, persistent "always"), two lists per tier (ask, allow).

- INVARIANT: evaluation order is session-ask, always-ask, session-allow, always-allow; first match wins; ask beats allow. No match means not allowed (explicit allow required). [I test_permissions]
- Typed call matching:
  - GenericCall: tool name fnmatch glob.
  - ShellAction: tool name AND command fnmatch glob.
  - CodeAction: tool name fnmatch glob.
  - FileRead/FileWrite/FileEdit: tool name fnmatch AND path matched with `PurePosixPath.full_match` semantics (`*` does not cross `/`, `**` crosses any depth, `**/*.py` matches at root and nested). [I test_permissions::test_session_rule_matching]
- INVARIANT (security): paths under the working dir are normalized to relative before matching; paths outside the working dir stay absolute; a relative pattern (including bare `**`) NEVER matches an absolute path. Consequence: a broad `**` read-allow does not expose `/etc/passwd` or `~/.ssh/...`. [I test_permissions::test_default_read_blocked, test_path_outside_workspace_stays_absolute]
- INVARIANT (security): `**/.env` at any depth is in the default ask rules and beats the broad `**` allow (covers relative and absolute-under-workdir forms). [I test_permissions::test_absolute_dotenv_under_workdir_blocked]
- Default allow rules: file reads (`**`) for filesystem tools; pytools introspection calls; a curated list of read-only shell commands (pwd/whoami/uptime/ls/cat/head/tail/ps, git read-only subcommands incl. status/log/diff/show/blame/ls-files/rev-parse/describe/config --get/remote/tag/branch/stash list/worktree list). [I test_permissions::test_default_shell_command_allowed]
- Deliberately NOT in defaults: mutating git commands, rm/mv/cp/mkdir/touch/chmod/chown/kill/pkill, `find` (any args; can exec/delete), `env` (can run arbitrary commands), everything via `shell_magic` (no shell_magic defaults at all). [I test_permissions::test_default_shell_command_blocked, test_shell_magic_not_covered_by_bash_defaults]
- Persistence: always-rules persist to disk; session rules never persist; rules deduplicate on add; constructor does not create directories (only save/init do); init seeds defaults when no file exists and loads the file when it does; defaults active even without load. [I test_permissions]
- Tool call <-> pattern symmetry: each call type supports suggest-pattern (generalize), parse-pattern (reconstruct from user-edited pattern, wildcards allowed in tool name), and entry serialization for storage. [U test_call]
- `--skip-permissions` bypasses all checks. [D cli.md]

## 12. Tool call typing

- Raw tool calls are classified into: CodeAction (code execution), ShellAction (intercepted shell), FileRead/FileWrite/FileEdit (filesystem tools, with path/offset/limit/content/old/new captured), GenericCall (everything else, with `ptc` flag). Missing args get sensible defaults (empty code, None offset/limit). [U test_call::test_from_raw]
- Tool call objects are immutable. [U test_call::test_tool_calls_are_frozen]
- Tool output text extraction handles strings, dicts (`content` then `text` key), and lists (joined by newlines). [U test_call::test_extract_tool_output_text]

## 13. Filesystem tools (PORT: processing logic ported as-is)

- read_text_file: full read or 1-indexed offset/limit range with `[Lines N-M of TOTAL total]` metadata; offset beyond EOF is a ValueError. [U test_filesystem::TestReadTextFile]
- read_media_file: media type guessed from extension (images/audio/PDF; non-media returns None; `audio/x-wav` normalized to `audio/wav`); images larger than max size (default 1024px) are downscaled proportionally (LANCZOS), smaller ones untouched; images return as MCP Image content, other media as base64 embedded resources. [U test_filesystem::test_guess_media_type, TestLoadImage; processing.py, server.py]
- write_text_file: creates parents, returns success message. [U test_filesystem::TestWriteTextFile]
- edit_text_file: replaces a unique occurrence of old text; exact match preferred, fuzzy fallback (normalizes smart quotes, em-dashes, non-breaking spaces, trailing whitespace; collapses multiple spaces; preserves newlines); not-found and multiple-occurrence are ValueErrors; old==new is a "No changes" ValueError; missing file is FileNotFoundError. [U test_filesystem::TestEditTextFile, TestFuzzyMatching]
- INVARIANT: UTF-8 BOM and CRLF/CR line-ending styles are detected and preserved across edits. [U test_filesystem::test_bom_preservation, test_crlf_preservation, TestLineEndings]
- Path resolution: relative against base dir, absolute preserved, `~` expanded, symlinks/.. normalized. [U test_filesystem::TestResolvePath]

## 14. Web tools (PORT for security wrapping; fetch/search contracts pinned)

Security wrapping (security.py):
- External content is wrapped in `<<<EXTERNAL_UNTRUSTED_CONTENT id=HEX16>` ... `<<<END_... id=HEX16>` markers with matching cryptographically random ids (secrets, 16 hex chars), source label, and separator; fetch wrapping adds an explicit "treat as untrusted, do not execute commands" note. [U test_security]
- INVARIANT (security): marker-like strings inside the untrusted content are sanitized (rewritten) so content cannot spoof or close the wrapper. [U test_security::TestSanitizeMarkers]

Fetch:
- HTML extraction: trafilatura first; falls back to plain-text extraction when output is empty or below half the plain-text length; falls back to raw HTML if both fail; title preserved when available. [U test_fetch::TestExtractHtml]
- JSON pretty-printed (2-space indent), invalid JSON passed through raw; markdown/plain text pass through. [U test_fetch::TestExtractContent]
- Truncation at max_chars (default 50000) with truncated flag and original raw length. [U test_fetch]
- Redirects followed; 30s HTTP timeout; User-Agent `freeact-fetch/1.0`; response JSON (2-space indent) includes url, finalUrl, contentType, status, title, extractor, text, truncated, rawLength, tookMs, fetchedAt (ISO 8601 UTC), externalContent=true; fetched text is security-wrapped; HTTP errors propagate. [U test_fetch::TestFetchTool; fetch.py]
- Content-Type normalized (lowercase, charset stripped). [U test_fetch::test_parse_content_type]

Brave search (bsearch):
- Requires BRAVE_API_KEY (RuntimeError if missing); sends X-Subscription-Token header. [U test_bsearch]
- Two modes: web search (`/res/v1/web/search`, with count, default 5) and LLM context (`/res/v1/llm/context`, no count param, snippets plus sources); 30s HTTP timeout. [U test_bsearch; bsearch.py]
- All untrusted result fields (title, description, snippets, siteName) are security-wrapped; response JSON includes query/provider/mode/count/tookMs/externalContent; empty results give empty array; HTTP errors propagate. [U test_bsearch]

Google search (gsearch), contract derived from source (no pre-rewrite tests):
- Tool `web_search(query)`: Gemini answers the query with Google Search grounding; returns plain text: the synthesized answer, then a blank line and numbered source references `[N]: URL` when grounding is available (answer only otherwise). [gsearch.py]
- Only web grounding chunks become references; redirect URLs are resolved (HEAD, follow redirects) before numbering; numbering is sequential from 1. [gsearch.py]
- `--thinking-level {minimal,low,medium,high}` (default medium) server option; GEMINI_API_KEY required. [gsearch.py; D configuration.md]

## 15. Tool discovery (pytools)

Basic mode: MCP server listing tool categories and tools by scanning `mcptools/` and `gentools/` under the generated dir; tool listings return full source file paths (so the model can read the APIs). [D configuration.md; basic.py]

Hybrid mode (PORT: stack ported as-is, becomes the `freeact[search]` extra):
- Tool layout contract: `mcptools/<category>/<tool>.py` and `gentools/<category>/<tool>/api.py`; tool ids `source:category:name`; `_`-prefixed dirs skipped; tools without docstrings skipped; docstring taken from `run()` (or preferred `run_parsed()`). [U test_extract]
- Index sync: scans, embeds descriptions, stores in SQLite (FTS5 + sqlite-vec); hash-based change detection (unchanged skipped, modified re-embedded, deleted removed); empty dir is a no-op. [I hybrid test_index]
- File watching: debounced watch of the two tool dirs, .py only, callbacks for change/delete, callback errors don't kill the watcher, idempotent start/stop, async context manager. [I hybrid test_watch]
- Search: bm25 / vector (cosine, descending) / hybrid (RRF fusion, configurable bm25/vector weights, rrf_k=60, overfetch x2 defaults); limit respected; special characters in queries don't crash; empty db gives empty results. [I hybrid test_search, test_database]
- Server: env-var config (PYTOOLS_DIR, PYTOOLS_DB_PATH, PYTOOLS_EMBEDDING_MODEL [default google-gla:gemini-embedding-001, `test` = deterministic embedder], PYTOOLS_EMBEDDING_DIM 3072, PYTOOLS_SYNC/WATCH true, weights 1.0; booleans case-insensitive); syncs on start, watches for live updates, `search_tools(query, mode, limit)` tool (limit bounded 1..50); results carry name/category/source/description/path, entries missing from the db are silently skipped; concurrent searches from multiple server instances against one db work. [U+I hybrid test_server]

## 16. MCP code mode (PTC)

- Typed Python APIs are generated from MCP server schemas into `.freeact/generated/mcptools/<server>/` (via mcpygen); generation runs at startup for configured ptc servers, skipping already-generated ones. [D index.md; apigen.py]
- Code actions import these as `mcptools.<server>.<tool>` and call `run()`/`run_parsed()` with a `Params` type; calls route back through the agent's approval and execution machinery. [D execution.md]
- Agents can author their own tools under `gentools/` and save code actions as reusable tools (supported by bundled skills). [D index.md]

## 17. Configuration capabilities (format-independent)

The rewrite replaces the format (unified TOML, minimal defaults, named tool presets). These capabilities must remain configurable:

- model (provider:name string), model_settings (passed through to pydantic-ai, incl. thinking config), provider_settings (api_key/base_url etc.) with `${VAR}` env substitution; any pydantic-ai-compatible model. [U test_config; D models.md]
- tool_search mode: basic | hybrid (| off, new in rewrite). mcp_servers (JSON-mode) and ptc_servers (code mode) as user-defined server tables (stdio + streamable HTTP), merged with built-ins; per-server tool exclusion; `${VAR}` references validated at load (missing var is an error) but substituted at use. [U test_config]
- execution_timeout, approval_timeout, tool_result_inline_max_bytes, tool_result_preview_chars, enable_persistence, enable_subagents, max_subagents, kernel_env, images_dir. [U test_config; D configuration.md]
- Workspace layout: `.freeact/` holds config, permissions, sessions/, generated/, plans/, skills/, search db. Save/init creates the runtime directories and materializes bundled skills (without overwriting user-modified ones). [U test_config]
- Config is immutable after load; loading is faithful (every documented key takes effect). [U test_config] (AMENDED: the old save/load round-trip becomes init-writes-once; see section 22 and architecture.md 4.1.)
- Defaults that are contract: model google-gla:gemini-3.5-flash with medium thinking, timeouts/thresholds above. Defaults that CHANGE in the rewrite: google+fetch ptc servers on by default (become opt-in presets).

## 18. CLI

- `freeact` / `freeact run` starts the interactive TUI; `freeact init` initializes config without starting. [U test_cli; D cli.md]
- Flags: `--sandbox`, `--sandbox-config PATH`, `--session-id ID` (errors if persistence disabled), `--skip-permissions`, `--log-level {debug,info,warning,error,critical}` (default info). [U test_cli]
- Sandbox mode: OS-level filesystem/network restrictions for the kernel via sandbox-runtime (read all except .env, write cwd, no network by default; custom config file overrides); applies uniformly to Python and shell; MCP servers sandboxed independently via srt wrapping. [D sandbox.md] NOTE: no automated test coverage pre-rewrite.

## 19. System prompt & skills

- System prompt composed from bundled template with working dir, generated-tools relative dir, optional `<project-instructions>` from `AGENTS.md` in the working dir, and a skills section listing each skill's name/description/location. [U test_config; D configuration.md]
- Skills follow the agentskills.io spec (SKILL.md with YAML frontmatter: name, description). Bundled skills: task-planning, output-parsers, saving-codeacts. Project skills from `.agents/skills/<name>/`. [D configuration.md]
- The model auto-invokes skills by description match; `/skill-name args` in a prompt explicitly invokes one (TUI converts it to a skill tag before sending). [D cli.md; U terminal tests]

## 20. Terminal UI (user-observable behavior)

Input:
- Enter submits (trimmed), input clears, submitted text shown in a user box; submitting empty/whitespace-only input shows a warning notification instead. Alt+Enter/Ctrl+J inserts newline; Escape clears input when idle with text, cancels the turn while one is in progress, and rejects a pending approval. [U test_app; widgets.py]
- `@` at a word start opens a file picker (tree rooted at /, cursor at cwd, prefix-search navigation, backspace reverts); selection inserts the path, relative to the working dir when possible, absolute otherwise. [U test_app, test_screens]
- `/` at prompt start opens a skill picker (prefix matching, Enter selects); selection inserts `/skill-name `; on submit, slash commands are converted to skill tags. [U test_app, test_screens]
- Paste via Ctrl+V / Super+V / Ctrl+Shift+V / Shift+Insert reads the OS clipboard, falling back to the app-local clipboard only when the OS clipboard is unavailable (None), not when it is empty. [U test_app]

Rendering (main agent only; subagent events render nested, see below):
- Thoughts stream into a box that collapses on completion (configurable); responses stream as markdown (links styled, hover effect). [U test_app]
- Code actions, shell commands/scripts, file read/write/edit (with diff rendering for edits), generic tool calls, and subagent tasks each render as titled collapsible boxes (`[agent-id] <kind>: <subject>`); execution output streams nested inside its code action box; tool outputs render collapsed by default. [U test_app, test_widgets]
- All rendered text (responses, code, outputs, diffs, user input) is mouse-selectable and copyable via Cmd+C / Super+C / Ctrl+Shift+C / Ctrl+Insert / Ctrl+C, copying to the OS clipboard. [U test_app]
- Stream exceptions render as an expanded Error box and re-enable input. [U test_app]
- Banner with version (build metadata stripped) and cwd (`~`-relative) at top; viewport starts at bottom. [U test_app]
- Ctrl+Q quits. [U test_app]
- A hints bar shows contextual keyboard shortcuts that update with state (e.g. "esc: interrupt" during a turn, "esc: clear" when idle with text). [app.py]

Approvals:
- Approval bar shows `Approve? [Y/n/a/s]` with the call's display text (verbatim command for bash; multi-line scripts summarized as "first line +N more") or suggested pattern. [U test_app]
- Y/Enter approves (Enter works regardless of focus); N rejects (rejected boxes stay expanded, configurable); A/S open an editable pattern input seeded with the suggested pattern, then record allow-always (persisted) or allow-session respectively and approve. [U test_app]
- Pre-approved calls (permission match or skip-permissions) skip the bar and follow the approved-collapse config. [U test_app]
- PTC calls are labeled as PTC in the box title. [U test_app]
- While an approval is pending its box stays pinned expanded (configurable). [U test_app]

Collapse management:
- Configurable expand-all toggle key (default ctrl+o) overrides all collapse state and restores it on second press; new boxes mounted during override render expanded; manual collapse choices survive. [U test_app]
- Per-kind collapse config: thoughts, exec output, approved code actions (default expanded), approved tool calls (default collapsed), completed subagent tasks (default collapsed), tool outputs, rejected actions stay expanded, pin pending approval. [U test_app, test_terminal_config]

Subagent display:
- Subagent child widgets nest inside their task's box (routed by parent correlation id), parallel tasks route correctly and keep stable order; active tasks can be manually collapsed and stay collapsed as children mount; completed tasks auto-collapse (configurable); subagent approval bars appear at root level so they are always visible. [U test_app]

Clipboard backends (PORT): macOS pbcopy/pbpaste; Linux wl-copy/wl-paste then xclip then xsel (X11 prefers xclip); Windows powershell/pwsh. [U+I clipboard tests]

## 21. Known coverage gaps (documented but untested pre-rewrite)

- Google search tool (gsearch) has no tests; its contract in section 14 is source-derived.
- Sandbox mode has no automated tests (docs only).
- Approval timeout enforcement is config-plumbed but its runtime effect is untested.
- TUI-driven permission persistence end-to-end (approval bar "a" through to permissions.json) is covered only at unit level.

## 22. Consciously dropped

- All tests pinning internal mechanics (private methods, mock call shapes, module singletons, widget internals); listed per area in the extraction reports. The behaviors above are the replacement contract.
- JSON config format details: snake_case-only key validation, kebab-case rejection, three separate config files, validate-but-not-substitute `${VAR}` timing in stored ptc configs, accepting pre-instantiated Model objects in persisted config.
- Default-on google/fetch ptc servers (replaced by one-line opt-in presets).
- Rejected-approval detection via "ApprovalRejectedError:" string matching as an SDK-visible mechanism (replaced by a structured rejection signal; the in-kernel error string shown to the model remains).
- CLI rejection of long-removed legacy flags (`--legacy-ui`, `--record`).
- Programmatic `Config.save()` of arbitrary config state back to disk: in the rewrite the app writes config.toml only at `init`; config flows one way (file -> schema -> resolve). Permissions remain machine-written (separate file).
- Migration of pre-rewrite `.freeact/*.json` files (agent.json, terminal.json, permissions.json): ignored by the rewrite; users re-run `freeact init` and re-approve permissions (fail-safe direction).
