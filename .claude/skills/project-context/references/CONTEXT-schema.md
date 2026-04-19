# CONTEXT.md Schema Reference

Canonical definition for the CONTEXT.md file format. This is the contract
between the project-context skill (writer) and the Ezra context aggregator
(reader). Both sides must agree on this schema.

---

## Frontmatter Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `project` | string | Yes | Repo/folder name, lowercase-hyphenated. Must match the parent directory name. Used as the primary key for sync. |
| `updated` | ISO date | Yes | Date this file was last regenerated (`YYYY-MM-DD`). Used by the aggregator to detect staleness. |
| `description` | string | No | One-sentence summary of the project. Shown in the Knowledge Center project list. |

### Example

```yaml
---
project: ezra-assistant
updated: 2026-04-16
description: "Personal multi-agent AI assistant for Troy Sybert, built on LangGraph and FastAPI."
---
```

---

## Section Format

Each section is a `##` heading followed by prose or bullet points.
The heading text becomes the bolus title in the memory store.

Allowed heading levels: `##` only at the top level. Use `###` within a
section for sub-structure if needed. The aggregator splits on `##` headings
only -- `###` content stays within the parent section's bolus body.

---

## Default Sections

These five sections cover most projects. The skill generates whichever have
substantive content; the aggregator handles any number of `##` headings.

### Overview
**Bolus title:** `{project} -- Overview`
**Content:** What the project is, its goal, and current status. 2-4 sentences.

### Architecture
**Bolus title:** `{project} -- Architecture`
**Content:** Components, stack, runtime, data flow, major design decisions.

### Key Conventions
**Bolus title:** `{project} -- Key Conventions`
**Content:** Naming rules, non-obvious constraints, patterns the codebase enforces.

### Dependencies
**Bolus title:** `{project} -- Dependencies`
**Content:** External systems, sibling repos, APIs, infrastructure.

### Active Work
**Bolus title:** `{project} -- Active Work`
**Content:** What is currently in progress or planned next.

---

## Sync Contract (Ezra Memory Store)

When synced, each `##` section becomes one `KnowledgeBolus` with:

| Field | Value |
|-------|-------|
| `id` | `uuid5(NAMESPACE_DNS, "{project}::{section_heading}")` |
| `title` | `"{project} -- {section_heading}"` |
| `body` | Full section content (heading excluded) |
| `namespace` | `"facts"` |
| `source` | `"context_seed"` |
| `scope` | `"project"` |
| `project` | The `project` frontmatter value |
| `priority` | `4` |
| `tags` | `["context_seed", "{project}"]` |

Deterministic IDs ensure idempotent sync. Re-syncing an unchanged section
produces no database change. Re-syncing an edited section updates the body
in place and triggers re-embedding.

**Orphan pruning:** On sync, any `source="context_seed"` bolus for the same
project whose ID was not generated in the current pass is deleted. This
handles removed sections automatically.

---

## Validation Rules

- `project` must be lowercase, hyphens allowed, no spaces.
- `updated` must parse as ISO 8601 date (`YYYY-MM-DD`).
- At least one `##` section must be present for the file to be valid.
- Section bodies must not be empty -- omit the section rather than leaving it blank.
