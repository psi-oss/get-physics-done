---
name: gpd:verify-work
description: Verify research results through physics consistency checks
argument-hint: "[phase] [--dimensional] [--limits] [--convergence] [--regression] [--all]"
context_mode: project-required
requires:
  files: [".gpd/ROADMAP.md"]
  state: "phase_executed"
review-contract:
  review_mode: review
  schema_version: 1
  required_outputs:
    - ".gpd/phases/XX-name/{phase}-VERIFICATION.md"
  required_evidence:
    - roadmap
    - phase summaries
    - artifact files
  blocking_conditions:
    - missing project state
    - missing roadmap
    - missing phase artifacts
    - degraded review integrity
  preflight_checks:
    - project_state
    - roadmap
    - phase_artifacts
  required_state: phase_executed
allowed-tools:
  - file_read
  - shell
  - find_files
  - search_files
  - file_edit
  - file_write
  - task
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Verify research results through systematic physics checks with persistent state.

Purpose: Confirm that derivations are correct, numerical results are trustworthy, and physical conclusions are sound. One check at a time, plain text responses, no interrogation. When issues are found, automatically diagnose, classify severity, and prepare for resolution.

Output: `.gpd/phases/XX-name/{phase}-VERIFICATION.md` tracking all check results. This workflow is only valid once the phase has reached the `phase_executed` state. If issues are found, return diagnosed gaps with severity classification and verified fix plans ready for `/gpd:execute-phase`.

Physics verification is fundamentally different from software testing. A software test has a binary pass/fail; a physics check has degrees of agreement, expected approximation errors, and regime-dependent validity. The verification framework accounts for this.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/verify-work.md
@{GPD_INSTALL_DIR}/references/verification/core/verification-core.md
@{GPD_INSTALL_DIR}/templates/verification-report.md
@{GPD_INSTALL_DIR}/templates/contract-results-schema.md
</execution_context>

<context>
Phase: $ARGUMENTS (optional)
- If provided: Verify specific phase (e.g., "4")
- If not provided: Check for active sessions or prompt for phase

@.gpd/STATE.md
@.gpd/ROADMAP.md
</context>

<process>
**CRITICAL: First, read the full workflow file using the file_read tool:**
Read the file at {GPD_INSTALL_DIR}/workflows/verify-work.md — this contains the complete step-by-step instructions. Do NOT improvise. Follow the workflow file exactly.

Execute the workflow end-to-end.
Preserve all workflow gates (session management, check presentation, diagnosis, fix planning, routing).

The verification applies the following physics checks, selected based on the phase type:

## For Analytical Derivations

1. **Dimensional analysis** — Does every term in every equation have consistent dimensions? Track dimensions through every algebraic step, not just the final result.
2. **Limiting cases** — Does the result reduce to known expressions in appropriate limits?
   - Weak/strong coupling
   - Large/small N
   - High/low temperature
   - Non-relativistic / classical limit
   - Free theory limit
   - Single-particle / mean-field limit
3. **Symmetry preservation** — Does the result respect all symmetries of the original problem?
   - Gauge invariance (if applicable)
   - Lorentz / rotational / translational invariance
   - Hermiticity of observables
   - Unitarity of time evolution
   - CPT or other discrete symmetries
4. **Special values** — Does the result give correct answers for exactly solvable special cases?
5. **Sign and factor checks** — Are overall signs physically sensible? (e.g., energy bounded below, probabilities non-negative, entropy non-negative) Are factors of 2, pi, hbar correct?
6. **Logical completeness** — Does the derivation proceed from stated assumptions to conclusion without gaps? Are all approximations explicitly stated and justified?

## For Numerical Results

7. **Convergence tests** — Do results converge as resolution parameters are refined?
   - Grid spacing / time step refinement
   - Basis set / cutoff convergence
   - Monte Carlo statistical convergence
   - Extrapolation to continuum / thermodynamic limit
8. **Analytical benchmarks** — Do numerical results match analytical predictions in regimes where both are available?
9. **Conservation laws** — Are conserved quantities (energy, particle number, momentum, charge) actually conserved to expected precision?
10. **Physical plausibility** — Are results physically reasonable?
    - Correct order of magnitude
    - Correct qualitative behavior (monotonicity, asymptotic behavior)
    - No unphysical artifacts (negative probabilities, acausal propagation)
11. **Reproducibility** — Do results reproduce when re-run with different random seeds, initial conditions, or numerical methods?

## For Literature Comparisons

12. **Quantitative agreement** — Do results agree with published values within stated uncertainties?
13. **Discrepancy resolution** — If results disagree with literature, is the source of disagreement identified? (Different conventions, different approximations, error in prior work, or error in current work?)

## Severity Classification

- **CRITICAL** — Result is wrong (dimensional error, symmetry violation, sign error). Blocks all downstream work.
- **MAJOR** — Result may be wrong (failed limiting case, numerical non-convergence). Must be resolved before conclusions are drawn.
- **MINOR** — Result is probably correct but incompletely validated (missing one limiting case, no error bars on a qualitative plot). Should be resolved before publication.
- **NOTE** — Observation for the record (e.g., "convergence is slow but adequate", "agrees with Smith et al. to 3 significant figures").

**For deeper focused analysis**, use the dedicated commands: `/gpd:dimensional-analysis` (unit consistency), `/gpd:limiting-cases` (known limit recovery), or `/gpd:numerical-convergence` (convergence testing).
  </process>
