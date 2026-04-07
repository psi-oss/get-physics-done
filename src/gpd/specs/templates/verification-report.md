---
template_version: 1
type: verification-report-template
---

# Verification Report Template

Verification reports are the decisive readout of the same contract-backed ledger. Reload `@{GPD_INSTALL_DIR}/templates/contract-results-schema.md` immediately before writing and apply it literally.

## Canonical Report Surface

When `VERIFICATION.md` is contract-backed, keep the machine-readable surface limited to the schema-owned ledgers from `contract-results-schema.md`: `plan_contract_ref`, `contract_results`, `comparison_verdicts`, and `suggested_contract_checks`. Keep `status` strict, and do not invent verifier-local aliases or ad hoc machine-readable artifact fields.

`status: passed` is strict: use it only when every contract-backed target is satisfied, every required decisive comparison is decisive, and `suggested_contract_checks` is empty. Keep `uncertainty_markers` explicit. If decisive work remains open, use `partial`, `gaps_found`, `expert_needed`, or `human_needed` and record structured `suggested_contract_checks` instead of padding prose.

When a contract requires decisive comparisons, surface `comparison_verdicts`; the canonical schema owns their exact shape.
Proof-backed claims follow the proof-audit rules in the canonical schema, including stale-audit handling and the requirement for explicit proof-specific acceptance tests.
Legacy frontmatter aliases are forbidden in model-facing output; use only the canonical contract-ledger fields from `contract_results`.
Comparison verdicts must declare `subject_role` explicitly; decisive checks use `subject_role: decisive`.
verification-side `suggested_contract_checks` remains the place for any unresolved decisive work.
