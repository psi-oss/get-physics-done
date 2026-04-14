---
template_version: 1
type: verification-report-template
---

# Verification Report Template

Verification reports are the decisive readout of the same contract-backed ledger. Reload the canonical contract-results schema immediately before writing. Author canonical YAML; validators may salvage narrow drift, but do not rely on salvage.

Reload `@{GPD_INSTALL_DIR}/templates/contract-results-schema.md` immediately before writing.

`@{GPD_INSTALL_DIR}/templates/contract-results-schema.md`

## Required Frontmatter

- `phase`: non-empty scalar matching the phase folder.
- `verified`: ISO 8601 timestamp.
- `status`: `passed | gaps_found | expert_needed | human_needed`.
- `score`: non-empty string summarizing verification progress (ex: `3/4 contract targets verified`).
- `plan_contract_ref`: required when `contract_results`, `comparison_verdicts`, or `suggested_contract_checks` are present.

## Canonical Report Surface

When `VERIFICATION.md` is contract-backed, keep the machine-readable surface limited to the schema-owned ledgers from `contract-results-schema.md`: `plan_contract_ref`, `contract_results`, `comparison_verdicts`, and `suggested_contract_checks`. Keep `status` strict, and do not invent verifier-local aliases or ad hoc machine-readable artifact fields.

`status: passed` is strict: use it only when every contract-backed target is satisfied, every required decisive comparison is decisive, and `suggested_contract_checks` is empty. Keep `uncertainty_markers` explicit. If decisive work remains open, use `gaps_found`, `expert_needed`, or `human_needed`, not top-level `partial`, and record structured `suggested_contract_checks` instead of padding prose. Reserve `partial` for nested `contract_results` section statuses only.

When a contract requires decisive comparisons, surface `comparison_verdicts`; the canonical schema owns their exact shape.
Proof-backed claims follow the proof-audit rules in the canonical schema, including stale-audit handling and the requirement for explicit proof-specific acceptance tests.
Legacy frontmatter aliases are forbidden in model-facing output; use only the canonical contract-ledger fields from `contract_results`.
Comparison verdicts must declare `subject_role` explicitly; decisive checks use `subject_role: decisive`.
verification-side `suggested_contract_checks` remains the place for any unresolved decisive work.
