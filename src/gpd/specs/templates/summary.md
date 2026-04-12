---
template_version: 1
type: summary-template
---

# Summary Template

Contract-backed summaries are user-visible outcome ledgers. When the source PLAN has a `contract:` block, reload `@{GPD_INSTALL_DIR}/templates/contract-results-schema.md` immediately before writing and treat that file as the single detailed rule source.

## Required Frontmatter

- `phase`: non-empty scalar matching the phase folder.
- `plan`: non-empty scalar matching the PLAN name.
- `depth`: `minimal | standard | full | complex`.
- `provides`: non-empty list of strings describing what this summary covers.
- `completed`: date string (YYYY-MM-DD or ISO 8601) or a boolean.
- `plan_contract_ref`: required when `contract_results` or `comparison_verdicts` are present.

For contract-backed summaries, include `plan_contract_ref`, `contract_results`, and any required `comparison_verdicts`. Keep `uncertainty_markers` explicit. The canonical schema defines the exact list-trimming semantics, status vocabularies, and ID alignment; this wrapper should not restate them.

`suggested_contract_checks` is verification-only and does not belong in summaries.
Legacy frontmatter aliases are forbidden in model-facing output; use only the canonical contract-ledger fields from `contract_results`.
If the ledger records a forbidden proxy, bind it through `forbidden_proxy_id` in the canonical schema rather than inventing a new field.
