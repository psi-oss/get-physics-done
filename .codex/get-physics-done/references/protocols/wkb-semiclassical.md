---
load_when:
  - "WKB"
  - "semiclassical"
  - "Bohr-Sommerfeld"
  - "tunneling"
  - "turning point"
  - "connection formula"
  - "eikonal"
  - "stationary phase"
  - "saddle point"
  - "instanton"
tier: 2
context_cost: medium
---

# WKB and Semiclassical Methods Protocol

Physics verification protocol for WKB approximation, Bohr-Sommerfeld quantization, tunneling calculations, and semiclassical path integral methods.

## When This Protocol Applies

- Quantum mechanics in the limit hbar → 0 or short-wavelength limit
- Tunneling through potential barriers
- Energy eigenvalue estimation via Bohr-Sommerfeld
- Semiclassical propagators and trace formulas
- Connection formulas at classical turning points

## Core Validity Condition

WKB is valid when the de Broglie wavelength varies slowly compared to itself:

```
|d lambda / dx| << 1  ⟺  |dp/dx| << p^2/hbar  ⟺  |V'(x)| << p^3/(m*hbar)
```

**Breaks down at:** Classical turning points where p(x) → 0, and near the top of potential barriers where V''(x) changes sign.

## Verification Checklist

### 1. Validity Check
- [ ] Compute `|d lambda/dx|` at representative points — must be << 1 away from turning points
- [ ] Identify ALL classical turning points (where E = V(x))
- [ ] Check that turning points are well-separated (if close, uniform approximation needed)
- [ ] For tunneling: verify barrier width >> de Broglie wavelength inside barrier

### 2. Connection Formula Verification
- [ ] At each turning point, apply the correct Airy function matching:
  - Linear turning point (V' ≠ 0): standard Airy connection formulas
  - Quadratic turning point (V' = 0, V'' ≠ 0): parabolic cylinder functions
- [ ] Check direction of connection: classically allowed → forbidden is different from forbidden → allowed
- [ ] **Critical sign:** The phase factor e^{iπ/4} vs e^{-iπ/4} depends on direction of propagation relative to turning point

### 3. Bohr-Sommerfeld Quantization
- [ ] Contour integral: ∮ p(x) dx = (n + 1/2) * 2π*hbar for 1D bound states
- [ ] The 1/2 (Maslov correction) counts turning points — verify it matches geometry
- [ ] For multi-dimensional: use EBK (Einstein-Brillouin-Keller) quantization on invariant tori
- [ ] Compare first few eigenvalues with exact result (if available) or numerical diagonalization

### 4. Tunneling Calculation
- [ ] Transmission coefficient: T ≈ exp(-2/hbar ∫_{x1}^{x2} |p(x)| dx) where x1, x2 are turning points
- [ ] Pre-exponential factor: include the WKB prefactor 1/√|p(x)| — affects absolute rate
- [ ] For double-well: splitting ΔE ∝ exp(-S_E/hbar) where S_E is Euclidean action through barrier
- [ ] Verify T ≤ 1 (unitarity) — if T > 1, the approximation has broken down

### 5. Dimensional Analysis
- [ ] Action S has dimensions of hbar ([energy × time] or [momentum × length])
- [ ] Phase φ = S/hbar is dimensionless
- [ ] Tunneling exponent is dimensionless: [∫ |p| dx] / [hbar] = 1
- [ ] Prefactor 1/√p has dimensions of [length/momentum]^{1/2} — verify normalization

### 6. Known Limits
- [ ] Harmonic oscillator: WKB gives E_n = hbar*omega*(n+1/2) exactly (one of the few exact WKB results)
- [ ] Free particle: WKB wavefunction = exact plane wave
- [ ] High quantum numbers (n >> 1): WKB eigenvalues → exact eigenvalues (correspondence principle)
- [ ] Deep tunneling (barrier >> E): T → 0 exponentially — verify monotonic decrease with barrier height

## Common Errors

| Error | Symptom | Fix |
|-------|---------|-----|
| Wrong connection formula direction | Exponentially growing solution where decaying expected | Re-derive connection matching at turning point |
| Missing Maslov index | Eigenvalues shifted by 1/2 quantum | Count turning points; Maslov index = #turning points / 2 |
| WKB at turning point | Divergent wavefunction (1/√p → ∞) | Use uniform (Airy) approximation near turning point |
| Forgetting pre-exponential in tunneling | Rate off by polynomial factor | Include √(omega_0/(2π)) prefactor from fluctuation determinant |
| Double-counting in multi-well | Splitting too large by factor 2 | Each instanton-anti-instanton pair contributes once |

## Test Values

**Particle in a box (L=1, m=1, hbar=1):**
- Bohr-Sommerfeld: E_n = (n+1/2)^2 * π^2 / 2 — compare with exact E_n = (n+1)^2 * π^2 / 2
- Error: O(1/n) — WKB gives wrong ground state but excellent for n >> 1

**Harmonic oscillator (omega=1, m=1, hbar=1):**
- WKB: E_n = n + 1/2 — EXACT for all n
- Turning points at x = ±√(2E/omega^2)

**Square barrier tunneling (V_0=2, width=a, E=1, m=1, hbar=1):**
- T_WKB = exp(-2a) for thick barrier
- Compare with exact T = [1 + V_0^2 sinh^2(κa)/(4E(V_0-E))]^{-1} where κ = √(2m(V_0-E))/hbar
