# Internal Documentation

Agent-optimized reference material. Not published via MkDocs.

Do not use mkdocs-formatter, mkdocs-docstrings, or mkdocs-style skills for files in this directory.

The codebase is the primary reference: modules are small and single-purpose, so derive
component maps, APIs, and flows from source. These docs contain only what source cannot
explain.

## Living reference

- [invariants.md](invariants.md) -- non-obvious rules and why-invariants whose
  violation looks like a valid refactor. Read before changing core behavior.
- [testing.md](testing.md) -- test harness patterns (agent, terminal, e2e via tmux).
- [examples/rerun.md](examples/rerun.md) -- how to reproduce the documentation example
  sessions and screenshots.
