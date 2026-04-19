---
name: prd-creator
description: >
  Create feature canvases and user stories using the F##/S## system. Use whenever
  HacksterT is planning a new feature, scoping work, or breaking an idea into
  stories -- even if they don't say "PRD" explicitly. Load this skill when someone
  describes something they want to build and needs a plan, not just when the word
  PRD is used. Output is feature canvas + story files saved to tasks/backlog.
  TRIGGERS - "create a PRD", "new PRD", "write a feature spec", "plan this feature",
  "break this into stories", "scope this out", "I want to build X", "help me scope",
  "what are the stories", "document this project", "create a feature", "new feature",
  "structure this work", "what would the stories be", "I need to plan this",
  "spec this out", "let's plan", "write up the stories for"
---

# Feature & Story Creator

Create feature canvases and user stories using the F##/S## nomenclature system. Features are the "what and why." Stories are the executable work.

## Nomenclature

```
F01-dashboard-overhaul.md           ← Feature canvas
F01-S01-data-model.md               ← Story 1
F01-S02-docs-viewer.md              ← Story 2
F01-S03-activity-log.md             ← Story 3
```

- **F##** — Feature number, zero-padded (F01–F99)
- **S##** — Story number within a feature, zero-padded (S01–S99)
- **Naming drives linkage.** `F01-*` finds everything for feature 01. No hard links needed.

## ID Generation

**Always use the script — never invent IDs manually.**

```bash
# Get next feature number
.atlas/skills/prd-creator/scripts/next-id.sh feature
# → F05

# Get next story number for a feature
.atlas/skills/prd-creator/scripts/next-id.sh story F01
# → F01-S05
```

The script scans `tasks/` and `tasks/completed/` recursively for existing IDs to find the highest number and increments. Override the tasks path by setting `ATLAS_TASKS_PATH`.

## When NOT to Use This Skill

- Quick bug fixes (just fix it, no PRD needed)
- One-liner tasks with obvious scope
- Research or exploration tasks
- Updating existing stories (edit the file directly)
- Simple documentation tasks (not everything needs F##/S## structure)

## Three-Phase Process

### Phase 1: Clarification (3-5 Questions)

**Skip Phase 1 if** the user provides: (1) a clear problem statement, (2) explicit scope boundaries, and (3) at least 2-3 named stories or tasks. Briefly confirm understanding before generating.

Before writing, ask targeted questions based on gaps in the request. Skip questions already answered.

**Question Areas:**
- **Problem/Goal** — What are we solving? What does success look like?
- **Scope** — What's in? What's explicitly out?
- **Stories** — What are the major chunks of work? (probe for natural splits)
- **Dependencies** — What must exist first?
- **Type** — Software, operations, marketing, or infrastructure? (skip if obvious from context -- code/API/UI → software, server/Docker → infrastructure, content/campaign → marketing)

### Phase 1.5: Premortem

After clarification is complete, before generating files, run a brief premortem. Imagine the feature has been built and has failed. Identify 3-5 realistic failure scenarios:

- What technical risks could derail this? (wrong abstraction, missing dependency, performance)
- What scope risks exist? (creep, ambiguous boundaries, unstated assumptions)
- What external risks apply? (third-party API changes, data quality, timing)

For each failure scenario, assess: does the current story set address it? If yes, note which story. If no, either add it as an Open Design Decision in the feature canvas or propose an additional story.

**Skip the premortem if** HacksterT explicitly says to skip it, or if the feature is trivially scoped (single story, under 30 minutes of work).

### Phase 2: Generate Files

After clarification, generate the feature canvas and all story files.

**Step-by-step:**

1. Run `next-id.sh feature` to get the feature ID
2. For each story, run `next-id.sh story F##` to get the story ID
3. Write the feature canvas using `references/feature-canvas-template.md`
4. Write each story file using the appropriate template:
   - Software stories → `references/software-story-template.md`
   - All other types → `references/story-template.md`
5. Save all files to `tasks/`

## File Structure

### Feature Canvas (lightweight overview)

Read `references/feature-canvas-template.md` for full template.

Key sections:
- **Overview** — Feature name, problem, goal
- **Context** — Background, why now
- **Stories table** — ID, title, priority, status (the index)
- **Non-Goals** — Explicit scope boundaries
- **Dependencies** — What must exist first
- **Success Metrics** — How we know it's done
- **Open Design Decisions** — Unresolved questions

### User Story (full spec per story)

Read `references/story-template.md` for full template. For software stories with migrations, tests, and Git workflow, read `references/software-story-template.md`.

Key sections:
- **Title** — `F##-S##: [Story Title]`
- **Feature reference** — Which feature this belongs to
- **Priority** — Must-Have / Should-Have / Nice-to-Have
- **Summary** — One paragraph "what and why" (MANDATORY)
- **Acceptance Criteria** — Testable, observable outcomes
- **Tasks** — Specific, actionable steps (max 8-10)
- **Technical Notes** — Implementation details and decisions
- **Blockers** — Dependencies or "None"

## Story Types

| Type | When to Use | Template | Task Style |
|------|-------------|----------|------------|
| **Software** | Code features, APIs, UI | `software-story-template.md` | Backend/Frontend/Testing/Git categories |
| **Operations** | Workflows, processes, automation | `story-template.md` | Plain task list |
| **Marketing** | Content, campaigns, strategy | `story-template.md` | Plain task list |
| **Infrastructure** | Server, Docker, deployments | `story-template.md` | Command-level detail |

## Status Tracking

PRD status is tracked via YAML front matter in each file.

```yaml
---
type: prd
feature: F05
status: draft    # draft | active | completed
created: 2026-02-25
priority: high
---
```

### File Lifecycle

- **Active/Draft PRDs** live in `tasks/` (the working backlog)
- **Completed PRDs** are moved to `tasks/completed/`, optionally into topic subdirectories

```text
tasks/
  F15-knowledge-base-consolidation.md     ← Active feature
  F15-S01-move-references.md              ← Active story
  completed/
    skills/
      F04-skills-architecture.md          ← Done
      F13-*.md                            ← Done
    memory/
      F07-*.md, F10-*.md                  ← Done
```

When marking a feature complete:
1. Update YAML front matter: `status: completed`
2. Move the feature canvas and all its story files to `tasks/completed/` (optionally into a topic subdirectory)

The `next-id.sh` script scans both `tasks/` and `tasks/completed/` recursively, so completed PRDs never get reissued an ID.

## Sizing Rules

**Feature level:**
- Target **3-6 stories** per feature
- Fewer than 3 = probably a single story, not a feature
- More than 6 = split into multiple features

**Story level:**
- Max **8-10 tasks** per story — split if larger
- Every story must be **self-contained** — readable without the feature canvas
- Summary is **mandatory** — no exceptions

## Story Quality Check (INVEST)

Before writing a story, verify it passes these criteria:

- **Independent** — Can be built and delivered on its own, not tangled with other stories
- **Negotiable** — Details can be adjusted during implementation; it's a plan, not a contract
- **Valuable** — Delivers something meaningful, not just busywork
- **Estimable** — You can roughly gauge the effort (if you can't, it needs more clarification)
- **Small** — Fits in a focused work session, not a multi-week saga
- **Testable** — You can verify it works by checking the acceptance criteria

## Acceptance Criteria Formats

Use whichever format fits the story:

**Checklist format** (default — good for most stories):
- [ ] User can do X
- [ ] Error Y displays message Z
- [ ] Edge case handled

**Given/When/Then format** (good for complex behavioral specs):
- Given [precondition]
- When [action]
- Then [expected outcome]

## Scope Creep Signals

Watch for these during Phase 1 clarification or story writing:

1. Requirements keep growing after the feature was scoped
2. "While we're at it..." additions that aren't part of the original problem
3. A story needs more than 10 tasks — it's probably two stories
4. The feature is solving problems nobody asked about
5. The list of stories keeps growing past 6 — split into multiple features

If scope is creeping, stop and re-clarify: what's the core problem? What's the smallest thing that solves it?

## Architecture Decision Records

When a feature involves a significant technical choice (database, library, API pattern, data model), document it using the ADR template at `references/adr-template.md`.

Save ADRs to `docs/decisions/ADR-##-short-title.md`.

Not every decision needs one — only choices you'd question later or that constrain future options.

## Validation Checklist

Before finalizing:

- [ ] Feature ID generated via `next-id.sh feature`
- [ ] All story IDs generated via `next-id.sh story F##`
- [ ] Feature canvas has: overview, stories table, non-goals, dependencies, success metrics
- [ ] Every story has: summary, acceptance criteria, tasks, technical notes, blockers
- [ ] Stories pass INVEST check (Independent, Negotiable, Valuable, Estimable, Small, Testable)
- [ ] No story exceeds 8-10 tasks
- [ ] Feature has 3-6 stories (or justified exception)
- [ ] All files saved to `tasks/`
- [ ] Filenames follow pattern: `F##-short-title.md` and `F##-S##-short-title.md`
- [ ] YAML front matter includes type, feature, status, created, priority
- [ ] ADR written for any significant technical decisions (if applicable)
- [ ] No scope creep — every story traces back to the original problem
