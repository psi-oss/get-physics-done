---
template_version: 1
---

> **Status:** Supplemental analysis template. The live `map-research` workflow now loads
> `{GPD_INSTALL_DIR}/references/templates/research-mapper/*` via `gpd-research-mapper`, not this file.
> Keep this template only as standalone reference material for manual analysis work.
>
> For new-project research, use `templates/research.md` (the primary research template, which
> incorporates methods coverage). For workflow-consumed literature survey details, see
> `templates/research-project/METHODS.md`.

# Methods Template

Template for `.gpd/analysis/METHODS.md` - captures the mathematical and computational methods used.

**Purpose:** Document what methods are used to go from theory to results. Focused on "what mathematical techniques and computational tools execute the physics."

---

## File Template

```markdown
# Methods

**Analysis Date:** [YYYY-MM-DD]

## Analytical Methods

**Primary:**

- [Method] - [Where used: e.g., "perturbation theory for PN expansion"]

**Secondary:**

- [Method] - [Where used: e.g., "dimensional regularization for UV divergences"]

## Computational Methods

**Numerical techniques:**

- [Method] - [Purpose: e.g., "adaptive Runge-Kutta for orbital evolution"]

  - Implementation: [e.g., "scipy.integrate.solve_ivp with DOP853"]
  - Parameters: [e.g., "rtol=1e-12, atol=1e-14"]

- [Method] - [Purpose]
  - Implementation: [Details]
  - Parameters: [Configuration]

**Algorithms:**

- [Algorithm] - [Purpose: e.g., "FFT for time-to-frequency domain conversion"]
  - Implementation: [e.g., "numpy.fft.rfft with zero-padding to next power of 2"]
  - Complexity: [e.g., "O(N log N)"]

## Programming Languages

**Primary:**

- [Language] [Version] - [Where used: e.g., "all numerical code"]

**Secondary:**

- [Language] [Version] - [Where used: e.g., "symbolic algebra, derivations"]

## Computational Environment

**Runtime:**

- [Environment] - [e.g., "Python 3.11 with NumPy/SciPy stack"]
- [Additional requirements if any]

**Package manager:**

- [Manager] - [e.g., "uv for Python dependency management"]
- Lockfile: [e.g., "uv.lock present"]

## Symbolic Computation

**Computer algebra:**

- [System] [Version] - [Purpose: e.g., "Mathematica 14 for PN derivations"]

  - Key notebooks: [e.g., "`derivations/pn_energy.nb`"]

- [System] [Version] - [Purpose: e.g., "SymPy for tensor algebra in Python"]
  - Key files: [e.g., "`src/symbolic/tensor_algebra.py`"]

## Simulation Codes

**In-house:**

- [Code name] - [What it simulates]
  - Language: [e.g., "Fortran 90 with MPI"]
  - Input: [e.g., "Parameter file specifying initial conditions"]
  - Output: [e.g., "HDF5 time series of observables"]

**External:**

- [Code name] [Version] - [What it computes for us]
  - Purpose: [e.g., "Reference waveforms for validation"]
  - Interface: [e.g., "Python bindings via pip install"]

## Key Libraries and Dependencies

[Only include dependencies critical to the methods - limit to 5-10 most important]

**Critical:**

- [Library] [Version] - [Why it matters: e.g., "core numerical integration"]
- [Library] [Version] - [Why it matters: e.g., "arbitrary precision arithmetic"]

**Visualization:**

- [Library] [Version] - [e.g., "matplotlib for publication figures"]
- [Library] [Version] - [e.g., "corner for parameter estimation posteriors"]

## Data Formats

**Input data:**

- [Format] - [What uses it: e.g., "HDF5 for numerical relativity waveforms"]
- [Format] - [What uses it: e.g., "ASCII tables for spectral data"]

**Output data:**

- [Format] - [What produces it: e.g., "NumPy .npz for intermediate results"]
- [Format] - [What produces it: e.g., "HDF5 for final waveform banks"]

**Configuration:**

- [Format] - [e.g., "YAML for simulation parameters"]
- [Format] - [e.g., "TOML for project configuration (pyproject.toml)"]

## Verification Methods

**How results are checked:**

- [Method]: [e.g., "Compare against published results at known parameter points"]
- [Method]: [e.g., "Check analytic limits (e.g., test-particle, equal-mass)"]
- [Method]: [e.g., "Convergence tests varying numerical resolution"]
- [Method]: [e.g., "Independent reimplementation by second team member"]

## Platform Requirements

**Development:**

- [Requirements: e.g., "macOS/Linux, Python 3.11+, Mathematica license for symbolic work"]

**Production:**

- [Requirements: e.g., "HPC cluster with MPI for large parameter surveys"]
- [Resources: e.g., "~100 CPU-hours per full analysis run"]

---

_Methods analysis: [date]_
_Update after major methodological changes_
```

<good_examples>

```markdown
# Methods

**Analysis Date:** 2025-06-15

## Analytical Methods

**Primary:**

- Post-Newtonian perturbation theory - Systematic expansion of GR in v/c for binary dynamics and radiation
- Multipolar post-Minkowskian formalism - Waveform generation from source to detector

**Secondary:**

- Dimensional regularization - UV divergences in PN point-particle integrals at 3PN and beyond
- Hadamard regularization (partie finie) - IR divergences in tail integrals
- Pade resummation - Improve convergence of poorly-converging PN flux series

## Computational Methods

**Numerical techniques:**

- Adaptive ODE integration - Evolve binary orbit under radiation reaction

  - Implementation: scipy.integrate.solve_ivp with method='DOP853'
  - Parameters: rtol=1e-12, atol=1e-14; dense_output=True for interpolation
  - File: `src/dynamics/orbital_evolution.py`

- Cubic spline interpolation - Smooth waveform evaluation at arbitrary times
  - Implementation: scipy.interpolate.CubicSpline
  - Parameters: bc_type='not-a-knot'; extrapolation disabled
  - File: `src/waveform/interpolation.py`

**Algorithms:**

- FFT - Convert time-domain waveform to frequency domain

  - Implementation: numpy.fft.rfft with zero-padding to 2^N
  - Complexity: O(N log N), N ~ 10^6 typical
  - File: `src/waveform/frequency_domain.py`

- Reduced order modeling (ROM) - Fast waveform evaluation via SVD basis
  - Implementation: Custom SVD decomposition + greedy basis selection
  - Complexity: O(n^2) evaluation where n ~ 100 basis elements
  - File: `src/waveform/rom.py`

## Programming Languages

**Primary:**

- Python 3.11 - All numerical code, analysis scripts, plotting

**Secondary:**

- Wolfram Language (Mathematica 14) - Symbolic PN derivations, series manipulation
- C (via Cython) - Performance-critical inner loops in waveform evaluation

## Computational Environment

**Runtime:**

- Python 3.11 with scientific stack (NumPy, SciPy, Matplotlib)
- Mathematica 14 kernel for symbolic notebooks

**Package manager:**

- uv for Python dependency management
- Lockfile: uv.lock present and committed

## Symbolic Computation

**Mathematica 14:**

- Purpose: PN expansion of Einstein equations, Hadamard regularization, series acceleration
- Key notebooks:
  - `derivations/pn_energy_flux.nb` - Energy flux to 3.5PN
  - `derivations/tail_integrals.nb` - Hereditary tail and memory contributions
  - `derivations/spin_orbit.nb` - Spin-orbit coupling terms

**SymPy (via Python):**

- Purpose: Automated tensor index manipulation, quick symbolic checks
- Key files: `src/symbolic/christoffel.py`, `src/symbolic/riemann.py`

## Key Libraries and Dependencies

**Critical:**

- NumPy 1.26 - Array operations, linear algebra, FFT
- SciPy 1.12 - ODE integration, interpolation, special functions
- mpmath 1.3 - Arbitrary precision arithmetic for high-order PN coefficients
- h5py 3.10 - HDF5 I/O for waveform data and NR comparison

**Visualization:**

- Matplotlib 3.8 - All publication figures
- corner 2.2 - Parameter estimation posterior plots

## Data Formats

**Input data:**

- HDF5 - NR waveforms from SXS catalog (`data/nr_waveforms/*.h5`)
- ASCII - Detector noise PSDs (`data/noise_curves/*.dat`)
- JSON - Binary parameter sets for batch runs (`configs/*.json`)

**Output data:**

- HDF5 - Final waveform banks and analysis results (`output/*.h5`)
- NumPy .npz - Intermediate numerical results (`cache/*.npz`)
- PDF - Publication figures (`figures/*.pdf`)

**Configuration:**

- YAML - Run parameters (`configs/run_config.yaml`)
- TOML - Project metadata (`pyproject.toml`)

## Verification Methods

**How results are checked:**

- Known limits: Compare equal-mass result against Blanchet (2014) Table I through 3.5PN
- Test-particle limit: Compare nu -> 0 limit against black hole perturbation theory (Fujita 2012)
- Convergence: Verify that N-th PN truncation converges as N increases for v/c < 0.3
- Cross-code: Compare against LALSuite IMRPhenomD at 100 parameter points (max phase diff < 0.05 rad)
- Internal consistency: Energy balance dE/dt = -F verified at each PN order

## Platform Requirements

**Development:**

- macOS or Linux with Python 3.11+
- Mathematica license for symbolic derivation work (optional for purely numerical work)
- ~8 GB RAM sufficient for typical calculations

**Production:**

- Standard workstation for single waveform calculations (~1 CPU-second each)
- HPC cluster with MPI for template bank generation (~10^5 waveforms)
- ~100 CPU-hours for full parameter space survey
- ~1 GB storage per completed template bank

---

_Methods analysis: 2025-06-15_
_Update after major methodological changes_
```

</good_examples>

<guidelines>
**What belongs in METHODS.md:**
- Analytical and computational methods used
- Programming languages and versions
- Simulation codes (in-house and external)
- Key libraries and their roles
- Data formats for input/output
- Symbolic computation tools
- Verification methods
- Platform and resource requirements

**What does NOT belong here:**

- Theoretical framework (that's THEORETICAL_FRAMEWORK.md)
- Notation and conventions (that's CONVENTIONS.md)
- File organization (that's STRUCTURE.md)
- Every Python package installed (only critical ones)
- Specific derivation steps (defer to notebooks)

**When filling this template:**

- Check pyproject.toml or requirements.txt for dependencies
- Identify numerical methods from the core computation code
- Note CAS (computer algebra system) tools and key notebooks
- Include only methods that affect understanding (not every utility)
- Specify versions when version matters for reproducibility

**Useful for research planning when:**

- Adding new calculations (which methods are already available?)
- Choosing implementation approach (must work with existing stack)
- Estimating compute requirements (what resources are needed?)
- Reproducing results (what exact tools and versions were used?)
- Understanding verification strategy (how do we know results are correct?)
  </guidelines>
