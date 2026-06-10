# Session Persistence Constraints

`Session` (`freeact/agent/session.py`) is the single source of truth for message history: it owns the in-memory list and keeps the `SessionStore` (when persistence is enabled; `store=None` otherwise) in sync on every mutation. Nothing else writes history.

## JSONL invariants (`SessionStore`)

- Versioned envelopes: `{"v": 1, "message": ..., "meta": {"ts": ...}}`; `meta.agent_id` is explicitly forbidden (`_validate_envelope`).
- One file per agent stream under `.freeact/sessions/<session-id>/`: `main.jsonl` for the parent, `sub-xxxx.jsonl` for subagents. Resume rehydrates main history only (`Session.load`); subagent files are an audit record.
- Incremental append: history is persisted after every mutation, not at turn end.
- Crash tolerance: a malformed FINAL line is ignored on load; earlier malformed lines raise `ValueError`.
- Fidelity: messages round-trip via `to_jsonable_python(..., bytes_mode="base64")` / `ModelMessagesTypeAdapter`.

## Rollback

`Session.rollback(n)` (memory + persisted tail) runs ONLY on turn exceptions (`Agent.stream` except path). Cancellation NEVER rolls back: it keeps partial responses and appends synthetic "Interrupted by user" returns so persisted history stays valid for resumption.

## Tool result overflow (`ToolResultMaterializer`)

- Results at or below `tool_result_inline_max_bytes` stay inline; larger ones are written to `tool-results/<id>.<ext>` in the session directory and replaced by a notice (threshold, actual size, optional preview of `tool_result_preview_chars` for string results, file path).
- Materialization happens exactly once per result, on the FINAL output only (`ToolExecutor._final_output` / MCP result path); streamed chunks never materialize.
- INVARIANT: if saving the overflow file fails, the content stays inline (no data loss).
- INVARIANT: file extensions are sanitized (`_sanitize_extension`: lowercase alphanumeric or `bin`), so media-type-derived extensions cannot traverse paths.
- Pass-through when persistence is disabled (`Session.materialize` without a store).
