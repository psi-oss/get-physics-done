---
template_version: 1
type: author-response-template
---

<!-- Used by: respond-to-referees workflow and gpd-paper-writer for the canonical internal author-response contract. -->

# Author Response Template

Canonical source of truth for `GPD/AUTHOR-RESPONSE{round_suffix}.md`.

Use this structure whenever drafting the internal response tracker that later review rounds and the referee workflow will read. The journal-facing `GPD/review/REFEREE_RESPONSE{round_suffix}.md` mirrors the same issue IDs, classifications, statuses, and new-calculation tracking.

The paired response-artifact contract at `@{GPD_INSTALL_DIR}/references/publication/publication-response-artifacts.md` owns the one-shot completion gate, the fresh `gpd_return.files_written` requirement, and the rule that `fixed` is only valid after the manuscript edit already exists on disk.

---

## File Template

```markdown
---
response_to: REFEREE-REPORT{round_suffix}.md
round: {N}
date: YYYY-MM-DDTHH:MM:SSZ
issues_fixed: {count}
issues_rebutted: {count}
issues_acknowledged: {count}
issues_needing_calculation: {count}
---

# Author Response — Round {N}

## Summary

{1-2 paragraph overview: what changed, what was rebutted, what remains.}

## Point-by-Point Responses

### REF-001: {brief description from referee report}

**Classification:** fixed | rebutted | acknowledged | needs-calculation
**Assessment:** {is the referee correct, partially correct, or mistaken?}
**Response:** {issue-by-issue narrative response}
**Changes:** {exact manuscript locations changed or planned follow-up work}
**New calculations required:** yes | no
**Source phase for new work:** Phase X or N/A
**Status:** Not started | In progress | Response drafted | Final

### REF-002: {brief description from referee report}

**Classification:** fixed | rebutted | acknowledged | needs-calculation
**Assessment:** {assessment}
**Response:** {response text}
**Changes:** {changes}
**New calculations required:** yes | no
**Source phase for new work:** Phase X or N/A
**Status:** Not started | In progress | Response drafted | Final

## Blocking Items From Decision Artifacts

| Issue ID | Source Artifact | Blocking Reason | Resolution Plan | Status |
| -------- | --------------- | --------------- | --------------- | ------ |
| REF-001  | REVIEW-LEDGER{round_suffix}.json | [blocking reason] | [narrow claim, revise text, or add evidence] | [Open / In progress / Cleared] |

## New Calculations Summary

| ID | Issue ID | Requested By | Description | Phase | Plan | Status |
| -- | -------- | ------------ | ----------- | ----- | ---- | ------ |
| NC-1 | REF-001 | Referee 1 | [description] | [X] | [XX-YY] | [status] |

## Manuscript Changes Summary

### Major changes

1. [Description of significant revision, referencing which comment prompted it]

### Minor changes

1. [Typo fix, reference addition, wording clarification]

### Unchanged (with justification)

1. [What was not changed and why, referencing the comment]

## Response Letter Draft

Draft the journal-facing letter from the same issue-by-issue content and keep the point-by-point substance synchronized with `GPD/review/REFEREE_RESPONSE{round_suffix}.md`.
```

## Guidance

- Keep `needs-calculation` visible whenever a response requires new research work.
- Keep `Source phase for new work` explicit for every comment that depends on future work.
- Do not omit the status field; later review rounds rely on it.
- Use `fixed` only when the corresponding manuscript edit is already on disk.
