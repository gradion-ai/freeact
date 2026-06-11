# Rewrite Archive (2026)

Frozen historical record of the 2026 greenfield rewrite (phases 1-6, completed
2026-06-10/11). Do NOT treat these files as current reference; they describe the
rewrite process and its decision state, not necessarily today's code.

The living references are:

- [docs/internal/invariants.md](../invariants.md) -- non-obvious rules and
  why-invariants of the implemented system
- The test suite -- the executable behavior contract

Disposal plan: delete this directory after `wip-rewrite` is merged to `main` (deleting
earlier would erase these files from history entirely under a squash merge). When
deleting, move the three remaining test gaps from phase3-coverage.md "Known gaps"
(subagent kernel-interrupt e2e, MCP exclude_tools behavioral test, sandbox smoke test)
to GitHub issues.

Contents:

- [behavior-inventory.md](behavior-inventory.md) -- the functional contract extracted
  from the pre-rewrite tests/docs/source that the rewrite had to preserve
- [architecture.md](architecture.md) -- the target design the rewrite was built
  against, including resolved decisions and implementation notes
- [phase3-coverage.md](phase3-coverage.md) -- mapping of every inventory item to its
  test coverage at the end of the rewrite, including known deferred gaps (the "Known
  gaps carried forward" section remains useful as a TODO source)
