---
name: gpd:parameter-sweep
description: Systematic parameter sweep with parallel execution and result aggregation
argument-hint: "[phase] [--param name --range start:end:steps] [--adaptive] [--log]"
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - find_files
  - search_files
  - task
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Execute a systematic parameter sweep: vary one or more parameters across a range, collect results, and produce summary tables and data. Uses wave-based parallelism for independent parameter values.

**Why a dedicated command:** Parameter sweeps are the workhorse of computational physics — mapping phase diagrams, finding critical points, checking universality, validating scaling laws. But sweeps done ad hoc lead to wasted compute (uniform grids in boring regions), missed features (phase transitions between grid points), and disorganized results (scattered output files). This command structures the sweep from design through execution to analysis.

**The principle:** A well-designed sweep puts points where the physics is, not on a uniform grid. It monitors convergence during execution, refines near interesting features, and produces structured output that downstream analysis can consume.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/parameter-sweep.md
</execution_context>

<context>
Phase: $ARGUMENTS

@.gpd/ROADMAP.md
@.gpd/STATE.md
</context>

<process>
Execute the parameter-sweep workflow from @{GPD_INSTALL_DIR}/workflows/parameter-sweep.md end-to-end.

## 1. Define the Parameter Space

Specify what varies and what stays fixed:

- **Sweep parameters** — which parameters to vary, with ranges and scaling
- **Fixed parameters** — which parameters are held constant (and at what values)
- **Observable(s)** — what to compute at each point
- **Constraints** — any parameter combinations to exclude (e.g., g > g_c for ordered phase only)

### Grid Design

| Grid Type | When to Use | Example |
| --- | --- | --- |
| **Uniform** | Default for smooth observables | `np.linspace(0, 1, 20)` |
| **Logarithmic** | Parameters spanning orders of magnitude (couplings, masses, energies) | `np.logspace(-3, 1, 20)` |
| **Chebyshev** | Need to interpolate the result accurately | `0.5*(1 + cos(pi*k/N))` |
| **Adaptive** | Phase transitions, critical points, sharp features | Start coarse, refine where gradient is large |
| **Latin Hypercube** | Multi-dimensional sweeps with limited budget | `scipy.stats.qmc.LatinHypercube(d=3).random(n=50)` |

```python
import numpy as np

# 1D uniform
g_values = np.linspace(0.0, 2.0, 21)

# 1D logarithmic (for coupling constants, masses)
m_values = np.logspace(-2, 2, 21)  # 0.01 to 100

# 2D grid (tensor product)
g_grid, T_grid = np.meshgrid(
    np.linspace(0, 2, 11),
    np.linspace(0.1, 5.0, 11)
)
param_pairs = list(zip(g_grid.ravel(), T_grid.ravel()))
```

**Resolution guidance:**
- Phase diagrams: 20-50 points per dimension (minimum to resolve boundaries)
- Scaling laws: 10-20 points on log scale (need to fit power law)
- Convergence studies: 5-8 points in geometric sequence (need Richardson extrapolation)
- Quick survey: 5-10 points to find interesting region, then refine

## 2. Parallelization Strategy

Group sweep points into independent waves for parallel execution:

```
Wave 1: [g=0.0, g=0.4, g=0.8, g=1.2, g=1.6, g=2.0]  — coarse skeleton
Wave 2: [g=0.2, g=0.6, g=1.0, g=1.4, g=1.8]           — fill in gaps
Wave 3: [adaptive refinement near features found in waves 1-2]
```

**Wave design principles:**
- Wave 1 covers the full range at coarse resolution — reveals the landscape
- Wave 2 fills in the gaps — smooth regions need no more, interesting regions get wave 3
- Wave 3+ adapts: refine near phase transitions, critical points, extrema, or unexpected features
- Within each wave, all points are independent and execute in parallel via task tool

For multi-dimensional sweeps, each wave executes a slice or random subset of the full grid.

## 3. Convergence Monitoring During Sweep

After each wave completes, check whether the results are sufficiently resolved:

```python
def needs_refinement(x_values, y_values, threshold=0.1):
    """Identify intervals needing refinement."""
    refine_at = []
    for i in range(len(y_values) - 1):
        # Large relative change between adjacent points
        dy = abs(y_values[i+1] - y_values[i])
        y_scale = max(abs(y_values[i]), abs(y_values[i+1]), 1e-10)
        if dy / y_scale > threshold:
            refine_at.append(0.5 * (x_values[i] + x_values[i+1]))
    return refine_at
```

**Convergence criteria:**
- **Smooth regions** — relative change between adjacent points < 10% (or user-specified tolerance)
- **Near critical points** — switch to fine grid, estimate critical exponent from log-log slope
- **Discontinuities** — identify jump location, report as phase boundary
- **Divergences** — identify divergence location, fit critical exponent, report pole

## 4. Adaptive Refinement (--adaptive flag)

When `--adaptive` is specified, the sweep automatically refines:

1. Execute wave 1 (coarse grid)
2. Analyze results: find large gradients, sign changes, extrema
3. Generate wave 2 centered on interesting features
4. Repeat until convergence criterion is met or budget is exhausted

```python
def adaptive_sweep(compute_f, x_range, initial_points=10, max_points=100, tol=0.05):
    """Adaptive 1D sweep with refinement."""
    x = np.linspace(x_range[0], x_range[1], initial_points)
    y = np.array([compute_f(xi) for xi in x])

    while len(x) < max_points:
        new_points = needs_refinement(x, y, threshold=tol)
        if not new_points:
            break
        new_y = np.array([compute_f(xi) for xi in new_points])
        x = np.sort(np.concatenate([x, new_points]))
        y = np.array([compute_f(xi) for xi in x])

    return x, y
```

## 5. Output Format

Structured output for downstream analysis:

```markdown
---
sweep_type: {1d | 2d | nd}
parameters: [{name, range, scale, points}]
observable: {name}
total_points: {N}
date: {YYYY-MM-DD}
---

# Parameter Sweep: {observable} vs {parameters}

## Configuration

| Parameter | Range | Scale | Points |
| --- | --- | --- | --- |
| {param} | [{lo}, {hi}] | {linear/log} | {N} |

Fixed: {param} = {value}, {param} = {value}

## Results

### Data Table

| {param1} | {param2} | {observable} | Converged | Notes |
| --- | --- | --- | --- | --- |
| {val} | {val} | {val} | yes/no | {any issues} |

### Features Detected

- **Phase boundary** at {param} ≈ {value}: {description of transition}
- **Extremum** at {param} = {value}: {observable} = {value}
- **Scaling law**: {observable} ~ {param}^{exponent} for {regime}

### Data Files

- `sweep-results.json` — raw sweep results (machine-readable)
- `SWEEP-SUMMARY.md` — metadata, detected features, and interpretation
```

Save to:
- Internal sweep docs: `.gpd/phases/{phase-dir}/sweep-{PADDED_INDEX}-PLAN.md`, `.gpd/phases/{phase-dir}/sweep-{PADDED_INDEX}-SUMMARY.md`, and `.gpd/phases/{phase-dir}/SWEEP-SUMMARY.md`
- Durable sweep artifacts: `artifacts/phases/{phase-dir}/sweeps/{sweep-slug}/`

Do not put machine-readable sweep datasets under `.gpd/phases/**` or `.gpd/analysis/**`. Keep the `.gpd` documents as internal execution records and write the durable JSON/CSV outputs to `artifacts/`.

## 6. Common Pitfalls

### Uniform grids waste compute near phase transitions
Phase transitions concentrate physics in narrow parameter regions. A uniform grid with 100 points may have 90 points in boring regions and 10 points near the transition — insufficient to resolve the critical behavior. Use adaptive refinement or prior knowledge to concentrate points.

### Missing the critical point between grid points
If the observable changes sign between two grid points, the zero crossing (often a critical point) is missed entirely. Always check for sign changes and interpolate.

### Multi-dimensional sweeps scale exponentially
A 10-point grid in each of 5 dimensions is 10⁵ = 100,000 evaluations. Use Latin Hypercube Sampling, Sobol sequences, or adaptive methods for d > 2.

### Hysteresis near first-order transitions
First-order phase transitions show hysteresis: sweeping up gives a different result from sweeping down. Run the sweep in both directions near suspected first-order transitions to detect metastability.

### Not checking convergence at each point
A sweep that varies a physical parameter should also verify that the numerical computation at each point is converged. A phase diagram computed on an unconverged grid is meaningless. Run `/gpd:numerical-convergence` on representative points.

</process>

<success_criteria>

- [ ] Parameter space fully defined (sweep params, fixed params, ranges, scaling)
- [ ] Grid type selected with justification (uniform, log, adaptive, etc.)
- [ ] Wave structure designed for parallel execution
- [ ] Sweep executed with convergence monitoring
- [ ] Adaptive refinement applied near interesting features (if --adaptive)
- [ ] Phase boundaries, extrema, and scaling laws identified
- [ ] Machine-readable data files produced (CSV, JSON)
- [ ] Summary report with detected features and visualizations
- [ ] Convergence verified at representative points
      </success_criteria>
