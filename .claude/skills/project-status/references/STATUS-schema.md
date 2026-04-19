# STATUS.md Schema Reference

This document is the canonical definition of the STATUS.md file format used by the Project Portfolio Manager. It is the spec the `project-status` skill is built against and the contract the portfolio aggregator expects.

---

## Purpose

A STATUS.md file at the root of any project (repo, plain folder, or nested subdirectory) tells the portfolio aggregator everything it needs to display that project in the dashboard. The aggregator reads only the YAML frontmatter. Any prose below the frontmatter is for human readers and the `project-status` skill -- it is ignored by the aggregator.

STATUS.md presence is the opt-in mechanism. Projects without the file are invisible to the portfolio.

---

## YAML Frontmatter Schema

```yaml
---
project: <slug>
status: <active|paused|complete|deprecated>
phase: <milestone>
next_step: "<single sentence>"
blockers:
  - "<description>"
key_people:
  - "<name or role>"
updated: YYYY-MM-DD
---
```

### Field Reference

| Field | Type | Required | Allowed Values |
|-------|------|----------|---------------|
| `project` | string | yes | Lowercase slug matching the folder or repo name |
| `status` | enum | yes | `active`, `paused`, `complete`, `deprecated` |
| `phase` | string | yes | Free text -- feature ID, sprint name, funding stage, etc. |
| `next_step` | string | yes | One sentence max. The single action blocking everything else. |
| `blockers` | list of strings | yes | Use `[]` when nothing is blocking. Do not omit. |
| `key_people` | list of strings | yes | Names, orgs, or roles relevant to the current phase. Use `[]` if none. |
| `updated` | ISO date | yes | `YYYY-MM-DD`. Must change whenever any other field changes. |

### Field Rules

**`project`** -- lowercase, hyphens or underscores only, no spaces. Match the directory name exactly where possible. This is how the aggregator deduplicates entries and routes API requests.

**`status`** -- use these values as defined:
- `active` -- being worked on right now
- `paused` -- real project, not currently being worked on
- `complete` -- done; all work delivered
- `deprecated` -- abandoned or superseded; hidden from the portfolio by default

**`next_step`** -- singular. If you have two things to do, identify the one that blocks the other and use that. The UI surfaces this field prominently. It should be specific enough to act on without opening another file.

**`blockers`** -- must be present even when empty. `blockers: []` is correct. Do not omit the field. The aggregator uses field presence for validation.

**`key_people`** -- optional in practice but must be present in the file. Use `[]` when no people are relevant. Include only people relevant to the *current phase*, not the full project history.

**`updated`** -- this is the maintenance contract. The aggregator uses it to flag stale entries (> 14 days without an update). The `project-status` skill sets this to today whenever it writes the file. When editing STATUS.md manually, update this field.

### Source Field (aggregator-injected, not written to file)

The aggregator adds a `source` field to every entry at read time. This field is never written into STATUS.md files.

- `source: "file"` -- entry came from a STATUS.md file on the filesystem
- `source: "managed"` -- entry came from `portfolio-managed.json` (non-repo projects)

Do not include `source` in STATUS.md files. If present, it will be ignored.

---

## Annotated Example

```yaml
---
project: ezra-assistant
status: active
phase: F03
next_step: "Implement the apple_notes skill (F03-S04)"
blockers:
  - "anotes CLI must be confirmed accessible before starting"
key_people:
  - "Troy (owner)"
updated: 2026-04-15
---

## Next Steps

- [ ] Implement apple_notes skill (F03-S04) *(source: F03-S04-apple-notes-skill.md)*
- [ ] CMO system prompt and manifest (F03-S01) *(source: F03-cmo-agent.md)*
- [ ] manage_calendar skill: Apple Calendar JXA (F03-S02) *(source: F03-S02-manage-calendar-skill.md)*
- [ ] create_image skill: DALL-E 3 (F03-S03) *(source: F03-S03-create-image-skill.md)*
- [ ] Telegram bot wired to supervisor (F04-S03) *(source: F04-knowledge-pipeline-and-telegram.md)*

## Notes

Python/LangGraph runtime replacing Atlas (Node.js). F01 and F02 complete.
Anamnesis knowledge layer wired. CMO agent and Apple productivity skills are
the remaining gap before Atlas can be shut down.
```

### What each section does

The **YAML frontmatter** (between the `---` delimiters) is machine-readable. The aggregator parses it, the portfolio API serves it, and the UI renders it in the sidebar and detail panel.

The **`## Next Steps`** section is generated and refreshed by the `project-status` skill. It contains the next 5 unchecked to-do items extracted from active PRDs in the project's `tasks/` folder. The skill annotates each item with its source PRD filename. The UI renders this section as markdown in the detail panel (read-only).

The **`## Notes`** section is freeform prose -- current focus, recent decisions, relevant links. The `project-status` skill preserves this section on updates. Write whatever is useful here.

---

## Prose Below the Frontmatter

Any content below the closing `---` is prose. The aggregator ignores it entirely. The `project-status` skill reads and preserves it. Write freely -- project notes, ADR summaries, links to relevant docs, or nothing at all.

The `## Next Steps` and `## Notes` sections shown in the example above are conventions, not requirements. The project-status skill uses those headers. If you write STATUS.md manually without using the skill, any structure is acceptable.

---

## Validation

To confirm a STATUS.md file parses cleanly:

```bash
python3 -c "
import yaml, sys
text = open('STATUS.md').read()
parts = text.split('---', 2)
if len(parts) < 3:
    sys.exit('No frontmatter block found')
data = yaml.safe_load(parts[1])
required = ['project', 'status', 'phase', 'next_step', 'blockers', 'key_people', 'updated']
missing = [f for f in required if f not in data]
if missing:
    sys.exit(f'Missing fields: {missing}')
print('Valid:', data['project'], '|', data['status'], '|', data['updated'])
"
```

---

## Managed Projects (`portfolio-managed.json`)

Non-repo projects with no local filesystem presence are stored in `ezra-assistant/data/portfolio-managed.json`. These entries share the same six schema fields but add a `todos` array for structured to-do tracking (since managed projects have no PRDs for the skill to read from).

```json
{
  "version": 1,
  "projects": [
    {
      "project": "ai-labor-solutions",
      "status": "active",
      "phase": "agency launch",
      "next_step": "Define initial service packages",
      "blockers": [],
      "key_people": [],
      "updated": "2026-04-15",
      "todos": [
        { "text": "Define initial service packages", "done": false },
        { "text": "Set up LLC", "done": false },
        { "text": "Draft first client proposal", "done": false }
      ]
    }
  ]
}
```

The `todos` field does not exist in STATUS.md files and is not part of the YAML schema. It is only present in managed entries. The aggregator injects `source: "managed"` on these entries at read time.

---

*Schema version: 1 | Created: 2026-04-15*
