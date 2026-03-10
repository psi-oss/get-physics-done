---
load_when:
  - "verification"
  - "physics check"
  - "which verification file"
tier: 1
context_cost: small
---

# Verification Patterns — Index

This document has been split into modular files for better context efficiency. Load only the files relevant to your current work.

## Quick Start

For most verification needs, start with the quick reference:
- **`verification-quick-reference.md`** — Compact 14-check checklist, decision tree, domain quick-checks (~9KB)

## Modular Files

| File | Size | Content | Load When |
|------|------|---------|-----------|
| `verification-core.md` | ~15KB | Dimensional analysis, limiting cases, symmetry, conservation laws, order-of-magnitude, physical plausibility, in-execution validation, cancellation detection | Always — universal checks for any physics |
| `verification-numerical.md` | ~15KB | Convergence testing, cross-checks with literature, statistical validation, automated verification framework | Working with numerical calculations or simulations |
| `verification-domain-qft.md` | ~10KB | Ward identities, unitarity, causality, positivity, crossing symmetry | QFT, scattering, renormalization |
| `verification-domain-condmat.md` | ~10KB | Spectral sum rules, Kramers-Kronig, spectral representations | Many-body physics, response functions, spectral analysis |
| `verification-domain-statmech.md` | ~10KB | Thermodynamic consistency, detailed balance, KMS/FDT | Phase transitions, Monte Carlo |
| `verification-domain-gr-cosmology.md` | ~12KB | Constraint propagation, gauge invariance, energy conditions, Friedmann consistency, GW energy balance | General relativity, cosmology, black holes, gravitational waves |
| `verification-domain-amo.md` | ~10KB | Selection rules, dipole/RWA validity, Rabi normalization, TRK sum rule, decoherence, AC Stark shift | Atomic physics, quantum optics, cold atoms, laser-atom interaction |
| `verification-domain-nuclear-particle.md` | ~12KB | Crossing symmetry, chiral power counting, parton sum rules, CKM unitarity, heavy quark symmetry | Nuclear physics, collider phenomenology, flavor physics |
| `verification-domain-astrophysics.md` | ~10KB | Eddington luminosity, Jeans mass, hydrostatic/TOV, nuclear burning rates, GW source consistency | Stellar structure, accretion, compact objects, nucleosynthesis |
| `verification-domain-mathematical-physics.md` | ~12KB | Self-adjointness, spectral theory, index theorems, modular invariance, anomaly cancellation, representation completeness | Rigorous proofs, topology, functional analysis, integrable systems |
| `verification-domain-string-field-theory.md` | ~10KB | BRST nilpotency, ghost/picture counting, BPZ cyclicity, truncation convergence, tachyon benchmarks | Open/closed string field theory, tachyon condensation, off-shell string amplitudes |
| `verification-domain-fluid-plasma.md` | ~12KB | MHD equilibrium, Alfven waves, reconnection, turbulence spectra, conservation laws, CFL, div(B), Rankine-Hugoniot | Fluid dynamics, MHD, plasma physics, turbulence |

## Typical Loading Patterns

**Analytical derivation:** `verification-core.md` + domain file
**Numerical calculation:** `verification-core.md` + `verification-numerical.md` + domain file
**Monte Carlo simulation:** `verification-numerical.md` + `verification-domain-statmech.md`
**Response function calculation:** `verification-domain-condmat.md` + `verification-numerical.md`
**Scattering amplitude:** `verification-core.md` + `verification-domain-qft.md`
**String field theory:** `verification-core.md` + `verification-domain-string-field-theory.md`
**MHD/fluid simulation:** `verification-numerical.md` + `verification-domain-fluid-plasma.md`
**Paper-ready result:** All files relevant to the domain

## See Also

- `llm-physics-errors.md` — Catalog of 101 LLM-specific error classes with detection strategies
- `llm-errors-traceability.md` — Compact traceability matrix mapping errors to verification checks
- `physics-subfields.md` — Subfield-specific methods, tools, and pitfalls
- `checkpoints.md` — Pre-checkpoint automation and computational environment management
