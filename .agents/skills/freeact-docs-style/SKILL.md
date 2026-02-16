---
name: freeact-docs-style
description: Write or rewrite technical documentation in a concise, high-signal style. Use this skill for wording, tone, clarity, and information density. Do not use it for document structure, frontmatter, or markdown-format decisions.
---

# Documentation Style

Goal: technical documentation that is easy to scan and precise to act on.

## Voice

- Reference docs: impersonal third person. Subjects are the product, component, or thing being described. Never "we".
- Tutorials/examples: imperative second person for steps ("Create a directory"), third person for system behavior ("the agent discovers...").
- Consistent voice within a page. No mixing registers mid-section.

## Prose

- Short declarative sentences. One idea per sentence. Present tense.
- Lead with the key fact, then qualifiers as compact prepositional phrases: "on first call", "across restarts".
- Open paragraphs with a statement that names or defines the subject. Close with a cross-reference or consequence, not a summary.
- Colons for inline elaboration: "This allows safe customization: edit any file, and changes remain intact."
- Let structured content (code, lists, tables) carry primary weight. Prose provides the connective minimum.
- Prefer templates: `X does Y.` / `If X, Y happens.` / `X defaults to Y.` / `X is required.`

## Density

- Every sentence adds new information. No restating.
- Specific outcomes over broad claims. Precise verbs: `loads`, `persists`, `fails`, `returns`, `generates`.
- Parenthetical asides for defaults, examples, clarifications: "(default 5)", "(e.g., `pandas`)".
- No hedging ("might", "could", "perhaps", "should consider"). No filler (`simply`, `just`, `easy`, `powerful`, `seamless`). No em-dashes (use commas, colons, or parentheses).

## Rewriting Pass

1. Remove filler and duplicate statements.
2. Replace ambiguous language with explicit behavior.
3. Break compound sentences into compact declarative lines.
4. Stop when further compression would reduce clarity.
