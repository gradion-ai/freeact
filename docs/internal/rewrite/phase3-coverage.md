# Rewrite Coverage Map (phases 3-5)

STATUS: ARCHIVED (rewrite complete). Snapshot of inventory-to-test mapping at the end
of the rewrite. The "Known gaps carried forward" section at the bottom remains a valid
TODO source. See [README.md](README.md).

Maps every [behavior-inventory.md](behavior-inventory.md) item in sections 1-20 to its
test coverage after phases 3 (core SDK), 4 (tools layer), and 5 (terminal UI + CLI).

Legend: U = tests/unit, I = tests/integration, PORT = module ported verbatim with its
pre-rewrite tests, DEFER(phaseN) = explicitly deferred with reason.

## 1. Agent SDK: lifecycle & public API

- Construction params, context manager, start/stop: I test_agent (all tests construct via harness), U test_agent::TestSessionPersistenceConfig
- Default agent id `main`: I test_subagents::test_agent_has_default_id
- Turn ends when model stops calling tools: I test_agent::test_no_max_turns_completes_normally
- max_turns: I test_subagents::test_max_turns_limits_parent, test_max_turns_limits_subagent
- cancel(): U test_agent::TestCancellation (all), test_cancel_method_cancels_kernel
- session_id generation/validation: U test_agent::TestSessionPersistenceConfig
- tool_names / agent attrs: exercised throughout U+I test_agent
- .env autoload at CLI startup: DEFER(phase5) — CLI/TUI rewrite; minimal cli.py has no run command yet

## 2. Event model

- Chunk + final pairs (text, thinking): I test_agent::test_text_deltas_yielded, test_thinking_parts_yielded
- agent_id on every event: I test_subagents::test_events_carry_agent_id
- corr_id / parent_corr_id invariants: I test_subagents::test_subagent_events_keep_subagent_corr_ids, test_parallel_subagent_events_keep_parent_task_corr_ids
- None thinking deltas ignored: I test_agent::test_thinking_none_content_ignored
- CodeExecutionOutput.format + truncated flag: U test_agent::TestEvents, I test_agent overflow tests

## 3. Code execution

- Real kernel execution, cwd reset, exceptions, reset tool: I test_agent::test_real_code_execution, test_working_dir_reset_after_chdir, test_code_execution_exception_yields_error, test_ipybox_reset_*
- Timeout enforcement + approval wait excluded: I test_agent::test_execution_timeout_exceeded, test_execution_timeout_excludes_ptc_approval_wait, test_fast_execution_within_timeout; U test_agent::test_execution_timeout_passed_to_kernel, test_execution_timeout_disabled
- Kernel env (HOME, PYTHONPATH, ${VAR}): U test_config resolve tests

## 4. Shell command interception

- bash / shell_magic approvals: U test_agent::TestGeneratorExitRejectsIpyboxApproval (parametrized), U test_toolcalls (patterns, display)
- Composite splitting + quoting: U test_shell, U test_agent::test_shell_approvals_split_composite_command
- Partial rejection rejects whole command: U test_agent::test_composite_partial_rejection_rejects_whole_command; I test_agent::test_shell_approval_rejected
- Pattern suggestion: U test_toolcalls

## 5. Approvals

- Approval before execution, accept/reject paths (code, PTC, MCP, subagent): U test_agent::TestIpyboxExecution; I test_agent::test_mcp_tool_approval_*, I test_subagents::test_task_approval_rejected
- INVARIANT rejection ends turn: U+I (rejected cases assert "Tool call rejected" response)
- approve() idempotent / exactly-once: U test_approvals::test_approve_after_resolution_is_noop, TestApprovalRequest
- INVARIANT abandonment rejects pending approvals exactly once, nothing hangs: U test_agent::TestGeneratorExitRejectsIpyboxApproval (in-kernel, parametrized; double-reject guard) + test_abandoned_stream_rejects_pending_approval_via_agent (top-level, end-to-end). NEW vs pre-rewrite: top-level abandonment now also resolves the request (gate guarantee).
- Unknown tool: no approval, error return: U test_agent::test_unknown_tool_returns_error_without_approval; I test_agent::test_unknown_tool_returns_error_without_approval
- approval_timeout: U test_approvals::test_decide_timeout_resolves_request_rejected, test_decision_before_timeout_wins. NEW coverage (pre-rewrite gap, inventory 21).

## 6. Cancellation

- Phase-tagged Cancelled events (all three phases): U test_agent::TestCancellation
- Partial response/output preserved: U test_agent::test_cancel_during_llm_streaming, test_cancel_during_tool_execution
- Cancel during approval wait -> interrupted return: U test_agent::test_cancel_during_approval_wait; U test_approvals (cancel racing)
- INVARIANT synthetic returns for every issued call: U test_agent::test_cancel_produces_synthetic_returns_for_orphaned_calls, test_cancel_during_execution_with_empty_output
- No spurious events without cancel: U test_agent::test_stream_without_cancel_unchanged
- Parent cancel propagates to subagents: covered structurally (shared CancelToken passed at construction, monitor task in SubagentRunner); end-to-end kernel-interrupt propagation not separately tested. PORT of old mechanism; flagged for a future integration test.

## 7. MCP tool calls

- Registration, approval, results: I test_agent::test_mcp_tool_approval_accepted/rejected
- Exception -> error text: I test_agent::test_mcp_tool_exception_returns_error
- Binary content / media parts: I test_agent (media path via filesystem read in old suite ported), executor BinaryContent branch
- Per-server tool exclusion: PORT (_MCPServerStdioFiltered ported verbatim; config plumbing in U test_config server overrides). No dedicated behavioral test pre-rewrite or now; flagged.

## 8. Tool result overflow

- Threshold, preview, structured/binary, inline-on-failure INVARIANT, extension sanitization INVARIANT: U test_session (materializer + store)
- End-to-end file storage + notice + exactly-one-file INVARIANT: I test_agent::test_mcp_tool_result_overflow_is_saved_to_file, test_mcp_tool_result_under_threshold_stays_inline, test_code_execution_final_output_overflow_replaced_with_notice, test_code_execution_chunk_does_not_create_duplicate_overflow_file
- System prompt overflow guidance: U test_config

## 9. Subagents

- Delegation, sub- ids, event bubbling, approvals, no nesting, kernel isolation, parallel tasks, error ToolOutput, max_turns: I test_subagents (all tests ported)
- Runtime inheritance + sync/watch off: U test_config::for_subagent tests
- max_turns default 100 in schema: U test_agent::TestEvents

## 10. Session persistence & resume

- Incremental persistence at all history points: I test_session_persistence::test_agent_persists_incrementally_at_all_history_points
- Main-only resume, subagent audit files: I test_session_persistence; U test_session (Session.load)
- Crash-tolerant tail INVARIANT, fidelity INVARIANT, rollback: U test_session
- tool-results dir: I test_session_persistence

## 11. Permissions (security-critical)

- All evaluation-order, type-matching, path-semantics INVARIANTs, default rules, persistence/dedup/init: I test_permissions (137 tests, cases ported verbatim; storage assertions updated to TOML)
- Typed rule layer (rule_from_call, discriminators, TOML round-trip): U test_permissions

## 12. Tool call typing

- from_raw dispatch, defaults, immutability, pattern symmetry, output text extraction: U test_toolcalls

## 13. Filesystem tools (phase 4)

- PORT: read/write/edit semantics, BOM/line-ending INVARIANTs, fuzzy matching, media
  handling: U tests/unit/tools/test_filesystem.py (unchanged)

## 14. Web tools (phase 4)

- Security wrapping incl. spoof-sanitization INVARIANT: U test_security (PORT)
- Fetch contract: U test_fetch (PORT), I tools/test_fetch (local HTTP server)
- Brave search contract: U test_bsearch (PORT)
- Google search contract: U test_gsearch — NEW (pre-rewrite gap, inventory 21):
  answer + numbered references format, web-chunk filtering with position-based
  numbering, redirect resolution, None-text handling, grounding config,
  thinking-level option (parser extracted as gsearch.create_parser for testability)

## 15. Tool discovery (phase 4)

- Package restructured: pytools/search/basic.py -> pytools/basic.py,
  pytools/search/hybrid/ -> pytools/hybrid/ (architecture section 2 layout);
  resolve.py preset module paths updated
- Basic mode: U tests/unit/tools/pytools/test_basic.py — NEW (was source-derived
  only): categories from both sources, full source file paths, underscore skipping,
  gentools api.py requirement, list/string params, unknown category
- Hybrid stack: U+I tests/*/tools/pytools/hybrid/ (PORT, paths updated): extract,
  embed, database, search (BM25/vector/RRF/weights), index sync, watch, MCP server

## 16. MCP code mode (phase 4)

- apigen: thin mcpygen wrapper, exercised by I conftest mcp_sources_dir and the PTC
  integration tests (test_agent PTC approval flows). Generation skip-if-exists logic:
  covered-by-port (apigen.py unchanged).
- gentools authoring: bundled skills materialization U test_config; tool layout
  contract U hybrid test_extract

## 17. Configuration capabilities

- Schema defaults, load/init, validation, presets, ${VAR} handling, kernel env, timeouts, for_subagent, system prompt composition, skills: U test_config
- Hybrid extra check: resolve-level guard implemented; both extra modules installed in dev env so the missing-extra error path is untestable until phase 6 moves them to extras. DEFER(phase6).
- AMENDED items (init-writes-once, no Config.save) per inventory section 22.

## 18. CLI (phase 5)

- Commands (run default, init), flags (--sandbox/--sandbox-config/--session-id with
  persistence guard/--skip-permissions/--log-level), init-does-not-overwrite, wiring
  (session id, sandbox, skip-permissions through to Agent/TerminalApp): U test_cli
  (12 tests, ported; legacy-flag rejection consciously dropped per inventory 22)
- .env autoload, PTC source generation at startup, agent lifecycle ownership:
  cli.run() (covered by the wiring harness; generation skip-if-exists covered-by-port)
- Sandbox runtime effect: DEFER (inventory 21, docs-only contract, no automated test)

## 19. System prompt & skills (phases 3+5)

- Prompt composition, skills discovery/materialization: U test_config (phase 3)
- /skill-name conversion to skill tags on submit, skill picker: U terminal test_app,
  test_screens

## 20. Terminal UI (phase 5)

- Implementation rebuilt into app/dispatcher/view/approvals/widgets/screens/clipboard
  per architecture section 5; behavior ported from the pre-rewrite TUI.
- Test suite ported with every old behavioral case surviving by name (59/59 in
  test_app plus 3 new: empty-prompt warning, skip-permissions bar skip, user toggle):
  U tests/unit/terminal/ (138 tests: input/pickers/slash commands, streaming render,
  copy/paste incl. OS-clipboard fallback, approval flows y/n/a/s incl. pattern
  editing and verbatim/summary display, collapse precedence incl. expand-all
  override and manual-beats-forced, subagent nesting/parallel routing/stable order,
  exec output finalization, error box, cancellation, banner, quit) + I
  test_clipboard (platform roundtrips)
- TrackedCollapsible user-toggle detection: watcher-based (handler override
  double-fires under Textual MRO dispatch; found by the ported pilot tests, fixed)
- Terminal config section validation: U terminal test_config_section + U test_config

## Known gaps carried forward

- Subagent kernel-interrupt propagation end-to-end (see section 6 note).
- MCP tool exclusion behavioral test (see section 7 note).
- Sandbox smoke test: DEFER (inventory 21, no pre-rewrite coverage either).
- gsearch contract tests: DEFER(phase4) with the tools layer.
