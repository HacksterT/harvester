# Software Story Template

Full template for software development stories with migrations, tests, and Git workflow.

Use this template when creating stories for code features, APIs, or UI work. Follows the F##-S## nomenclature system.

---

## Story Template

```markdown
# F##-S##: [Story Title]

**Feature:** F## — [Feature Title]
**Priority:** Must-Have | Should-Have | Nice-to-Have

## Summary

[One paragraph describing what this story delivers and why it matters. This is the quick "what and why" — readable without digging into tasks. Include enough context that someone picking this up cold understands the intent.]

## Acceptance Criteria

- [ ] [Testable criterion — specific, observable outcome with error messages]
- [ ] [Edge case handling]
- [ ] All new dependencies audited for known vulnerabilities and pinned to exact versions

## Tasks

### Backend
- [ ] [Specific task — models, migrations, endpoints, services, validation]
- [ ] Create migration (test up/down locally before committing)

### Frontend
- [ ] [Specific task — components, pages, context providers, forms, hooks]

### Dependencies (if new packages added)
- [ ] Audit each new package: check weekly downloads, last publish date, maintainer count, known advisories
- [ ] Pin exact version in lock file (npm ci / uv pip compile)
- [ ] Run `npm audit` or `uv pip audit` after install
- [ ] Document new dependencies and versions in Technical Notes for traceability

### Testing & Verification
- [ ] [Story-specific tests only — unit, integration, e2e as appropriate]
- [ ] Local Testing: Run story-specific tests and verify all acceptance criteria pass
- [ ] Manual Testing: CHECKPOINT — Notify user to manually verify before proceeding

### Git
- [ ] Commit, fetch/rebase, push

## Technical Notes

[Implementation details, architectural decisions, constraints, technology choices. Or "None" if straightforward.]

## Blockers

[Dependencies on other stories, external resources, access needed, or unresolved decisions. Or "None".]

---

*Created: YYYY-MM-DD*
```

---

## Blocker Template

Place unresolved blockers at end of the feature's stories:

```markdown
# F##-BLOCK-##: [Description]

**Blocking:** F##-S##
**Resolution:** [How to resolve]
```

---

## Rules

- **Summary is mandatory.** Every story needs a clear one-paragraph overview.
- **Max 8-10 tasks per story.** If more, split into two stories.
- **Acceptance criteria are testable.** "Works correctly" is not a criterion. "User sees error message X when Y happens" is.
- **Every software story MUST end with**: Local Testing, Manual Testing, Git tasks.
- **Migration tasks must include**: "(test up/down locally before committing)".
- **Testing scope**: story-specific tests only (full app testing is QA's responsibility).
- **Technical notes capture decisions.** Why this approach, not just what to do.
- **Blockers are honest.** If a story depends on another, say so.
- **Self-contained.** A reader should understand the story without reading the feature canvas.
- **NO standalone TECH-XX items** — embed technical work in story tasks.
- **NO "See: FR-X" references** — all specs inline in the story.
- **Dependency audit is mandatory** when a story introduces new packages. Include the Dependencies task section. For critical packages (network, auth, crypto), note a 48-72 hour waiting period after new releases before upgrading.

---

## Task Categories

| Category | Examples |
|----------|----------|
| **Backend** | Models, migrations, endpoints, services, validation |
| **Frontend** | Components, pages, context providers, forms, hooks |
| **Dependencies** | Audit new packages, pin versions, run npm audit, document in Technical Notes |
| **Testing** | Unit tests, integration tests, e2e tests |
| **Local Testing** | Run tests, verify acceptance criteria locally |
| **Manual Testing** | Human verification checkpoint |
| **Git** | Commit, rebase, push |

---

## When to Split a Story

- More than 8-10 tasks
- Multiple distinct features bundled together
- Tasks span multiple domains with no shared acceptance criteria

---

## Example

```markdown
# F02-S01: User Registration

**Feature:** F02 — User Authentication
**Priority:** Must-Have

## Summary

Implement email/password registration so new users can create accounts. This is the foundational auth story — login (F02-S02) and password reset (F02-S03) depend on the user model and registration endpoint created here.

## Acceptance Criteria

- [ ] User can submit registration form with email and password
- [ ] Password must be minimum 8 characters with 1 number and 1 special character
- [ ] Duplicate email displays error: "An account with this email already exists"
- [ ] Invalid email format displays error: "Please enter a valid email address"
- [ ] Successful registration redirects to login page with success message

## Tasks

### Backend
- [ ] Create User model (id, email, password_hash, created_at, updated_at) with unique email constraint
- [ ] Create migration (test up/down locally before committing)
- [ ] Create POST /api/auth/register endpoint with bcrypt hashing
- [ ] Add email validation & duplicate check

### Frontend
- [ ] Build registration form with client-side validation

### Testing & Verification
- [ ] Write story-specific integration tests (success + all error cases)
- [ ] Local Testing: Run story-specific tests and verify all acceptance criteria pass
- [ ] Manual Testing: CHECKPOINT — Notify user to manually verify before proceeding

### Git
- [ ] Commit, fetch/rebase, push

## Technical Notes

Use bcrypt with cost factor 12. Email validation: RFC 5322.

## Blockers

None
```
