---
template_version: 1
purpose: Canonical schema for GPD/state.json — the machine-readable research state sidecar
---

# state.json Schema

Canonical schema for `GPD/state.json`. This file is the authoritative machine-readable state. STATE.md is a human-readable view generated from it.

Source of truth: `default_state_dict()` in `gpd.core.state`.

---

## Top-Level Fields

| Field | Type | Default | Purpose | Authoritative? |
|-------|------|---------|---------|----------------|
| `_version` | `integer` | `1` | Schema version for future evolution | Metadata |
| `_synced_at` | `string (ISO 8601)` | — | Last sync timestamp | Metadata |
| `project_reference` | `object` | see below | Pointer to PROJECT.md with key fields | Derived from PROJECT.md |
| `project_contract` | `ResearchContract \| null` | `null` | Canonical machine-readable scoping and anchor contract | **Authoritative** (JSON-only, stage-0+ contract flow) |
| `position` | `object` | see below | Current phase/plan/status | **Authoritative** (synced to STATE.md) |
| `active_calculations` | `string[]` | `[]` | Work in progress descriptions | STATE.md unless JSON has structured data |
| `intermediate_results` | `ResultObject[] \| string[]` | `[]` | Partial results with equations | **Authoritative** (structured objects from `result add`) |
| `open_questions` | `string[]` | `[]` | Physics questions that emerged | STATE.md unless JSON has structured data |
| `performance_metrics` | `{ rows: MetricRow[] }` | `{ rows: [] }` | Throughput tracking | Synced from STATE.md |
| `decisions` | `DecisionObject[]` | `[]` | Accumulated decisions with rationale | Synced from STATE.md |
| `approximations` | `ApproximationObject[]` | `[]` | Active approximations with validity | **Authoritative** (JSON-only, from `approximation add`) |
| `convention_lock` | `ConventionLock` | see below | Locked physics conventions | **Authoritative** (JSON-only, from `convention set`) |
| `propagated_uncertainties` | `UncertaintyObject[]` | `[]` | Uncertainty propagation tracking | **Authoritative** (JSON-only, from `uncertainty add`) |
| `pending_todos` | `string[]` | `[]` | Ideas captured via gpd:add-todo | Synced from todos/ |
| `blockers` | `string[]` | `[]` | Active blockers/concerns | Synced from STATE.md |
| `continuation` | `ContinuationObject` | see below | Durable canonical continuation authority for session handoff and recorded machine identity | **Authoritative** (JSON-only) |

### Authoritative vs Derived

Fields marked **Authoritative** exist only in state.json (not representable in STATE.md markdown). When `sync_state_json()` merges markdown into JSON, it preserves these fields. If state.json is lost, these fields are irrecoverable from STATE.md alone — hence `state.json.bak` exists for crash recovery.

---

## Object Schemas

### `project_reference`

```json
{
  "project_md_updated": "2026-03-15",
  "core_research_question": "What is the critical temperature of the 2D Ising model?",
  "current_focus": "Phase 3: Finite-size scaling analysis"
}
```

| Field | Type | Written By |
|-------|------|-----------|
| `project_md_updated` | `string \| null` | Workflows (after updating PROJECT.md) |
| `core_research_question` | `string \| null` | `gpd:new-project` |
| `current_focus` | `string \| null` | Phase transitions, `gpd state update` |

### `project_contract`

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

Stored as the canonical machine-readable contract once Stage 1 wiring is complete. Stage 0 freezes the field and model shape so later workflows can write to it safely.

Preferred validation + persistence path for prompt-authored contracts:

```bash
printf '%s\n' "$PROJECT_CONTRACT_JSON" | gpd --raw validate project-contract - --mode approved
printf '%s\n' "$PROJECT_CONTRACT_JSON" | gpd state set-project-contract -
```

The stdin path is canonical because it keeps the exact approved JSON payload in-memory across validation and persistence. Do not tell the model to round-trip through a temporary file unless a human explicitly chose that workflow.

#### Project Contract Object Rules

The `project_contract` value itself must be a JSON object. Do not replace it with prose, a list, or a string.

`schema_version` must be the integer `1`. Unsupported schema versions are invalid.

Project contracts must include at least one observable, claim, or deliverable.

`uncertainty_markers.weakest_anchors` and `uncertainty_markers.disconfirming_observations` must both be non-empty.

Canonical IDs and other required string fields are trimmed before validation. Blank-after-trim values are invalid, and duplicates that differ only by surrounding whitespace still collide after normalization.

`scope.in_scope` must name at least one project boundary or objective.

`context_intake` must not be empty. At least one of `must_read_refs`, `must_include_prior_outputs`, `user_asserted_anchors`, `known_good_baselines`, `context_gaps`, or `crucial_inputs` must carry a non-empty item, and the grounding fields must be concrete enough to re-find later.
`context_intake`, `approach_policy`, and `uncertainty_markers` are JSON objects when present; do not collapse them to strings or lists.
Closed-vocabulary enum fields use the exact lowercase literals shown here. Case drift such as `Theorem`, `Benchmark`, or `Read` fails strict validation.

#### Closed Schema And List Shape

The `project_contract` schema is closed. Do not invent extra keys at the top level or inside nested objects. Only the fields defined here are valid.

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
- `claims[].proof_deliverables[]` must be non-empty and contain only `deliverables[].id` values.
- `claims[].parameters[]`, `claims[].hypotheses[]`, and `claims[].conclusion_clauses[]` must each be non-empty.
- `claims[].acceptance_tests[]` must include at least one proof-specific test kind (`proof_hypothesis_coverage`, `proof_parameter_coverage`, `proof_quantifier_domain`, `claim_to_proof_alignment`, `lemma_dependency_closure`, or `counterexample_search`).
- `claims[].quantifiers[]` is optional but, when present, must stay a list (not a scalar string).

### Shared Grounding And Linkage Rules

If a project contract has any `references[]` and does not already carry concrete prior-output, user-anchor, or baseline grounding, at least one reference must set `must_surface: true`.

`must_include_prior_outputs[]` entries should be explicit project-artifact paths or filenames that already exist inside the current project root. If `project_root` is unavailable, treat them as non-grounding until the file can be resolved against a concrete root.

Placeholder or `TBD` text does not count as concrete grounding. Explicit missing-anchor notes preserve uncertainty, but they do not satisfy approved-mode grounding on their own.

Keep these exact grounding reminders visible in the raw schema surface as well:

- Need grounding before the decisive anchor is chosen.
- Decisive target not yet chosen before planning can proceed.
- If other grounding already exists, a missing `must_surface: true` reference is still a warning that should be repaired, not a silent ignore.

@{GPD_INSTALL_DIR}/templates/project-contract-grounding-linkage.md

### `position`

```json
{
  "current_phase": "03",
  "current_phase_name": "Finite-size scaling analysis",
  "total_phases": 7,
  "current_plan": "2",
  "total_plans_in_phase": 3,
  "status": "Executing",
  "last_activity": "2026-03-15",
  "last_activity_desc": "Completed Monte Carlo thermalization",
  "progress_percent": 42,
  "paused_at": null
}
```

| Field | Type | Written By | Read By |
|-------|------|-----------|---------|
| `current_phase` | `string \| null` | `gpd phase complete`, `state update` | All agents (via init) |
| `current_phase_name` | `string \| null` | `gpd phase complete`, `state update` | All agents (via init) |
| `total_phases` | `integer \| null` | `gpd phase add/remove` | Progress display |
| `current_plan` | `string \| integer \| null` | `gpd state advance` | Executor, orchestrators |
| `total_plans_in_phase` | `integer \| null` | Plan-phase orchestrator | Executor, state advance |
| `status` | `string \| null` | Multiple commands | All agents |
| `last_activity` | `string \| null` | Most state-modifying commands | Session display |
| `last_activity_desc` | `string \| null` | Executor, workflows | Session display |
| `progress_percent` | `integer` | `gpd state update-progress` | Progress display |
| `paused_at` | `string \| null` | `gpd:pause-work`, `gpd:resume-work` | Resume workflow |

**Valid `status` values:**

```
Not started, Planning, Researching, Ready to execute, Executing,
Paused, Phase complete — ready for verification,
Verifying, Verified, Complete, Blocked, Ready to plan, Milestone complete
```

**Phase ID format:** Top-level segment is zero-padded, sub-phases keep natural numeric width: `"03"`, `"03.1"`, `"03.1.2"`. See `phase_normalize()`.

### `convention_lock` (18 standard fields + custom)

```json
{
  "metric_signature": "(-,+,+,+)",
  "fourier_convention": "∫dk/(2π) e^{ikx}",
  "natural_units": "ħ=c=k_B=1",
  "gauge_choice": "Lorenz gauge",
  "regularization_scheme": "Dimensional regularization, d=4-2ε",
  "renormalization_scheme": "MS-bar at μ = m_Z",
  "coordinate_system": "Cartesian with x⁰=t",
  "spin_basis": "Pauli matrices in standard basis",
  "state_normalization": "⟨p|p'⟩ = (2π)³2E_p δ³(p-p')",
  "coupling_convention": "g² includes 1/(4π) factor",
  "index_positioning": "covariant derivatives ∂_μ with lower index",
  "time_ordering": "T-product with Feynman iε",
  "commutation_convention": "[x_i, p_j] = iħδ_{ij}",
  "levi_civita_sign": "ε^{0123} = +1",
  "generator_normalization": "Tr(T^a T^b) = 1/2 δ^{ab}",
  "covariant_derivative_sign": "D_μ = ∂_μ + i g A_μ",
  "gamma_matrix_convention": "Dirac basis with γ^5 = iγ^0γ^1γ^2γ^3",
  "creation_annihilation_order": "normal ordering puts a† left of a",
  "custom_conventions": {
    "lattice_spacing": "a = 1 (dimensionless)",
    "boundary_conditions": "periodic in all directions"
  }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `metric_signature` | `string \| null` | `null` | Spacetime metric sign convention |
| `fourier_convention` | `string \| null` | `null` | Fourier transform convention (where 2π lives) |
| `natural_units` | `string \| null` | `null` | Which constants are set to 1 |
| `gauge_choice` | `string \| null` | `null` | Gauge fixing condition |
| `regularization_scheme` | `string \| null` | `null` | How divergences are regulated |
| `renormalization_scheme` | `string \| null` | `null` | Renormalization prescription |
| `coordinate_system` | `string \| null` | `null` | Coordinate choice and orientation |
| `spin_basis` | `string \| null` | `null` | Spinor/spin representation |
| `state_normalization` | `string \| null` | `null` | State vector normalization |
| `coupling_convention` | `string \| null` | `null` | How coupling constants are defined |
| `index_positioning` | `string \| null` | `null` | Up/down index conventions |
| `time_ordering` | `string \| null` | `null` | Time-ordering and iε prescription |
| `commutation_convention` | `string \| null` | `null` | Commutation/anticommutation relations |
| `levi_civita_sign` | `string \| null` | `null` | Orientation/sign convention for ε tensors |
| `generator_normalization` | `string \| null` | `null` | Lie-algebra generator trace normalization |
| `covariant_derivative_sign` | `string \| null` | `null` | Sign convention in covariant derivatives |
| `gamma_matrix_convention` | `string \| null` | `null` | Gamma-matrix basis and γ⁵ convention |
| `creation_annihilation_order` | `string \| null` | `null` | Operator ordering convention |
| `custom_conventions` | `object` | `{}` | Project-specific conventions (key-value) |

**Written by:** `gpd convention set <key> <value>`
**Read by:** gpd-executor (load_conventions), gpd-planner, gpd-consistency-checker, gpd-notation-coordinator, gpd-paper-writer

### `ResultObject` (intermediate_results)

```json
{
  "id": "R-03-01-lxk7a2b",
  "equation": "\\omega(k) = \\sqrt{k^2 + m^2}",
  "description": "Dispersion relation",
  "units": "energy",
  "validity": "k << \\Lambda",
  "phase": "03",
  "depends_on": ["R-02-01-m1k3f9c"],
  "verified": false,
  "verification_records": []
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `string` | Yes | Unique identifier (auto-format: `R-{phase}-{seq}-{suffix}`) |
| `equation` | `string \| null` | No | LaTeX equation string |
| `description` | `string` | Yes | Human-readable description |
| `units` | `string \| null` | No | Physical units of the result |
| `validity` | `string \| null` | No | Validity conditions/range |
| `phase` | `string \| null` | No | Phase that produced this result (same format as `position.current_phase`) |
| `depends_on` | `string[]` | No | IDs of results this depends on |
| `verified` | `boolean` | No | Whether verified by gpd-verifier |
| `verification_records` | `VerificationEvidence[]` | No | Structured provenance attached by `gpd result verify` |

**Written by:** `gpd result add`
**Read by:** gpd-executor (downstream phases), gpd-verifier, gpd-paper-writer

**Note:** Markdown-derived entries in this section may be plain strings instead of structured objects. Code handles both formats.

### `DecisionObject`

```json
{
  "phase": "3",
  "summary": "Chose dim-reg over cutoff",
  "rationale": "preserve gauge invariance"
}
```

| Field | Type | Required |
|-------|------|----------|
| `phase` | `string` | Yes (default: `"?"`) |
| `summary` | `string` | Yes |
| `rationale` | `string \| null` | No |

**Written by:** `gpd state add-decision`

### `ApproximationObject`

```json
{
  "name": "Perturbative expansion",
  "validity_range": "g << 1",
  "controlling_param": "coupling g",
  "current_value": "0.1",
  "status": "Valid"
}
```

| Field | Type | Required |
|-------|------|----------|
| `name` | `string` | Yes |
| `validity_range` | `string` | Yes |
| `controlling_param` | `string` | Yes |
| `current_value` | `string` | Yes |
| `status` | `string` | Yes — one of: `Valid`, `Marginal`, `Invalid` |

**Written by:** `gpd approximation add`

### `UncertaintyObject`

```json
{
  "quantity": "T_c",
  "value": "0.893",
  "uncertainty": "+/- 0.005",
  "phase": "Phase 2",
  "method": "finite-size scaling"
}
```

| Field | Type | Required |
|-------|------|----------|
| `quantity` | `string` | Yes |
| `value` | `string` | Yes |
| `uncertainty` | `string` | Yes |
| `phase` | `string` | Yes |
| `method` | `string` | Yes |

**Written by:** `gpd uncertainty add`

### `MetricRow`

```json
{
  "label": "Phase 3 P1",
  "duration": "2h30m",
  "tasks": "5",
  "files": "12"
}
```

### `ContinuationObject`

```json
{
  "schema_version": 1,
  "handoff": {
    "recorded_at": "2026-03-15T14:30:00.000Z",
    "stopped_at": "Phase 3, Plan 2, Task 4: MC thermalization",
    "resume_file": "GPD/phases/03-analysis/.continue-here.md"
  },
  "bounded_segment": null,
  "machine": {
    "recorded_at": "2026-03-15T14:30:00.000Z",
    "hostname": "builder-01",
    "platform": "Linux 6.1 x86_64"
  }
}
```

**Written by:** `gpd state record-session`, `save_state_markdown()`, `save_state_json()`

`continuation` is the durable canonical continuation payload in `state.json`. It is JSON-only and does not render as a separate markdown section. The STATE.md ``## Session Continuity`` block is a human-readable rendering of `continuation.handoff` plus `continuation.machine`; parsing STATE.md projects that block back into canonical continuation.

`continuation.handoff` is the canonical handoff block:

| Field | Type | Meaning |
|-------|------|---------|
| `recorded_at` | `string \| null` | Timestamp of the recorded handoff |
| `stopped_at` | `string \| null` | Human-readable stop location |
| `resume_file` | `string \| null` | Project-relative handoff artifact when available |

`state.json.continuation.bounded_segment` is the durable authoritative bounded-segment state stored in `state.json`. When present, it is the canonical bounded-segment resume source. The live execution head is derived from execution lineage and may be written to `GPD/observability/current-execution.json` for live status, but that status file does not replace the persisted canonical state. `gpd --raw resume` emits one canonical continuation view from `state.json.continuation`, execution lineage, and current handoff artifacts.

`continuation.machine` is the canonical recorded machine state:

| Field | Type | Meaning |
|-------|------|---------|
| `recorded_at` | `string \| null` | Timestamp when the machine identity was recorded |
| `hostname` | `string \| null` | Advisory host identity from the last session |
| `platform` | `string \| null` | Advisory platform string from the last session |

---

## Validation Rules

Run via `gpd state validate`. Current checks:

1. **state.json exists and parses** — not corrupt JSON
2. **STATE.md exists and parses** — valid markdown structure
3. **Position cross-check** — position fields match between JSON and MD
4. **Convention lock completeness** — reports unset conventions (warning, not error)
5. **No NaN values** — numeric fields (total_phases, total_plans_in_phase, progress_percent) must not be NaN
6. **Schema completeness** — all fields from `default_state_dict()` must be present at top level
7. **Status vocabulary** — status must be from VALID_STATUSES list (13 values)
8. **Phase ID format** — current_phase must match `\d{2}(\.\d+)*` pattern
9. **Phase range** — current_phase must not exceed total_phases when both are set
10. **Result ID uniqueness** — all `intermediate_results[].id` values must be unique
11. **Dependency validity** — `depends_on` references must point to existing result IDs

---

## Dual-Write Protocol

STATE.md and state.json are kept in sync:

1. **STATE.md → state.json**: `sync_state_json()` parses markdown, merges into existing JSON (preserving JSON-only fields)
2. **state.json → STATE.md**: `save_state_json()` calls `generate_state_markdown()` to regenerate markdown
3. **Crash recovery**: `state.json.bak` created after every successful write; state saves fail closed if the backup cannot be refreshed, and `load_state_json()` tries the backup before falling back to STATE.md when primary JSON is missing or blocked
4. **Atomic writes**: Uses intent-marker protocol (`.state-write-intent`) to detect and recover from interrupted writes
5. **Locking**: `file_lock()` context manager prevents concurrent writes (TOCTOU races)

### Authority hierarchy

```
state.json > state.json.bak > STATE.md
```

For JSON-only fields (convention_lock, approximations, propagated_uncertainties, structured intermediate_results): state.json is sole authority. STATE.md renders a lossy view (structured objects become flat bullet strings).

For position/decisions/blockers: STATE.md is the primary edit surface; state.json is synced from it.

---

## Agent Access Patterns

| Agent | Reads | Writes (via gpd CLI) |
|-------|-------|----------------------|
| **gpd-executor** | `convention_lock`, `position`, `intermediate_results` | `state advance`, `state update`, `result add`, `convention set` |
| **gpd-planner** | `convention_lock`, `position`, `decisions`, `blockers` | (reads only — orchestrator writes) |
| **gpd-verifier** | `convention_lock`, `position` | (reads only) |
| **gpd-debugger** | full state | `state add-blocker` |
| **gpd-consistency-checker** | `convention_lock`, `intermediate_results` | (reads only) |
| **gpd-notation-coordinator** | `convention_lock` | `convention set` |
| **gpd-paper-writer** | `convention_lock`, `intermediate_results`, `decisions` | (reads only) |
| **Orchestrators** | `position`, `continuation` | `state update`, `state patch`, `state advance`, `state record-session`, `state record-metric` |
