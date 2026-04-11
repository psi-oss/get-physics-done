---
template_version: 1
type: contract-results-schema
---

# Contract Results Schema

Canonical source of truth for `plan_contract_ref`, `contract_results`, and `comparison_verdicts` in `SUMMARY.md` and `VERIFICATION.md`.

These ledgers are user-visible evidence. They describe what was established, what artifact exists, and what decisive comparisons passed or failed. They are not a place to log internal tool usage or generic workflow completion.

---

## Required Fields For Contract-Backed Outputs

If the source PLAN contains a `contract:` block, then the derived `SUMMARY.md` or `VERIFICATION.md` must include:

- `plan_contract_ref`
- `contract_results`
- `comparison_verdicts` whenever a decisive comparison is required by the contract or decisive anchor context

If `contract_results` or `comparison_verdicts` are present, `plan_contract_ref` is required, and `uncertainty_markers` must stay explicit in the frontmatter. In contract-backed outputs, `weakest_anchors` and `disconfirming_observations` must be non-empty so unresolved anchors stay visible before writing.

---

## `plan_contract_ref`

```yaml
plan_contract_ref: GPD/phases/XX-name/XX-YY-PLAN.md#/contract
```

Rules:

- Must be a string.
- Must be the canonical project-root-relative `GPD/phases/XX-name/XX-YY-PLAN.md#/contract` path, not an absolute path, URL, or parent-traversing path.
- Must end with the exact `#/contract` fragment; pointing at the PLAN file alone or at another fragment is invalid.
- Must resolve to the matching PLAN contract when validated from disk.

---

## `contract_results`

```yaml
contract_results:
  claims:
    claim-main:
      status: passed
      summary: Established the phase-specific claim using the cited verification evidence.
      linked_ids: [deliv-main, test-main, ref-main]
      proof_audit:
        completeness: complete
        reviewed_at: "2026-04-02T12:00:00Z"
        reviewer: gpd-check-proof
        summary: Proof review found all declared hypotheses, parameters, quantifiers, and conclusion clauses covered.
        proof_artifact_path: derivations/main-proof.tex
        proof_artifact_sha256: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
        audit_artifact_path: GPD/phases/01-proof/01-01-PROOF-REDTEAM.md
        audit_artifact_sha256: fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210
        claim_statement_sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
        covered_hypothesis_ids: [hyp-main]
        missing_hypothesis_ids: []
        covered_parameter_symbols: [r_0]
        missing_parameter_symbols: []
        uncovered_quantifiers: []
        uncovered_conclusion_clause_ids: []
        quantifier_status: matched
        scope_status: matched
        counterexample_status: none_found
        stale: false
      evidence:
        - verifier: gpd-verifier
          method: benchmark reproduction
          confidence: high
          claim_id: claim-main
          deliverable_id: deliv-main
          acceptance_test_id: test-main
          reference_id: ref-main
          forbidden_proxy_id: fp-main
          evidence_path: GPD/phases/XX-name/XX-VERIFICATION.md
  deliverables:
    deliv-main:
      status: passed
      path: GPD/phases/XX-name/artifacts/main-result.md
      summary: Phase-specific artifact produced for the declared deliverable.
      linked_ids: [claim-main, test-main]
  acceptance_tests:
    test-main:
      status: passed
      summary: Decisive benchmark reproduced the required reference value within tolerance.
      linked_ids: [claim-main, deliv-main, ref-main]
  references:
    ref-main:
      status: completed
      completed_actions: [read, compare, cite]
      missing_actions: []
      summary: Required anchor was read, compared against the result, and cited in the verification report.
  forbidden_proxies:
    fp-main:
      status: rejected
      notes: Disallowed proxy was not used; the decisive benchmark evidence is direct.
  uncertainty_markers:
    weakest_anchors: [anchor-1]
    unvalidated_assumptions: [assumption-1]
    competing_explanations: [alternative-1]
    disconfirming_observations: [observation-1]
```

Rules:

- Replace example IDs and prose with phase-specific contract IDs and evidence; placeholder text is invalid.
- Ledger keys must be real IDs from the referenced PLAN contract.
- `contract_results` and every nested entry use a closed schema. Only the documented keys are allowed; invented keys such as `context_usage` fail validation.
- Missing contract-backed `contract_results` is invalid.
- `uncertainty_markers` must remain explicit in contract-backed outputs so the model sees unresolved anchors, competing explanations, and disconfirming observations before writing.
- Every declared claim, deliverable, acceptance test, reference, and forbidden proxy ID from the referenced PLAN contract must appear in the matching section.
- Section-specific status vocabularies are mandatory:
  - `claims|deliverables|acceptance_tests -> passed|partial|failed|blocked|not_attempted`
  - `references -> completed|missing|not_applicable`
  - `forbidden_proxies -> rejected|violated|unresolved|not_applicable`
- Do not silently omit unfinished work. Use the section-specific open-work status explicitly when a contract ID is still open.
- `linked_ids` and evidence sub-IDs (`claim_id`, `deliverable_id`, `acceptance_test_id`, `reference_id`, `forbidden_proxy_id`) must point to declared contract IDs.
- A claim is proof-bearing when `claim_kind` is `theorem|lemma|corollary|proposition|claim`, the statement is theorem-like, proof fields are populated, or `observables[]` references a `proof_obligation` target.
- `proof_audit` belongs on `contract_results.claims.<claim-id>` for theorem/proof claims. Do not move it to `deliverables` or `acceptance_tests`.
- If a proof-bearing claim is marked `status: passed`, `proof_audit` is mandatory and `proof_audit.completeness` must be explicit.
- `proof_audit.completeness: complete | incomplete`
- `proof_audit.quantifier_status: matched | narrowed | mismatched | unclear`
  A quantified proof-bearing claim must keep `proof_audit.quantifier_status` explicit; passed quantified claims require `matched`.
- `proof_audit.scope_status: matched | narrower_than_claim | mismatched | unclear`
- `proof_audit.counterexample_status: none_found | counterexample_found | not_attempted | narrowed_claim`
- `proof_audit.completeness: complete` is valid only with `reviewer: gpd-check-proof`, non-empty review/artifact/hash fields, no missing/uncovered proof obligations, `scope_status: matched`, `counterexample_status: none_found`, and `stale: false`.
- A passed quantified proof-bearing claim must use `quantifier_status: matched`.
- A passed proof-bearing claim must carry `proof_artifact_path`, `proof_artifact_sha256`, `audit_artifact_path`, `audit_artifact_sha256`, `claim_statement_sha256`; the statement hash must be current.
- `proof_audit.proof_artifact_path` must match a declared `proof_deliverables` path, and `proof_audit.audit_artifact_path` must point to a proof-redteam artifact.
- A passed proof-bearing claim must also have every declared proof-specific acceptance test in `claims[].acceptance_tests[]` passing; proof-bearing claims must declare at least one such test (`claim_to_proof_alignment`, `proof_hypothesis_coverage`, `proof_parameter_coverage`, `proof_quantifier_domain`, `lemma_dependency_closure`, or `counterexample_search`).
- If a PLAN reference has `must_surface: true`, the ledger must include a matching `contract_results.references.<reference-id>` entry.
- For `must_surface` references, `completed_actions` must cover every `required_actions` item; do not mark the anchor as handled while leaving required actions only in prose.
- `required_actions`, `completed_actions`, and `missing_actions` use the same closed action vocabulary: `read`, `use`, `compare`, `cite`, `avoid`.
- Every strict string list is trimmed before validation. Blank-after-trim entries are invalid, and duplicate-after-trim entries are invalid. This includes `linked_ids`, `completed_actions`, `missing_actions`, and the list-valued proof-audit coverage fields.
- Author canonical form: lists stay lists and closed-enum literals stay exact lowercase. Artifact readers may salvage narrow singleton string/list drift and closed-enum case drift, but do not rely on salvage for new ledgers.
- `claims`, `deliverables`, and `acceptance_tests` entries with `status: failed|blocked` must include at least one of `summary`, `notes`, or non-empty `evidence` so the gap is explained instead of implied.
- For `contract_results.references`:
  `status: completed` requires non-empty `completed_actions` and empty `missing_actions`.
  `status: missing` requires non-empty `missing_actions` plus `summary` or non-empty `evidence` explaining what is missing.
  `status: not_applicable` requires both `completed_actions` and `missing_actions` to stay empty.
  `completed_actions` and `missing_actions` must not overlap.
- For `contract_results.forbidden_proxies`, `status: violated|unresolved` requires `notes` or non-empty `evidence` explaining the proxy issue.
- For decisive acceptance tests, benchmark requirements must close with `comparison_kind: benchmark` and cross-method requirements must close with `comparison_kind: cross_method`; `prior_work`, `experiment`, `baseline`, and `other` do not satisfy those decisive mappings on their own.
- List-typed proof-audit fields (`covered_hypothesis_ids`, `missing_hypothesis_ids`, `covered_parameter_symbols`, `missing_parameter_symbols`, `uncovered_quantifiers`, `uncovered_conclusion_clause_ids`) must stay YAML lists even for one item.
- `status`, `proof_audit.completeness`, and evidence literals such as `confidence`, `quantifier_status`, and `counterexample_status` use the exact lowercase literals shown here. Near-matches like `Passed` or `High` are invalid.
- `evidence[].confidence: high | medium | low | unreliable`
- Inside `evidence[]`, list-typed proof coverage fields must also stay YAML lists.

---

## `comparison_verdicts`

```yaml
comparison_verdicts:
  - subject_id: claim-main
    subject_kind: claim
    subject_role: decisive
    reference_id: ref-main
    comparison_kind: benchmark
    metric: relative_error
    threshold: "<= 0.01"
    verdict: pass
    recommended_action: "[what to do next]"
    notes: "[optional context]"
```

Rules:

- `subject_id` must be a real ID from the referenced PLAN contract.
- `subject_kind: claim|deliverable|acceptance_test|reference`; it must match the actual contract ID kind referenced by `subject_id`.
- Do not invent `artifact` or `other` subject kinds for contract-backed verdicts. If the thing you compared is a file, plot, or table, point the verdict at the deliverable or reference ID that owns it.
- `subject_role: decisive|supporting|supplemental|other`; it is required on every verdict.
- Only `subject_role: decisive` satisfies a required decisive comparison or participates in pass/fail consistency checks against `contract_results`. `supporting` and `supplemental` verdicts are informative context only.
- `comparison_kind: benchmark|prior_work|experiment|cross_method|baseline|other`; benchmark acceptance tests require `benchmark`, and cross-method acceptance tests require `cross_method`.
- List-typed ledger fields such as `linked_ids`, `completed_actions`, `missing_actions`, and all `uncertainty_markers` entries must stay YAML lists even for one item.
- If a decisive external anchor was used, include `reference_id`. If the decisive anchor is itself the compared subject, use `subject_kind: reference` and `subject_id: <reference-id>`.
- `verdict: pass|tension|fail|inconclusive`; if a required decisive comparison is still open, use `inconclusive` or `tension` instead of omitting the entry.
- A prose sentence like “agrees with literature” does not replace a verdict entry.
- When a reference-backed decisive comparison is required, use `comparison_kind: benchmark`, `prior_work`, `experiment`, `baseline`, or `cross_method`. `comparison_kind: other` does not satisfy that requirement.
- A decisive verdict is required whenever the PLAN contract includes an acceptance test with `kind: benchmark` or `kind: cross_method`, whenever a benchmark-style reference anchors the subject, whenever a reference lists `required_actions` containing `compare`, or whenever you performed a decisive comparison in practice.

---

## Verification-Specific Note

For `VERIFICATION.md`, use the same frontmatter surface as `verification-report.md`.
If a decisive benchmark / cross-method check remains `partial`, `not_attempted`, or still lacks a decisive verdict, the frontmatter must also include structured `suggested_contract_checks` entries explaining the missing decisive work.
The same requirement applies when a benchmark-style reference anchors the subject or a reference with `required_actions` containing `compare` is still incomplete.
Each `suggested_contract_checks` entry may only use these keys: `check`, `reason`, `suggested_subject_kind`, `suggested_subject_id`, and `evidence_path`. Invented keys such as `check_id` fail validation. Copy the `check_key` returned by `suggest_contract_checks(contract)` into the frontmatter `check` field when you record one of those suggestions in `VERIFICATION.md`.
If you bind a `suggested_contract_checks` entry to a known contract target, `suggested_subject_kind` and `suggested_subject_id` must appear together; otherwise omit both.

---

## Validation Commands

Prefer the contract-specific commands below for contract-backed summaries and verification reports because they resolve the referenced PLAN from disk and enforce ID alignment, not just bare YAML shape.

```bash
gpd frontmatter validate GPD/phases/XX-name/XX-YY-SUMMARY.md --schema summary
gpd validate summary-contract GPD/phases/XX-name/XX-YY-SUMMARY.md
gpd frontmatter validate GPD/phases/XX-name/XX-VERIFICATION.md --schema verification
gpd validate verification-contract GPD/phases/XX-name/XX-VERIFICATION.md
```

`PLAN` and `SUMMARY` artifacts are plan-scoped (`XX-YY-*`). `VERIFICATION.md` is phase-scoped (`XX-VERIFICATION.md`).
