---
load_when:
  - "peer review"
  - "review reliability"
  - "review recovery"
  - "stage failure"
  - "review phase entry"
tier: 2
context_cost: low
---

# Peer Review Phase Reliability

Guidance for reliable execution of the staged peer-review pipeline, covering when the phase triggers, how stages recover from failure, how to distinguish internal from external review, and how review findings feed back into manuscript revisions.

## When Peer Review Triggers

The peer review phase activates **after a complete manuscript draft exists** and **before final PDF packaging and submission**. Specifically:

1. **After draft completion.** The `/gpd:write-paper` workflow produces a manuscript with all sections, equations, figures, and bibliography in place. Peer review does not run on incomplete drafts or outlines.
2. **Before final PDF.** Peer review must complete and its findings must be addressed before the manuscript is packaged for submission (e.g., via `/gpd:arxiv-submission`).
3. **Explicit invocation.** Peer review runs when the user invokes `/gpd:peer-review` or when the write-paper workflow reaches its internal review gate. It is not triggered automatically by file saves or partial edits.

### Precondition Checklist

- Manuscript main file exists under `paper/`, `manuscript/`, or `draft/`
- `.gpd/STATE.md` and `.gpd/ROADMAP.md` are present
- Phase summaries and verification reports are available under `.gpd/phases/`
- `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and reproducibility manifest are present (strict mode)

If any precondition fails, the review preflight blocks entry and reports the missing items.

## Internal Review vs. External Review

The staged peer-review panel is an **automated internal review**. It is not a substitute for external peer review by human referees at a journal.

| Dimension | Internal (automated panel) | External (journal referees) |
|-----------|---------------------------|----------------------------|
| Trigger | Author invokes before submission | Editor assigns after submission |
| Agents | Six staged subagents with fresh context | Human domain experts |
| Scope | Claim extraction, math, physics, literature, significance, adjudication | Full scientific judgment including community context |
| Authority | Advisory; author decides how to respond | Binding; editor decides publication |
| Artifacts | `.gpd/review/` JSON stage reports, referee report | Journal referee reports |
| Rounds | Up to 3 automated rounds | Journal-determined |

Use internal review to catch overclaiming, missing evidence, mathematical errors, and weak physical interpretation **before** submitting to external review. Internal review findings should be treated as a quality gate, not as a publication decision.

## Entry and Exit Criteria

### Entry Criteria

All of the following must hold before the review phase begins:

1. **Manuscript completeness.** All sections referenced in the paper structure are drafted. No placeholder or stub sections remain.
2. **Artifact readiness.** `ARTIFACT-MANIFEST.json` and `BIBLIOGRAPHY-AUDIT.json` exist and pass validation.
3. **Verification coverage.** At least one verification report exists under `.gpd/phases/`.
4. **Preflight pass.** `gpd validate review-preflight peer-review --strict` exits zero.

### Exit Criteria

The review phase is complete when:

1. **All six stages have run.** Stage artifacts exist for reader, literature, math, physics, interestingness, and the final referee decision.
2. **Referee decision is valid.** `REFEREE-DECISION.json` passes schema validation.
3. **Review ledger is valid.** `REVIEW-LEDGER.json` passes schema validation.
4. **Findings are dispositioned.** Every blocking finding has either been addressed in a revision or explicitly acknowledged in an author response.

If the recommendation is `accept` or `minor_revision` with no unresolved blockers, the manuscript may proceed to submission packaging. If the recommendation is `major_revision` or `reject`, the manuscript must return to revision before re-entering peer review.

## Stage Failure Modes and Recovery

Each of the six review stages can fail. The pipeline is **fail-closed**: a failed stage blocks all downstream stages that depend on it.

### Common Failure Modes

| Failure mode | Affected stages | Symptom | Recovery |
|-------------|----------------|---------|----------|
| Subagent spawn failure | Any | Stage artifact not written | Retry the stage once; if it fails again, stop and report |
| Malformed stage output | Any | JSON does not match `StageReviewReport` schema | Validate output, retry stage with explicit schema reminder |
| Missing upstream artifact | Stages 2-6 | Stage cannot read required input | Re-run the failed upstream stage first |
| Manuscript file not found | Stage 1 | Reader cannot locate `.tex` files | Verify manuscript path before retrying |
| Timeout or resource limit | Any | Stage does not complete | Retry once; if persistent, reduce manuscript scope or run stages sequentially |
| Claim index missing | Stages 2-6 | `CLAIMS.json` absent after Stage 1 | Re-run Stage 1 before proceeding |

### Recovery Protocol

1. **Detect.** After each stage completes, validate that the expected output artifact exists and conforms to the `StageReviewReport` JSON schema.
2. **Retry.** Each stage is allowed at most **one retry**. On retry, pass the same inputs and explicit schema guidance.
3. **Escalate.** If a stage fails after one retry, halt the pipeline and report the failure with the stage name, failure mode, and any partial output.
4. **No silent skipping.** Never skip a failed stage and continue to the next. The staged design depends on each stage producing a valid handoff artifact.

### Stage Output Validation

After each stage writes its artifact, confirm:

- The file exists at the expected path
- The file parses as valid JSON
- Required top-level keys are present: `version`, `round`, `stage_id`, `stage_kind`, `summary`, `findings`, `confidence`, `recommendation_ceiling`
- The `stage_id` matches the expected stage
- `findings` is an array (may be empty)
- Each finding has `issue_id`, `severity`, `summary`, and `blocking` fields

If validation fails, treat it as a stage failure and apply the retry protocol above.

## How Review Findings Feed Into Revisions

### Artifact Outputs

The review pipeline produces these actionable artifacts:

1. **Review summary** (`.gpd/REFEREE-REPORT.md` / `.gpd/REFEREE-REPORT.tex`): Human-readable narrative of the panel findings, recommendation, and rationale.
2. **Review ledger** (`.gpd/review/REVIEW-LEDGER.json`): Machine-readable list of all issues with severity, blocking status, affected claims, and required actions.
3. **Referee decision** (`.gpd/review/REFEREE-DECISION.json`): Final recommendation, confidence, blocking issue IDs, and stage artifact references.

### Severity and Prioritization

Findings are classified by severity:

| Severity | Meaning | Blocks acceptance | Typical action |
|----------|---------|-------------------|----------------|
| `critical` | Fundamental flaw in claims, math, or physics | Yes | Must fix before any resubmission |
| `major` | Significant gap in evidence, literature, or interpretation | Yes | Must fix or honestly scope down claims |
| `minor` | Local clarification, missing citation, wording issue | No | Should fix but does not block |
| `suggestion` | Optional improvement for clarity or presentation | No | Author discretion |

### Revision Workflow

1. **Read the review ledger.** Sort findings by severity (critical first, then major, then minor).
2. **Address blocking issues.** Every finding with `"blocking": true` must be resolved or the claims must be narrowed to match the available evidence.
3. **Write author response.** Document how each finding was addressed in `.gpd/AUTHOR-RESPONSE.md` (or `-R2.md` / `-R3.md` for subsequent rounds).
4. **Re-enter review.** After revisions, re-run `/gpd:peer-review` for the next round. The pipeline detects prior reports and author responses to increment the round number automatically.
5. **Converge.** The pipeline supports up to 3 review rounds. If the manuscript has not converged to `accept` or `minor_revision` after 3 rounds, consider restructuring the central contribution.

### Mapping Findings to Manuscript Changes

Each finding in the review ledger includes:

- `claim_ids`: Which claims are affected
- `manuscript_locations`: Where in the manuscript the issue appears
- `required_action`: What must change
- `evidence_refs`: Supporting evidence for the finding

Use these fields to make targeted, traceable revisions rather than broad rewrites. The author response should reference the `issue_id` for each finding and state whether it was fixed, partially addressed, or disputed with justification.
