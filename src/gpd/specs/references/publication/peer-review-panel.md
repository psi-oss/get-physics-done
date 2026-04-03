---
load_when:
  - "peer review"
  - "panel review"
  - "referee adjudication"
  - "review stage artifact"
  - "journal fit"
tier: 2
context_cost: medium
---

# Peer Review Panel Protocol

Use this protocol when reviewing a manuscript through the staged peer-review pipeline. The objective is to prevent one generalist reviewer from rubber-stamping technically competent but physically thin or overclaimed work.

## Core Principle

Peer review is not one pass. It is a sequence of skeptical checks with fresh context:

1. Read the manuscript end-to-end and identify what it actually claims.
2. Compare those claims with the literature and the paper's own novelty framing.
3. Check mathematical correctness and internal consistency.
4. Check whether the physical assumptions and interpretations are reasonable.
5. Check whether the result is interesting enough for the claimed venue.
6. Adjudicate across all evidence and decide.

No stage is allowed to silently substitute for another. A mathematically coherent paper can still deserve major revision or rejection if its physical story is weak, its novelty collapses against prior work, or its significance is overstated.

## Six-Agent Panel

### Stage 1. Manuscript Read

Agent: `gpd-review-reader`

Goal:
- Read the whole manuscript once.
- Extract the main claim, the supporting subclaims, and the paper's logic.
- Flag narrative jumps, overclaims, and any places where the conclusions outrun the evidence.

Output:
- `GPD/review/CLAIMS{round_suffix}.json`
- `GPD/review/STAGE-reader{round_suffix}.json`

### Stage 2. Literature Context

Agent: `gpd-review-literature`

Goal:
- Evaluate novelty and prior-work positioning using the manuscript, bibliography, and targeted literature search.
- Identify missing foundational work, unacknowledged overlap, and inflated novelty claims.

Output:
- `GPD/review/STAGE-literature{round_suffix}.json`

### Stage 3. Mathematical Soundness

Agent: `gpd-review-math`

Goal:
- Check key equations, derivation integrity, theorem-to-proof alignment, self-consistency, limits, sign conventions, and verification coverage.

Output:
- `GPD/review/STAGE-math{round_suffix}.json`

### Auxiliary Proof Critique Gate

Agent: `gpd-check-proof`

Goal:
- When theorem-bearing claims are present, run a separate adversarial proof critique instead of overloading the math stage.
- Audit theorem-to-proof alignment claim by claim: named parameters, stated hypotheses, quantifiers/domains, and conclusion clauses.
- Try to break the proof by forcing narrower-case, dropped-parameter, or hidden-assumption failures into the open before final adjudication.

Output:
- `GPD/review/PROOF-REDTEAM{round_suffix}.md`

### Stage 4. Physical Soundness

Agent: `gpd-review-physics`

Goal:
- Check regime of validity, physical assumptions, interpretation, connection between math and physics, and whether the claimed physical conclusions are actually supported.

Output:
- `GPD/review/STAGE-physics{round_suffix}.json`

### Stage 5. Significance And Venue Fit

Agent: `gpd-review-significance`

Goal:
- Judge interestingness, scientific value, and venue fit after seeing the reading, literature, and physics outputs.
- Be willing to conclude that the paper is mathematically respectable but scientifically weak.

Output:
- `GPD/review/STAGE-interestingness{round_suffix}.json`

### Stage 6. Final Adjudication

Agent: `gpd-referee`

Goal:
- Read all stage artifacts.
- Spot-check the manuscript where the stage artifacts disagree or feel under-evidenced.
- Issue the final recommendation.

Output:
- `GPD/review/REVIEW-LEDGER{round_suffix}.json`
- `GPD/review/REFEREE-DECISION{round_suffix}.json`
- `GPD/REFEREE-REPORT{round_suffix}.md`
- `GPD/REFEREE-REPORT{round_suffix}.tex`
- `GPD/CONSISTENCY-REPORT.md` when applicable

## Fresh-Context Rule

Every stage must be executed in a fresh subagent context. The orchestrator should pass only:

- the manuscript and directly relevant support files
- the immediately needed prior stage artifacts
- the target journal and scope

Do not pass the entire orchestration transcript into later stages. The stage artifacts are the handoff.

## Stage Dependency Graph

- Stage 1 runs first and is mandatory.
- Stages 2 and 3 may run in parallel after Stage 1.
- The auxiliary `gpd-check-proof` pass may run in parallel with Stages 2 and 3 when theorem-bearing claims are present.
- Stage 4 should read Stage 1 and Stage 3, and Stage 2 when literature overlap affects physical interpretation.
- Stage 5 should read Stages 1, 2, and 4.
- Stage 6 reads all prior stage artifacts and spot-checks the manuscript as needed. When theorem-bearing claims exist, `PROOF-REDTEAM{round_suffix}.md` is mandatory Stage 6 input rather than optional context.
- For theorem-bearing review, a missing, invalid, or non-passing `PROOF-REDTEAM{round_suffix}.md` artifact is itself a blocking stage-integrity failure.

## Stage Artifact Contract

Every stage report should be compact and machine-readable, matching the staged-review artifact models:

```json
{
  "version": 1,
  "round": 1,
  "stage_id": "reader | literature | math | physics | interestingness",
  "stage_kind": "reader | literature | math | physics | interestingness",
  "manuscript_path": "paper/topic_stem.tex",
  "manuscript_sha256": "<sha256>",
  "claims_reviewed": ["CLM-001"],
  "summary": "One paragraph synthesis of the stage result",
  "strengths": ["Specific strength"],
  "findings": [
    {
      "issue_id": "REF-001",
      "claim_ids": ["CLM-001"],
      "severity": "critical | major | minor | suggestion",
      "summary": "What is wrong",
      "rationale": "Why it is wrong",
      "evidence_refs": ["paper/topic_stem.tex#Conclusion"],
      "manuscript_locations": ["paper/topic_stem.tex:42"],
      "support_status": "supported | partially_supported | unsupported | unclear",
      "blocking": true,
      "required_action": "What must change"
    }
  ],
  "proof_audits": [
    {
      "claim_id": "CLM-001",
      "theorem_assumptions_checked": ["N is compact"],
      "theorem_parameters_checked": ["r_0"],
      "proof_locations": ["paper/topic_stem.tex:120"],
      "uncovered_assumptions": [],
      "uncovered_parameters": ["r_0"],
      "coverage_gaps": ["Proof specializes to the centered case and never reinstates r_0."],
      "alignment_status": "misaligned",
      "notes": "The proof establishes the r_0 = 0 case only."
    }
  ],
  "confidence": "high | medium | low",
  "recommendation_ceiling": "accept | minor_revision | major_revision | reject"
}
```

Additionally:

- Stage 1 must also emit `CLAIMS{round_suffix}.json` as a compact `ClaimIndex`.
- Strict-stage specialist artifacts must use canonical names `STAGE-reader`, `STAGE-literature`, `STAGE-math`, `STAGE-physics`, `STAGE-interestingness`.
- In strict mode, specialist stage filenames must match `STAGE-(reader|literature|math|physics|interestingness)(-R<round>)?.json`, and all five must share the same optional `-R<round>` suffix.
- In strict mode, any additional noncanonical `stage_artifacts` entry fails validation rather than being ignored.
- The final adjudicator must emit `REVIEW-LEDGER{round_suffix}.json` and `REFEREE-DECISION{round_suffix}.json` (empty suffix on the first round).
- The artifact should stay compact. It is a decision handoff, not a second manuscript.
- `StageReviewReport`, nested `ReviewFinding`, and nested `ProofAuditRecord` entries use a closed schema; do not invent extra keys beyond those shown here.
- `manuscript_path` must be non-empty and must name the exact manuscript snapshot under review.
- `claims_reviewed` and every nested `claim_ids` list must use Stage 1 `CLM-...` claim IDs, not free-form labels.
- Every nested `proof_audits[].claim_id` must reuse a Stage 1 `CLM-...` claim ID and must also appear in `claims_reviewed`.
- In Stage 3, `proof_audits[]` coverage is exact rather than best-effort: emit exactly one proof audit for each reviewed theorem-bearing claim, emit none for unreviewed claims, and do not repeat `claim_id` values.
- `proof_audits[].alignment_status` must be one of: `aligned`, `partially_aligned`, `misaligned`, `not_applicable`.
- For theorem-bearing claims, `proof_audits[].alignment_status` must never be `not_applicable`; theorem-bearing audits must resolve to `aligned`, `partially_aligned`, or `misaligned`.
- `alignment_status: aligned` is strict: it requires non-empty `proof_locations`, at least one checked theorem assumption or checked parameter, and empty `uncovered_assumptions`, `uncovered_parameters`, and `coverage_gaps`.
- For stages other than math, keep `proof_audits` as an empty array unless the workflow explicitly asks that stage to perform a theorem-proof audit.
- `manuscript_sha256` must be the lowercase 64-hex digest for the exact manuscript snapshot under review.
- The filename `STAGE-<stage_id>{round_suffix}.json` and the JSON `round` field must agree: unsuffixed first-round artifacts use `round: 1`, and `-R<round>` filenames must use that same integer in `round`.
- For Stages 2-5, `manuscript_path` and `manuscript_sha256` must exactly match the sibling `CLAIMS{round_suffix}.json` claim index for the same round.
- In Stage 3, every reviewed theorem-bearing Stage 1 claim must receive exactly one `proof_audits[]` entry. Treat theorem-bearing status from the full Stage 1 claim record, not only from non-empty `theorem_assumptions` / `theorem_parameters` arrays: theorem-style `claim_kind` values and theorem-like statement text still require proof audits even when extraction is incomplete. Missing proof audits, extra audits for unreviewed claims, or repeated `claim_id` values are contract failures, not soft omissions.
- In Stage 3, any uncovered theorem assumption, uncovered theorem parameter, or explicit theorem-to-proof mismatch caps `recommendation_ceiling` at `major_revision` or `reject`.
- Every nested `ReviewFinding.issue_id` must match `REF-[A-Za-z0-9][A-Za-z0-9_-]*`.

The runtime artifact path is `CLAIMS{round_suffix}.json`; use the same compact schema on later rounds, preserving the shared optional `-R<round>` suffix across all staged-review artifacts.

Stage 1 `CLAIMS{round_suffix}.json` must follow this compact `ClaimIndex` shape:

```json
{
  "version": 1,
  "manuscript_path": "paper/topic_stem.tex",
  "manuscript_sha256": "<sha256>",
  "claims": [
    {
      "claim_id": "CLM-001",
      "claim_type": "main_result | novelty | significance | physical_interpretation | generality | method",
      "claim_kind": "theorem | lemma | corollary | proposition | claim | other",
      "text": "Exact manuscript claim text or faithful paraphrase",
      "artifact_path": "paper/topic_stem.tex",
      "section": "Conclusion",
      "equation_refs": ["paper/topic_stem.tex#eq:main"],
      "figure_refs": ["paper/topic_stem.tex#fig:main"],
      "supporting_artifacts": ["paper/figures/main-result.pdf"],
      "theorem_assumptions": ["N is compact"],
      "theorem_parameters": ["r_0"]
    }
  ]
}
```

- `manuscript_path` and `manuscript_sha256` are required `ClaimIndex` metadata, not optional bookkeeping.
- `manuscript_path` must be non-empty and must name the exact manuscript snapshot under review.
- `manuscript_sha256` must be the lowercase 64-hex digest for the exact manuscript snapshot under review.
- `ClaimIndex` and every nested `ClaimRecord` use a closed schema; do not invent extra keys beyond those shown here.
- `claim_id` must match `CLM-[A-Za-z0-9][A-Za-z0-9_-]*`.
- `claim_kind` must use exactly: `theorem`, `lemma`, `corollary`, `proposition`, `claim`, `other`.
- Keep `section` as an empty string and `equation_refs`, `figure_refs`, `supporting_artifacts` as empty lists when unavailable.
- Keep `theorem_assumptions` and `theorem_parameters` as arrays even when unavailable.
- When a claim is theorem-bearing, set `claim_kind` explicitly instead of leaving it at `other`; `theorem_assumptions` must enumerate the theorem's explicit hypotheses or regime assumptions, and `theorem_parameters` must enumerate the free target parameters or quantified variables the proof must cover.
- Do not silently drop statement parameters just because the derivation later centers or normalizes the algebra. If the statement quantifies over `r_0`, index `r_0`.
- Do not invent locations, equations, figures, or supporting artifacts just to populate the schema.

The final adjudicator JSON artifacts must follow these canonical schemas:

- @{GPD_INSTALL_DIR}/templates/paper/review-ledger-schema.md
- @{GPD_INSTALL_DIR}/templates/paper/referee-decision-schema.md

Minimal final artifact shapes:

```json
{
  "version": 1,
  "round": 1,
  "manuscript_path": "paper/topic_stem.tex",
  "issues": [
    {
      "issue_id": "REF-001",
      "opened_by_stage": "physics",
      "severity": "major",
      "blocking": true,
      "claim_ids": ["CLM-001"],
      "summary": "What remains wrong",
      "required_action": "What must change",
      "status": "open"
    }
  ]
}
```

```json
{
  "manuscript_path": "paper/topic_stem.tex",
  "target_journal": "jhep",
  "final_recommendation": "major_revision",
  "final_confidence": "medium",
  "stage_artifacts": [
    "GPD/review/STAGE-reader{round_suffix}.json",
    "GPD/review/STAGE-literature{round_suffix}.json",
    "GPD/review/STAGE-math{round_suffix}.json",
    "GPD/review/STAGE-physics{round_suffix}.json",
    "GPD/review/STAGE-interestingness{round_suffix}.json"
  ],
  "blocking_issue_ids": ["REF-001"]
}
```

Validate both files before trusting the final recommendation:

```bash
gpd validate review-ledger GPD/review/REVIEW-LEDGER{round_suffix}.json
gpd validate referee-decision GPD/review/REFEREE-DECISION{round_suffix}.json --strict --ledger GPD/review/REVIEW-LEDGER{round_suffix}.json
```

## Recommendation Guardrails For The Final Referee

### `accept`

Only if all are true:
- no unresolved blockers
- no major concerns in math, physics, literature, or significance
- the claims are proportionate to the evidence
- every central theorem-bearing claim has a Stage 3 `proof_audits[]` entry with `alignment_status: aligned`
- the venue-fit bar is met

### `minor_revision`

Only if all are true:
- the core contribution is sound
- novelty/significance are at least adequate for the target venue
- central theorem-bearing claims still have complete proof-audit coverage and no theorem-to-proof alignment gaps
- remaining issues are local clarifications, citation additions, wording fixes, or presentation polish

Minor revision is not allowed when the paper's central physical story is unsupported, when a theorem statement outruns what its proof actually establishes, or when the title/abstract/conclusions materially overclaim what the analysis shows.

### `major_revision`

Use when:
- the core technical result may survive, but the paper needs substantial reframing, new checks, stronger literature comparison, or narrower claims
- the math is mostly sound but the physical interpretation is weak or overstated
- the math stage finds missing proof audits, uncovered theorem assumptions, or uncovered theorem parameters that look fixable with a real revision
- the paper is potentially publishable only after substantial restructuring

### `reject`

Use when any of the following is true:
- the main claim depends on unsupported physical reasoning
- a central theorem-bearing claim is not actually proved as stated and the gap is not repairable by honest narrowing alone
- the novelty claim collapses against prior work
- the paper is mathematically consistent but scientifically uninteresting for the claimed venue and cannot be repaired without changing the central claim
- the authors make repeated unfounded connections between formal manipulations and physics
- the work lacks sufficient scientific quality or significance for the venue

Reject is not reserved for algebraic failure. A physically unconvincing or scientifically minor paper can deserve rejection even when the equations are internally consistent.

### Required Claim-Evidence Audit

The final referee must preserve a compact claim-evidence table, at minimum:

`claim | claim_type | manuscript_location | direct_evidence | support_status | overclaim_severity | required_fix`

Unsupported central physical-interpretation or significance claims are never compatible with `minor_revision`.

## Claim-Discipline Rules

The final referee must explicitly test these:

- Does the title promise more than the paper delivers?
- Does the abstract imply physical consequences not established in the body?
- Do the conclusions convert formal analogy into physical evidence without justification?
- Does the paper use suggestive language ("connection", "implication", "relevance", "prediction") without adequate support?

If yes, treat claim inflation as publication-relevant, not stylistic.

## Journal Calibration

Use official venue expectations as a hard calibration input.

### PRL-style standard

APS describes PRL as publishing results with significant new advances and broad interest across physics. A paper that is merely technically competent inside a narrow corner of the field should not receive a soft-positive recommendation for PRL.

### JHEP-style standard

JHEP describes itself as seeking significant new material of high scientific quality and broad interest within high-energy physics. Incremental or physically thin manuscripts should not be waved through as minor revisions just because the formal manipulations are consistent.

### General reviewer standard

Springer reviewer guidance emphasizes originality, significance, and whether the conclusions are supported by the results. The final recommendation must check all three explicitly.
