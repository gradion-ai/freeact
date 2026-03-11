# Session Persistence Constraints

- JSONL format with versioned envelopes: `{"v": 1, "message": ..., "meta": {"ts": ...}}`.
- One file per agent stream: `main.jsonl` for parent, `sub-xxxx.jsonl` for subagents.
- Stored under `.freeact/sessions/<session-id>/`.
- Large tool results materialized to `.freeact/sessions/<session-id>/tool-results/<id>.<ext>`.
- Truncated final lines are tolerated; earlier malformed lines raise `ValueError`.
- `meta.agent_id` is explicitly forbidden in envelopes (validated in `_validate_envelope`).
