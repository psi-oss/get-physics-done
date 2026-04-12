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
- Proof-bearing claims must use explicit non-`other` `claim_kind` (`theorem | lemma | corollary | proposition | result | claim | other`) and keep `proof_deliverables`, `parameters`, `hypotheses`, `conclusion_clauses`, and `observables[].kind: proof_obligation` auditable when relevant.
- Link relations use `supports | computes | visualizes | benchmarks | depends_on | evaluated_by | proves | uses_hypothesis | depends_on_lemma | other`.
- reference actions use `read | use | compare | cite | avoid`.
