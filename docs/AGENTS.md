# Documentation Guidelines
- Use mkdocs-formatter and mkdocs-style skills for documentation (except `docs/internal/`)
- In `docs/internal/`, match the conciseness of surrounding entries when adding new ones

## Structure (Diataxis)
- Every page belongs to exactly ONE genre and nav section: tutorial (`getting-started/`), task-oriented how-to (`guides/`), lookup reference (`reference/`), or explanation (`concepts/`). Do not mix genres within a page; cross-link instead of repeating.
- When moving or renaming a page, add the old path to `REDIRECTS` in `scripts/mkdocs_redirects.py` and update the mkdocs-llmstxt sections in `mkdocs.yml`. NEVER add the `mkdocs-redirects` pip package (its release channel shipped a malicious dependency in 1.2.3); the local hook replaces it.

## Sync hazards
- `docs/reference/configuration.md` embeds a copy of `DEFAULT_CONFIG_TOML` from `freeact/config/load.py`; keep them identical when either changes.
- `docs/getting-started/sdk-tutorial.md` embeds `examples/*.py` via `--8<--` snippet markers; keep marker names stable when editing the examples.

## Accuracy
- Verify capabilities and supported formats before documenting them (check source code, official docs, or run a test)
- When unsure, say it depends or link to the authoritative source
