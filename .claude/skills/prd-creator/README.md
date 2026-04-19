# /prd-creator

Create feature canvases and user stories using the F##/S## nomenclature system.

## Commands

```
/prd-creator                            Start creating a PRD interactively
```

## Process

1. **Phase 1 -- Clarification:** 3-5 targeted questions about problem, scope, stories, dependencies
2. **Phase 2 -- Generate:** Feature canvas + story files saved to `tasks/`

Skips Phase 1 if the request already has a clear problem statement, scope, and named stories.

## Scripts

```bash
# Get next feature ID
.atlas/skills/prd-creator/scripts/next-id.sh feature
# → F05

# Get next story ID for a feature
.atlas/skills/prd-creator/scripts/next-id.sh story F01
# → F01-S05
```

## File Naming

```
F01-dashboard-overhaul.md           Feature canvas
F01-S01-data-model.md               Story 1
F01-S02-docs-viewer.md              Story 2
```

## Templates

- `references/feature-canvas-template.md` -- Feature canvas structure
- `references/software-story-template.md` -- Software stories (with testing/git sections)
- `references/story-template.md` -- General stories (ops, marketing, infra)
- `references/adr-template.md` -- Architecture Decision Records

## Sizing Rules

- 3-6 stories per feature (fewer = single story, more = split features)
- Max 8-10 tasks per story
- Every story must have a summary, acceptance criteria, and tasks

## File Lifecycle

- Active PRDs: `tasks/`
- Completed PRDs: `tasks/completed/` (optionally in topic subdirs)
- Status tracked via YAML frontmatter: `draft` | `active` | `completed`
