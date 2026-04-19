# Architecture Decision Record (ADR) Template

Use this template when you make a technical or design decision worth remembering. Not every choice needs an ADR — only ones you might question later or that constrain future options.

**When to write one:**
- Choosing between two viable approaches (e.g., Redis vs PostgreSQL for caching)
- Picking a library, framework, or service that you'll depend on
- Deciding on a data model or API pattern that's hard to change later
- Making a tradeoff you want documented (e.g., "chose speed over flexibility because...")

**Where to save:** `docs/decisions/ADR-##-short-title.md`

---

## Template

```markdown
# ADR-##: [Decision Title]

**Date:** YYYY-MM-DD
**Status:** Accepted | Superseded by ADR-## | Deprecated
**Feature:** F## (if tied to a specific feature, otherwise "General")

## Context

[What situation led to this decision? What problem were you solving? Keep it to 2-3 sentences — just enough that future-you remembers the circumstances.]

## Decision

[What did you decide? State it directly.]

## Why

[Why this approach over the alternatives? What tipped the balance?]

## Alternatives Considered

- **[Alternative A]** — [Why not. One sentence.]
- **[Alternative B]** — [Why not. One sentence.]

## Consequences

- [What this enables]
- [What this limits or makes harder]
- [Anything you'll need to revisit if circumstances change]

---

*Recorded by Spock 🖖*
```

## Rules

- **Keep it short.** One page max. If you need more than a page, the decision might be too complex for one ADR — split it.
- **Write it when you make the decision**, not weeks later. Context evaporates fast.
- **"Superseded" is fine.** Decisions change. Link to the new ADR rather than editing the old one. The history has value.
- **No ADR is too small** if it's something you'd forget. "Chose bcrypt over argon2 because Alpine doesn't ship libargon" is a perfectly good ADR.
