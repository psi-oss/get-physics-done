# Conventions

## Locked Conventions

- **Metric signature:** mostly-plus `(-,+,+,+)` for Lorentzian bulk conventions
- **Coordinate system:** boundary time `t` with spatial region `A`; bulk AdS uses Poincare coordinates `(z,t,\vec{x})` unless a cited anchor specifies otherwise
- **Natural units:** `\hbar = c = k_B = 1`

## Interpretation Notes

- The project is primarily conceptual, so conventions are fixed only where they materially affect comparisons across RT, JLMS, wedge reconstruction, and tensor-network papers.
- When an anchor paper uses a different convention, the comparison should state the translation explicitly rather than silently absorbing it.

## Still Unset

The following canonical convention slots remain unset in the structured lock and should only be filled if a later phase actually needs them:

- Fourier convention
- Gauge choice
- Regularization scheme
- Renormalization scheme
- Spin basis
- State normalization
- Coupling convention
- Index positioning
- Time ordering
- Commutation convention
- Levi-Civita sign
- Generator normalization
- Covariant derivative sign
- Gamma matrix convention
- Creation/annihilation order

## Source Of Truth

The authoritative machine-readable lock is `GPD/state.json` under `convention_lock`. This file is the human-readable mirror for later phase work.
