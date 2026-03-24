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
| `_version` | `integer` | `1` | Schema version for forward compatibility | Metadata |
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
| `pending_todos` | `string[]` | `[]` | Ideas captured via /gpd:add-todo | Synced from todos/ |
| `blockers` | `string[]` | `[]` | Active blockers/concerns | Synced from STATE.md |
| `session` | `SessionObject` | see below | Session continuity for resumption | Synced from STATE.md |

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
| `core_research_question` | `string \| null` | `/gpd:new-project` |
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
    "must_include_prior_outputs": ["GPD/phases/01-setup/01-01-SUMMARY.md"],
    "user_asserted_anchors": ["Recover known asymptotic limit from the accepted benchmark curve"],
    "known_good_baselines": ["Baseline derivation in notebook X"],
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
      "observables": ["obs-main"],
      "deliverables": ["deliv-main"],
      "acceptance_tests": ["test-main"],
      "references": ["Ref-01"]
    }
  ],
  "deliverables": [
    {
      "id": "deliv-main",
      "kind": "figure",
      "path": "paper/figures/benchmark-curve.pdf",
      "description": "Figure comparing the reproduced curve against the benchmark",
      "must_contain": ["benchmark overlay"]
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
printf '%s\n' "$PROJECT_CONTRACT_JSON" | gpd --raw validate project-contract -
printf '%s\n' "$PROJECT_CONTRACT_JSON" | gpd state set-project-contract -
```

The stdin path is canonical because it keeps the exact approved JSON payload in-memory across validation and persistence. Do not tell the model to round-trip through a temporary file unless a human explicitly chose that workflow.

#### Project Contract Object Rules

The `project_contract` value itself must be a JSON object. Do not replace it with prose, a list, or a string.

`schema_version` must be `1`. Unsupported schema versions are invalid.

Approved project contracts must include at least one observable, claim, or deliverable.

`uncertainty_markers.weakest_anchors` and `uncertainty_markers.disconfirming_observations` must both be non-empty.

Canonical IDs and other required string fields are trimmed before validation. Blank-after-trim values are invalid, and duplicates that differ only by surrounding whitespace still collide after normalization.

`scope.in_scope` must name at least one project boundary or objective.

The following fields always store arrays of objects, never arrays of plain strings:

- `observables[]` — `{ "id", "name", "kind", "definition", "regime?", "units?" }`
- `claims[]` — `{ "id", "statement", "observables[]", "deliverables[]", "acceptance_tests[]", "references[]" }`
- `deliverables[]` — `{ "id", "kind", "path?", "description", "must_contain[]" }`
- `acceptance_tests[]` — `{ "id", "subject", "kind", "procedure", "pass_condition", "evidence_required[]", "automation" }`
- `references[]` — `{ "id", "kind", "locator", "aliases[]", "role", "why_it_matters", "applies_to[]", "carry_forward_to[]", "must_surface", "required_actions[]" }`
- `forbidden_proxies[]` — `{ "id", "subject", "proxy", "reason" }`
- `links[]` — `{ "id", "source", "target", "relation", "verified_by[]" }`

If a project-contract reference sets `must_surface: true`, `required_actions[]` must not be empty.
`required_actions[]` uses the same closed action vocabulary enforced downstream in contract ledgers: `read`, `use`, `compare`, `cite`, `avoid`.

If a project contract has any `references[]` and does not already carry concrete prior-output, user-anchor, or baseline grounding, at least one reference must set `must_surface: true`. When that other grounding exists, a missing `must_surface: true` reference is still a warning that should be repaired, not a silent ignore.

If a project-contract reference sets `must_surface: true`, `applies_to[]` must not be empty.

Approved-mode grounding is field-specific:

- `must_include_prior_outputs[]` entries should be explicit project-artifact paths or filenames, such as `GPD/phases/.../*-SUMMARY.md` or `paper/main.tex`.
- `user_asserted_anchors[]` and `known_good_baselines[]` should name a concrete benchmark, baseline, reference, notebook, figure, dataset, or comparable anchor phrase. Single-token filler does not count.
- `Placeholder`, `TBD`, `TODO`, `unknown`, `unclear`, `none`, `n/a`, and `placeholder` remain non-grounding unless they are part of a genuinely missing-anchor blocker phrase.

#### Approved-Mode Grounding Rule

The approved-mode gate uses the exact rule:

`approved project contract requires at least one concrete anchor/reference/prior-output/baseline; explicit missing-anchor notes preserve uncertainty but do not satisfy approval on their own`

Placeholder or `TBD` text does not count as concrete grounding. That includes generic filler such as `TBD`, `TODO`, `unknown`, `unclear`, `none`, `n/a`, and `placeholder` when they are not attached to a real anchor.

#### Project Contract ID Linkage Rules

Every ID-like field must point to a declared object ID in the same contract:

- Do not reuse the same ID across `claims[]`, `deliverables[]`, `acceptance_tests[]`, or `references[]`; target resolution becomes ambiguous.
- `context_intake.must_read_refs[]` must contain `references[].id` values only.
- `references[].aliases[]` may store stable human-facing labels or citation strings that help canonicalize downstream anchor mentions.
- `claims[].observables[]` must contain `observables[].id` values only.
- `claims[].deliverables[]` must contain `deliverables[].id` values only.
- `claims[].acceptance_tests[]` must contain `acceptance_tests[].id` values only.
- `claims[].references[]` must contain `references[].id` values only.
- `acceptance_tests[].subject` must point to a `claims[].id` or `deliverables[].id`, never an observable ID or prose label.
- `acceptance_tests[].evidence_required[]` may point only to claim, deliverable, acceptance-test, or reference IDs.
- `references[].applies_to[]` must point to a claim ID or deliverable ID.
- `references[].carry_forward_to[]` is free-text workflow scope (for example `planning`, `verification`, `writing`) and must not be overloaded with claim or deliverable IDs.
- `forbidden_proxies[].subject` must point to a claim ID or deliverable ID.
- `links[].source` and `links[].target` may point only to claim, deliverable, acceptance-test, or reference IDs.
- `links[].verified_by[]` must contain `acceptance_tests[].id` values only.

#### Explicit Anchor-Gap Guidance

If the user does not know the decisive anchor yet, keep that uncertainty explicit instead of inventing a paper, reference, benchmark, or baseline. Put that blocker in `scope.unresolved_questions`, `context_intake.context_gaps`, or `uncertainty_markers.weakest_anchors`. Accepted phrasings include:

- `Which reference should serve as the decisive benchmark anchor?`
- `Benchmark reference not yet selected; still to identify the decisive anchor.`
- `Need grounding before the decisive anchor is chosen.`
- `Decisive target not yet chosen before planning can proceed.`
- `Baseline comparison is TBD before planning can proceed.`

These phrases are valid for preserving uncertainty when they point to a genuinely missing decisive anchor, but they do not satisfy approved-mode grounding on their own. Approved mode still needs a concrete reference, prior output, user anchor, or baseline elsewhere in the contract; placeholder-only wording does not count.

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
| `paused_at` | `string \| null` | `/gpd:pause-work`, `/gpd:resume-work` | Resume workflow |

**Valid `status` values:**

```
Not started, Planning, Researching, Ready to execute, Executing,
Paused, Phase complete — ready for verification,
Verifying, Complete, Blocked, Ready to plan, Milestone complete
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

### `SessionObject`

```json
{
  "last_date": "2026-03-15T14:30:00.000Z",
  "stopped_at": "Phase 3, Plan 2, Task 4: MC thermalization",
  "resume_file": "GPD/phases/03/.continue-here"
}
```

**Written by:** `gpd state record-session`, `/gpd:pause-work`

---

## Validation Rules

Run via `gpd state validate`. Current checks:

1. **state.json exists and parses** — not corrupt JSON
2. **STATE.md exists and parses** — valid markdown structure
3. **Position cross-check** — position fields match between JSON and MD
4. **Convention lock completeness** — reports unset conventions (warning, not error)
5. **No NaN values** — numeric fields (total_phases, total_plans_in_phase, progress_percent) must not be NaN
6. **Schema completeness** — all fields from `default_state_dict()` must be present at top level
7. **Status vocabulary** — status must be from VALID_STATUSES list (12 values)
8. **Phase ID format** — current_phase must match `\d{2}(\.\d+)*` pattern
9. **Phase range** — current_phase must not exceed total_phases when both are set
10. **Result ID uniqueness** — all `intermediate_results[].id` values must be unique
11. **Dependency validity** — `depends_on` references must point to existing result IDs

---

## Dual-Write Protocol

STATE.md and state.json are kept in sync:

1. **STATE.md → state.json**: `sync_state_json()` parses markdown, merges into existing JSON (preserving JSON-only fields)
2. **state.json → STATE.md**: `save_state_json()` calls `generate_state_markdown()` to regenerate markdown
3. **Crash recovery**: `state.json.bak` created after every successful write; `load_state_json()` tries backup before falling back to STATE.md
4. **Atomic writes**: Uses intent-marker protocol (`.state-write-intent`) to detect and recover from interrupted writes
5. **Locking**: `file_lock()` context manager prevents concurrent writes (TOCTOU races)

### Authority hierarchy

```
state.json > STATE.md > state.json.bak > STATE.md (regenerated from defaults)
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
| **Orchestrators** | `position`, `session` | `state update`, `state patch`, `state advance`, `state record-session`, `state record-metric` |
