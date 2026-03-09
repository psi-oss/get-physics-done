---
template_version: 1
---

> **Context:** This template is for the `map-theory` workflow — analyzing an EXISTING research project
> to understand its current state. For pre-project literature research, see `templates/research-project/`.

# Connections Template

Template for `.planning/analysis/CONNECTIONS.md` - captures how different parts of the physics connect, what feeds into what, and cross-domain relationships.

**Purpose:** Document what external physics, data sources, and computational resources this research depends on. Focused on "what lives outside our immediate calculation that we rely on."

---

## File Template

```markdown
# Connections

**Analysis Date:** [YYYY-MM-DD]

## Theoretical Inputs

**From other subfields:**

- [Source theory/field] - [What it provides: e.g., "equation of state for neutron star matter"]

  - Input quantity: [e.g., "pressure-density relation P(rho)"]
  - How obtained: [e.g., "tabulated from Lattimer & Prakash (2001)"]
  - Uncertainty: [e.g., "+/- 20% at nuclear saturation density"]

- [Source theory/field] - [What it provides]
  - Input quantity: [e.g., "QCD coupling constant alpha_s(M_Z)"]
  - How obtained: [e.g., "PDG world average"]
  - Uncertainty: [e.g., "alpha_s = 0.1180 +/- 0.0009"]

**From other calculations in this project:**

- [Upstream calculation] - [What it feeds into]
  - Output: [What it produces]
  - Consumer: [What uses it]
  - Interface: [How data is passed: e.g., "JSON file", "function call", "lookup table"]

## Experimental/Observational Data

**Calibration data:**

- [Experiment/Survey] - [What data is used for calibration]
  - Data source: [e.g., "LIGO O3 strain data from GWOSC"]
  - Access: [e.g., "Public via gwosc.org", "Collaboration-internal"]
  - Format: [e.g., "HDF5 time series", "FITS catalog"]

**Validation data:**

- [Experiment/Survey] - [What data is used for comparison]
  - Data source: [e.g., "Planck 2018 CMB power spectra"]
  - Access: [e.g., "Planck Legacy Archive"]
  - Relevant quantities: [e.g., "C_l^TT, C_l^EE for l = 2-2500"]

**Input parameters from experiment:**

- [Measurement] - [What parameter it determines]
  - Value: [e.g., "H_0 = 67.4 +/- 0.5 km/s/Mpc"]
  - Source: [e.g., "Planck 2018, Table 2"]
  - Impact on our results: [e.g., "Sets overall distance scale"]

## Computational Dependencies

**Simulation codes:**

- [Code name] - [What it computes]
  - Version: [e.g., "v3.2.1"]
  - Input: [What we feed it]
  - Output: [What it returns]
  - Interface: [e.g., "Command-line with parameter file", "Python API"]

**Databases and tables:**

- [Database] - [What it contains]
  - Access method: [e.g., "SQL query", "REST API", "local CSV"]
  - Update frequency: [e.g., "Updated annually", "Static"]
  - Key tables/fields: [e.g., "atomic_data.oscillator_strengths"]

**Numerical libraries:**

- [Library] - [What functions are used]
  - Version: [e.g., "NumPy 1.26, SciPy 1.12"]
  - Critical functions: [e.g., "scipy.integrate.solve_ivp for ODE evolution"]
  - Configuration: [e.g., "RK45 with rtol=1e-12"]

## Cross-Domain Connections

**How our physics connects to adjacent fields:**

**[Connection to Field A]:**

- Interface: [What quantity connects the two fields]
- Direction: [We provide X to field A / Field A provides Y to us / Bidirectional]
- Sensitivity: [How sensitive are results to this connection]
- Active collaboration: [Yes/No - who]

**[Connection to Field B]:**

- Interface: [Connecting quantity]
- Direction: [Data flow direction]
- Sensitivity: [Impact assessment]
- Active collaboration: [Yes/No - who]

## Downstream Consumers

**Who uses our results:**

**[Consumer]:**

- What they need: [e.g., "Waveform templates for matched filtering"]
- Format required: [e.g., "Frequency-domain strain h(f) on uniform grid"]
- Accuracy requirement: [e.g., "Phase accuracy < 0.1 rad over 1000 cycles"]
- Interface: [e.g., "LALSuite C library", "Python package"]

**[Consumer]:**

- What they need: [e.g., "Cross section predictions for collider analysis"]
- Format required: [e.g., "Differential distributions in pT and eta"]
- Accuracy requirement: [e.g., "NNLO accuracy, < 5% scale uncertainty"]

## Data Flow Diagram
```

[Upstream Theory/Data]
|
v
[Our Input Processing] --> [Core Calculation] --> [Output Processing]
^ | |
| v v
[Parameter Tables] [Intermediate Results] [Downstream Consumers]
^ |
| v
[Experimental Values] [Validation/Comparison]

```

## Environment and Configuration

**Development:**
- Required data files: [List critical data files and where to obtain them]
- Environment variables: [e.g., "LIGO_DATA_PATH for strain data location"]
- External code setup: [e.g., "LALSuite must be installed separately"]

**Production runs:**
- Compute requirements: [e.g., "100 CPU-hours per waveform bank generation"]
- Storage: [e.g., "~50 GB for full parameter space survey"]
- Dependencies: [e.g., "MPI for parallel runs, HDF5 for output"]

---

*Connections audit: [date]*
*Update when adding or removing external dependencies*
```

<good_examples>

```markdown
# Connections

**Analysis Date:** 2025-06-15

## Theoretical Inputs

**From numerical relativity:**

- NR simulations - Calibration data for the late inspiral and merger regime

  - Input quantity: GW strain h(t) from binary black hole mergers
  - How obtained: SXS catalog (public), BAM code runs (collaboration)
  - Uncertainty: Numerical truncation error ~0.01 rad in phase at merger

- NR fits - Phenomenological coefficients for merger-ringdown
  - Input quantity: Final mass M_f, final spin a_f, QNM frequencies
  - How obtained: Fitting formulas from Husa et al. (2016), Jimenez-Forteza et al. (2017)
  - Uncertainty: < 1% in M_f, < 2% in a_f for mass ratio q < 10

**From black hole perturbation theory:**

- Gravitational self-force - High-order PN coefficients
  - Input quantity: PN expansion coefficients at 6PN and beyond from GSF calculations
  - How obtained: Akcay et al. (2012), Shah et al. (2014), numerical values
  - Uncertainty: Numerical precision ~10^-20 (effectively exact)

**From other calculations in this project:**

- PN orbital dynamics (`src/dynamics/`) - Orbital phase evolution

  - Output: Orbital frequency omega(t), orbital phase phi(t)
  - Consumer: Waveform generator (`src/waveform/`)
  - Interface: Python function call returning numpy arrays

- Waveform generator (`src/waveform/`) - Strain time series
  - Output: h\_+(t), h_x(t) polarizations
  - Consumer: Fisher matrix code (`src/analysis/fisher.py`)
  - Interface: Python function returning complex strain h = h\_+ - i h_x

## Experimental/Observational Data

**Calibration data:**

- LIGO/Virgo O3 - Detector noise power spectral density
  - Data source: GWOSC (Gravitational Wave Open Science Center)
  - Access: Public at gwosc.org/data/
  - Format: ASCII PSD files, units of Hz^{-1/2}
  - File: `data/noise_curves/aLIGO_O3_psd.dat`

**Validation data:**

- GW150914 parameters - First binary black hole detection
  - Data source: LIGO Scientific Collaboration, Abbott et al. (2016)
  - Access: Public (published parameters)
  - Relevant quantities: Masses m_1 = 35.6, m_2 = 30.6 M_sun; chi_eff = -0.01

**Input parameters from experiment:**

- Hubble constant
  - Value: H_0 = 67.4 +/- 0.5 km/s/Mpc (Planck 2018)
  - Source: Planck Collaboration (2020), Table 2
  - Impact on our results: Affects luminosity distance and hence strain amplitude calibration

## Computational Dependencies

**Simulation codes:**

- LALSuite - Reference waveform generation for comparison

  - Version: 7.x (latest stable)
  - Input: Binary parameters (masses, spins, distance, inclination)
  - Output: Frequency-domain strain h(f)
  - Interface: Python via lalsimulation module

- SpEC/SXS - Numerical relativity waveforms for calibration
  - Version: Catalog v2
  - Input: Simulation ID (e.g., SXS:BBH:0305)
  - Output: Waveform modes h\_{lm}(t)
  - Interface: sxs Python package

**Numerical libraries:**

- NumPy 1.26 / SciPy 1.12 - Core numerical computation

  - Critical functions: scipy.integrate.solve_ivp (orbital evolution), scipy.interpolate.CubicSpline (waveform interpolation), numpy.fft (frequency-domain conversion)
  - Configuration: solve_ivp with method='DOP853', rtol=1e-12, atol=1e-14

- mpmath 1.3 - Arbitrary precision arithmetic
  - Critical functions: mpmath.mpf for high-precision PN coefficients
  - Configuration: mp.dps = 50 for coefficient extraction

## Cross-Domain Connections

**Connection to data analysis / parameter estimation:**

- Interface: Waveform templates h(f; theta) as function of source parameters theta
- Direction: We provide waveform models to data analysis pipelines
- Sensitivity: Phase accuracy must be < 1/(2 \* SNR) radians for unbiased parameter estimation
- Active collaboration: Yes - LIGO parameter estimation group

**Connection to cosmology:**

- Interface: Standard siren measurements via luminosity distance from GW amplitude
- Direction: Our distance measurements feed into Hubble constant estimation
- Sensitivity: Distance accuracy limited by waveform systematic errors (~1-5% for loud events)
- Active collaboration: No - downstream use of published results

**Connection to nuclear physics:**

- Interface: Neutron star tidal deformability Lambda connects GW signal to equation of state
- Direction: Nuclear physics provides EOS -> we compute tidal waveform effects -> GW data constrains EOS
- Sensitivity: Lambda enters at 5PN order; detectable for nearby BNS mergers (SNR > 30)
- Active collaboration: Yes - EOS working group provides tabulated Lambda(M) relations

## Downstream Consumers

**LIGO/Virgo search pipelines:**

- What they need: Waveform template banks covering BBH parameter space
- Format required: Frequency-domain h(f) on uniform frequency grid (df = 1/T_obs)
- Accuracy requirement: Fitting factor > 0.97 (< 3% SNR loss) against target signals
- Interface: LALSuite-compatible C functions or interpolated ROM (reduced order model)

**Parameter estimation codes (Bilby/LALInference):**

- What they need: Fast waveform evaluation at arbitrary parameter points
- Format required: Python callable returning h\_+(f), h_x(f) given intrinsic + extrinsic parameters
- Accuracy requirement: Phase error < 0.1 rad over full bandwidth for unbiased PE
- Interface: Bilby waveform plugin following bilby.gw.source interface

## Environment and Configuration

**Development:**

- Required data files: `data/noise_curves/` (detector PSDs), `data/nr_waveforms/` (SXS catalog subset)
- Environment variables: LALSUITE_DATADIR for LAL data files
- External code setup: `pip install lalsuite` for comparison waveforms; `pip install sxs` for NR data

**Production runs:**

- Compute requirements: ~1 CPU-second per waveform evaluation; ~10^5 evaluations for template bank
- Storage: ~1 GB per completed template bank
- Dependencies: No MPI needed (embarrassingly parallel); HDF5 for output storage

---

_Connections audit: 2025-06-15_
_Update when adding or removing external dependencies_
```

</good_examples>

<guidelines>
**What belongs in CONNECTIONS.md:**
- External theories and subfields the calculation depends on
- Input parameters and their sources (experimental values, other calculations)
- Computational dependencies (codes, databases, libraries)
- Cross-domain connections (how the physics links to adjacent fields)
- Downstream consumers (who uses our results and what they need)
- Data flow between components
- Environment setup for external dependencies

**What does NOT belong here:**

- Internal theoretical structure (that's THEORETICAL_FRAMEWORK.md)
- Notation and conventions (that's CONVENTIONS.md)
- Computational methods details (that's METHODS.md)
- Specific results (those belong in research logs)

**When filling this template:**

- Check imports and data loading for external dependencies
- Look for hardcoded parameter values and trace their source
- Identify what other codes or calculations feed into yours
- Document who needs your output and in what format
- Note version numbers and access methods for external resources
- Include uncertainty estimates for input quantities

**Useful for research planning when:**

- Adding new physics (what new inputs are needed?)
- Debugging discrepancies (is an input value outdated?)
- Understanding data flow (what depends on what?)
- Setting up new environments (what external tools are needed?)
- Assessing systematic errors (what input uncertainties propagate?)
- Planning collaborations (who provides what?)

**Important note:**
Document WHERE data lives and HOW to access it, but do not include large datasets inline. Reference file paths, URLs, and access credentials locations (not the credentials themselves).
</guidelines>
