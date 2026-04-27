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

The `project_contract` field stores the canonical ResearchContract object or `null`. The raw object schema and contract rules are single-sourced in:

@{GPD_INSTALL_DIR}/templates/project-contract-schema.md

This state schema intentionally includes that template instead of restating the contract payload inline. Keep prompt-authored contract validation and persistence guidance there so `state-json-schema.md` remains the top-level `GPD/state.json` container schema.

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
