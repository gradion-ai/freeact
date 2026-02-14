---
name: freeact-docs-style
description: Write or rewrite technical documentation in a concise, high-signal style. Use this skill for wording, tone, clarity, and information density. Do not use it for document structure, frontmatter, or markdown-format decisions.
disable-model-invocation: true
---

# Documentation Style

## Goal

Produce technical documentation that is easy to scan and precise to act on.

## Voice

- Use impersonal third person in reference documentation. Subjects are the product, the component, or the specific thing being described. Never "we".
- Use imperative second person in tutorials and examples for instructional steps ("Create a directory", "Set the API key"). Describe system behavior in third person ("the agent discovers...").
- Keep voice consistent within a page. Do not mix registers mid-section.

## Sentence and Paragraph Patterns

- Short declarative sentences. One idea per sentence. Present tense for current behavior.
- Lead with the key fact, then qualifiers.
- Open paragraphs with a single declarative statement that names or defines the subject.
- Use colons for inline elaboration: "This allows safe customization: edit any file, and changes remain intact."
- Append qualifiers as compact prepositional phrases: "on first call", "on next initialization", "across restarts".
- Keep paragraphs compact. Close sections with a cross-reference or consequence, not a summary.
- Let structured content (code examples, lists, tables) carry primary weight. Prose provides the connective minimum to frame them.

## Information Density

- Every sentence adds new information. No restating.
- Replace broad claims with specific outcomes.
- Prefer precise verbs: `loads`, `persists`, `fails`, `returns`, `requires`, `generates`.
- Use parenthetical asides for defaults, examples, and clarifications: "(default 5)", "(e.g., `pandas`)".
- Fully assertive language. No hedging: "might", "could", "perhaps", "it seems", "should consider".
- No filler: `simply`, `just`, `easy`, `powerful`, `seamless`.
- No em-dashes. Use commas, colons, or parentheses.

## Wording Templates

- `X does Y.`
- `If X, Y happens.`
- `X defaults to Y.`
- `X is required.` / `X is optional.`

## Rewriting Pass

1. Remove filler and duplicate statements.
2. Replace ambiguous language with explicit behavior.
3. Break compound sentences into compact declarative lines.
4. Tighten word choice until each sentence is high-signal.
5. Stop when further compression would reduce clarity.
