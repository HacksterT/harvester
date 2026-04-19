# Feature Canvas Template

Use this template for the feature canvas — the lightweight overview document that describes the "what and why" of a feature. Individual user stories are separate files.

---

## Template

```markdown
# F##: [Feature Title]

## Overview

**Feature:** [Name]
**Problem:** [What we're solving — the pain point or gap]
**Goal:** [What success looks like — concrete outcome]

## Context

[1-2 paragraphs of background. Why now? What led to this? How does it fit into the bigger picture?]

## Stories

| ID | Title | Priority | Status |
|----|-------|----------|--------|
| F##-S01 | [Story title] | Must-Have | Backlog |
| F##-S02 | [Story title] | Must-Have | Backlog |
| F##-S03 | [Story title] | Should-Have | Backlog |

## Non-Goals

- [What this feature will NOT do]
- [Explicit scope boundaries]

## Dependencies

- [What must exist before this can start]
- [External services, tools, access needed]

## Success Metrics

- [How we know the feature is done and working]
- [Measurable outcomes]

## Open Design Decisions

- [Unresolved questions that may affect multiple stories]
- [Decisions pending HacksterT input]

---

*Created: YYYY-MM-DD by Spock 🖖*
```

## Rules

- **Keep it lean.** The canvas is an overview, not a spec. Details live in story files.
- **Story table is the index.** Lists all stories with current status. No full story specs here.
- **Update status as stories progress.** When a story moves to active/done, update the table.
- **One canvas per feature.** If a feature is too big, split into multiple features.
- **Target 3-6 stories per feature.** Fewer than 3 = probably a single story, not a feature. More than 6 = split.
