---
name: project-status
description: >
  Create or update a STATUS.md file for the current project. Reads project
  context (README, active PRDs in any tasks/ folder) and generates a structured
  status file with YAML frontmatter and the next 5 to-dos extracted from active
  PRDs. Works in any project -- software repos, plain folders, or anything with
  a tasks/ directory. Install in any repo's .claude/skills/ and it works without
  modification.
  TRIGGERS - "create a status file", "update my status", "update status.md",
  "generate status", "refresh status", "add status to this project",
  "make a status file", "create status.md", "update the status", "sync status"
---

# STATUS.md Skill

Generate or refresh a STATUS.md at the repo root. The file has two parts: a
YAML frontmatter block (consumed by the portfolio aggregator) and a prose
section with the next 5 actionable to-dos from active PRDs.

Do not hardcode paths. Resolve everything relative to the repo root.

**Schema reference:** `references/STATUS-schema.md` -- canonical field
definitions, allowed values, validation rules, and the full aggregator contract.
Read it when any field semantics are unclear. The table in Step 5 is a
convenience summary only; the reference file takes precedence.

---

## Mode Detection

- **Create mode:** No STATUS.md at the repo root. Generate from scratch.
- **Update mode:** STATUS.md exists. Re-extract to-dos, set `updated` to today,
  preserve all other frontmatter unless the user explicitly changes a field.

Default to update if STATUS.md exists.

---

## Step 1: Locate the Repo Root

```bash
git rev-parse --show-toplevel 2>/dev/null || echo "not a git repo"
```

If not a git repo, use the directory containing the `.claude/skills/` folder.
If running from the-claude command center with no repo context, ask the user
which project to target before proceeding.

---

## Step 2: Read Project Context

Read selectively -- only what is needed to fill the STATUS.md fields.

```bash
ls {REPO_ROOT}/
cat {REPO_ROOT}/README.md 2>/dev/null || cat {REPO_ROOT}/README 2>/dev/null
head -20 {REPO_ROOT}/pyproject.toml 2>/dev/null || \
head -20 {REPO_ROOT}/package.json 2>/dev/null
```

Stop reading once you have enough to infer `project`, `phase`, `next_step`,
`key_people`, and `status`.

---

## Step 3: Find Active PRDs

Active PRDs are Markdown files in any `tasks/` directory that are NOT inside a
`completed/` subfolder. Scan up to 4 levels deep.

```bash
find {REPO_ROOT} -type d -name "tasks" \
  -not -path "*/node_modules/*" -not -path "*/.git/*" 2>/dev/null

# For each tasks/ directory found:
find {TASKS_DIR} -maxdepth 1 -name "*.md" -type f 2>/dev/null
```

If multiple `tasks/` directories exist, scan all of them.

---

## Step 4: Extract Next 5 To-Dos

From all active PRDs, extract the next 5 unchecked items (`- [ ] `).

Priority order: Must-Have before Should-Have, earlier story numbers first
(F03-S01 before F03-S02), Tasks section before Acceptance Criteria.

Format each item as:
```
- [ ] {task text} *(source: {PRD filename without path})*
```

Keep each line under 120 characters. If fewer than 5 exist, include all.
If no active PRDs exist, leave the section empty with a placeholder.

---

## Step 5: Fill the YAML Schema

| Field | How to fill it |
|-------|---------------|
| `project` | Repo/folder name, lowercase-hyphenated. Match the directory name. |
| `status` | `active`, `paused`, `complete`, or `deprecated`. Default to `active`. |
| `phase` | Highest active feature number (e.g., `F03`) or descriptive phase name. |
| `next_step` | One sentence. The single action that blocks everything else. |
| `blockers` | Explicit blockers from PRDs or README. Use `[]` if none. |
| `key_people` | Names, orgs, or roles relevant to the current phase. Use `[]` if none. |
| `updated` | Today's date, `YYYY-MM-DD`. Always set this. |

---

## Step 6: Write the File

```markdown
---
project: {slug}
status: {active|paused|complete|deprecated}
phase: {current milestone}
next_step: "{single sentence}"
blockers:
{  - "{blocker}" | []}
key_people:
{  - "{name/role}" | []}
updated: {YYYY-MM-DD}
---

## Next Steps

{Extracted to-dos with source annotations, or placeholder if none}

## Notes

{1-2 sentences of current focus, recent decisions, or relevant links.
Omit this section entirely if nothing useful to add.}
```

**Create mode:** Write the full file.

**Update mode:** Preserve existing frontmatter verbatim (except `updated`).
Replace `## Next Steps` entirely. Preserve `## Notes` verbatim.

---

## Step 7: Report

After writing, tell the user:
- Mode (created / updated)
- File path written
- Number of to-dos extracted and which PRDs they came from
- Any fields where you made an inference

Write first, report after. Do not ask for confirmation before writing.

---

## Edge Cases

**No tasks/ folder:** Write STATUS.md with an empty `## Next Steps` and note:
`*(No tasks/ folder found -- add to-dos manually or create PRDs)*`

**All PRDs in completed/:** Infer `status: complete`. Leave `## Next Steps`
empty with: `*(All PRDs are complete)*`

**Non-standard existing STATUS.md:** Rewrite using the standard template.
Preserve any prose from `## Notes` if present.

**Ambiguous `next_step`:** Use the first unchecked to-do as the value.

---

## References

- `references/STATUS-schema.md` -- Canonical schema: all field rules, allowed
  values, the aggregator contract, and a full annotated example. Read when
  field semantics are unclear or you need validation rules.

---

## Portability

To install in any repo, copy the entire `project-status/` folder (including
`references/STATUS-schema.md`) to `{any-repo}/.claude/skills/project-status/`.
The skill resolves all paths from the repo root at runtime -- no configuration
needed.
