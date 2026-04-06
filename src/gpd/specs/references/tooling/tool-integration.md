# Computational Tool Integration

GPD generates code for the tools physicists actually use. This reference guides agents on which libraries, languages, and tools are standard for different types of physics computations.

<purpose>
This reference is loaded by GPD agents when generating code or recommending computational approaches. It provides:

1. **For the planner (gpd-planner):** Which tools are appropriate for the computational task at hand
2. **For the executor (gpd-executor):** Correct library APIs, idiomatic patterns, and best practices
3. **For the verifier (gpd-verifier):** How to set up independent numerical checks using alternative tools
4. **For the researcher (gpd-phase-researcher):** What software ecosystem to investigate for a given problem
   </purpose>

---

## Package Preference Policy

**Principle: Prefer adapting existing packages before writing code from scratch.**

Physics software has decades of accumulated domain knowledge, edge-case handling, and community testing. A custom reimplementation rarely matches the reliability of an established package, and the development time is almost always better spent on the physics.

### Decision Hierarchy

When a computational task arises, follow this order:

1. **Use an existing package directly.** Configure it, call its API, write a thin wrapper. This is the default and requires no justification.
2. **Adapt an existing package.** Subclass, extend, monkey-patch, or fork. Justified when the package covers 70%+ of the need but lacks a specific feature.
3. **Combine existing packages.** Write glue code between established tools. Justified when the problem decomposes into subproblems each solved by a different package.
4. **Write custom code.** Justified ONLY when:
   - No package implements the required algorithm or physics
   - The adaptation overhead genuinely exceeds a clean implementation
   - Performance requirements cannot be met by existing tools
   - The plan's `package_strategy` frontmatter documents the justification

### Common Domains and Their Standard Packages

| Computational Need | Standard Packages | Do NOT Rewrite |
|--------------------|-------------------|----------------|
| ODE/PDE integration | SciPy, DifferentialEquations.jl, FEniCS | Adaptive timesteppers, stiff solvers |
| Monte Carlo sampling | emcee, PyMC, Stan | MCMC walkers, convergence diagnostics |
| Molecular dynamics | LAMMPS, OpenMM, GROMACS, ASE | Force field evaluation, neighbor lists, integrators |
| Quantum dynamics | QuTiP, Qiskit, Cirq | Master equations, state tomography, gate decomposition |
| Electronic structure | PySCF, Quantum ESPRESSO, VASP | SCF loops, exchange-correlation functionals |
| Tensor networks | ITensors.jl, TeNPy, quimb | Contraction ordering, DMRG sweeps |
| Symbolic algebra | SymPy, Mathematica, FORM | Pattern matching, simplification engines |
| Linear algebra | NumPy/SciPy (LAPACK/BLAS), Eigen | Matrix decompositions, sparse solvers |
| Fluid dynamics | Dedalus, OpenFOAM, Firedrake | Spectral methods, mesh generation |
| Lattice field theory | Grid, Chroma, openQCD | Gauge field updates, fermion inversions |
| N-body / orbital | REBOUND, Gadget, AREPO | Gravity solvers, tree codes, SPH |
| Statistical analysis | pandas, xarray, uncertainties | Data manipulation, error propagation |
| Optimization | SciPy, NLopt, Optuna | Constrained optimization, hyperparameter tuning |

### Anti-Patterns

- **Reimplementing a Runge-Kutta integrator** when `scipy.integrate.solve_ivp` exists
- **Writing a custom MCMC sampler** when `emcee` or `PyMC` handles the problem
- **Building a molecular dynamics engine** when LAMMPS/OpenMM has the required force fields
- **Coding matrix diagonalization** when `scipy.linalg.eigh` wraps optimized LAPACK routines
- **Writing a custom FFT** when `numpy.fft` or `FFTW` exists
- **Implementing a finite element solver** when FEniCS/Firedrake handles the PDE class

### When Custom Code IS Appropriate

- Novel algorithms not yet in any package (document the novelty)
- Tight inner loops where Python overhead is prohibitive and no compiled package exists
- Highly specialized physics with no community package (e.g., novel lattice actions, custom effective potentials)
- Educational/pedagogical implementations where understanding the algorithm is the goal
- Prototyping a new method before packaging it

---

## Python Scientific Stack

- **NumPy/SciPy** -- Numerical linear algebra, integration, optimization, special functions
- **SymPy** -- Symbolic computation, algebraic manipulation, simplification
- **matplotlib** -- Publication-quality figures, phase diagrams, dispersion relations
- **QuTiP** -- Quantum dynamics, master equations, Lindblad evolution
- **Qiskit / Cirq** -- Quantum circuit simulation and analysis

### When to use Python

Python is the default choice for most physics computations. Use it for:

- Prototyping numerical methods before optimizing
- Symbolic algebra that feeds into numerical evaluation
- Data analysis and visualization
- Quantum computing and quantum optics simulations
- Any computation where development time matters more than runtime

---

## Mathematica / Wolfram Language

- Symbolic integration and summation
- Series expansion, asymptotic analysis
- Tensor algebra, differential geometry computations
- Generating Mathematica notebooks with proper formatting

### When to use Mathematica

Mathematica excels at:

- Heavy symbolic manipulation (multi-page expressions, tensor contractions)
- Exploring mathematical structure before committing to a numerical approach
- Computations involving special functions, hypergeometric identities, or combinatorics
- Visualization of complex mathematical objects

---

## Julia

- **DifferentialEquations.jl** -- High-performance ODE/PDE solvers
- **ITensors.jl** -- Tensor network methods, DMRG
- **QuantumOptics.jl** -- Quantum systems simulation

### When to use Julia

Julia is the right choice when:

- Performance matters but you want high-level syntax (tight loops, large-scale linear algebra)
- The problem involves stiff differential equations or adaptive time-stepping
- Tensor network calculations require efficient contractions
- You need compiled performance without writing C/Fortran

---

## Fortran / C / C++

- Performance-critical numerical routines
- Code that interfaces with established physics libraries (LAPACK, BLAS, FFTW)
- MPI parallelization for large-scale simulations

### When to use Fortran/C/C++

Use compiled languages when:

- The computation is dominated by a tight inner loop that must run for hours/days
- Interfacing with existing physics codes (Quantum ESPRESSO, LAMMPS, etc.)
- MPI-parallel simulations on clusters
- Memory layout control is critical for performance

---

## LaTeX

- Structured paper writing with consistent notation
- Equation environments, theorem formatting, bibliography management
- TikZ/PGFPlots figure generation
- Beamer presentation slides

### Best practices

- Use `\newcommand` for all physics quantities to enforce notation consistency
- Prefer `align` over `eqnarray` for multi-line equations
- Use `siunitx` for units and numerical values
- Use `hyperref` and `cleveref` for cross-references

---

## Data Analysis

- **pandas / xarray** -- Structured data from simulations
- **h5py** -- HDF5 data files common in computational physics
- **uncertainties** -- Error propagation
- **emcee / PyMC** -- Bayesian inference, MCMC sampling

### Data management patterns

- Store raw simulation output in HDF5 with metadata attributes
- Use xarray for multi-dimensional parameter sweeps with labeled axes
- Propagate uncertainties through post-processing pipelines
- Version-control analysis scripts, not data files
