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

If `contract_results` or `comparison_verdicts` are present, `plan_contract_ref` is required.

---

## `plan_contract_ref`

```yaml
plan_contract_ref: .gpd/phases/XX-name/XX-YY-PLAN.md#/contract
```

Rules:

- Must be a string.
- Must resolve to the matching PLAN contract when validated from disk.

---

## `contract_results`

```yaml
contract_results:
  claims:
    claim-main:
      status: passed|partial|failed|blocked|not_attempted
      summary: "[what was actually established]"
      linked_ids: [deliv-main, test-main, ref-main]
      evidence:
        - verifier: gpd-verifier
          method: benchmark reproduction
          confidence: high
          claim_id: claim-main
          deliverable_id: deliv-main
          acceptance_test_id: test-main
          reference_id: ref-main
          evidence_path: .gpd/phases/XX-name/XX-VERIFICATION.md
  deliverables:
    deliv-main:
      status: passed|partial|failed|blocked|not_attempted
      path: path/to/artifact
      summary: "[what artifact exists and why it matters]"
      linked_ids: [claim-main, test-main]
  acceptance_tests:
    test-main:
      status: passed|partial|failed|blocked|not_attempted
      summary: "[what decisive test happened and what it showed]"
      linked_ids: [claim-main, deliv-main, ref-main]
  references:
    ref-main:
      status: completed|missing|not_applicable
      completed_actions: [read, compare, cite]
      missing_actions: []
      summary: "[how the anchor was surfaced]"
  forbidden_proxies:
    fp-main:
      status: rejected|violated|unresolved|not_applicable
      notes: "[why this proxy was or was not allowed]"
  uncertainty_markers:
    weakest_anchors: []
    unvalidated_assumptions: []
    competing_explanations: []
    disconfirming_observations: []
```

Rules:

- Ledger keys must be real IDs from the referenced PLAN contract.
- Missing contract-backed `contract_results` is invalid.
- Every declared claim, deliverable, acceptance test, reference, and forbidden proxy ID from the referenced PLAN contract must appear in its matching section.
- Do not silently omit unfinished work. Use `not_attempted`, `missing`, `not_applicable`, or `unresolved` explicitly when a contract ID is still open.
- `linked_ids` and evidence sub-IDs (`claim_id`, `deliverable_id`, `acceptance_test_id`, `reference_id`) must point to declared contract IDs.
- If a PLAN reference has `must_surface: true`, the ledger must include a matching `contract_results.references.<reference-id>` entry.
- For `must_surface` references, `completed_actions` must cover every `required_actions` item; do not mark the anchor as handled while leaving required actions only in prose.

---

## `comparison_verdicts`

```yaml
comparison_verdicts:
  - subject_id: claim-main
    subject_kind: claim|deliverable|acceptance_test|reference|artifact
    subject_role: decisive|supporting|supplemental
    reference_id: ref-main
    comparison_kind: benchmark|prior_work|experiment|cross_method|baseline
    metric: relative_error
    threshold: "<= 0.01"
    verdict: pass|tension|fail|inconclusive
    recommended_action: "[what to do next]"
    notes: "[optional context]"
```

Rules:

- `subject_id` must be a real ID from the referenced PLAN contract.
- `subject_kind` must match the actual contract ID kind referenced by `subject_id`.
- If a decisive comparison is required, omitting its verdict makes the artifact incomplete.
- If the decisive comparison is still open, emit `verdict: inconclusive` or `verdict: tension` instead of omitting the entry.
- A prose sentence like “agrees with literature” does not replace a verdict entry.

---

## Verification-Specific Note

For `VERIFICATION.md`, keep the frontmatter compatible with `verification-report.md`.
If a decisive benchmark / cross-method check remains `partial`, `not_attempted`, or still lacks a decisive verdict, the frontmatter must also include structured `suggested_contract_checks` entries explaining the missing decisive work.

---

## Validation Commands

Prefer the contract-specific commands below for contract-backed summaries and verification reports because they resolve the referenced PLAN from disk and enforce ID alignment, not just bare YAML shape.

```bash
gpd frontmatter validate .gpd/phases/XX-name/XX-YY-SUMMARY.md --schema summary
gpd validate summary-contract .gpd/phases/XX-name/XX-YY-SUMMARY.md
gpd frontmatter validate .gpd/phases/XX-name/XX-VERIFICATION.md --schema verification
gpd validate verification-contract .gpd/phases/XX-name/XX-VERIFICATION.md
```

`PLAN` and `SUMMARY` artifacts are plan-scoped (`XX-YY-*`). `VERIFICATION.md` is phase-scoped (`XX-VERIFICATION.md`).
