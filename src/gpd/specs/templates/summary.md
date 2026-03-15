---
template_version: 1
---

# Summary Template

Template for `.gpd/phases/XX-name/{phase}-{plan}-SUMMARY.md` - phase completion documentation.

---

## Summary Depth Selection

This single template covers all summary depths. The `depth` field in frontmatter controls which sections are required:

| Depth | When to Use | Sections Required |
|-------|------------|-------------------|
| **minimal** | Convention setup, tool configuration, single clear result | Performance, Key Results, Task Commits, Next Phase Readiness |
| **standard** | Simple calculations, setup phases, straightforward results | + Equations Derived, Approximations, Validations, Decisions, Deviations |
| **full** (default) | Most plans: derivations, code, and verification | + Key Quantities table, Files, Figures, Issues, Open Questions |
| **complex** | Multi-step derivations, parameter sweeps, extensive validation | + Cross-Phase Dependencies, Convention Changes, full deviation detail |

**Default to full** unless the plan is clearly simple enough for a lighter variant.

---

## File Template

Not all frontmatter fields are required. Minimum required: `phase`, `plan`, `depth`, `provides`, `completed`. All other fields are optional and should be populated as relevant.

**Contract-backed summaries:** if the source PLAN has a `contract` block, the SUMMARY must also carry `plan_contract_ref`, `contract_results`, and any decisive `comparison_verdicts`. `contract_results` is the authoritative machine-readable outcome ledger.
Keep this ledger user-visible: record what claim was established, what artifact exists, and what decisive comparison passed or failed. Do not use it to log administrative progress such as "ran verifier" or "completed task."
Use `@{GPD_INSTALL_DIR}/templates/contract-results-schema.md` as the schema source of truth for these fields. If `contract_results` or `comparison_verdicts` are present, `plan_contract_ref` is also required. If a decisive comparison is required, omitting its `comparison_verdicts` entry is a validation failure, not a stylistic omission.
Every declared claim, deliverable, acceptance test, reference, and forbidden proxy ID from the source PLAN contract must appear in the matching `contract_results` section. Use explicit statuses like `not_attempted`, `missing`, `not_applicable`, or `unresolved` instead of silently omitting contract IDs.

```markdown
---
phase: XX-name
plan: YY
depth: minimal|standard|full|complex  # Controls which sections to include (default: full)
one-liner: "[Substantive one-liner describing outcome — NOT 'phase complete' or 'derivation finished']"
subsystem (optional):
  [
    primary category: derivation,
    computation,
    simulation,
    analysis,
    validation,
    literature,
    formalism,
    numerics,
    etc.,
  ]
tags (optional):
  [
    searchable physics: hamiltonian,
    perturbation-theory,
    monte-carlo,
    feynman-diagrams,
    renormalization,
    DFT,
    lattice,
  ]

# Dependency graph
requires:
  - phase: [prior phase this depends on]
    provides: [what that phase derived/computed that this uses]
provides:
  - [bullet list of what this phase derived/computed/validated]
affects: [list of phase names or keywords that will need this context]

# Physics tracking
methods:
  added: [techniques/tools introduced in this phase]
  patterns: [computational/analytical patterns established]

key-files:
  created: [important files created]
  modified: [important files modified]

key-decisions:
  - "Decision 1"
  - "Decision 2"

patterns-established:
  - "Pattern 1: description"
  - "Pattern 2: description"

# Conventions used (checked by regression-check for cross-phase consistency)
conventions:
  - "hbar = 1"
  - "metric = (+,-,-,-)"
  - "Fourier = e^{-ikx} forward"

# Canonical contract outcome ledger (required when source PLAN has a contract)
plan_contract_ref (required when `contract_results` or `comparison_verdicts` are present): ".gpd/phases/XX-name/{phase}-{plan}-PLAN.md#/contract"
contract_results (required for contract-backed plans):
  # Every ID declared in the PLAN contract must appear in its matching section below.
  claims:
    claim-id:
      status: passed|partial|failed|blocked|not_attempted
      summary: "[what was actually established in user-visible terms]"
      linked_ids: [deliverable-id, acceptance-test-id, reference-id]
      evidence:
        - verifier: gpd-verifier
          method: benchmark reproduction
          confidence: high
          claim_id: claim-id
          deliverable_id: deliverable-id
          acceptance_test_id: acceptance-test-id
          reference_id: reference-id
          evidence_path: ".gpd/phases/XX-name/{phase}-VERIFICATION.md"
  deliverables:
    deliverable-id:
      status: passed|partial|failed|blocked|not_attempted
      path: path/to/artifact
      summary: "[what artifact exists and why it matters]"
      linked_ids: [claim-id, acceptance-test-id]
  acceptance_tests:
    acceptance-test-id:
      status: passed|partial|failed|blocked|not_attempted
      summary: "[what decisive test actually happened and what it showed]"
      linked_ids: [claim-id, deliverable-id, reference-id]
  references:
    reference-id:
      status: completed|missing|not_applicable
      completed_actions: [read, use, compare, cite]
      missing_actions: []
      summary: "[how the anchor was surfaced for a visible claim]"
  forbidden_proxies:
    forbidden-proxy-id:
      status: rejected|violated|unresolved|not_applicable
      notes: "[why this proxy was or was not allowed]"
  uncertainty_markers:
    weakest_anchors: []
    unvalidated_assumptions: []
    competing_explanations: []
    disconfirming_observations: []

# Decisive comparison verdict ledger
# Required whenever a contract-backed claim / deliverable / acceptance test depends on a decisive comparison.
comparison_verdicts (required when a decisive comparison was required or attempted):
  - subject_id: claim-id
    subject_kind: claim|deliverable|acceptance_test|reference|artifact|other
    subject_role: decisive|supporting|supplemental|other
    reference_id: reference-id
    comparison_kind: benchmark|prior_work|experiment|cross_method|baseline|other
    metric: relative_error
    threshold: "<= 0.01"
    verdict: pass|tension|fail|inconclusive
    recommended_action: "[what to do next]"
    notes: "[optional context]"

[When a decisive comparison is required by the contract, omitting the corresponding `comparison_verdicts` entry makes the summary incomplete. If the check is still open, emit `verdict: inconclusive` or `verdict: tension` instead of omitting the entry.]

# Metrics
duration: Xmin
completed: YYYY-MM-DD
---

# Phase [X]: [Name] Summary

**[Substantive one-liner describing outcome - NOT "phase complete" or "derivation finished"]**

## Performance

- **Duration:** [time] (e.g., 23 min, 1h 15m)
- **Started:** [ISO timestamp]
- **Completed:** [ISO timestamp]
- **Tasks:** [count completed]
- **Files modified:** [count]

## Key Results

- [Most important result: equation, numerical value, or validated relationship]
- [Second key result]
- [Third if applicable]

## Task Commits

Each task was committed atomically:

1. **Task 1: [task name]** - `abc123f` (derive/compute/validate/simplify)
2. **Task 2: [task name]** - `def456g` (derive/compute/validate/simplify)
3. **Task 3: [task name]** - `hij789k` (derive/compute/validate/simplify)

**Plan metadata:** `lmn012o` (docs: complete plan)

_Note: Validation tasks may have multiple commits (derive -> compute -> cross-check)_

## Files Created/Modified

- `path/to/derivation.py` - What it computes
- `path/to/notebook.ipynb` - What it analyzes

## Next Phase Readiness

[What's ready for next phase; key quantity available for downstream use]

## Contract Coverage

- Claim IDs advanced: [claim-id -> status]
- Deliverable IDs produced: [deliverable-id -> path/status]
- Acceptance test IDs run: [acceptance-test-id -> status]
- Reference IDs surfaced: [reference-id -> actions completed]
- Forbidden proxies rejected or violated: [proxy-id -> status]
- Decisive comparison verdicts: [subject-id -> verdict]

<!-- depth:minimal stops here. Sections below require depth:standard or higher. -->

## Equations Derived

[Central equations produced in this phase, in LaTeX notation.
Number equations for cross-referencing in downstream phases.]

**Eq. ({phase}.1):**

$$
[key equation 1]
$$

**Eq. ({phase}.2):**

$$
[key equation 2]
$$

[Use the convention Eq. (phase.N) for cross-referencing: e.g., Eq. (02.3) refers to the 3rd equation in Phase 2. This enables unambiguous references across phases and in the final manuscript.]

## Validations Completed

- [Limiting case checked and result]
- [Numerical cross-check against known result]
- [Dimensional analysis confirmation]

## Decisions & Deviations

[Key decisions (approximation scheme, notation, method choice) or "None - followed plan as specified"]
[Minor deviations if any, or "None"]

## Open Questions

- [Unresolved question surfaced during this phase]

<!-- depth:standard stops here. Sections below require depth:full or higher. -->

## Key Quantities and Uncertainties

[Record every numerical output of this phase with its uncertainty. Downstream phases that use these values must propagate the stated uncertainties.]

| Quantity                     | Symbol | Value     | Uncertainty  | Source                    | Valid Range |
| ---------------------------- | ------ | --------- | ------------ | ------------------------- | ----------- |
| {e.g., Critical temperature} | {T_c}  | {0.893}   | {+/- 0.005}  | {finite-size scaling fit} | {L >= 32}   |
| {e.g., Ground state energy}  | {E_0}  | {-0.4327} | {+/- 0.0003} | {Lanczos convergence}     | {N >= 50}   |

[**Source** describes how the uncertainty was estimated: statistical (MC sampling, bootstrap), systematic (finite-size, truncation, discretization), analytical (series truncation, approximation error), or combined. **Valid Range** states the parameter regime where this value and its uncertainty apply.]

## Approximations Used

| Approximation              | Valid When        | Error Estimate | Breaks Down At |
| -------------------------- | ----------------- | -------------- | -------------- |
| [e.g., Born approximation] | [coupling g << 1] | [O(g^2)]       | [g ~ 1]        |

## Figures Produced

| Figure         | File              | Description     | Key Feature                                           |
| -------------- | ----------------- | --------------- | ----------------------------------------------------- |
| Fig. {phase}.1 | `path/to/fig.pdf` | [What it shows] | [What to look for: e.g., "linear regime for q < 0.1"] |

[Use convention Fig. (phase.N) for cross-referencing. Figures should be publication-quality: labeled axes with units, legend, appropriate font size.]

## Decisions Made

[Key decisions with brief rationale, or "None - followed plan as specified"]

## Deviations from Plan

[If no deviations: "None - plan executed exactly as written"]

[If deviations occurred:]

### Auto-fixed Issues

**1. [Rule X - Category] Brief description**

- **Found during:** Task [N] ([task name])
- **Issue:** [What was wrong]
- **Fix:** [What was done]
- **Files modified:** [file paths]
- **Verification:** [How it was verified]
- **Committed in:** [hash] (part of task commit)

[... repeat for each auto-fix ...]

---

**Total deviations:** [N] auto-fixed ([breakdown by rule])
**Impact on plan:** [Brief assessment - e.g., "All auto-fixes necessary for correctness. No scope creep."]

## Issues Encountered

[Problems and how they were resolved, or "None"]

[Note: "Deviations from Plan" documents unplanned work that was handled automatically via deviation rules. "Issues Encountered" documents problems during planned work that required problem-solving.]

## User Setup Required

[If USER-SETUP.md was generated:]
**External tools or data require manual configuration.** See [{phase}-USER-SETUP.md](./{phase}-USER-SETUP.md) for:

- Environment variables to add
- Data files to obtain
- Computational resources to configure

[If no USER-SETUP.md:]
None - no external configuration required.

<!-- depth:full stops here. Sections below require depth:complex. -->

## Derivation Summary

### Starting Point

[Initial assumptions, Lagrangian/Hamiltonian, or setup equations]

$$
[starting equation]
$$

### Intermediate Steps

[Key intermediate results that may be reused or referenced]

1. **[Step name]:** [Brief description of what was done]

   $$
   [intermediate result]
   $$

2. **[Step name]:** [Brief description]
   $$
   [intermediate result]
   $$

### Final Result

$$
[final derived equation]
$$

[Physical interpretation: what this equation tells us, regime of validity, key parameters]

## Cross-Phase Dependencies

### Results This Phase Provides To Later Phases

| Result                        | Used By Phase        | How                                |
| ----------------------------- | -------------------- | ---------------------------------- |
| {e.g., Exact energy spectrum} | {Phase 3: Transport} | {Input to Kubo formula evaluation} |

### Results This Phase Consumed From Earlier Phases

| Result                              | From Phase           | Verified Consistent                            |
| ----------------------------------- | -------------------- | ---------------------------------------------- |
| {e.g., Hamiltonian matrix elements} | {Phase 1: Formalism} | {Yes - dimensions match, symmetries preserved} |

### Convention Changes

| Convention                               | Previous | This Phase | Reason |
| ---------------------------------------- | -------- | ---------- | ------ |
| {e.g., None — all conventions preserved} |          |            |        |

---

_Phase: XX-name_
_Completed: [date]_
```

<frontmatter_guidance>
**Purpose:** Enable automatic context assembly via dependency graph. Frontmatter makes summary metadata machine-readable so plan-phase can scan all summaries quickly and select relevant ones based on dependencies.

**Fast scanning:** Frontmatter is first ~25 lines, cheap to scan across all summaries without reading full content.

**Dependency graph:** `requires`/`provides`/`affects` create explicit links between phases, enabling transitive closure for context selection. In physics, dependencies are often equations or validated results from prior phases.

**Subsystem (optional):** Primary categorization (derivation, computation, simulation, analysis, validation, literature, formalism, numerics) for detecting related phases.

**Tags (optional):** Searchable physics keywords (techniques, formalisms, tools) for methodology awareness.

**Key-files:** Important files for @context references in PLAN.md.

**Patterns:** Established conventions future phases should maintain (notation, units, approximation schemes).

**Population:** Frontmatter is populated during summary creation in execute-plan.md. See `<step name="create_summary">` for field-by-field guidance.
</frontmatter_guidance>

<one_liner_rules>
The one-liner MUST be substantive:

**Good:**

- "Derived RG flow equations for phi-4 theory to two-loop order with MS-bar scheme"
- "Computed ground-state energy of 2D Ising model via transfer matrix, validated against Onsager"
- "Established Hamiltonian formalism for coupled oscillators with dissipation using Caldeira-Leggett model"

**Bad:**

- "Phase complete"
- "Derivation finished"
- "Calculation done"
- "All tasks done"

The one-liner should tell someone what physics was actually accomplished.
</one_liner_rules>

<example>
```markdown
# Phase 1: Effective Hamiltonian Summary

**Derived effective low-energy Hamiltonian for bilayer graphene via Schrieffer-Wolff transformation, validated against tight-binding numerics**

## Performance

- **Duration:** 45 min
- **Started:** 2025-01-15T14:22:10Z
- **Completed:** 2025-01-15T15:07:33Z
- **Tasks:** 4
- **Files modified:** 6

## Key Results

- Effective 2-band Hamiltonian captures low-energy physics within 2% of full 4-band model
- Trigonal warping corrections become significant above 10 meV
- Berry phase of 2pi confirmed for massive Dirac fermions

## Equations Derived

$$
H_{\text{eff}} = -\frac{1}{2m^*}\begin{pmatrix} 0 & (p_x - ip_y)^2 \\ (p_x + ip_y)^2 & 0 \end{pmatrix} + \Delta\sigma_z
$$

$$
m^* = \frac{\gamma_1}{2v_F^2} \approx 0.054\, m_e
$$

## Validations Completed

- Monolayer limit (gamma_1 -> infinity): recovers linear Dirac spectrum
- Effective mass matches experimental ARPES value within 5%
- Berry phase integral yields 2pi numerically

## Files Created/Modified

- `derivations/schrieffer_wolff.py` - Symbolic SW transformation using sympy
- `numerics/tight_binding_4band.py` - Full tight-binding diagonalization
- `notebooks/comparison.ipynb` - Side-by-side band structure comparison
- `results/effective_hamiltonian.tex` - LaTeX writeup of derivation

## Decisions Made

- Used Schrieffer-Wolff instead of Lowdin partitioning (cleaner for this block structure)
- Kept trigonal warping as separate perturbation rather than folding into H_eff
- Natural units with hbar=1 throughout; restored for final expressions

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added Hermiticity check for effective Hamiltonian**

- **Found during:** Task 2 (Schrieffer-Wolff implementation)
- **Issue:** Plan didn't specify Hermiticity verification - non-Hermitian H_eff would invalidate all downstream results
- **Fix:** Added symbolic Hermiticity check after each order of perturbation theory
- **Files modified:** derivations/schrieffer_wolff.py
- **Verification:** H_eff - H_eff^dagger = 0 symbolically at each order
- **Committed in:** abc123f (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Essential correctness check. No scope creep.

## Issues Encountered

- Sympy simplification hung on fourth-order terms - restricted to second order as planned, added numerical check instead

## Open Questions

- Does trigonal warping qualitatively change the Landau level spectrum?
- Spin-orbit coupling effects at low energy - relevant for next phase?

## Next Phase Readiness

- Effective Hamiltonian ready for Landau level computation
- Berry phase result feeds into Hall conductivity calculation
- Need to decide on disorder model before transport phase

---

_Phase: 01-effective-hamiltonian_
_Completed: 2025-01-15_

```
</example>

<guidelines>
**Depth selection:** Default to `full`. Use `minimal` only for pure setup phases (convention setup, tool config) with a single clear result. Use `complex` for multi-step derivations, parameter sweeps, or plans with cross-phase dependencies. When in doubt, use `full`.

**Frontmatter:** Required fields: `phase`, `plan`, `depth`, `provides`, `completed`. Populate optional fields (`subsystem`, `tags`, `requires`, `affects`, `methods`, `key-files`, `key-decisions`, `patterns-established`, `duration`) as relevant. For contract-backed summaries, `contract_results` is required, `comparison_verdicts` is required whenever a decisive comparison was required or attempted, and `plan_contract_ref` is required whenever either ledger is present. Enables automatic context assembly for future planning.

**One-liner:** Must be substantive. "Derived RG flow equations for phi-4 theory to two-loop order" not "Derivation finished".

**Key Results:** The most important physics outcomes - equations, numerical values, validated relationships.

**Equations Derived:** Central equations in LaTeX. These are the deliverables of a physics phase.

**Validations Completed:** Limiting cases, cross-checks, dimensional analysis. Physics results without validation are untrustworthy.

**Open Questions:** Unresolved issues surfaced during the phase. Critical for planning subsequent phases.

**Decisions section:**
- Key decisions made during execution with rationale (approximation schemes, notation choices, numerical methods)
- Extracted to STATE.md accumulated context
- Use "None - followed plan as specified" if no deviations

**After creation:** STATE.md updated with position, decisions, issues.
</guidelines>
