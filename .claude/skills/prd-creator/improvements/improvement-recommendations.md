# prd-creator Improvement Recommendations

Analysis performed using skill-creator principles. Generated: 2026-03-08

---

## 1. Description Undertriggering Risk

**Current:** Good but could be more aggressive. Per skill-creator: "Undertriggering is the most common failure."

**Suggestion:** Add casual trigger phrases that don't explicitly mention PRD:

```yaml
description: >
  Create PRDs (Product Requirements Documents) with working backlogs.
  Use when asked to create a PRD, write a feature spec, document a project,
  plan a new feature, or structure work into stories.
  TRIGGERS - create PRD, new PRD, write PRD, feature spec, project plan,
  document this project, structure this work, "break this down into stories",
  "plan this feature", "spec this out", "I want to build X", "help me scope this",
  "what are the stories for this"
```

That last batch catches users who describe intent without knowing they need a PRD.

---

## 2. Missing: When NOT to Use This Skill

skill-creator recommends testing against "should-not-trigger" queries. prd-creator lacks explicit scope boundaries.

**Suggestion:** Add section after "Two-Phase Process":

```markdown
## When NOT to Use This Skill
- Quick bug fixes (just fix it, no PRD needed)
- One-liner tasks with obvious scope
- Research/exploration (use Task tool instead)
- Updating existing stories (edit directly)
- Simple documentation tasks (not everything needs F##/S## structure)
```

---

## 3. Skip Heuristic for Phase 1

Phase 1 says "skip questions already answered" but no guidance for skipping Phase 1 entirely when the user provides a complete spec.

**Suggestion:** Add heuristic at start of Phase 1:

```markdown
### Phase 1: Clarification (3-5 Questions)

**Skip Phase 1 if** the user provides: (1) clear problem statement, (2) explicit
scope boundaries, and (3) at least 2-3 named stories or tasks. In this case,
briefly confirm understanding before generating.
```

---

## 4. Script Path Mismatch

**Problem:** SKILL.md references `.claude/skills/prd-creator/scripts/next-id.sh`
**Actual path:** `.atlas/skills/prd-creator/scripts/next-id.sh`

**Fix:** Update line 28-34 to use correct path:
```bash
# Get next feature number
.atlas/skills/prd-creator/scripts/next-id.sh feature
```

---

## 5. No Example Workflow

skill-creator emphasizes examples. prd-creator has templates but no end-to-end example.

**Suggestion:** Create `references/example-workflow.md`:

```markdown
# Example: Notification System PRD

## User Request
"I want to add push notifications to the app. Users should be able to opt in,
and we need to handle quiet hours."

## Phase 1 Clarification
1. What platforms? (iOS, Android, web push, all?)
2. What events trigger notifications?
3. Should quiet hours be user-configurable or system-wide?

## Generated Files
- F06-notification-system.md (feature canvas)
- F06-S01-push-infrastructure.md
- F06-S02-user-preferences-ui.md
- F06-S03-quiet-hours-logic.md
```

---

## 6. Missing Test Cases

Per skill-creator: "At least 2 test cases have been run and reviewed."

**Suggestion:** Add test cases (this file lives in tests/):

### Should Trigger:
1. "Create a PRD for user authentication"
2. "I want to build a dashboard. Help me plan it."
3. "Break this feature into stories"
4. "Spec out the API integration"
5. "Document this project properly"

### Should NOT Trigger:
1. "Fix the bug in login.py"
2. "What does this function do?"
3. "Update F05-S02 acceptance criteria"
4. "Research how other apps handle notifications"
5. "Write a unit test for the parser"

---

## 7. Kanban Integration Is Dangling

SKILL.md mentions Kanban cards and `prd_link` but no script or reference explains the integration.

**Options:**
- A) Add `references/kanban-integration.md` explaining the workflow
- B) Mark it as "planned" with a note: `<!-- TODO: Kanban integration pending -->`
- C) Remove the reference until implemented

---

## 8. YAML Front Matter Inconsistency

The status tracking section shows `type: prd` but templates may vary. Consider standardizing:

| File Type | `type` value |
|-----------|--------------|
| Feature canvas | `feature` |
| Story | `story` |

Or keep `prd` for both and add `subtype: feature | story`.

---

## Priority Order

If implementing changes:

1. **Script path fix** (line 28-34) - broken reference
2. **Undertriggering** - biggest impact on usability
3. **When NOT to use** - prevents misuse
4. **Skip heuristic** - quality of life
5. **Example workflow** - nice to have
6. **Test cases** - ongoing validation
7. **Kanban clarification** - documentation debt
8. **YAML standardization** - minor consistency

---

## Summary

The skill works well because the F##/S## system, templates, and ID script are solid. Main gaps are in triggering reliability and edge-case guidance. None of these are urgent.
