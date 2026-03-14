---
template_version: 1
---

<!-- Used by: respond-to-referees workflow for structured referee responses. -->

# Referee Response Template

Template for `.gpd/paper/REFEREE_RESPONSE.md` — tracks referee comments, responses, and manuscript changes for peer review.

---

## File Template

```markdown
# Referee Response: [Paper Title]

**Journal:** [journal name]
**Manuscript ID:** [submission ID]
**Submitted:** [YYYY-MM-DD]
**Reports received:** [YYYY-MM-DD]
**Response deadline:** [YYYY-MM-DD or "none specified"]
**Response submitted:** [YYYY-MM-DD or "pending"]

## Decision Summary

**Editor decision:** [Major revision / Minor revision / Reject and resubmit]
**Editor comments:** [Any specific editor guidance beyond referee reports]
**Recommendation floor:** [accept / minor_revision / major_revision / reject / N/A]
**Decision artifacts loaded:** [REFEREE-DECISION.json, REVIEW-LEDGER.json, or "none"]

**Referee count:** [N referees]
**Overall assessment:**

| Referee   | Recommendation                    | Tone                          | Effort Required          |
| --------- | --------------------------------- | ----------------------------- | ------------------------ |
| Referee 1 | [Accept / Minor / Major / Reject] | [Positive / Mixed / Critical] | [Small / Medium / Large] |
| Referee 2 | [Accept / Minor / Major / Reject] | [Positive / Mixed / Critical] | [Small / Medium / Large] |

## Referee 1

### REF-001 (Referee 1, Comment 1.1): [Brief summary of the comment]

**Category:** [Physics concern / Clarity / Missing reference / Technical error / Presentation / Additional calculation requested]
**Priority:** [Must address / Should address / Optional]
**Blocking issue:** [Yes / No / Unknown]
**Decision-artifact context:** [What REVIEW-LEDGER / REFEREE-DECISION says about this issue, or "N/A"]

> [Full quote of referee comment]

**Assessment:** [Is the referee correct? Partially correct? Based on misunderstanding?]

**Response:**

[Draft response text. Be respectful, specific, and thorough. Address the concern directly.]

**Changes made:**

- [Specific change in manuscript: e.g., "Added paragraph in Section III explaining the regularization scheme (page X, lines Y-Z)"]
- [e.g., "New Eq. (14) added showing the explicit cancellation"]
- [e.g., "No change — explained why current treatment is sufficient"]

**New calculations required:** [Yes — describe / No]
**Source phase for new work:** [Phase X or "N/A"]
**Status:** [Not started / In progress / Response drafted / Final]

---

### REF-002 (Referee 1, Comment 1.2): [Brief summary]

**Category:** [category]
**Priority:** [priority]

> [Full quote]

**Assessment:** [assessment]

**Response:**

[Response text]

**Changes made:**

- [changes]

**New calculations required:** [Yes/No]
**Status:** [status]

---

### REF-003 (Referee 1, Comment 1.3): [Brief summary]

[Same structure]

---

## Referee 2

### REF-101 (Referee 2, Comment 2.1): [Brief summary]

**Category:** [category]
**Priority:** [priority]

> [Full quote]

**Assessment:** [assessment]

**Response:**

[Response text]

**Changes made:**

- [changes]

**New calculations required:** [Yes/No]
**Source phase for new work:** [Phase X or "N/A"]
**Status:** [status]

---

### REF-102 (Referee 2, Comment 2.2): [Brief summary]

[Same structure]

---

## Blocking Items From Decision Artifacts

[If `.gpd/review/REVIEW-LEDGER*.json` or `.gpd/review/REFEREE-DECISION*.json` exists, list every blocking issue here. Keep the `REF-*` IDs identical to the referee report.]

| Issue ID | Source Artifact | Blocking Reason | Resolution Plan | Status |
| -------- | --------------- | --------------- | --------------- | ------ |
| REF-001  | REVIEW-LEDGER.json | [Unsupported central claim / unresolved math issue / etc.] | [Narrow claim, revise text, or add evidence] | [Open / In progress / Cleared] |

## New Calculations Summary

[List all additional calculations requested by referees that require new research work:]

| ID   | Issue ID | Requested By | Description                              | Phase | Plan    | Status   |
| ---- | -------- | ------------ | ---------------------------------------- | ----- | ------- | -------- |
| NC-1 | REF-001  | Referee 1    | [e.g., Extend calculation to next order] | [X]   | [XX-YY] | [status] |
| NC-2 | REF-101  | Referee 2    | [e.g., Compare with alternative method]  | [X]   | [XX-YY] | [status] |

## Manuscript Changes Summary

[Consolidated list of all changes to the manuscript, for the cover letter:]

### Major changes

1. [Description of significant addition/revision, referencing which comment prompted it]
2. [Description]

### Minor changes

1. [Typo fix, reference addition, wording clarification]
2. [Description]

### Unchanged (with justification)

1. [What was not changed and why, referencing the comment]

## Response Letter Draft

[Draft of the cover letter to the editor accompanying the revised manuscript:]

---

Dear Editor,

We thank the referees for their careful reading of our manuscript and their constructive comments. We have revised the manuscript to address all points raised. Below we respond to each comment in detail.

[Responses organized by referee, with each comment quoted and addressed. Changes highlighted with "We have added/modified/clarified..." language.]

Sincerely,
[Authors]

---

## Progress

| Item                | Status                             |
| ------------------- | ---------------------------------- |
| Referee 1 responses | [N/M comments addressed]           |
| Referee 2 responses | [N/M comments addressed]           |
| New calculations    | [N/M complete]                     |
| Manuscript revised  | [Not started / In progress / Done] |
| Response letter     | [Not started / Draft / Final]      |
| Resubmission        | [Pending / Submitted]              |
```

<guidelines>

**When to create this file:**

- Immediately upon receiving referee reports
- One file per round of review (create `.gpd/paper/REFEREE_RESPONSE-R2.md` for second round)
- Keep every `REF-*` issue ID exactly aligned with `REFEREE-REPORT*.md`

**Comment categories:**

- `Physics concern` — referee questions the physics content or correctness
- `Clarity` — referee found the presentation unclear or confusing
- `Missing reference` — referee suggests citing additional work
- `Technical error` — referee identifies a specific error (sign, factor, etc.)
- `Presentation` — suggestions about figures, notation, organization
- `Additional calculation requested` — referee wants more results

**Response principles:**

- Thank the referee for every substantive comment (genuine, not perfunctory)
- Address every point — never ignore a comment, even if you disagree
- If the referee is wrong, explain respectfully why, with evidence
- If the referee is right, acknowledge it and describe the fix
- Quote the specific change in the manuscript (page, section, equation number)
- New calculations should be tracked in the roadmap as additional phases

**Priority levels:**

- `Must address` — ignoring this could lead to rejection
- `Should address` — strengthens the paper; editor expects it addressed
- `Optional` — nice to address but paper is acceptable without it

**Integration with GPD workflow:**

- New calculations requested by referees become new phases in ROADMAP.md
- Use /gpd:add-phase or /gpd:insert-phase to add referee-requested work
- Verification of new calculations follows standard GPD verification workflow
- Track new calculations in the "New Calculations Summary" table
- Use `.gpd/review/REVIEW-LEDGER*.json` and `.gpd/review/REFEREE-DECISION*.json` to identify recommendation floors and blocking items, but do not invent new `REF-*` IDs from those JSON files

</guidelines>
