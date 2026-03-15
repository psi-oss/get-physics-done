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
- `.gpd/review/CLAIMS.json`
- `.gpd/review/STAGE-reader.json`

### Stage 2. Literature Context

Agent: `gpd-review-literature`

Goal:
- Evaluate novelty and prior-work positioning using the manuscript, bibliography, and targeted literature search.
- Identify missing foundational work, unacknowledged overlap, and inflated novelty claims.

Output:
- `.gpd/review/STAGE-literature.json`

### Stage 3. Mathematical Soundness

Agent: `gpd-review-math`

Goal:
- Check key equations, derivation integrity, self-consistency, limits, sign conventions, and verification coverage.

Output:
- `.gpd/review/STAGE-math.json`

### Stage 4. Physical Soundness

Agent: `gpd-review-physics`

Goal:
- Check regime of validity, physical assumptions, interpretation, connection between math and physics, and whether the claimed physical conclusions are actually supported.

Output:
- `.gpd/review/STAGE-physics.json`

### Stage 5. Significance And Venue Fit

Agent: `gpd-review-significance`

Goal:
- Judge interestingness, scientific value, and venue fit after seeing the reading, literature, and physics outputs.
- Be willing to conclude that the paper is mathematically respectable but scientifically weak.

Output:
- `.gpd/review/STAGE-interestingness.json`

### Stage 6. Final Adjudication

Agent: `gpd-referee`

Goal:
- Read all stage artifacts.
- Spot-check the manuscript where the stage artifacts disagree or feel under-evidenced.
- Issue the final recommendation.

Output:
- `.gpd/review/REVIEW-LEDGER{round_suffix}.json`
- `.gpd/review/REFEREE-DECISION{round_suffix}.json`
- `.gpd/REFEREE-REPORT.md`
- `.gpd/REFEREE-REPORT.tex`
- `.gpd/CONSISTENCY-REPORT.md` when applicable

## Fresh-Context Rule

Every stage must be executed in a fresh subagent context. The orchestrator should pass only:

- the manuscript and directly relevant support files
- the immediately needed prior stage artifacts
- the target journal and scope

Do not pass the entire orchestration transcript into later stages. The stage artifacts are the handoff.

## Stage Dependency Graph

- Stage 1 runs first and is mandatory.
- Stages 2 and 3 may run in parallel after Stage 1.
- Stage 4 should read Stage 1 and Stage 3, and Stage 2 when literature overlap affects physical interpretation.
- Stage 5 should read Stages 1, 2, and 4.
- Stage 6 reads all prior stage artifacts and spot-checks the manuscript as needed.

## Stage Artifact Contract

Every stage report should be compact and machine-readable, matching the staged-review artifact models:

```json
{
  "version": 1,
  "round": 1,
  "stage_id": "reader | literature | math | physics | interestingness",
  "stage_kind": "reader | literature | math | physics | interestingness",
  "manuscript_path": "paper/main.tex",
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
      "evidence_refs": ["paper/main.tex#Conclusion"],
      "manuscript_locations": ["paper/main.tex:42"],
      "support_status": "supported | partially_supported | unsupported | unclear",
      "blocking": true,
      "required_action": "What must change"
    }
  ],
  "confidence": "high | medium | low",
  "recommendation_ceiling": "accept | minor_revision | major_revision | reject"
}
```

Additionally:

- Stage 1 must also emit `CLAIMS.json` as a compact `ClaimIndex`.
- The final adjudicator must emit `REVIEW-LEDGER{round_suffix}.json` and `REFEREE-DECISION{round_suffix}.json` (empty suffix on the first round).
- The artifact should stay compact. It is a decision handoff, not a second manuscript.

The final adjudicator JSON artifacts must follow these canonical schemas:

- @{GPD_INSTALL_DIR}/templates/paper/review-ledger-schema.md
- @{GPD_INSTALL_DIR}/templates/paper/referee-decision-schema.md

Minimal final artifact shapes:

```json
{
  "version": 1,
  "round": 1,
  "manuscript_path": "paper/main.tex",
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
  "manuscript_path": "paper/main.tex",
  "target_journal": "jhep",
  "final_recommendation": "major_revision",
  "final_confidence": "medium",
  "stage_artifacts": [
    ".gpd/review/STAGE-reader{round_suffix}.json",
    ".gpd/review/STAGE-literature{round_suffix}.json",
    ".gpd/review/STAGE-math{round_suffix}.json",
    ".gpd/review/STAGE-physics{round_suffix}.json",
    ".gpd/review/STAGE-interestingness{round_suffix}.json"
  ],
  "blocking_issue_ids": ["REF-001"]
}
```

Validate both files before trusting the final recommendation:

```bash
gpd validate review-ledger .gpd/review/REVIEW-LEDGER{round_suffix}.json
gpd validate referee-decision .gpd/review/REFEREE-DECISION{round_suffix}.json --strict --ledger .gpd/review/REVIEW-LEDGER{round_suffix}.json
```

## Recommendation Guardrails For The Final Referee

### `accept`

Only if all are true:
- no unresolved blockers
- no major concerns in math, physics, literature, or significance
- the claims are proportionate to the evidence
- the venue-fit bar is met

### `minor_revision`

Only if all are true:
- the core contribution is sound
- novelty/significance are at least adequate for the target venue
- remaining issues are local clarifications, citation additions, wording fixes, or presentation polish

Minor revision is not allowed when the paper's central physical story is unsupported or when the title/abstract/conclusions materially overclaim what the analysis shows.

### `major_revision`

Use when:
- the core technical result may survive, but the paper needs substantial reframing, new checks, stronger literature comparison, or narrower claims
- the math is mostly sound but the physical interpretation is weak or overstated
- the paper is potentially publishable only after substantial restructuring

### `reject`

Use when any of the following is true:
- the main claim depends on unsupported physical reasoning
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
