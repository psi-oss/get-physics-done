---
load_when:
  - "publication round artifacts"
  - "referee response"
  - "revision round"
  - "round suffix"
type: publication-review-round-artifacts
tier: 2
context_cost: low
---

# Publication Review Round Artifacts

Canonical round-suffix and sibling-artifact contract for publication review rounds.

## Suffix Rule

- Round 1 uses `round_suffix=""`.
- Round `N` for `N >= 2` uses `round_suffix="-R{N}"`.
- Keep one suffix shared across every artifact emitted for that review or response round.

## Required Artifact Family

- Stage-review artifacts: `GPD/review/CLAIMS{round_suffix}.json`, `GPD/review/STAGE-reader{round_suffix}.json`, `GPD/review/STAGE-literature{round_suffix}.json`, `GPD/review/STAGE-math{round_suffix}.json`, `GPD/review/STAGE-physics{round_suffix}.json`, and `GPD/review/STAGE-interestingness{round_suffix}.json`.
- Final adjudication artifacts: `GPD/review/REVIEW-LEDGER{round_suffix}.json`, `GPD/review/REFEREE-DECISION{round_suffix}.json`, `GPD/REFEREE-REPORT{round_suffix}.md`, and `GPD/REFEREE-REPORT{round_suffix}.tex`.
- Response artifacts: `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/review/REFEREE_RESPONSE{round_suffix}.md`.
- Proof artifact when theorem review requires it: `GPD/review/PROOF-REDTEAM{round_suffix}.md`.

## Ownership Boundary

- GPD-authored auxiliary outputs for a review round live under `GPD/` or `GPD/review/` exactly as listed above.
- These artifacts are siblings of, not replacements for, manuscript-local artifacts such as `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, `reproducibility-manifest.json`, or the compiled manuscript under the resolved manuscript root.
- Do not copy manuscript-local artifacts into `GPD/` to satisfy strict review or submission gates.

## Consistency Rules

- `GPD/REFEREE-REPORT{round_suffix}.md` is the canonical source for round-scoped `REF-*` issue IDs.
- Do not mix suffixes from different rounds in one workflow run, ledger pair, or response set.
- Downstream response or packaging work stays fail-closed until the latest round's required artifact family is complete for the active manuscript.
