---
template_version: 1
type: proof-redteam-schema
---

# Proof Redteam Schema

Canonical source of truth for the `*-PROOF-REDTEAM.md` artifact shape. Use this when authoring or validating a proof audit. The model must see the hard output contract before it writes the artifact.

---

## Required Frontmatter

Every proof-redteam artifact must include:

- `status: passed | gaps_found | human_needed`
- `reviewer: gpd-check-proof`
- `claim_ids: []` or a non-empty list of claim IDs, depending on the active review scope
- `proof_artifact_paths: [path, ...]`
- `missing_parameter_symbols: []`
- `missing_hypothesis_ids: []`
- `coverage_gaps: []`
- `scope_status: matched | narrower_than_claim | mismatched | unclear`
- `quantifier_status: matched | narrowed | mismatched | unclear`
- `counterexample_status: none_found | counterexample_found | not_attempted | narrowed_claim`

Manuscript-scoped artifacts also require:

- `manuscript_path`
- `manuscript_sha256`
- `round`

Rules:

- `claim_ids` must be a YAML list, even when empty.
- `proof_artifact_paths` must be a non-empty YAML list of readable proof-artifact paths.
- All structured audit list fields must stay as YAML lists, not scalar strings.
- Newly written YAML must use exact lowercase enum values.
- `status: passed` is invalid if any structured audit field records a missing parameter, missing hypothesis, coverage gap, narrowed scope, narrowed quantifier, or any counterexample finding.

## Required Body Structure

The artifact body must contain these sections in order:

1. `# Proof Redteam`
2. `## Proof Inventory`
3. `## Coverage Ledger`
4. `## Adversarial Probe`
5. `## Verdict`
6. `## Required Follow-Up`

## Proof Inventory

The proof inventory must enumerate the exact claim under review and the proof obligations it imposes.

Required items:

- exact claim / theorem text
- claim / theorem target
- named parameters
- hypotheses
- quantifier / domain obligations
- conclusion clauses

Rules:

- The exact claim / theorem text must quote the statement under audit, not a paraphrase.
- If a named parameter appears in the claim, it must be listed in the proof inventory and covered in the ledger.
- If a hypothesis is named in the claim, it must be listed in the proof inventory and covered in the ledger.
- If the proof only establishes a narrower special case, `status` must not be `passed`.

## Coverage Ledger

The coverage ledger must include these subsections:

- `### Named-Parameter Coverage`
- `### Hypothesis Coverage`
- `### Quantifier / Domain Coverage`
- `### Conclusion-Clause Coverage`

Each subsection must use a table with explicit status and notes columns.

Rules:

- Every named parameter from the proof inventory must appear in `Named-Parameter Coverage`.
- Every named hypothesis from the proof inventory must appear in `Hypothesis Coverage`.
- Every quantifier or domain obligation from the proof inventory must appear in `Quantifier / Domain Coverage`.
- Every conclusion clause from the proof inventory must appear in `Conclusion-Clause Coverage`.
- Missing entries are blockers, not stylistic omissions.

## Adversarial Probe

The adversarial probe must record:

- probe type
- result

Use at least one adversarial probe such as a counterexample attempt, boundary case, dropped-parameter test, or narrower-case challenge.

## Verdict

The verdict section must explicitly restate:

- scope status
- quantifier status
- counterexample status
- blocking gaps

Rules:

- The verdict must agree with the frontmatter structured audit fields.
- If any coverage entry is missing or any proof obligation is only partially established, the verdict cannot be `passed`.

## Required Follow-Up

Record the smallest concrete changes needed before the claim may be treated as established.

Rules:

- Do not hide unresolved proof obligations in prose.
- Do not convert a gap into a style suggestion.
- If the claim is salvageable but not yet complete, state the exact repair path.

