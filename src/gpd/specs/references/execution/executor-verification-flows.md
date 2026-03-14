# Executor Verification Flows

Load this reference during task execution when verification is needed.

## Analytical Verification (for derivations and symbolic calculations)

1. **Dimensional analysis:** Check that every equation has consistent dimensions/units
2. **Symmetry check:** Verify expected symmetries are preserved (gauge invariance, Lorentz covariance, hermiticity, etc.)
3. **Limiting cases:** Evaluate in at least two known limits and compare against established results
4. **Special values:** Check at specific parameter values where the answer is known exactly
5. **Consistency:** Verify the result is consistent with previously derived equations in this project
6. **Anomaly awareness:** For quantum calculations, check whether classical symmetries survive quantization (ABJ anomaly, trace anomaly). Verify anomaly matching between UV and IR descriptions.
7. **Topological properties:** If relevant, verify topological invariants are integers, gauge-independent, and satisfy bulk-boundary correspondence.
8. **Analytic structure:** For Green's functions and response functions, verify Kramers-Kronig relations, correct pole/branch cut structure, and spectral positivity.

## Numerical Verification (for computational results)

1. **Conservation laws:** Verify that conserved quantities remain constant (energy, momentum, charge, probability, etc.)
2. **Convergence:** Demonstrate convergence with respect to relevant numerical parameters (grid size, basis size, time step, etc.)
3. **Benchmark comparison:** Compare against known results from literature or independent calculations
4. **Error estimation:** Provide error bars or convergence measures for all numerical values
5. **Sanity checks:** Order of magnitude, sign, symmetry of output
6. **Thermodynamic consistency:** For stat-mech / many-body calculations, verify Maxwell relations, response function positivity (specific heat, susceptibility > 0 for stable phases), and fluctuation-dissipation theorem.
7. **Finite-size scaling:** For lattice/discrete calculations, verify correct continuum limit extrapolation and absence of lattice artifacts (fermion doubling, discretization errors).
8. **Autocorrelation analysis:** For Monte Carlo, verify decorrelation between samples, report effective sample size, and check thermalization.

## Implementation Verification (for code)

1. **Known-answer tests:** Run against cases with analytically known results
2. **Regression tests:** Verify previously passing tests still pass
3. **Scaling tests:** Check that computational cost scales as expected (O(N), O(N^2), etc.)
4. **Reproducibility:** Verify that results are deterministic (or statistically consistent for stochastic methods)

## Figure Verification (for plots and visualizations)

1. **Labels and units:** All axes labeled with correct units
2. **Legends:** All curves/data series identified
3. **Physical reasonableness:** Curves have expected qualitative behavior
4. **Completeness:** All relevant data shown; no missing curves or data points
5. **Readability:** Font sizes appropriate, colors distinguishable, resolution sufficient

**Subfield-specific verification:** For priority checks, red flags, standard benchmarks, and recommended software per physics subfield, consult `references/physics-subfields.md`.

## Mandatory Computational Evidence

**Hard requirement:** Every VERIFICATION.md must include at least one computational oracle check — an executed code block (Python/SymPy/numpy) with actual output pasted alongside it. Reasoning about physics is necessary but not sufficient; external computation breaks the LLM self-consistency loop where the same model that produced the result also "verifies" it.

### Minimum Computational Evidence Per Verification Type

| Verification Type | Required Oracle Check |
|---|---|
| Analytical derivation | At least one limiting case evaluated via SymPy; at least one numerical spot-check |
| Numerical computation | Convergence test at 3+ resolutions with computed convergence order |
| Code implementation | Known-answer test executed with output shown |
| Literature comparison | Benchmark value computed independently and compared numerically |

### What Counts as Computational Evidence

**Counts:**
- Python/SymPy code block followed by actual execution output (both shown)
- Numerical evaluation with computed values, expected values, and relative error
- Convergence table with computed values at multiple resolutions

**Does NOT count:**
- Code block without output ("this would produce...")
- Verbal reasoning about what a computation would show
- Claiming agreement without showing numbers
- Citing the executor's own output as verification (circular)

### Templates

See `references/verification/core/computational-verification-templates.md` for copy-paste-ready templates covering: dimensional analysis, limiting case evaluation, numerical spot-check, identity verification, and convergence testing.

## Research Log Protocol

Maintain a running research log during execution. This is distinct from the Summary --- it captures the process, not just the outcome.

**Log location:** `${phase_dir}/{phase}-{plan}-LOG.md`

**Log entries follow this format:**

```markdown
### [TIMESTAMP] Task N: [task name]

**Objective:** [what this step aims to accomplish]

**Conventions:** [which conventions are active for this task, noting any that differ from project defaults]

**Approach:** [method/algorithm/technique used]

**Execution:**

- [what was done, step by step]
- [key commands run]
- [intermediate values observed]
- [derivation checkpoints: dimensions checked, test point evaluated, limit verified]

**Result:** [outcome --- success/partial/failure]

- [key equations derived, with equation numbers]
- [key numerical values, with units and uncertainties]
- [files created/modified]

**Verification:** [how correctness was checked]

- [which tests passed/failed]
- [limiting cases checked and results]
- [convergence data if numerical]
- [convention consistency verified with prior results]

**Issues encountered:** [or "None"]

- [what went wrong, what was tried, what worked]
- [deviation rule applied, if any]
- [any common error catalog entry triggered and resolved]

**Decision rationale:** [why this approach was chosen over alternatives, if relevant]

**Next step depends on:** [what downstream tasks need from this result]
```

**Log principles:**

- Write the log entry DURING task execution, not after
- Record failed attempts, not just successes --- this is invaluable for the researcher
- Include specific numerical values, not just "the calculation worked"
- Note any surprises or unexpected behavior, even if the task ultimately succeeded
- If a deviation rule was applied, document the full reasoning
- If a derivation checkpoint failed and was corrected: document what went wrong and how it was fixed

## State Tracking

The executor maintains comprehensive state about the research project's progress.

**Conventions in effect:**

```markdown
## Active Conventions

| Convention            | Choice                    | Set by                | Locked   |
| --------------------- | ------------------------- | --------------------- | -------- |
| Units                 | natural (hbar = c = 1)    | Phase 01              | Yes      |
| Metric signature      | (+,-,-,-)                 | Phase 01              | Yes      |
| Fourier convention    | physics: e^{-ikx} forward | Phase 01              | Yes      |
| State normalization   | relativistic: `<p,q> = (2pi)^3 2E delta(p-q)` | Phase 01              | Yes      |
| Gauge                 | Feynman (xi = 1)          | This plan             | No       |
| Coupling convention   | alpha_s = g^2/(4pi)       | Phase 01              | Yes      |
| Renormalization scheme | MS-bar at scale mu        | Phase 01              | Yes      |
```

**Equations and derivations:**

```markdown
## Derived Results

| ID    | Equation/Result          | Verified | Method        | Convention | File       | Task |
| ----- | ------------------------ | -------- | ------------- | ---------- | ---------- | ---- |
| eq:1  | H = p^2/2m + V(x)        | Yes      | Standard      | SI units   | theory.tex | 1    |
| eq:2  | E_n = (n+1/2)hbar\*omega | Yes      | Limiting case | SI units   | theory.tex | 3    |
| res:1 | sigma = 42.7 +/- 0.3 mb  | Yes      | Monte Carlo   | natural    | results.py | 5    |
```

**Numerical parameters:**

```markdown
## Parameter Values

| Parameter | Value     | Units  | Source      | Used in |
| --------- | --------- | ------ | ----------- | ------- |
| m         | 0.511     | MeV/c2 | PDG 2024    | eq:1-5  |
| alpha     | 1/137.036 | ---    | PDG 2024    | eq:3-7  |
| N_grid    | 1024      | ---    | Convergence | sim:1-3 |
| dt        | 0.001     | fm/c   | Stability   | sim:1-3 |
```

**Approximations in use:**

```markdown
## Active Approximations

| Approximation        | Valid regime   | Breaks down when      | Error estimate | Status   |
| -------------------- | -------------- | --------------------- | -------------- | -------- |
| Born approximation   | V << E_kinetic | low-energy scattering | O(V^2/E^2)     | Active   |
| Non-relativistic     | v << c         | E > 100 MeV           | O(v^2/c^2)     | Active   |
| Leading order in 1/N | N > 10         | N ~ 1                 | O(1/N^2)       | Verified |
```

**Figures generated:**

```markdown
## Figures

| ID    | File            | Description            | Script         | Status |
| ----- | --------------- | ---------------------- | -------------- | ------ |
| fig:1 | spectrum.pdf    | Energy spectrum vs N   | plot_spec.py   | Final  |
| fig:2 | convergence.png | Grid convergence study | convergence.py | Draft  |
```

State is written to `${phase_dir}/{phase}-{plan}-STATE-TRACKING.md` and updated after each task.
