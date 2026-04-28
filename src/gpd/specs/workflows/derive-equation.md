<purpose>
Perform a rigorous physics derivation with systematic verification at each step. Handles the complete derivation pipeline: stating assumptions, establishing notation, performing algebraic manipulations, verifying intermediate results, checking limits, and documenting the full chain of reasoning.

This workflow ensures that derivations are not just correct in their final form but verifiably correct at every intermediate step, with all assumptions explicit and all approximations justified.
</purpose>

<core_principle>
A derivation is a chain of logical steps from assumptions to conclusion. Every link in the chain must be verifiable. A derivation that skips steps, hides assumptions, or handwaves through approximations is not a derivation -- it is a plausibility argument.

**The derivation contract:** Given these assumptions and these definitions, the following result follows by mathematical necessity. No step relies on physical intuition (intuition motivates, it doesn't prove). No step invokes "it can be shown that" without showing it. No approximation is made without stating what is neglected and estimating the error.
</core_principle>

<derivation_standards>

### What Makes a Rigorous Derivation

1. **Assumptions are stated explicitly before the derivation begins.**

   - Physical assumptions (system is in equilibrium, fields are weak, particles are non-relativistic)
   - Mathematical assumptions (function is analytic, series converges, integral exists)
   - Each assumption is numbered and referenced when used

2. **Notation is defined before use.**

   - Every symbol has exactly one meaning
   - Conventions are stated (metric signature, Fourier transform, index ranges)
   - Operator ordering is specified for quantum systems

3. **Each step follows logically from the previous.**

   - Algebraic manipulations are explicit enough to verify
   - When a step involves a nontrivial identity, the identity is stated and cited
   - When a step involves a standard technique (integration by parts, completing the square, saddle-point approximation), name it explicitly

4. **Approximations are justified and bounded.**

   - State what is being neglected: "We drop terms of O(epsilon^2) and higher"
   - State why it is valid: "because epsilon = m/M << 1 in this regime"
   - Estimate the error: "The leading correction is O(epsilon^2) ~ 0.01"

5. **Intermediate results are checked.**

   - Dimensional analysis at each stage (not just the final result)
   - Known limits at intermediate stages (not just the final result)
   - Symmetry properties preserved through each step

6. **The result is clearly stated and interpreted.**
   - Final expression boxed or highlighted
   - Physical interpretation in words
   - Domain of validity stated explicitly
   - Connection to known results

</derivation_standards>

<process>

<step name="load_context">
**Pre-Step: Load Project Context**

Load current-workspace state and conventions before beginning any derivation.

Keep this bootstrap bound to the invoking workspace. `derive-equation` can run as a current-workspace standalone derivation, so do not auto-reenter an ancestor or recent project here.

- Run:

```bash
INIT=$(gpd --raw init progress --include state,config --no-project-reentry)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

- Parse JSON for: `workspace_root`, `project_root`, `state_exists`, `current_phase`, `convention_lock`, `derived_convention_lock`, and any continuation/runtime fields that pin this run to a concrete phase directory.
- Treat phase context as authoritative only when the bootstrap surfaces a concrete phase number and phase directory (for example via `current_phase.number` plus `current_phase.directory`, or an equivalent canonical continuation field). Do not invent `phase_dir` from an ancestor project, a guessed numeric phase, or prose alone.
- A nonzero init exit is a hard stop, not standalone mode.
- **If init succeeds** (non-empty JSON with `state_exists: true`): Extract `convention_lock` for metric signature, Fourier transform convention, and index ranges. Extract active approximations and their validity ranges. Load any previously established notation from STATE.md.
- If project state exists, inspect `intermediate_results` before re-deriving. Capture any existing canonical equation/result entries related to the target, including `id`, `equation`, `description`, `phase`, `depends_on`, and `verified`, so you can reuse the authoritative result instead of restating it.
- Use `gpd result search` to locate the canonical result first when the target equation or derived quantity may already exist in the registry. Prefer `--equation` for exact formula lookup and `--text` for descriptive or shorthand matching. Once a canonical `result_id` is known, use `gpd result show "{result_id}"` for the direct stored-result view before deciding whether a fresh derivation is still warranted.
- **If init succeeds** (non-empty JSON with `state_exists: false`): Proceed in standalone mode with explicit convention declarations required from user in Step 1. All conventions must be stated explicitly before any derivation begins.
- **If init succeeds** with `state_exists: true` but no authoritative phase context: Keep the project conventions and prior results visible as supporting context, but keep durable outputs under `GPD/analysis/` and skip phase-local persistence later.

**This is the most critical workflow to have convention context.** Derivations without locked conventions risk sign errors, missing factors of 2pi, and metric signature inconsistencies that propagate silently through all subsequent steps.

**Convention verification** (if project exists):

```bash
CONV_CHECK=$(gpd --raw convention check 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — review before deriving"
  echo "$CONV_CHECK"
fi
```

If the convention lock is empty but prior phases exist, this is an error — conventions should have been established.
</step>

<step name="state_problem">
**Step 0: State What We Are Deriving**

Before any calculation, write:

```markdown
## Derivation Objective

**Goal:** Derive [expression/relation/equation] for [physical system/quantity].

**Starting point:** [Lagrangian/Hamiltonian/action/equation that is given, not derived here]

**Expected result:** [If known, the expression we expect to obtain. If unknown, the general form expected from dimensional analysis or symmetry arguments.]

**Method:** [Variational/perturbative/exact/saddle-point/RG/etc.]
```

This forces clarity about what is being assumed and what is being derived.
</step>

<step name="proof_obligation_screen">
**Step 0.5: Classify proof-bearing work before deriving**

If the objective is theorem-style or contract-backed `proof_obligation` work, proof review is mandatory and fail-closed.

@{GPD_INSTALL_DIR}/references/verification/core/proof-redteam-workflow-gate.md

For proof-bearing derivations, create a theorem inventory before Step 1 and carry it through the document:

```markdown
## Proof Inventory

- **Claim / theorem target:** [exact statement being proved]
- **Named parameters:** [symbol -> role / domain]
- **Hypotheses:** [H1, H2, ...]
- **Quantifier / domain obligations:** [for all x in ..., exists y such that ...]
- **Conclusion clauses:** [what the proof must establish]
```

Proof-bearing derivations must also reserve a sibling audit artifact:

- **Phase-scoped:** `${phase_dir}/DERIVATION-{slug}-PROOF-REDTEAM.md`
- **Standalone:** `GPD/analysis/derivation-{slug}-proof-redteam.md`

That audit must inventory coverage of every parameter, hypothesis, quantifier, and conclusion clause, and it must probe at least one adversarial special case. Do not treat a derivation as complete or established without it.
When runtime delegation is available, spawn `gpd-check-proof` to produce that artifact instead of relying on the derivation writer to audit their own proof. If the runtime cannot spawn `gpd-check-proof`, stop at a checkpoint rather than self-certifying theorem-proof alignment in the same context that wrote the proof.
</step>

<step name="establish_framework">
**Step 1: Establish Framework**

### 1a. Assumptions

Number each assumption:

```markdown
## Assumptions

A1. [Physical assumption]: [justification, regime of validity]
A2. [Physical assumption]: [justification]
A3. [Mathematical assumption]: [when this might fail]
...
```

### 1b. Definitions, notation, and convention lock verification

**If a convention lock exists** (loaded in pre-step), verify that the conventions you declare match the project lock. Run the 5-point checklist from `shared-protocols.md`:

1. Metric signature matches lock?
2. Fourier convention matches lock?
3. State normalization matches lock?
4. Coupling convention matches lock?
5. Renormalization scheme matches lock?

**If any convention differs from the lock, STOP.** Either the lock needs updating (via `gpd convention set`) or the derivation must use the locked convention. Never derive with one convention and combine with locked results using another.

```markdown
## Definitions

| Symbol   | Meaning | Dimensions     | Defined by               |
| -------- | ------- | -------------- | ------------------------ |
| {symbol} | {name}  | {[dimensions]} | {equation or convention} |

## Conventions

<!-- ASSERT_CONVENTION: natural_units={from lock}, metric_signature={from lock}, fourier_convention={from lock} -->

- Metric signature: {from convention_lock, or declared explicitly if standalone}
- Fourier transform: {from convention_lock, or declared explicitly if standalone}
- Index ranges: {Greek = spacetime 0..3, Latin = spatial 1..3, etc.}
- Operator ordering: {normal, Weyl, time, etc.}
- Coupling definition: {from convention_lock if set}
- Renormalization scheme: {from convention_lock if set}
```

**The `ASSERT_CONVENTION` comment is machine-readable.** The verifier and consistency checker scan for it to validate against the project lock. Include it in EVERY derivation file.

### 1c. Starting point

Write the starting expression explicitly with all indices, factors, and conventions visible:

```markdown
## Starting Point

The action for [system] is:

$$
S[\phi] = \int d^4x \, \mathcal{L}(\phi, \partial_\mu \phi)
$$

where $\mathcal{L}$ is given by Eq. (X) of [reference], with [our convention for signs/normalization].

**Dimensional check:** [S] = [dimensionless in natural units] = [energy * time in SI]. CHECK: ...
```

</step>

<step name="derive_step_by_step">
**Step 2: Perform the Derivation**

For each step in the derivation:

### 2a. Name the operation

State what mathematical operation you are performing:

- "Vary the action with respect to phi"
- "Integrate by parts, dropping the boundary term (justified by A3)"
- "Expand to second order in the fluctuation delta_phi"
- "Apply the saddle-point approximation (valid when S >> 1, using A2)"
- "Sum the geometric series (converges for |x| < 1, guaranteed by A4)"

### 2b. Perform the operation

Show enough intermediate algebra that each step can be verified independently. The appropriate level of detail:

- **Too terse:** "From the action we obtain the equation of motion." (Reader cannot verify)
- **Too verbose:** Writing out every application of the product rule. (Wastes space, obscures logic)
- **Just right:** Show the key algebraic step with sufficient context. A competent physicist should be able to fill in the routine algebra between displayed equations.

### 2c. Check the step

After each major step (not every line, but every conceptually distinct operation):

1. **Dimensional analysis:** Does the new expression have the correct dimensions?
2. **Symmetry check:** Does the result respect the symmetries it should?
3. **Special case:** Does a simple special case (N=1, d=1, g=0) give the expected result?
4. **Convention assertion:** Write an `ASSERT_CONVENTION` header for any convention used in this step. This catches convention drift mid-derivation — the most common source of silent sign errors and missing factors of 2pi.

Document the check:

```markdown
**Check:** [LHS] has dimensions [energy^2 / length], [RHS] = [coupling^2] \* [field^2] / [length] = [energy^2 / length]. CONSISTENT.

<!-- ASSERT_CONVENTION: metric_signature=mostly_minus, fourier_convention=physics -->
**Convention used:** Fourier convention exp(-ikx) applied in integration by parts (consistent with lock).
```

If any convention in the ASSERT_CONVENTION line differs from the Step 1 declaration or the project lock, **STOP immediately** — a convention has drifted mid-derivation. Resolve before continuing.

### 2d. Handle approximations

When making an approximation:

```markdown
**Approximation (using A2):** We expand the exponential to first order:

$$
e^{-\beta V} \approx 1 - \beta V + O(\beta^2 V^2)
$$

**Validity:** This requires $\beta V \ll 1$, i.e., $V \ll k_B T$. In our regime (T > T_c, V ~ J), this gives $J/k_B T < 0.1$, so the neglected term is $O(10^{-2})$.

**Error bound:** The leading correction is $\frac{1}{2}(\beta V)^2 \leq \frac{1}{2}(0.1)^2 = 0.005$, contributing at most 0.5% error to the final result.
```

</step>

<step name="verify_intermediate">
**Step 3: Verify Intermediate Results**

At natural checkpoints in the derivation (after completing a major sub-calculation), perform verification:

### 3a. Dimensional consistency

Check dimensions of the intermediate result. This should be routine by now -- if it's not consistent, the error is in the last few steps.

### 3b. Limiting cases

Test the intermediate result in known limits:

```markdown
**Limit check (g -> 0):**
Setting g = 0 in Eq. (7):

$$
\Sigma(p) \big|_{g=0} = 0
$$

CORRECT: The self-energy vanishes in the free theory.

**Limit check (p -> 0):**
Setting p = 0 in Eq. (7):

$$
\Sigma(0) = -\frac{g^2}{16\pi^2} m^2 \ln\frac{\Lambda^2}{m^2}
$$

CONSISTENT with standard result (Peskin & Schroeder, Eq. 10.28).
```

### 3c. Symmetry preservation

Verify that intermediate results respect required symmetries:

- If the system has rotational symmetry, the intermediate result should not depend on direction
- If the system has gauge symmetry, the intermediate result should be gauge-invariant (or transform covariantly)
- If the system has time-reversal symmetry, the intermediate result should be real (for appropriate quantities)

### 3d. Numerical spot-check

For complicated algebraic expressions, evaluate both sides of a key equation at random numerical parameter values:

```python
# Spot-check: evaluate LHS and RHS of Eq. (7) at random parameters
import numpy as np

# Random physical parameters
g, m, p, Lambda = 0.3, 1.5, 2.7, 100.0

LHS = self_energy_LHS(g, m, p, Lambda)
RHS = self_energy_RHS(g, m, p, Lambda)

print(f"LHS = {LHS:.10e}")
print(f"RHS = {RHS:.10e}")
print(f"Relative diff = {abs(LHS - RHS) / abs(LHS):.2e}")
# Should be < machine epsilon if algebra is correct
```

### 3e. Cross-phase consistency check

When combining this derivation's results with expressions from prior phases:

1. **Read the prior phase's ASSERT_CONVENTION line** and verify it matches this derivation's conventions. If conventions differ, an explicit conversion factor is required.
2. **Verify shared symbols have the same definition.** If Phase 2 defines $g$ as a bare coupling and this derivation uses $g$ as a renormalized coupling, state the relation explicitly.
3. **Check that approximation regimes are compatible.** If a prior phase derived a result valid for $T \gg T_c$ and this derivation assumes $T \sim T_c$, the results cannot be naively combined.

If the project has a convention lock, run the cross-phase consistency check:

```bash
gpd --raw convention check 2>/dev/null
```

Any convention drift between phases must be resolved before combining results.

</step>

<step name="state_result">
**Step 4: State the Final Result**

```markdown
## Result

Under assumptions A1-A{N}, the [quantity] is given by:

$$
\boxed{
  [final expression]
}
$$

**Dimensions:** [verify]
**Regime of validity:** [where this holds]

### Interpretation

[Physical meaning of the result in 2-3 sentences. What does this expression tell us about the physics?]

### Limiting Cases Verified

| Limit   | Expected     | Obtained     | Status |
| ------- | ------------ | ------------ | ------ |
| {limit} | {expression} | {expression} | MATCH  |

### Connection to Known Results

- Reduces to [known result] when [condition] (Eq. X of [reference])
- Extends [previous result] by including [new physics]
- Resolves discrepancy between [ref A] and [ref B] by [explanation]
```

</step>

<step name="document_derivation">
**Step 5: Create Derivation Document**

Write a complete, self-contained derivation document:

```markdown
---
title: Derivation of [result]
date: { YYYY-MM-DD }
status: completed | draft
assumptions: [A1, A2, ...]
method: [variational, perturbative, etc.]
result: [brief form of final expression]
result_id: [stable registry ID, if persisted]
verified_limits: [list of limits checked]
---

# Derivation of [Result]

## Objective

{What we derive and why}

## Assumptions

{Numbered list}

## Definitions and Conventions

<!-- ASSERT_CONVENTION: natural_units={units}, metric_signature={signature}, fourier_convention={convention} -->

{Symbol table and conventions — include ASSERT_CONVENTION comment above with values from convention lock}

## Starting Point

{The expression we begin from}

## Derivation

### Step 1: {Name of operation}

<!-- ASSERT_CONVENTION: {conventions used in this step, e.g. metric_signature=mostly_minus, fourier_convention=physics} -->

{Derivation with checks}

### Step 2: {Name of operation}

<!-- ASSERT_CONVENTION: {conventions used in this step} -->

{Derivation with checks}

...

## Result

{Boxed final expression with interpretation}

## Verification

{Limiting cases, symmetry checks, numerical spot-checks}

## Error Analysis

{If approximations were made: error estimates}

## References

{Sources used for identities, conventions, comparison results}
```

Save to:

- **Phase-scoped (authoritative phase context only):** `${phase_dir}/DERIVATION-{slug}.md` (where `{slug}` is derived from the derivation goal, e.g., `dispersion-relation`)
- **Current-workspace fallback (standalone or no authoritative phase context):**

```bash
mkdir -p GPD/analysis
```

Write to `GPD/analysis/derivation-{slug}.md`.
Do not synthesize a phase-local output path from an ancestor project root or an unverified phase guess.

If the derivation is proof-bearing, reserve the sibling proof-redteam artifact path for the independent proof critic:

- **Phase-scoped (authoritative phase context only):** `${phase_dir}/DERIVATION-{slug}-PROOF-REDTEAM.md`
- **Current-workspace fallback:** `GPD/analysis/derivation-{slug}-proof-redteam.md`

Apply the shared proof-redteam artifact content rules from Step 0.5; do not restate them here.

Do not have the derivation writer self-author this artifact as its own independent critique. If any named parameter, hypothesis, quantifier, or conclusion clause is uncovered, `gpd-check-proof` must set `status: gaps_found` and the derivation must not describe the theorem as established.

When the runtime supports delegation, resolve the proof-critic model and spawn `gpd-check-proof` as the canonical owner of the audit:

```bash
CHECK_PROOF_MODEL=$(gpd resolve-model gpd-check-proof)
```

@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

> If subagent spawning is unavailable, STOP at a checkpoint instead of self-certifying the proof audit in the derivation writer context.

```
task(
  subagent_type="gpd-check-proof",
  model="{check_proof_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-check-proof.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/templates/proof-redteam-schema.md and {GPD_INSTALL_DIR}/references/verification/core/proof-redteam-protocol.md before writing any proof audit artifact.

Operate in proof-redteam mode with a fresh context.
If the runtime needs user input, return `status: checkpoint` instead of waiting inside this run.

Write to:
- `${phase_dir}/DERIVATION-{slug}-PROOF-REDTEAM.md` when authoritative phase context is phase-scoped
- `GPD/analysis/derivation-{slug}-proof-redteam.md` when operating in the current-workspace fallback branch

Files to read:
- The newly written derivation artifact
- Any theorem inventory carried in the derivation
- Relevant PLAN / contract context if available
- Supporting summary or verification artifacts if available

Audit the exact theorem text, not a paraphrase. Fail closed on missing parameter coverage, hidden assumptions, or narrower special-case proofs sold as general claims.",
  description="Proof redteam for derivation {slug}"
)
```
</step>

<step name="persist_result">
**Step 6: Persist Canonical Result**

Persist the final derived equation through the executable `gpd result persist-derived` bridge only when project state is available and the phase context is authoritative.

- If `state_exists` is true **and** authoritative phase context exists:
  1. Resolve a stable `result_id` request. On reruns, prefer the `result_id` already associated with the derivation record or invocation context if one is available. Otherwise derive a deterministic ID from the derivation slug and authoritative phase.
  2. Re-check `state.json.intermediate_results` for the same preferred `result_id` or an existing canonical equation for the same target. If a matching entry already exists, reuse its actual canonical `result_id` instead of creating a duplicate.
  3. Persist the final result with the bridge, using the authoritative phase identifier from the bootstrap context:

```bash
gpd result persist-derived --id "{result_id}" --derivation-slug "{derivation_slug}" --equation "{final_equation}" --description "{short description}" --phase "{phase}" --validity "{validity}" [--depends-on "{comma-separated ids}"]
```

If no stable `result_id` is available yet, use the derivation-slug form instead:

```bash
gpd result persist-derived --derivation-slug "{derivation_slug}" --equation "{final_equation}" --description "{short description}" --phase "{phase}" --validity "{validity}" [--depends-on "{comma-separated ids}"]
```

This bridge reuses an explicit `result_id` request when one is already known. Otherwise it derives a stable `requested_result_id` from the derivation slug and phase before delegating to the canonical upsert path, which reuses a unique exact equation match in the same phase when the existing canonical entry already exists, falls back to a unique exact description match when the equation is not yet stable, and only adds a new registry entry when no safe match exists.

If `gpd result persist-derived` reports multiple matches for the same equation or description, STOP and disambiguate with an explicit `result_id` or narrower `phase`. Do not guess which registry entry should be canonical.

  4. Read the bridge output carefully:
     - `requested_result_id` is the stable derivation-oriented ID the workflow asked for.
     - `result_id` is the actual canonical registry entry that was persisted or reused.
     - `requested_result_redirected=true` means the requested derivation-oriented ID was redirected to an existing canonical entry; in that case `result_id` is the canonical anchor.
     If the bridge reused an existing canonical entry, `result_id` may differ from `requested_result_id`; carry the actual `result_id` forward for later reruns and canonical continuity.
  5. If an active continuation context exists, the canonical path seeds continuity automatically from the actual `result_id` so later reruns can target the same registry entry without rediscovering it from prose.
  6. Keep `verified=false` unless the derivation also produced verification evidence that should be recorded separately. For proof-bearing derivations, a passed proof-redteam artifact is part of that evidence; without it, the result may be recorded as derived but not as established.
  7. For proof-bearing derivations, `gpd-check-proof` is the canonical owner of the proof audit whenever subagent spawning is available. If it cannot run, keep the derivation recorded as derived but not established and checkpoint for follow-up instead of self-certifying the proof.
- If `state_exists` is true but authoritative phase context is missing:
  - Skip registry write-back entirely.
  - Keep the derivation document self-contained under `GPD/analysis/`.
  - Do not synthesize `--phase` from `current_phase` prose, an ancestor project, or a guessed numeric label.
- If `state_exists` is false:
  - Skip registry write-back entirely.
  - Keep the derivation document self-contained under `GPD/analysis/` and do not invent a project result entry.

If the bridge returns `status=skipped` with `reason=no_recoverable_project_state`, treat that as the standalone branch above. Do not reconstruct project registry state from the derivation text alone.

This keeps standalone/current-workspace derivations safe while making phase-backed project derivations reusable as canonical structured memory.
</step>

</process>

<common_derivation_pitfalls>

| Pitfall                   | What Goes Wrong                                                  | Prevention                                                            |
| ------------------------- | ---------------------------------------------------------------- | --------------------------------------------------------------------- |
| Unsigned conventions      | Metric signature flipped mid-derivation                          | Write conventions ONCE at the top, reference throughout               |
| Integration by parts      | Dropped boundary term that isn't zero                            | Explicitly check boundary conditions every time                       |
| Index mistakes            | Contracted wrong indices, missing index                          | Write all indices explicitly, verify free indices match on both sides |
| Factor of i               | Missing or extra factor of i from Wick rotation                  | Track i explicitly through every step involving analytic continuation |
| Measure factors           | Wrong integration measure (missing (2pi)^d, wrong Jacobian)      | Dimensional analysis catches this -- check after every integral       |
| Symmetry factors          | Missing 1/n! from identical terms, wrong multiplicity            | Count diagrams/terms independently using a systematic method          |
| Order of limits           | Non-commuting limits taken in wrong order                        | State order explicitly, check both orders if uncertain                |
| Convergence of series     | Summing a divergent series                                       | Check convergence radius before summing                               |
| Branch cuts               | Wrong sheet of multivalued function                              | Specify branch cut conventions, check continuity                      |
| Distributional identities | Using delta function identities outside their domain of validity | Verify test function requirements                                     |

</common_derivation_pitfalls>

<success_criteria>

- [ ] Convention lock loaded and verified (5-point checklist passed)
- [ ] ASSERT_CONVENTION comment included in derivation document header AND per derivation step
- [ ] No convention drift: every step's ASSERT_CONVENTION matches Step 1 declaration and project lock
- [ ] Cross-phase convention consistency verified (if combining with prior results)
- [ ] Existing `intermediate_results` inspected before re-deriving, and matching canonical results reused when present
- [ ] Derivation objective clearly stated
- [ ] All assumptions numbered and explicit
- [ ] All notation defined before use
- [ ] Starting point written with all factors and conventions visible
- [ ] Each step named (what operation is being performed)
- [ ] Each approximation justified with error estimate
- [ ] Dimensional analysis performed at each major step
- [ ] Intermediate results checked against known limits
- [ ] Symmetry preservation verified
- [ ] Numerical spot-check performed for algebraically complex steps
- [ ] Final result boxed with interpretation
- [ ] Regime of validity stated
- [ ] All relevant limiting cases verified
- [ ] Connection to known results documented
- [ ] Proof-bearing derivations include a theorem inventory before the algebra starts
- [ ] Proof-bearing derivations reserve the sibling `DERIVATION-{slug}-PROOF-REDTEAM.md` artifact and hand it to `gpd-check-proof`
- [ ] The theorem is not treated as established unless `gpd-check-proof` writes that sibling artifact with `status: passed`
- [ ] Proof-bearing derivations fail closed when a named parameter, hypothesis, quantifier, or conclusion clause is uncovered
- [ ] Final derived equation persisted through the executable `gpd result persist-derived` bridge in project mode, with the actual persisted canonical `result_id` retained for later reruns and carried into canonical continuation for later pause/resume continuity
- [ ] Runs without authoritative phase context skipped registry write-back and stayed self-contained under `GPD/analysis/`
- [ ] Complete derivation document written

</success_criteria>
