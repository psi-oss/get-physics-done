---
template_version: 1
---

# Phase Prompt Template

> **Note:** Planning methodology is in `agents/gpd-planner.md`.
> This template defines the PLAN.md output format that the agent produces.

Template for `.planning/phases/XX-name/{phase}-{plan}-PLAN.md` - executable research phase plans optimized for parallel execution.

**Naming:** Use `{phase}-{plan}-PLAN.md` format (e.g., `01-02-PLAN.md` for Phase 1, Plan 2)

---

## File Template

```markdown
---
phase: XX-name
plan: NN
type: execute
wave: N # Execution wave (1, 2, 3...). Pre-computed at plan time.
depends_on: [] # Plan IDs this plan requires (e.g., ["01-01"]).
files_modified: [] # Files this plan modifies (notebooks, scripts, derivation docs).
autonomous: true # false if plan has checkpoints requiring user interaction
user_setup: [] # Human-required setup the agent cannot automate (see below)

# Goal-backward verification (derived during planning, verified after execution)
must_haves:
  truths: [] # Physics results that must be established for goal achievement
  artifacts: [] # Files that must exist with real content (not stubs)
  key_links: [] # Critical connections between artifacts (derivation -> code, code -> plot)
  uncertainties: [] # REQUIRED for plans producing numbers. Schema: {quantity, target_precision, method}
---

<objective>
[What this plan accomplishes]

Purpose: [Why this matters for the research program]
Output: [What artifacts will be created - derivations, code, plots, results]
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/execute-plan.md
@{GPD_INSTALL_DIR}/templates/summary.md
[If plan contains checkpoint tasks (type="checkpoint:*"), add:]
@{GPD_INSTALL_DIR}/references/checkpoints.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

# Only reference prior plan SUMMARYs if genuinely needed:

# - This plan uses results/expressions derived in a prior plan

# - Prior plan established a convention or approximation that affects this plan

# Do NOT reflexively chain: Plan 02 refs 01, Plan 03 refs 02...

[Relevant source files:]
@src/path/to/relevant.py
@derivations/path/to/relevant.tex
</context>

<tasks>

<task type="auto">
  <name>Task 1: [Action-oriented name]</name>
  <files>path/to/file.ext, another/file.ext</files>
  <action>[Specific research action - what to derive/compute/analyze, how to do it, what to avoid and WHY]</action>
  <verify>[Physics verification - dimensional analysis, limiting cases, comparison with known results]</verify>
  <done>[Measurable success criteria - quantitative where possible]</done>
</task>

<task type="auto">
  <name>Task 2: [Action-oriented name]</name>
  <files>path/to/file.ext</files>
  <action>[Specific research action]</action>
  <verify>[Physics verification]</verify>
  <done>[Success criteria]</done>
</task>

<!-- For checkpoint task examples and patterns, see @{GPD_INSTALL_DIR}/references/checkpoints.md -->
<!-- Key rule: Agent prepares all materials BEFORE human-verify checkpoints. User only reviews results. -->

<task type="checkpoint:decision" gate="blocking">
  <decision>[What needs deciding - e.g., which approximation scheme, which parameter regime]</decision>
  <context>[Why this decision matters for the physics]</context>
  <options>
    <option id="option-a"><name>[Name]</name><pros>[Benefits - physical correctness, tractability]</pros><cons>[Tradeoffs - approximation quality, computational cost]</cons></option>
    <option id="option-b"><name>[Name]</name><pros>[Benefits]</pros><cons>[Tradeoffs]</cons></option>
  </options>
  <resume-signal>Select: option-a or option-b</resume-signal>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>[What was derived/computed] - results in [file/notebook]</what-built>
  <how-to-verify>Review [artifact] and verify: [physics checks - do limits make sense, are plots physical, does derivation logic hold]</how-to-verify>
  <resume-signal>Type "approved" or describe concerns</resume-signal>
</task>

</tasks>

<verification>
Before declaring plan complete:
- [ ] [Dimensional analysis of all derived expressions]
- [ ] [Limiting cases checked against known results]
- [ ] [Numerical results compared with published benchmarks]
- [ ] [Conservation laws / symmetries verified]
</verification>

<success_criteria>

- All tasks completed
- All verification checks pass
- No unphysical results or dimensional inconsistencies
- [Plan-specific criteria]
  </success_criteria>

<output>
After completion, create `.planning/phases/XX-name/{phase}-{plan}-SUMMARY.md`
</output>
```

---

## Frontmatter Fields

| Field            | Required | Purpose                                                               |
| ---------------- | -------- | --------------------------------------------------------------------- |
| `phase`          | Yes      | Phase identifier (e.g., `01-hamiltonian`)                             |
| `plan`           | Yes      | Plan number within phase (e.g., `01`, `02`)                           |
| `type`           | Yes      | Always `execute` for standard plans, `derivation` for analytical work |
| `wave`           | Yes      | Execution wave number (1, 2, 3...). Pre-computed at plan time.        |
| `depends_on`     | Yes      | Array of plan IDs this plan requires.                                 |
| `files_modified` | Yes      | Files this plan touches.                                              |
| `autonomous`     | Yes      | `true` if no checkpoints, `false` if has checkpoints                  |
| `user_setup`     | No       | Array of human-required setup items (external resources, data access) |
| `must_haves`     | Yes      | Goal-backward verification criteria (see below)                       |

**Wave is pre-computed:** Wave numbers are assigned during `$gpd-plan-phase`. Execute-phase reads `wave` directly from frontmatter and groups plans by wave number. No runtime dependency analysis needed.

**Must-haves enable verification:** The `must_haves` field carries goal-backward requirements from planning to execution. After all plans complete, execute-phase spawns a verification subagent that checks these criteria against the actual results.

---

## Context Section

**Parallel-aware context:**

```markdown
<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

# Only include SUMMARY refs if genuinely needed:

# - This plan uses derived results from prior plan

# - Prior plan established conventions affecting this plan

# - Prior plan's output is input to this plan

#

# Independent plans need NO prior SUMMARY references.

# Do NOT reflexively chain: 02 refs 01, 03 refs 02...

@src/relevant/module.py
@derivations/relevant_result.tex
</context>
```

**Bad pattern (creates false dependencies):**

```markdown
<context>
@.planning/phases/02-spectrum/02-01-SUMMARY.md  # Just because it's earlier
@.planning/phases/02-spectrum/02-02-SUMMARY.md  # Reflexive chaining
</context>
```

---

## Scope Guidance

**Plan sizing:**

- 2-3 tasks per plan
- ~50% context usage maximum
- Complex phases: Multiple focused plans, not one large plan

**When to split:**

- Different physics subproblems (analytical derivation vs numerical computation vs data analysis)
- > 3 tasks
- Risk of context overflow
- Verification-heavy tasks - separate plans

**Vertical slices preferred:**

```
PREFER: Plan 01 = Derive + implement + verify quantity A
        Plan 02 = Derive + implement + verify quantity B

AVOID:  Plan 01 = All derivations
        Plan 02 = All implementations
        Plan 03 = All verifications
```

---

## Task Types

| Type                      | Use For                                                              | Autonomy                        |
| ------------------------- | -------------------------------------------------------------------- | ------------------------------- |
| `auto`                    | Everything the agent can do independently                            | Fully autonomous                |
| `checkpoint:human-verify` | Physics review of derivations, result plausibility                   | Pauses, returns to orchestrator |
| `checkpoint:decision`     | Choice of approximation, method, parameter regime                    | Pauses, returns to orchestrator |
| `checkpoint:human-action` | Truly unavoidable manual steps - e.g., access restricted data (rare) | Pauses, returns to orchestrator |

**Checkpoint behavior in parallel execution:**

- Plan runs until checkpoint
- Agent returns with checkpoint details + agent_id
- Orchestrator presents to user
- User responds
- Orchestrator resumes agent with `resume: agent_id`

---

## Examples

**Autonomous parallel plan:**

```markdown
---
phase: 02-spectrum
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  [
    derivations/perturbation_theory.tex,
    src/perturbative_spectrum.py,
    tests/test_spectrum.py,
  ]
autonomous: true
must_haves:
  truths:
    - "Energy eigenvalues correct to second order in coupling"
    - "Perturbative result matches exact diagonalization within 1% for weak coupling"
  artifacts:
    - path: "derivations/perturbation_theory.tex"
      provides: "Second-order energy correction derivation"
      contains: "E^{(2)}"
    - path: "src/perturbative_spectrum.py"
      provides: "Perturbative spectrum computation"
      exports: ["compute_spectrum", "second_order_correction"]
  key_links:
    - from: "derivations/perturbation_theory.tex"
      to: "src/perturbative_spectrum.py"
      via: "Formula implementation"
      pattern: "second_order_correction"
  uncertainties:
    - quantity: "E_n^(2)"
      target_precision: "+/- 0.1% relative to exact diag"
      method: "comparison with exact diagonalization"
---

<objective>
Derive and implement perturbative spectrum to second order in coupling.

Purpose: Establish analytical baseline for comparison with non-perturbative methods.
Output: Derivation document, implementation, and tests against known results.
</objective>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
</context>

<tasks>
<task type="auto">
  <name>Task 1: Derive second-order energy corrections</name>
  <files>derivations/perturbation_theory.tex</files>
  <action>Apply Rayleigh-Schrodinger perturbation theory to the Hamiltonian from PROJECT.md. Compute E^(1) and E^(2) for the first 5 energy levels. Use the unperturbed basis from the free theory. Check all intermediate steps for dimensional consistency.</action>
  <verify>Verify dimensions of each term. Check that E^(1) = 0 for this symmetry class (parity). Verify E^(2) is negative for the ground state (second-order always lowers ground state energy).</verify>
  <done>Explicit expressions for E_n^(2) for n=0,...,4 with all matrix elements evaluated</done>
</task>

<task type="auto">
  <name>Task 2: Implement and validate perturbative spectrum</name>
  <files>src/perturbative_spectrum.py, tests/test_spectrum.py</files>
  <action>Implement the derived expressions in Python. Compare against exact diagonalization for lambda = 0.01, 0.1, 0.5. Plot relative error vs coupling strength.</action>
  <verify>At lambda=0.01, relative error < 0.01% (perturbation theory should be excellent). At lambda=0.1, relative error < 1%. Verify convergence: |E^(2)| < |E^(1)| for small lambda.</verify>
  <done>Perturbative spectrum agrees with exact diag within expected accuracy for lambda < 0.1</done>
</task>
</tasks>

<verification>
- [ ] All derived expressions have correct dimensions
- [ ] E^(2) < 0 for ground state (guaranteed by perturbation theory)
- [ ] Perturbative result converges to exact at small coupling
- [ ] Results match any published values in RESEARCH.md
</verification>

<success_criteria>

- All tasks completed
- Perturbative spectrum validated against exact diagonalization
- Clear identification of coupling regime where perturbation theory breaks down
  </success_criteria>

<output>
After completion, create `.planning/phases/02-spectrum/02-01-SUMMARY.md`
</output>
```

**Plan with checkpoint (non-autonomous):**

```markdown
---
phase: 03-phase-diagram
plan: 03
type: execute
wave: 2
depends_on: ["03-01", "03-02"]
files_modified: [results/phase_boundary.py, results/phase_diagram.png]
autonomous: false
---

<objective>
Construct phase diagram from order parameter and susceptibility data.

Purpose: Identify phase boundaries and critical exponents from computed observables.
Output: Phase diagram plot with error bars and critical exponent estimates.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/execute-plan.md
@{GPD_INSTALL_DIR}/templates/summary.md
@{GPD_INSTALL_DIR}/references/checkpoints.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/03-phase-diagram/03-01-SUMMARY.md
@.planning/phases/03-phase-diagram/03-02-SUMMARY.md
</context>

<tasks>
<task type="auto">
  <name>Task 1: Extract phase boundaries from order parameter data</name>
  <files>results/phase_boundary.py</files>
  <action>Fit order parameter vs temperature data near the transition. Use finite-size scaling analysis to extract critical temperature and exponent beta. Compare multiple system sizes (L=16,32,64) for scaling collapse.</action>
  <verify>Scaling collapse quality (chi-squared). Critical exponent beta within known universality class bounds. T_c consistent across system sizes.</verify>
  <done>Phase boundary identified with error bars. Critical exponents estimated.</done>
</task>

<task type="auto">
  <name>Task 2: Generate phase diagram with uncertainty</name>
  <files>results/phase_diagram.png</files>
  <action>Plot phase diagram in (T, g) plane. Include error bars on phase boundary. Mark known limiting cases. Overlay literature values if available from RESEARCH.md.</action>
  <verify>Correct limiting behavior at g=0 and g->infinity. Smooth phase boundary. Error bars visible and reasonable.</verify>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>Phase diagram with critical exponents - results in results/phase_diagram.png</what-built>
  <how-to-verify>Review phase diagram: Does the topology make sense? Are the limiting cases correct? Do the critical exponents match the expected universality class? Is the finite-size scaling collapse convincing?</how-to-verify>
  <resume-signal>Type "approved" or describe concerns</resume-signal>
</task>
</tasks>

<verification>
- [ ] Phase boundary is continuous (no unphysical jumps)
- [ ] Critical exponents within known universality class bounds
- [ ] Finite-size scaling collapse is convincing (chi-squared / DOF ~ 1)
- [ ] Limiting cases match exactly solvable limits
</verification>

<success_criteria>

- All tasks completed
- User approved phase diagram
- Critical exponents reported with uncertainties
  </success_criteria>

<output>
After completion, create `.planning/phases/03-phase-diagram/03-03-SUMMARY.md`
</output>
```

---

## Anti-Patterns

**Bad: Reflexive dependency chaining**

```yaml
depends_on: ["02-01"] # Just because 01 comes before 02
```

**Bad: Horizontal layer grouping**

```
Plan 01: All derivations
Plan 02: All implementations (depends on 01)
Plan 03: All plots (depends on 02)
```

**Bad: Missing autonomy flag**

```yaml
# Has checkpoint but no autonomous: false
depends_on: []
files_modified: [...]
# autonomous: ???  <- Missing!
```

**Bad: Vague tasks**

```xml
<task type="auto">
  <name>Compute the spectrum</name>
  <action>Calculate the energy levels</action>
</task>
```

**Bad: No physics verification**

```xml
<task type="auto">
  <name>Derive partition function</name>
  <action>...</action>
  <verify>Code runs without errors</verify>  <!-- This verifies nothing physical! -->
</task>
```

---

## Guidelines

- Always use XML structure for agent parsing
- Every plan producing numerical results MUST specify target uncertainties in must_haves. Results without error bars are incomplete.
- Include `wave`, `depends_on`, `files_modified`, `autonomous` in every plan
- Prefer vertical slices over horizontal layers
- Only reference prior SUMMARYs when genuinely needed
- Group checkpoints with related auto tasks in same plan
- 2-3 tasks per plan, ~50% context max
- Every task must have physics-grounded verification (not just "code runs")

---

## User Setup (External Resources)

When a plan requires external resources needing human configuration, declare in frontmatter:

```yaml
user_setup:
  - service: hpc_cluster
    why: "Large-scale exact diagonalization requires cluster access"
    env_vars:
      - name: HPC_HOST
        source: "Cluster admin provides hostname"
      - name: HPC_ALLOCATION
        source: "Allocation ID from resource manager"
    data_access:
      - task: "Download experimental dataset"
        location: "[journal/database URL]"
        details: "Requires institutional access or author request"
    local_dev:
      - "ssh-keygen and copy public key to cluster"
```

**The automation-first rule:** `user_setup` contains ONLY what the agent literally cannot do:

- Access restricted databases (requires institutional credentials)
- Obtain experimental data (requires author permission or subscription)
- Configure HPC access (requires admin-provisioned accounts)

**NOT included:** Package installs, code changes, file creation, commands the agent can run.

**Result:** Execute-plan generates `{phase}-USER-SETUP.md` with checklist for the user.

See `{GPD_INSTALL_DIR}/templates/user-setup.md` for full schema and examples

---

## Must-Haves (Goal-Backward Verification)

The `must_haves` field defines what must be TRUE for the phase goal to be achieved. Derived during planning, verified after execution.

**Structure:**

```yaml
must_haves:
  truths:
    - "Ground state energy agrees with exact diag to within 0.1%"
    - "Spectral form factor shows dip-ramp-plateau structure"
    - "Critical exponent nu = 0.63 +/- 0.03 (3D Ising universality)"
  uncertainties:
    - quantity: "E_0"
      target_precision: "+/- 0.1%"
      method: "Lanczos convergence"
    - quantity: "nu"
      target_precision: "+/- 0.03"
      method: "finite-size scaling"
  artifacts:
    - path: "derivations/effective_action.tex"
      provides: "Effective action derivation"
      contains: "S_{eff}"
    - path: "src/exact_diag.py"
      provides: "Exact diagonalization implementation"
      exports: ["diagonalize", "compute_spectrum"]
    - path: "results/spectral_form_factor.png"
      provides: "SFF plot showing dip-ramp-plateau"
  key_links:
    - from: "derivations/effective_action.tex"
      to: "src/field_theory.py"
      via: "Formula implementation"
      pattern: "effective_action"
    - from: "src/exact_diag.py"
      to: "results/spectrum.json"
      via: "Computation output"
      pattern: "json\\.dump.*spectrum"
```

**Field descriptions:**

| Field                   | Purpose                                                           |
| ----------------------- | ----------------------------------------------------------------- |
| `truths`                | Physics results that must hold. Each must be testable/verifiable. |
| `uncertainties`         | Numerical outputs with target precision. Every plan producing numerical results MUST specify. |
| `uncertainties[].quantity` | Name of the numerical output (e.g., "T_c", "E_0").            |
| `uncertainties[].target_precision` | Required precision (e.g., "+/- 1%", "+/- 0.005").   |
| `uncertainties[].method` | How uncertainty is estimated (bootstrap, finite-size scaling, series truncation). |
| `artifacts`             | Files that must exist with real content.                          |
| `artifacts[].path`      | File path relative to project root.                               |
| `artifacts[].provides`  | What this artifact delivers.                                      |
| `artifacts[].min_lines` | Optional. Minimum lines to be considered substantive.             |
| `artifacts[].exports`   | Optional. Expected exports to verify.                             |
| `artifacts[].contains`  | Optional. Pattern that must exist in file.                        |
| `key_links`             | Critical connections between artifacts.                           |
| `key_links[].from`      | Source artifact.                                                  |
| `key_links[].to`        | Target artifact or endpoint.                                      |
| `key_links[].via`       | How they connect (description).                                   |
| `key_links[].pattern`   | Optional. Regex to verify connection exists.                      |

**Why this matters:**

Task completion does not equal goal achievement. A task "derive effective action" can complete by writing a placeholder. The `must_haves` field captures what must actually be established, enabling verification to catch gaps before they compound.

**Verification flow:**

1. Plan-phase derives must_haves from phase goal (goal-backward)
2. Must_haves written to PLAN.md frontmatter
3. Execute-phase runs all plans
4. Verification subagent checks must_haves against actual results
5. Gaps found -> fix plans created -> execute -> re-verify
6. All must_haves pass -> phase complete

See `{GPD_INSTALL_DIR}/workflows/verify-phase.md` for verification logic.
