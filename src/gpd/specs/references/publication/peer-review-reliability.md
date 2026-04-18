---
load_when:
  - "peer review"
  - "review reliability"
  - "review recovery"
  - "stage failure"
  - "review phase entry"
type: peer-review-reliability
tier: 2
context_cost: low
---

# Peer Review Phase Reliability

Guidance for reliable execution of the staged peer-review pipeline, covering when the phase triggers, how stages recover from failure, how to distinguish internal from external review, and how review findings feed back into manuscript revisions.

This is the canonical reliability reference for the peer-review skill surface. Follow the path and round-suffix conventions here when the workflow, report, and response artifacts need a stable source of truth.

## When Peer Review Triggers

The peer review phase activates **after a complete manuscript draft exists** and **before final PDF packaging and submission**. Specifically:

1. **After draft completion.** The `gpd:write-paper` workflow produces a manuscript with all sections, equations, figures, and bibliography in place. Peer review does not run on incomplete drafts or outlines.
2. **Before final PDF.** Peer review must complete and its findings must be addressed before the manuscript is packaged for submission (e.g., via `gpd:arxiv-submission`).
3. **Explicit invocation.** Peer review runs when the user invokes `gpd:peer-review` or when the write-paper workflow reaches its internal review gate. It is not triggered automatically by file saves or partial edits.

### Precondition Checklist

- Either the active manuscript exists under `paper/`, `manuscript/`, or `draft/`, or the user supplies one explicit `.tex`, `.md`, `.txt`, `.pdf`, `.docx`, `.csv`, `.tsv`, or `.xlsx` review target
- `GPD/STATE.md` and `GPD/ROADMAP.md` are present when reviewing the current GPD project manuscript
- Phase summaries and verification reports are available under `GPD/phases/` when reviewing the current GPD project manuscript
- `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and reproducibility manifest are required in strict project-backed mode and additive when present for explicit external artifact review
- Strict preflight semantic gates pass for any manuscript-root publication artifacts that are present

If any precondition fails, the review preflight blocks entry and reports the missing items.

## Internal Review vs. External Review

The staged peer-review panel is an **automated internal review**. It is not a substitute for external peer review by human referees at a journal.

| Dimension | Internal (automated panel) | External (journal referees) |
|-----------|---------------------------|----------------------------|
| Trigger | Author invokes before submission | Editor assigns after submission |
| Agents | Six staged subagents with fresh context | Human domain experts |
| Scope | Claim extraction, math, physics, literature, significance, adjudication | Full scientific judgment including community context |
| Authority | Advisory; author decides how to respond | Binding; editor decides publication |
| Artifacts | `GPD/review/` JSON stage reports, `GPD/REFEREE-REPORT{round_suffix}.md` / `.tex` | Journal referee reports |
| Rounds | Up to 3 automated rounds | Journal-determined |

Use internal review to catch overclaiming, missing evidence, mathematical errors, and weak physical interpretation **before** submitting to external review. Internal review findings should be treated as a quality gate, not as a publication decision.

## Entry and Exit Criteria

### Entry Criteria

All of the following must hold before the review phase begins:

1. **Manuscript completeness.** All sections referenced in the paper structure are drafted. No placeholder or stub sections remain.
2. **Artifact readiness.** `ARTIFACT-MANIFEST.json` and `BIBLIOGRAPHY-AUDIT.json` exist and pass validation. In strict mode the bibliography audit must also clear `bibliography_audit_clean`, and the reproducibility manifest must clear `reproducibility_ready`.
3. **Verification coverage.** At least one verification report exists under `GPD/phases/`.
4. **Preflight pass.** `gpd validate review-preflight peer-review "$REVIEW_TARGET" --strict` exits zero.

### Exit Criteria

The review phase is complete when:

1. **All six stages have run.** Stage artifacts exist for reader, literature, math, physics, interestingness, and the final referee decision.
2. **Auxiliary proof critique is complete.** If theorem-bearing claims are present, `GPD/review/PROOF-REDTEAM{round_suffix}.md` exists, is authored by `gpd-check-proof`, binds to the active manuscript snapshot, contains the canonical proof-audit sections, and reports `status: passed`.
3. **Math proof-audit coverage is complete.** If `CLAIMS{round_suffix}.json` contains theorem-bearing claims in the claim record, the matching `STAGE-math{round_suffix}.json` contains one `proof_audits[]` entry per reviewed theorem-bearing claim, and central theorem-bearing claims are not left at `alignment_status: not_applicable`.
4. **Referee decision is valid.** `GPD/review/REFEREE-DECISION{round_suffix}.json` passes `gpd validate referee-decision ... --strict --ledger ...`, including non-empty `manuscript_path` alignment with the review ledger and stage artifacts.
5. **Review ledger is valid.** `GPD/review/REVIEW-LEDGER{round_suffix}.json` passes `gpd validate review-ledger ...`, including a non-empty `manuscript_path`.
6. **Findings are dispositioned.** Every blocking finding has either been addressed in a revision or explicitly acknowledged in an author response.

If the recommendation is `accept` or `minor_revision` with no unresolved blockers, the manuscript may proceed to submission packaging. If the recommendation is `major_revision` or `reject`, the manuscript must return to revision before re-entering peer review.
When strict submission preflight sees `GPD/review/REVIEW-LEDGER*.json` and `GPD/review/REFEREE-DECISION*.json`, it treats the latest round-specific pair as authoritative and blocks packaging unless that condition is satisfied for the active manuscript.

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
| Claim index missing | Stages 2-6 | `CLAIMS{round_suffix}.json` absent after Stage 1 | Re-run Stage 1 before proceeding |
| Theorem-proof audit missing or stale | Stages 3, 6 | The claim record contains theorem-bearing claims but `STAGE-math{round_suffix}.json` omits `proof_audits[]` for them, `PROOF-REDTEAM{round_suffix}.md` is missing or malformed, or central audits use `not_applicable` / leave explicit parameters uncovered | Re-run `gpd-check-proof` and Stage 3 with an explicit theorem-to-proof coverage checklist before allowing Stage 6 to adjudicate |

### Recovery Protocol

1. **Detect.** After each stage completes, validate that the expected output artifact exists and conforms to the `StageReviewReport` JSON schema.
2. **Retry.** Each stage is allowed at most **one retry**. On retry, pass the same inputs and explicit schema guidance.
3. **Escalate.** If a stage fails after one retry, halt the pipeline and report the failure with the stage name, failure mode, and any partial output.
4. **No silent skipping.** Never skip a failed stage and continue to the next. The staged design depends on each stage producing a valid handoff artifact.

### Stage Output Validation

After each stage writes its artifact, confirm:

- The file exists at the expected path
- The file parses as valid JSON
- The built-in validators accept the matching artifact type:
  - `gpd validate review-claim-index GPD/review/CLAIMS{round_suffix}.json`
  - `gpd validate review-stage-report GPD/review/STAGE-<stage_id>{round_suffix}.json`
  - `gpd validate review-ledger GPD/review/REVIEW-LEDGER{round_suffix}.json`
  - `gpd validate referee-decision GPD/review/REFEREE-DECISION{round_suffix}.json --strict --ledger GPD/review/REVIEW-LEDGER{round_suffix}.json`
- Do not reimplement the schema checks manually in the workflow prose. The validators are the source of truth for required keys and cross-artifact consistency.
- A blank `manuscript_path` in the review ledger or referee decision is a contract failure, not a recoverable omission.
- For theorem-bearing claims, Stage 1 should preserve explicit theorem hypotheses and parameters in `CLAIMS{round_suffix}.json`, and Stage 3 should preserve the corresponding theorem-to-proof audit in `proof_audits[]`. The runtime determines theorem-bearing coverage from the claim record itself, not from a single proxy field. If that chain breaks, treat it as a stage failure rather than proceeding with a stale or inferred review.

If validation fails, treat it as a stage failure and apply the retry protocol above.

## How Review Findings Feed Into Revisions

### Artifact Outputs

The review pipeline produces these actionable artifacts:

1. **Review summary** (`GPD/REFEREE-REPORT{round_suffix}.md` / `.tex`): Human-readable narrative of the panel findings, recommendation, and rationale.
2. **Review ledger** (`GPD/review/REVIEW-LEDGER{round_suffix}.json`): Machine-readable list of all issues with severity, blocking status, affected claims, and required actions.
3. **Referee decision** (`GPD/review/REFEREE-DECISION{round_suffix}.json`): Final recommendation, confidence, blocking issue IDs, and stage artifact references.

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
3. **Treat uncovered theorem assumptions or parameters as blocking until resolved.** If a theorem statement quantifies over a parameter or names a hypothesis that the proof never uses, the manuscript must be corrected, narrowed, or explicitly re-proved before the next round.
4. **Write author response.** Document how each finding was addressed in `GPD/AUTHOR-RESPONSE{round_suffix}.md` (or `-R2.md` / `-R3.md` for subsequent rounds).
5. **Re-enter review.** After revisions, re-run `gpd:peer-review` for the next round. The pipeline detects prior reports and author responses to increment the round number automatically.
6. **Converge.** The pipeline supports up to 3 review rounds. If the manuscript has not converged to `accept` or `minor_revision` after 3 rounds, consider restructuring the central contribution.

### Mapping Findings to Manuscript Changes

Each finding in the review ledger includes:

- `claim_ids`: Which claims are affected
- `manuscript_locations`: Where in the manuscript the issue appears
- `required_action`: What must change
- `evidence_refs`: Supporting evidence for the finding

Use these fields to make targeted, traceable revisions rather than broad rewrites. The author response should reference the `issue_id` for each finding and state whether it was fixed, partially addressed, or disputed with justification.
