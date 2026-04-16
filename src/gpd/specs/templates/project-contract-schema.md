---
template_version: 1
purpose: Contract-critical schema slice for the `project_contract` payload
---

# Project Contract Schema

Canonical schema for the `project_contract` object inside `GPD/state.json`. This is the contract-critical slice used by `gpd:new-project` before a scope approval gate. Keep it narrow: model-facing contract setup should see only the `project_contract` shape and rules, not the unrelated top-level state schema.

---

## `project_contract`

```json
{
  "schema_version": 1,
  "scope": {
    "question": "What benchmark must the project recover?",
    "in_scope": ["Recover the published benchmark curve within tolerance"],
    "out_of_scope": ["adjacent question C"],
    "unresolved_questions": ["Which reference should serve as the decisive benchmark anchor?"]
  },
  "context_intake": {
    "must_read_refs": ["Ref-01"],
    "must_include_prior_outputs": ["GPD/phases/00-baseline/00-01-SUMMARY.md"],
    "user_asserted_anchors": ["GPD/phases/00-baseline/00-01-SUMMARY.md#benchmark-curve"],
    "known_good_baselines": ["GPD/phases/00-baseline/00-01-SUMMARY.md#accepted-baseline"],
    "context_gaps": ["Need grounding; decisive target not yet chosen before planning"],
    "crucial_inputs": ["Figure 2 from prior work"]
  },
  "approach_policy": {
    "formulations": ["continuum representation with direct observable X"],
    "allowed_estimator_families": ["direct estimator"],
    "forbidden_estimator_families": ["proxy-only estimator"],
    "allowed_fit_families": ["benchmark-motivated ansatz"],
    "forbidden_fit_families": ["pure convenience fit"],
    "stop_and_rethink_conditions": ["First result only validates a proxy while the decisive anchor remains unchecked"]
  },
  "observables": [
    {
      "id": "obs-main",
      "name": "Benchmark observable X",
      "kind": "curve",
      "definition": "Primary comparison curve for the published benchmark"
    }
  ],
  "claims": [
    {
      "id": "claim-main",
      "statement": "Recover the published benchmark curve within the stated tolerance",
      "claim_kind": "theorem",
      "observables": ["obs-main"],
      "deliverables": ["deliv-main", "deliv-proof-main"],
      "acceptance_tests": ["test-main", "test-proof-main"],
      "references": ["Ref-01"],
      "parameters": [
        {
          "symbol": "k",
          "domain_or_type": "benchmark sample index",
          "aliases": ["sample-k"],
          "required_in_proof": true
        }
      ],
      "hypotheses": [
        {
          "id": "hyp-main",
          "text": "Published normalization and tolerance convention are interpreted exactly as stated in Ref-01",
          "symbols": ["k"],
          "category": "assumption",
          "required_in_proof": true
        }
      ],
      "quantifiers": ["for every benchmark sample k in the approved comparison set"],
      "conclusion_clauses": [
        {
          "id": "concl-main",
          "text": "Relative error stays within the stated 1% tolerance at every approved benchmark sample"
        }
      ],
      "proof_deliverables": ["deliv-proof-main"]
    }
  ],
  "deliverables": [
    {
      "id": "deliv-main",
      "kind": "figure",
      "path": "paper/figures/benchmark-curve.pdf",
      "description": "Figure comparing the reproduced curve against the benchmark",
      "must_contain": ["benchmark overlay"]
    },
    {
      "id": "deliv-proof-main",
      "kind": "derivation",
      "path": "derivations/benchmark-proof.md",
      "description": "Auditable proof sketch tying the tolerance claim to the benchmark construction",
      "must_contain": ["named hypotheses", "parameter coverage", "conclusion mapping"]
    }
  ],
  "acceptance_tests": [
    {
      "id": "test-main",
      "subject": "claim-main",
      "kind": "benchmark",
      "procedure": "Compare the reproduced curve against Ref-01 within tolerance",
      "pass_condition": "Relative error <= 1%",
      "evidence_required": ["deliv-main", "Ref-01"],
      "automation": "hybrid"
    },
    {
      "id": "test-proof-main",
      "subject": "claim-main",
      "kind": "claim_to_proof_alignment",
      "procedure": "Check that every named hypothesis, parameter, and conclusion clause in the theorem claim is covered by the proof artifact",
      "pass_condition": "Every theorem field is covered explicitly or auditable as intentionally omitted",
      "evidence_required": ["deliv-proof-main"],
      "automation": "human"
    }
  ],
  "references": [
    {
      "id": "Ref-01",
      "kind": "paper",
      "locator": "Author et al., Journal, 2024",
      "aliases": ["benchmark-paper"],
      "role": "benchmark",
      "why_it_matters": "Primary published comparison target",
      "applies_to": ["claim-main"],
      "carry_forward_to": ["planning", "execution", "verification", "writing"],
      "must_surface": true,
      "required_actions": ["read", "compare", "cite", "avoid"]
    }
  ],
  "forbidden_proxies": [
    {
      "id": "fp-main",
      "subject": "claim-main",
      "proxy": "Qualitative trend match without the decisive benchmark comparison",
      "reason": "Would look like progress while skipping the contract-critical anchor"
    }
  ],
  "links": [
    {
      "id": "link-main",
      "source": "claim-main",
      "target": "deliv-main",
      "relation": "supports",
      "verified_by": ["test-main"]
    }
  ],
  "uncertainty_markers": {
    "weakest_anchors": ["Benchmark tolerance interpretation"],
    "unvalidated_assumptions": [],
    "competing_explanations": [],
    "disconfirming_observations": ["Benchmark agreement disappears after a notation-normalization fix"]
  }
}
```

## Contract Rules

The `project_contract` value must be a JSON object. Do not replace it with prose, a list, or a string.

`schema_version` must be the integer `1`. Unsupported schema versions are invalid.

Project contracts must include at least one observable, claim, or deliverable.

`uncertainty_markers.weakest_anchors` and `uncertainty_markers.disconfirming_observations` must both be non-empty.

Canonical IDs and other required string fields are trimmed before validation. Blank-after-trim values are invalid, and duplicates that differ only by surrounding whitespace still collide after normalization.

`scope.in_scope` must name at least one project boundary or objective.

`context_intake` must not be empty. At least one of `must_read_refs`, `must_include_prior_outputs`, `user_asserted_anchors`, `known_good_baselines`, `context_gaps`, or `crucial_inputs` must carry a non-empty item, and the grounding fields must be concrete enough to re-find later.
`context_intake`, `approach_policy`, and `uncertainty_markers` are JSON objects when present; do not collapse them to strings or lists.

### Closed Schema And List Shape

The `project_contract` schema is closed. Do not invent extra keys inside nested objects. Only the fields defined here are valid.

List-shaped fields must stay lists, even when they contain one item. Do not collapse `scope.in_scope`, `scope.out_of_scope`, `scope.unresolved_questions`, `context_intake.*`, or any nested `[]` field to a scalar string.

Blank list entries are invalid. Duplicate list entries are also invalid after trimming whitespace, even if the duplicates only differ by surrounding spaces.

The following fields always store arrays of objects, never arrays of plain strings:

- `observables[]` — `{ "id", "name", "kind", "definition", "regime?", "units?" }`
- `claims[]` — `{ "id", "statement", "claim_kind", "observables[]", "deliverables[]", "acceptance_tests[]", "references[]", "parameters[]", "hypotheses[]", "quantifiers[]", "conclusion_clauses[]", "proof_deliverables[]" }`
- `deliverables[]` — `{ "id", "kind", "path?", "description", "must_contain[]" }`
- `acceptance_tests[]` — `{ "id", "subject", "kind", "procedure", "pass_condition", "evidence_required[]", "automation" }`
- `references[]` — `{ "id", "kind", "locator", "aliases[]", "role", "why_it_matters", "applies_to[]", "carry_forward_to[]", "must_surface": true|false, "required_actions[]" }`
- `forbidden_proxies[]` — `{ "id", "subject", "proxy", "reason" }`
- `links[]` — `{ "id", "source", "target", "relation", "verified_by[]" }`

Treat a claim as proof-bearing whenever any of these is true: `claim_kind` is `theorem`, `lemma`, `corollary`, `proposition`, or `claim`; the statement is theorem-like (`prove/show that`, explicit `for all` / `exists`, or uniqueness language); any proof field is already populated (`parameters`, `hypotheses`, `quantifiers`, `conclusion_clauses`, or `proof_deliverables`); or `observables[]` references a `proof_obligation` target.

When that applies, require:

- proof-bearing claims must keep `parameters`, `hypotheses`, `quantifiers`, `conclusion_clauses`, and `proof_deliverables` visible.
- Do not collapse proof obligations into a generic claim statement.
- `claims[].claim_kind` must use the closed vocabulary: `theorem | lemma | corollary | proposition | result | claim | other`.
- Closed semantic enum fields use these exact lowercase literals:
  - `claims[].claim_kind: theorem | lemma | corollary | proposition | result | claim | other`
  - `observables[].kind: scalar | curve | map | classification | proof_obligation | other`
  - `deliverables[].kind: figure | table | dataset | data | derivation | code | note | report | other`
  - `acceptance_tests[].kind: existence | schema | benchmark | consistency | cross_method | limiting_case | symmetry | dimensional_analysis | convergence | oracle | proxy | reproducibility | proof_hypothesis_coverage | proof_parameter_coverage | proof_quantifier_domain | claim_to_proof_alignment | lemma_dependency_closure | counterexample_search | human_review | other`
  - `acceptance_tests[].automation: automated | hybrid | human`
  - `references[].kind: paper | dataset | prior_artifact | spec | user_anchor | other`
  - `references[].role: definition | benchmark | method | must_consider | background | other`
  - `required_actions[]: read | use | compare | cite | avoid`
  - `links[].relation: supports | computes | visualizes | benchmarks | depends_on | evaluated_by | proves | uses_hypothesis | depends_on_lemma | other`
- Closed-vocabulary enum fields use the exact lowercase literals shown here. Case drift such as `Theorem`, `Benchmark`, or `Read` fails strict validation.
- `claims[].proof_deliverables[]` must be non-empty and contain only `deliverables[].id` values.
- `claims[].parameters[]`, `claims[].hypotheses[]`, and `claims[].conclusion_clauses[]` must each be non-empty.
- `claims[].acceptance_tests[]` must include at least one proof-specific test kind (`proof_hypothesis_coverage`, `proof_parameter_coverage`, `proof_quantifier_domain`, `claim_to_proof_alignment`, `lemma_dependency_closure`, or `counterexample_search`).
- include an acceptance test with `kind: claim_to_proof_alignment` when the proof artifact must map a theorem-like claim to named hypotheses, parameters, and conclusion clauses.
- `claims[].quantifiers[]` is optional but, when present, must stay a list (not a scalar string).

### Shared Grounding And Linkage Rules

@{GPD_INSTALL_DIR}/templates/project-contract-grounding-linkage.md
