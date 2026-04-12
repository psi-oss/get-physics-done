---
template_version: 1
---

# Phase Prompt Guidance

## Quick contract guardrails

- Keep every PLAN `contract:` block as a YAML object with `schema_version: 1`, `scope`, `contract.context_intake`, and `uncertainty_markers` present before emitting tasks.
- Explicitly list `tool_requirements` and `researcher_setup`; the latter may stay empty when no human-only prep is needed. `tool_requirements[].id` values must stay unique, and any `tool: "command"` entry still needs a concrete `command` string.
- `type: execute` is the default for executable plans; use `gap_closure: true` only when this plan repairs verification failures. Surface any specialized tooling or machine-checkable requirements before the executor runs.
- Keep the canonical observables/claims/deliverables chain open: show `scope.in_scope`, `claim_kind`, `observables[].kind`, `deliverables[].kind`, `acceptance_tests[].kind`, `references[].kind`, `references[].role`, `links[].relation`, `must_surface`, and the `required_actions[]`, `applies_to[]`, and `carry_forward_to[]` arrays. When `references[].must_surface` is `true`, those arrays must be non-empty and concrete.
- Reference relations and actions stay closed: `links[].relation` uses `supports | computes | visualizes | benchmarks | depends_on | evaluated_by | proves | uses_hypothesis | depends_on_lemma | other`, and `references[].required_actions` uses `read | use | compare | cite | avoid`.
- Keep `context_intake`, `approach_policy`, and `uncertainty_markers` as structured YAML objects rather than plain text. When the plan is proof-bearing, name a non-`other` `claim_kind`, keep hypotheses/parameters/conclusions documented, and give the proof-focused `observables[]` entries `kind: proof_obligation`.
- The validator’s tool vocabulary stays limited to `wolfram` and `command`; `command` entries always carry a non-empty `command` string, while other tool entries omit `command`.

## Context decision guidance

- The `context_content` pasted below the phase prompt is the latest user discussion (`gpd:discuss-phase` output). Treat its sections as authoritative anchors.
- **Decisions** rows are locked commitments. Honor them exactly and do not revisit their stated choices—only articulate how the new plan carries them forward.
- **Agent's Discretion** rows describe choices where the user explicitly delegated freedom. Use them to guide methodology without reopening the locked decisions, and keep any constraints they mention visible.
- **Deferred Ideas** entries explicitly mark concepts that belong elsewhere. Do not drift the plan into those topics; treat them as out-of-scope anchors that should stay documented but untouched.

