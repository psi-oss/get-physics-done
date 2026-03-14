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
