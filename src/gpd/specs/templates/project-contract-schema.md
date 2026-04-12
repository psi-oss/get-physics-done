---
template_version: 1
purpose: Contract-critical schema slice for the `project_contract` payload
---

# Project Contract Schema

Canonical schema for the `project_contract` object inside `GPD/state.json`. This is the contract-critical slice used by `gpd:new-project` before a scope approval gate. Keep it narrow: model-facing contract setup should see only the `project_contract` shape and rules, not the unrelated top-level state schema.

Hard-schema capsule: `project_contract` must be one JSON object with `schema_version`, `scope`, `context_intake`, and `uncertainty_markers`; hard-schema fields must be model-visible before validation because validators do not infer `scope.question`, non-empty `scope.in_scope`, `context_intake`, or `uncertainty_markers` from prose; bool fields use literal `true`/`false` only; list fields stay lists; object arrays stay objects; proof-bearing claims must surface `parameters`, `hypotheses`, `quantifiers`, `conclusion_clauses`, `proof_deliverables`, and a `claim_to_proof_alignment` acceptance test before drafting approval text.

Project-local paths in `locator` or `applies_to[]` evidence require project-root-aware validation; validation cannot prove artifact grounding without that resolved project context.

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

Approval checklist:
1. `schema_version` must be integer `1`.
2. `scope.question` is required and `scope.in_scope[]` must name a boundary or objective.
3. Include at least one decisive `observables[]`, `claims[]`, or `deliverables[]` item.
4. `context_intake` must contain a concrete anchor; placeholder-only text does not count.
5. `uncertainty_markers.weakest_anchors[]` and `uncertainty_markers.disconfirming_observations[]` must be non-empty.
6. If `references[]` is the only grounding, one reference must set `must_surface=true` with `applies_to[]`, concrete `required_actions[]`, and a usable `locator`.
7. Approved contracts need concrete grounding from an anchor, reference, prior output, or baseline; never fabricate missing evidence.

- `project_contract` must be a JSON object whose `schema_version` is the integer `1`.
- Hard-schema fields must be model-visible before validation: `scope.question`, non-empty `scope.in_scope`, `context_intake`, and `uncertainty_markers` are not inferred from prose.
- Include at least one observable, claim, or deliverable.
- `scope.in_scope` must name at least one boundary or objective; `context_intake` must be a non-empty object whose anchor fields (`must_read_refs`, `must_include_prior_outputs`, `user_asserted_anchors`, `known_good_baselines`, `context_gaps`, `crucial_inputs`) keep concrete handles that can be re-found later. Placeholder-only text such as `TBD` or `unknown` does not satisfy grounding.
- `context_intake`, `approach_policy`, and `uncertainty_markers` must each remain objects and never collapse to strings or lists.
- `uncertainty_markers.weakest_anchors` and `uncertainty_markers.disconfirming_observations` must both be non-empty arrays.
- When references appear before approval and grounding is still pending, at least one anchor must set `must_surface: true`. Each such reference needs a concrete `locator`, `applies_to[]` coverage, non-empty `required_actions[]`, and any project-local paths must resolve once `project_root` is available.
- Canonical IDs and other required string fields are trimmed before validation; trimmed blanks and whitespace-only duplicates are invalid.

### Closed Schema And List Shape

- The `project_contract` schema is closed at every level; unknown keys are hard errors in strict validation. Salvage/repair flows may drop unknown keys while surfacing recoverable findings.
- List-shaped fields must stay arrays, even when they contain a single entry. Salvage/repair may normalize some list-shape drift, blank items, or case drift with explicit findings; strict validation still fails malformed shapes, blanks, or duplicates after trimming.
- The following sections always store arrays of objects; never substitute strings:
  - `observables[]` — `{ "id", "name", "kind", "definition", "regime?", "units?" }`
  - `claims[]` — `{ "id", "statement", "claim_kind", "observables[]", "deliverables[]", "acceptance_tests[]", "references[]", "parameters[]", "hypotheses[]", "quantifiers[]", "conclusion_clauses[]", "proof_deliverables[]" }`
  - `deliverables[]` — `{ "id", "kind", "path?", "description", "must_contain[]" }`
  - `acceptance_tests[]` — `{ "id", "subject", "kind", "procedure", "pass_condition", "evidence_required[]", "automation" }`
  - `references[]` — `{ "id", "kind", "locator", "aliases[]", "role", "why_it_matters", "applies_to[]", "carry_forward_to[]", "must_surface": true|false, "required_actions[]" }`
  - `forbidden_proxies[]` — `{ "id", "subject", "proxy", "reason" }`
  - `links[]` — `{ "id", "source", "target", "relation", "verified_by[]" }`

### Proof-bearing claims

Treat a claim as proof-bearing whenever any of the following is true:
- `claim_kind` is `theorem`, `lemma`, `corollary`, `proposition`, or `claim`.
- The statement is theorem-like (`prove/show that`, explicit `for all` / `exists`, or uniqueness language).
- Any proof field is already populated (`parameters`, `hypotheses`, `quantifiers`, `conclusion_clauses`, or `proof_deliverables`).
- `observables[]` references a `proof_obligation`.

When that applies, require:
- `parameters`, `hypotheses`, `quantifiers`, `conclusion_clauses`, and `proof_deliverables` remain visible and non-empty.
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
- `claims[].proof_deliverables[]` must be non-empty and reference declared deliverables.
- `claims[].parameters[]`, `claims[].hypotheses[]`, and `claims[].conclusion_clauses[]` must each be non-empty.
- `claims[].acceptance_tests[]` must include at least one proof-specific kind (`proof_hypothesis_coverage`, `proof_parameter_coverage`, `proof_quantifier_domain`, `claim_to_proof_alignment`, `lemma_dependency_closure`, or `counterexample_search`).
- Include `kind: claim_to_proof_alignment` when the proof artifact must map the theorem-like claim to the named hypotheses, parameters, and conclusion clauses.
- `claims[].quantifiers[]` is optional but, when present, must remain a list.

### Shared Grounding And Linkage Rules

@{GPD_INSTALL_DIR}/templates/project-contract-grounding-linkage.md

## Contract Addendum Guidance

When you append a contract addendum for the `draft`, `approved`, or `proof` stage, keep it compact:
- `draft` addenda should note the missing gating anchors, blockers, or unresolved questions that keep the contract unapproved.
- `approved` addenda should summarize the approved scope, decisive anchors/baselines, and the deliverables or acceptance tests that carry the approval.
- `proof` addenda should list the proof-specific claim, deliverables, acceptance tests, and metadata that justify the proof stage.
Limit each addendum to a status label plus one or two short bullets so the schema remains the authoritative source of truth; use this template for the detailed fields.

proof-bearing claims must keep `parameters`, `hypotheses`, `quantifiers`, `conclusion_clauses`, and `proof_deliverables` visible

Project contracts must include at least one observable, claim, or deliverable.

include an acceptance test with `kind: claim_to_proof_alignment`

If `references[]` is present before approval and grounding is not already concrete, at least one reference must set `must_surface: true`.

Every `must_surface: true` reference needs a concrete `locator` and concrete `applies_to[]` coverage

Project-local paths in `locator` or `applies_to[]` evidence must resolve when `project_root` is available.
