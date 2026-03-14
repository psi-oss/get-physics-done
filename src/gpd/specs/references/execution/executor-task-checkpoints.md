# Task Checkpoint Protocol

Load this reference during plan execution. The inline executor prompt has the compact commit type list and staging rules. This file provides the full protocol with examples.

---

## After Each Task Completes

After each task completes (verification passed, done criteria met), checkpoint immediately.

### 1. Check modified files

```bash
git status --short
```

### 2. Stage task-related files individually

**NEVER** use `git add .` or `git add -A`.

```bash
git add derivations/hamiltonian.tex
git add scripts/compute_spectrum.py
git add figures/spectrum.pdf
git add data/eigenvalues.csv
```

**Never stage:**

- `.aux`, `.log`, `.synctex.gz`, `.bbl`, `.blg` (LaTeX intermediates)
- `__pycache__/`, `.ipynb_checkpoints/` (Python artifacts)
- Large binary data files (> 10 MB) without explicit approval
- `.o`, `.mod`, `.exe` (compiled objects)

### 3. Checkpoint type

| Type          | When                                               |
| ------------- | -------------------------------------------------- |
| `derive`      | New equation, relation, or identity established    |
| `compute`     | Numerical result obtained and verified             |
| `implement`   | New code module, function, or script completed     |
| `analyze`     | Data analysis step completed, results extracted    |
| `figure`      | Publication-quality figure generated               |
| `document`    | LaTeX section or notebook section written          |
| `validate`    | Verification/validation step completed             |
| `fix`         | Bug fix, convergence fix, or numerical remedy      |
| `restructure` | Notebook/document restructuring, no physics change |
| `setup`       | Environment, dependencies, build configuration     |

### 4. Commit

```bash
git commit -m "{type}({phase}-{plan}): {concise description of physics content}

- {key result or change 1}
- {key result or change 2}
- {verification performed}
- Conventions: {metric, Fourier, units if relevant to this step}
"
```

### 5. Record hash

```bash
TASK_CHECKPOINT=$(git rev-parse --short HEAD)
```

Track for SUMMARY.

---

## Commit Examples

```bash
git commit -m "derive(02-scattering): establish optical theorem from unitarity

- Derived Im[f(0)] = k*sigma_tot / 4*pi (eq:12)
- Verified: reproduces Born approximation result in weak-coupling limit
- Dimensional analysis: consistent [length^2]
- Convention: metric (+,-,-,-), non-relativistic normalization
"
```

```bash
git commit -m "compute(03-numerics): converged ground state energy for N=100

- E_0 = -0.4327 +/- 0.0003 (Lanczos, 500 iterations)
- Convergence verified: |E_0(500) - E_0(400)| < 1e-6
- Benchmark: agrees with exact diagonalization for N=10
- Error budget: statistical 0, systematic 2e-4, truncation 3e-4
"
```

```bash
git commit -m "implement(04-simulation): Monte Carlo Ising model with Wolff cluster

- Wolff single-cluster algorithm for 2D square lattice
- Verified: reproduces exact T_c for L=8 within 2%
- Performance: 10x faster than Metropolis near T_c
- Seeds and parameters recorded in config.yaml
"
```

```bash
git commit -m "figure(05-results): phase diagram with critical line

- Phase boundary from susceptibility peaks at L=16,32,64
- Finite-size scaling collapse included in inset
- Error bars from bootstrap resampling (1000 samples)
- Convention: temperature in units of J/k_B
"
```
