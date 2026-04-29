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

The explicit `GPD/...` paths below are the default project-backed canonical layout. When centralized preflight exposes `selected_publication_root` and `selected_review_root`, use those selected roots instead of hard-coded global paths.

- Stage-review artifacts: `${selected_review_root}/CLAIMS{round_suffix}.json`, `${selected_review_root}/STAGE-reader{round_suffix}.json`, `${selected_review_root}/STAGE-literature{round_suffix}.json`, `${selected_review_root}/STAGE-math{round_suffix}.json`, `${selected_review_root}/STAGE-physics{round_suffix}.json`, and `${selected_review_root}/STAGE-interestingness{round_suffix}.json`.
- Final adjudication artifacts: `${selected_review_root}/REVIEW-LEDGER{round_suffix}.json`, `${selected_review_root}/REFEREE-DECISION{round_suffix}.json`, `${selected_publication_root}/REFEREE-REPORT{round_suffix}.md`, and `${selected_publication_root}/REFEREE-REPORT{round_suffix}.tex`.
- Response artifacts: `${selected_publication_root}/AUTHOR-RESPONSE{round_suffix}.md` and `${selected_review_root}/REFEREE_RESPONSE{round_suffix}.md`.
- Proof artifact when theorem review requires it: `${selected_review_root}/PROOF-REDTEAM{round_suffix}.md`.

## Ownership Boundary

- In default project-backed mode, centralized preflight resolves `selected_publication_root=GPD` and `selected_review_root=GPD/review`.
- For a managed or explicit external publication subject, the same round-artifact family binds under the subject-owned publication root `GPD/publication/{subject_slug}` and review root `GPD/publication/{subject_slug}/review` while preserving the same filenames, shared `round_suffix`, and sibling relationships.
- Do not write a managed-subject review bundle to global `GPD/review` as a fallback or duplicate copy.
- That subject-owned continuation path does not by itself promise a full relocation of manuscript drafts, manuscript-root manifests, or every publication artifact out of the global project tree.
- These artifacts are siblings of, not replacements for, manuscript-local artifacts such as `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, `reproducibility-manifest.json`, or the compiled manuscript under the resolved manuscript root.
- Do not copy manuscript-local artifacts into `GPD/` to satisfy strict review or submission gates.

## Consistency Rules

- `${selected_publication_root}/REFEREE-REPORT{round_suffix}.md` is the canonical source for round-scoped `REF-*` issue IDs.
- Do not mix suffixes from different rounds in one workflow run, ledger pair, or response set.
- Downstream response or packaging work stays fail-closed until the latest round's required artifact family is complete for the active manuscript.
