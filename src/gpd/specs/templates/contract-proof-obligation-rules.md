Use these rules for both PLAN frontmatter contracts and `project_contract` payloads.

In `ProjectContract` (`project_contract.claims[]` / `ContractClaim`), treat a claim as proof-bearing whenever any of these is true: `claim_kind` is `theorem`, `lemma`, `corollary`, `proposition`, or `claim`; the statement is theorem-like (`prove/show that`, explicit `for all` / `exists`, or uniqueness language); any proof field is already populated (`parameters`, `hypotheses`, `quantifiers`, `conclusion_clauses`, or `proof_deliverables`); or `observables[]` references a `proof_obligation` target. Do not import the staged peer-review Paper `ClaimRecord` meaning of `claim_kind: claim` here; in staged peer-review Paper records, `claim_kind: claim` is only a generic manuscript claim unless theorem metadata or theorem-like statement text makes a proof obligation explicit.

When proof-bearing applies:

- Proof-bearing claims must use an explicit non-`other` `claim_kind`.
- proof-bearing claims must keep `parameters`, `hypotheses`, `conclusion_clauses`, and `proof_deliverables` visible, and must keep `quantifiers` visible when an explicit quantifier or domain obligation exists.
- Proof-bearing claims must declare at least one proof-specific acceptance test in `acceptance_tests[]` and surface `proof_deliverables`, `parameters`, `hypotheses`, and `conclusion_clauses` so the proof obligation is auditable.
- Quantifiers are visible when explicit quantifier or domain obligations exist; unquantified proof-bearing claims do not need a non-empty quantifier list.
- `claims[].quantifiers[]` is optional for unquantified proof-bearing claims, but explicit quantifier or domain obligations must stay visible there as a list, not a scalar string.
- Do not collapse proof obligations into a generic claim statement.
- `claims[].proof_deliverables[]` must be non-empty and contain only `deliverables[].id` values.
- `claims[].parameters[]`, `claims[].hypotheses[]`, and `claims[].conclusion_clauses[]` must each be non-empty.
- Keep nested proof lists as arrays, even for one item: `parameters[].aliases`, `hypotheses[].symbols`, `quantifiers` when present, and `proof_deliverables` must not collapse to scalar strings.
- `required_in_proof` must be a literal JSON boolean (`true` or `false`), not a quoted string or synonym such as `"yes"` / `"no"`.
- `claims[].acceptance_tests[]` must include at least one proof-specific test kind (`proof_hypothesis_coverage`, `proof_parameter_coverage`, `proof_quantifier_domain`, `claim_to_proof_alignment`, `lemma_dependency_closure`, or `counterexample_search`).
- Include an acceptance test with `kind: claim_to_proof_alignment` when the proof artifact must map a theorem-like claim to named hypotheses, parameters, and conclusion clauses.

Closed vocabulary enum fields use the exact lowercase literals shown here. Case drift such as `Theorem`, `Benchmark`, or `Read` fails strict validation.

- `claims[].claim_kind: theorem | lemma | corollary | proposition | result | claim | other`
- `observables[].kind: scalar | curve | map | classification | proof_obligation | other`
- `deliverables[].kind: figure | table | dataset | data | derivation | code | note | report | other`
- `acceptance_tests[].kind: existence | schema | benchmark | consistency | cross_method | limiting_case | symmetry | dimensional_analysis | convergence | oracle | proxy | reproducibility | proof_hypothesis_coverage | proof_parameter_coverage | proof_quantifier_domain | claim_to_proof_alignment | lemma_dependency_closure | counterexample_search | human_review | other`
- `acceptance_tests[].automation: automated | hybrid | human`
- `references[].kind: paper | dataset | prior_artifact | spec | user_anchor | other`
- `references[].role: definition | benchmark | method | must_consider | background | other`
- `required_actions[]: read | use | compare | cite | avoid`
- `links[].relation: supports | computes | visualizes | benchmarks | depends_on | evaluated_by | proves | uses_hypothesis | depends_on_lemma | other`
