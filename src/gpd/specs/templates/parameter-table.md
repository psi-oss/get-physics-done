---
template_version: 1
---

<!-- Used by: parameter-sweep and sensitivity-analysis workflows. -->

# Parameter Table Template

Template for `.gpd/analysis/PARAMETERS.md` - tracks all physical parameters, their values, units, and valid ranges.

**Purpose:** Central registry of physical parameters used across the research project. Ensures consistent values, prevents unit errors, and documents parameter choices with physical justification.

---

## File Template

```markdown
# Physical Parameters

**Analysis Date:** [YYYY-MM-DD]
**Last Updated:** [YYYY-MM-DD]
**Unit System:** [e.g., Natural units ($\hbar = c = k_B = 1$), SI, CGS-Gaussian]

## Fundamental Constants

| Constant                   | Symbol  | Value                   | Units | Source        |
| -------------------------- | ------- | ----------------------- | ----- | ------------- |
| [e.g., Speed of light]     | $c$     | $2.998 \times 10^8$     | m/s   | [CODATA 2018] |
| [e.g., Planck constant]    | $\hbar$ | $1.055 \times 10^{-34}$ | J·s   | [CODATA 2018] |
| [e.g., Boltzmann constant] | $k_B$   | $1.381 \times 10^{-23}$ | J/K   | [CODATA 2018] |

[In natural units, note which constants are set to 1 and the resulting dimension conversions.]

## Model Parameters

| Parameter                 | Symbol | Value / Range | Units           | Physical Meaning       | Justification                                     |
| ------------------------- | ------ | ------------- | --------------- | ---------------------- | ------------------------------------------------- |
| [e.g., Coupling constant] | $g$    | $0.1 - 0.5$   | [Dimensionless] | [Interaction strength] | [Weak coupling regime; perturbation theory valid] |
| [e.g., Lattice spacing]   | $a$    | $0.1$ fm      | fm              | [UV cutoff]            | [Standard lattice QCD value]                      |
| [e.g., Temperature]       | $T$    | $0.01 - 10$   | $T_c$           | [Thermal energy scale] | [Spans ordered and disordered phases]             |

## Derived Quantities

| Quantity                  | Symbol     | Expression                       | Typical Value        | Units |
| ------------------------- | ---------- | -------------------------------- | -------------------- | ----- |
| [e.g., Fermi energy]      | $E_F$      | $\hbar^2(3\pi^2 n)^{2/3}/(2m)$   | $7.0$ eV (Cu)        | eV    |
| [e.g., Debye temperature] | $\Theta_D$ | $\hbar\omega_D / k_B$            | $343$ K (Cu)         | K     |
| [e.g., Skin depth]        | $\delta$   | $\sqrt{2/(\mu_0 \sigma \omega)}$ | [$\sim \mu$m at GHz] | m     |

## Dimensionless Ratios

| Ratio                           | Symbol     | Expression                    | Value / Range | Physical Significance   |
| ------------------------------- | ---------- | ----------------------------- | ------------- | ----------------------- |
| [e.g., Fine structure constant] | $\alpha$   | $e^2/(4\pi\epsilon_0\hbar c)$ | $1/137.036$   | [EM coupling strength]  |
| [e.g., Expansion parameter]     | $\epsilon$ | $v/c$                         | $< 0.3$       | [PN expansion validity] |

## Numerical Parameters

| Parameter           | Symbol     | Value     | Units     | Purpose                     | Convergence Verified                              |
| ------------------- | ---------- | --------- | --------- | --------------------------- | ------------------------------------------------- |
| [e.g., Grid points] | $N$        | $1024$    | —         | [Spatial discretization]    | [Yes: doubled to 2048, <0.1% change]              |
| [e.g., Time step]   | $\Delta t$ | $10^{-3}$ | [natural] | [ODE integration]           | [Yes: halved, <$10^{-6}$ change]                  |
| [e.g., Cutoff]      | $\Lambda$  | $100$     | $E_F$     | [Energy integration cutoff] | [Yes: results independent for $\Lambda > 50 E_F$] |

## Parameter Sets

[Named parameter configurations used in different calculations]

### Set A: [Name, e.g., "Weak coupling benchmark"]

| Parameter | Value     | Notes                          |
| --------- | --------- | ------------------------------ |
| $g$       | $0.1$     | [Perturbation theory reliable] |
| $T$       | $0.5 T_c$ | [Deep in ordered phase]        |
| $N$       | $256$     | [Sufficient for this regime]   |

**Used in:** Phase [X], Phase [Y]
**Purpose:** [e.g., Benchmark against known analytical results]

### Set B: [Name, e.g., "Strong coupling exploration"]

| Parameter | Value     | Notes                                 |
| --------- | --------- | ------------------------------------- |
| $g$       | $2.0$     | [Non-perturbative]                    |
| $T$       | $0.9 T_c$ | [Near critical point]                 |
| $N$       | $1024$    | [Higher resolution needed near $T_c$] |

**Used in:** Phase [Z]
**Purpose:** [e.g., Test beyond perturbative regime]

## Systematic Uncertainties

| Source | Affects | Estimated Size | How to Reduce | Phase |
| --- | --- | --- | --- | --- |
| [e.g., Truncation at 2-loop] | [Cross section] | [~3% from scale variation] | [Compute 3-loop] | [4] |
| [e.g., Finite lattice size L=64] | [Critical exponent nu] | [< 1% from FSS extrapolation] | [Run L=128] | [3] |
| [e.g., Basis set incompleteness] | [Ground state energy] | [~5 meV from CBS extrapolation] | [Larger basis or explicit correlation] | [2] |

[Track systematic uncertainties separately from statistical errors. Each entry should state what physics it affects, how large the effect is estimated to be, and what would reduce it. Update as phases complete and uncertainties are quantified.]

## Unit Conversion Reference

[Quick reference for converting between unit systems used in the project]

| Quantity       | Natural Units | SI                        | CGS                         | Conversion                 |
| -------------- | ------------- | ------------------------- | --------------------------- | -------------------------- |
| [e.g., Energy] | $1$           | $1.602 \times 10^{-19}$ J | $1.602 \times 10^{-12}$ erg | $1 \text{ eV}$             |
| [e.g., Length] | $1$           | $1.973 \times 10^{-7}$ m  | ...                         | $\hbar c / (1 \text{ eV})$ |

---

_Parameter table: [date]_
_Update when parameters change or new ones are introduced_
```

<guidelines>
**What belongs in PARAMETERS.md:**
- All fundamental constants used (with values and sources)
- Model parameters with physical ranges and justification
- Derived quantities with their expressions
- Key dimensionless ratios that control physics
- Numerical parameters with convergence verification
- Named parameter sets for reproducibility
- Unit conversion tables

**What does NOT belong here:**

- Notation conventions (that's NOTATION_GLOSSARY.md or CONVENTIONS.md)
- Broad theoretical framing (that's PRIOR-WORK.md or FORMALISM.md)
- Derivation details (those live in phase files)

**When filling this template:**

- Start with the unit system choice from CONVENTIONS.md
- List fundamental constants actually used (not every constant known to physics)
- For each model parameter: document its physical meaning, valid range, and why that range
- Track dimensionless ratios that control expansion validity or phase boundaries
- Record numerical parameters with convergence evidence
- Group related calculations into named parameter sets

**Why parameter tracking matters:**

- Prevents unit errors (the Mars Climate Orbiter problem)
- Documents which parameter regime validates which approximation
- Enables reproducibility: exact parameters for every calculation
- Supports parameter sweeps: know what ranges have been explored
- Catches inconsistencies: e.g., using $T > T_c$ with an ordered-phase formula

**Convergence verification:**

- Every numerical parameter should have a note on whether convergence was tested
- "Convergence Verified: No" is acceptable early; flag it for later verification
- Convergence testing is a natural task for hypothesis-driven plans
  </guidelines>
