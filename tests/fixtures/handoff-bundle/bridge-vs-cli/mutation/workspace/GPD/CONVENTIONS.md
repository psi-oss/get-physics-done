# Conventions Ledger

**Project:** Cosmological singularity from entangled CFTs
**Created:** 2026-04-09
**Last updated:** 2026-04-09 (Bootstrap)

> This file is append-only for convention entries. When a convention changes, add a new
> entry with the updated value and mark the old entry as superseded. Never delete entries.

---

## Spacetime

### Metric Signature

| Field | Value |
| ----- | ----- |
| **Convention** | Mostly plus for Lorentzian metrics: eta = diag(-1, +1, +1, +1), extended similarly in AdS_5 when needed |
| **Introduced** | Bootstrap |
| **Rationale** | Matches the high-energy holography literature used in the anchor papers and keeps crunch discussions aligned with standard AdS/CFT notation |
| **Dependencies** | FRW sign conventions, curvature sign, holographic stress tensor sign choices |
| **Test value** | Timelike four-momentum satisfies p^2 = -m^2 |

### Coordinate System

| Field | Value |
| ----- | ----- |
| **Convention** | Use boundary time t for CFT evolution, proper time tau for FRW cosmological slices, and a radial AdS coordinate only when the cited paper fixes one explicitly |
| **Introduced** | Bootstrap |
| **Rationale** | Keeps boundary and bulk times distinct across microstate, braneworld, and closed-universe discussions |
| **Dependencies** | Dictionary statements, analytic continuation, reconstruction claims |

### Index Positioning

| Field | Value |
| ----- | ----- |
| **Convention** | Greek indices for spacetime components; repeated upper-lower pairs summed unless a paper-specific convention overrides it temporarily |
| **Introduced** | Bootstrap |
| **Rationale** | Standard GR/holography usage |
| **Dependencies** | Tensor equations, boundary stress tensor, curvature formulas |

## Units

### Natural Units

| Field | Value |
| ----- | ----- |
| **Convention** | hbar = c = k_B = 1 |
| **Introduced** | Bootstrap |
| **Rationale** | Matches the anchor papers and avoids artificial unit conversions during the literature phase |
| **Dependencies** | Entropy, acceleration, curvature, and temperature scales |

## Deferred Conventions

The following conventions are intentionally deferred until a later derivational phase makes them necessary: Fourier convention, curvature sign beyond the cited-paper default, state normalization, commutation convention, and any gamma-matrix or gauge-field conventions.
