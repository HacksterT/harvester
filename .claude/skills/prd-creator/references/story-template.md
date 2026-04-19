# User Story Template

Use this template for individual user story files. Each story is a standalone document with everything needed to understand and execute the work.

---

## Template

```markdown
# F##-S##: [Story Title]

**Feature:** [F## — Feature Title]
**Priority:** Must-Have | Should-Have | Nice-to-Have

## Summary

[One paragraph describing what this story delivers and why it matters. This is the quick "what and why" — readable without digging into tasks. Include enough context that someone picking this up cold understands the intent.]

## Acceptance Criteria

- [ ] [Testable criterion — specific, observable outcome]
- [ ] [Another criterion — include error cases where relevant]
- [ ] [Edge case handling]

## Tasks

- [ ] [Specific, actionable task]
- [ ] [Another task]
- [ ] [Group related tasks logically]

### Software Tasks (use when applicable)

- [ ] Backend: [specific task — models, migrations, endpoints]
- [ ] Backend: Create migration (test up/down locally before committing)
- [ ] Frontend: [specific task — components, UI, state]
- [ ] Testing: [story-specific tests only]
- [ ] Local Testing: Run tests and verify acceptance criteria
- [ ] Manual Testing: CHECKPOINT — Notify user to verify before proceeding
- [ ] Git: Commit, fetch/rebase, push

## Technical Notes

[Implementation details, architectural decisions, constraints, technology choices. Or "None" if straightforward.]

## Blockers

[Dependencies on other stories, external resources, access needed, or unresolved decisions. Or "None".]

---

*Created: YYYY-MM-DD by Spock 🖖*
```

## Story Types

| Type | When to Use | Task Style |
|------|-------------|------------|
| **Software** | Code features, APIs, UI work | Use Software Tasks section with Backend/Frontend/Testing/Git categories |
| **Operations** | Workflows, processes, automation | Use plain Tasks section |
| **Marketing** | Content, campaigns, strategy | Use plain Tasks section |
| **Infrastructure** | Server, Docker, deployments | Use plain Tasks section with command-level detail |

## Rules

- **Summary is mandatory.** Every story needs a clear one-paragraph overview.
- **Max 8-10 tasks per story.** If more, split into two stories.
- **Acceptance criteria are testable.** "Works correctly" is not a criterion. "User sees error message X when Y happens" is.
- **Technical notes capture decisions.** Why this approach, not just what to do.
- **Blockers are honest.** If a story depends on another, say so. Don't let someone start blocked work.
- **Self-contained.** A reader should understand the story without reading the feature canvas. The canvas provides context; the story provides everything needed to execute.
