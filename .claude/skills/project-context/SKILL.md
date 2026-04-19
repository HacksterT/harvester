---
name: project-context
description: >
  Generate or update a CONTEXT.md file for the current project. Mines repo
  artifacts (README, CLAUDE.md, tasks/, source tree, git log) and produces a
  structured context file with YAML frontmatter and section headings. Content
  is synced into Ezra's memory store on demand via the Knowledge Center UI.
  TRIGGERS - "generate context", "update context", "create context.md",
  "update context.md", "refresh project context", "seed project context",
  "mine project context", "generate CONTEXT.md"
---

# CONTEXT.md Skill

Generate or refresh a CONTEXT.md at the repo root. This file is the canonical
description of a project -- what it is, how it works, what conventions it
follows. It is maintained by this skill and synced into Ezra's memory on demand.

Do not hardcode paths. Resolve everything relative to the repo root.

**Schema reference:** `references/CONTEXT-schema.md` -- canonical field
definitions and section descriptions. Read it when any field semantics are
unclear.

---

## Mode Detection

- **Create mode:** No CONTEXT.md at the repo root. Generate from scratch.
- **Update mode:** CONTEXT.md exists. Re-mine all sections, preserve frontmatter
  (except `updated`). Replace section content with freshly mined content.
  Preserve sections that are not in the default set if they were added manually.

Default to update if CONTEXT.md exists.

---

## Step 1: Locate the Repo Root

```bash
git rev-parse --show-toplevel 2>/dev/null || echo "not a git repo"
```

If not a git repo, use the directory containing the `.claude/skills/` folder.

---

## Step 2: Read Project Artifacts

Read selectively. Only what is needed to fill the sections.

```bash
ls {REPO_ROOT}/
cat {REPO_ROOT}/README.md 2>/dev/null
cat {REPO_ROOT}/CLAUDE.md 2>/dev/null
head -30 {REPO_ROOT}/pyproject.toml 2>/dev/null || head -30 {REPO_ROOT}/package.json 2>/dev/null
ls {REPO_ROOT}/src/ 2>/dev/null || ls {REPO_ROOT}/lib/ 2>/dev/null
git -C {REPO_ROOT} log --oneline -10 2>/dev/null
```

Find active tasks/PRDs:

```bash
find {REPO_ROOT} -type d -name "tasks" \
  -not -path "*/node_modules/*" -not -path "*/.git/*" 2>/dev/null
find {TASKS_DIR} -maxdepth 1 -name "*.md" -type f 2>/dev/null
```

Read the frontmatter of each active PRD (first 20 lines) to get feature titles
and statuses. Do not read full PRD bodies unless you need detail for Active Work.

---

## Step 3: Mine Each Section

Generate only sections that have substantive content. Omit a section entirely
rather than filling it with vague placeholder text.

### Overview
What the project is, its goal, the problem it solves, and its current status.
2-4 sentences. Pull from README and STATUS.md if present.

### Architecture
Key components, tech stack, runtime, data flow, and major design decisions.
Use bullet points. Pull from CLAUDE.md architecture section and source tree.

### Key Conventions
Naming patterns, coding rules, non-obvious constraints. Things a developer
needs to know that aren't discoverable from the code alone.
Pull from CLAUDE.md conventions section.

### Dependencies
External systems, other repos, services, APIs, and infrastructure this project
relies on. Include local paths to sibling repos when relevant.
Pull from README, pyproject.toml/package.json, and CLAUDE.md.

### Active Work
What is currently in progress or planned next. Pull from active PRDs and
STATUS.md next_step. 3-5 bullet points with story IDs where applicable.

---

## Step 4: Write the File

```markdown
---
project: {slug}
updated: {YYYY-MM-DD}
description: "{one sentence summary}"
---

## Overview

{mined content}

## Architecture

{mined content}

## Key Conventions

{mined content}

## Dependencies

{mined content}

## Active Work

{mined content}
```

**Create mode:** Write the full file.

**Update mode:** Preserve frontmatter except `updated` (set to today).
Replace each section's content. Preserve any non-default `##` sections verbatim.

---

## Step 5: Report

After writing, tell the user:
- Mode (created / updated)
- File path written
- Which sections were generated and which were omitted (and why)
- Any inferences made about the project

Write first, report after. Do not ask for confirmation before writing.

---

## Edge Cases

**No README or CLAUDE.md:** Generate what you can from source tree structure,
pyproject.toml/package.json, and git log. Note in the report what was missing.

**Monorepo:** Treat the top-level as the project root. Include sub-package
names in Architecture.

**Non-code repo:** Generate Overview and Active Work from whatever artifacts
exist. Omit Architecture and Key Conventions if not applicable.

---

## References

- `references/CONTEXT-schema.md` -- Canonical schema: frontmatter fields,
  section definitions, sync contract with Ezra memory store.

---

## Portability

To install in any repo, copy the entire `project-context/` folder to
`{any-repo}/.claude/skills/project-context/`. The skill resolves all paths
from the repo root at runtime -- no configuration needed.
