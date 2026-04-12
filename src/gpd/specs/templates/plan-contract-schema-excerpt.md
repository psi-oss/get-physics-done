---
template_version: 1
type: plan-contract-schema-excerpt
---

**PLAN contract schema-critical excerpt:**
- `contract` is a YAML object with `schema_version: 1`.
- Required sections: object-valued `scope`, `context_intake`, and `uncertainty_markers`; list sections `claims`, `deliverables`, `acceptance_tests`, `forbidden_proxies`, `references` (unless grounding is already concrete); optional `approach_policy`, `observables`, `links`.
- `scope.question` and `scope.in_scope` are required and non-empty.
- Each claim needs a stable `id`, non-empty `deliverables` and `acceptance_tests`, and only declared IDs in cross-references.
- Grounding uses `must_surface`, `required_actions`, `applies_to`, `carry_forward_to`; `approach_policy` never satisfies grounding by itself.
- `context_intake` must anchor the work: surface concrete `must_read_refs`, `must_include_prior_outputs`, `user_asserted_anchors`, or `known_good_baselines` that reference actual artifacts or previously surfaced anchors so that `_has_contract_grounding_context` can detect durable grounding. When those concrete anchors are missing, at least one `references[]` entry must set `must_surface: true` so execution still knows what to dig up.
- Proof-bearing claims must use explicit non-`other` `claim_kind` (`theorem | lemma | corollary | proposition | result | claim | other`) and keep `proof_deliverables`, `parameters`, `hypotheses`, `conclusion_clauses`, and `observables[].kind: proof_obligation` auditable when relevant.
- Link relations use `supports | computes | visualizes | benchmarks | depends_on | evaluated_by | proves | uses_hypothesis | depends_on_lemma | other`.
- reference actions use `read | use | compare | cite | avoid`.
- `uncertainty_markers` must list the contract’s weakest anchors and disconfirming observations (see `weakest_anchors`/`disconfirming_observations`). These lists must stay non-empty so integrity checks can surface the assumptions the model still needs to resolve.
