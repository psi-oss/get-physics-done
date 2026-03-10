---
load_when:
  - "Green function"
  - "Green's function"
  - "propagator"
  - "retarded Green"
  - "advanced Green"
  - "Matsubara Green"
  - "Keldysh"
  - "spectral function"
  - "Lehmann representation"
  - "Dyson equation"
tier: 2
context_cost: medium
---

# Green's Functions Protocol

Physics verification protocol for retarded, advanced, Matsubara, and Keldysh Green's functions in many-body physics and field theory.

## When This Protocol Applies

- Single-particle or two-particle propagators in many-body systems
- Spectral functions and quasiparticle properties
- Linear response theory (Kubo formula)
- Diagrammatic perturbation theory (Feynman, Matsubara)
- Non-equilibrium dynamics (Keldysh formalism)

## Core Definitions

The retarded Green's function (fermionic, zero temperature):

```
G^R(x,t; x',t') = -i θ(t-t') <{ψ(x,t), ψ†(x',t')}>
```

**Key identity:** G^R(ω) = 1/(ω - ε_k - Σ^R(ω)) where Σ^R is the retarded self-energy.

## Verification Checklist

### 1. Analytic Properties
- [ ] **Retarded G^R:** All poles in LOWER half-plane (Im ω < 0). If any pole has Im ω > 0, causality is violated.
- [ ] **Advanced G^A:** All poles in UPPER half-plane. G^A(ω) = [G^R(ω)]*.
- [ ] **Matsubara G(iω_n):** Defined only at discrete frequencies ω_n = (2n+1)πT (fermions) or 2nπT (bosons).
- [ ] **Spectral function:** A(k,ω) = -2 Im G^R(k,ω) ≥ 0 for all ω. NEVER negative.
- [ ] **Kramers-Kronig:** Re G^R(ω) = P ∫ Im G^R(ω')/(ω'-ω) dω'/π. Verify numerically.

### 2. Sum Rules
- [ ] **Spectral sum rule:** ∫ A(k,ω) dω/(2π) = 1 (single-particle). Deviation indicates missing spectral weight.
- [ ] **f-sum rule:** ∫ ω A(k,ω) dω/(2π) = ε_k (free particle) + correction (interactions).
- [ ] **Moment sum rules:** Higher moments ∫ ω^n A(k,ω) dω relate to equal-time commutators — verify first 2-3 moments.
- [ ] **Particle number:** n = ∫ A(k,ω) f(ω) dω dk/(2π)^d where f is Fermi/Bose function.

### 3. Symmetries
- [ ] **Time-reversal:** G^R(k,ω) = G^R(-k,ω) if system is time-reversal invariant.
- [ ] **Particle-hole:** At half-filling on bipartite lattice, G(k,ω) = -G(k+Q,-ω) where Q = (π,π,...).
- [ ] **Hermiticity:** G^R(k,ω)* = G^A(k,ω) = G^R(k,ω*)*.
- [ ] **Bosonic:** G_B(τ) = G_B(τ + β) periodicity; fermionic: G_F(τ) = -G_F(τ + β) anti-periodicity.

### 4. Perturbation Theory
- [ ] **Dyson equation:** G = G_0 + G_0 Σ G (or equivalently G^{-1} = G_0^{-1} - Σ). Check both forms agree.
- [ ] **Self-energy:** Σ must be proper (1PI diagrams only). No disconnected parts. No external leg corrections.
- [ ] **Skeleton expansion:** If using bold (dressed) propagators, verify no double-counting of self-energy insertions.
- [ ] **Luttinger theorem:** Im Σ^R(k_F, ω=0) = 0 at the Fermi surface (Fermi liquid). The Fermi surface volume is fixed by particle number.

### 5. Analytic Continuation (Matsubara → Real Frequency)
- [ ] **Direction:** iω_n → ω + iη (retarded) or iω_n → ω - iη (advanced). NEVER confuse.
- [ ] **Padé approximant:** Use at least N/2 Padé coefficients for N Matsubara points. Check convergence by varying N.
- [ ] **Maximum entropy (MaxEnt):** Verify the default model doesn't dominate. Check the spectral function satisfies sum rules.
- [ ] **Stochastic analytic continuation:** Multiple independent runs should give consistent spectra.
- [ ] **Positive-definiteness:** After continuation, A(ω) ≥ 0 must hold. Negative spectral weight is unphysical.

### 6. Non-Equilibrium (Keldysh)
- [ ] **Contour ordering:** The Keldysh contour goes forward (+) then backward (-). G has 4 components: G^{++}, G^{+-}, G^{-+}, G^{--}.
- [ ] **Physical components:** G^R = G^{++} - G^{+-}, G^A = G^{++} - G^{-+}, G^K = G^{++} + G^{--}.
- [ ] **FDT in equilibrium:** G^K(ω) = (1 - 2f(ω)) [G^R(ω) - G^A(ω)]. If system is in equilibrium, verify this holds.
- [ ] **Causality structure:** G^R(t < 0) = 0, G^A(t > 0) = 0.

### 7. Dimensional Analysis
- [ ] **Single-particle G:** Dimensions of [1/energy] in frequency domain, [1/time] in time domain.
- [ ] **Self-energy Σ:** Same dimensions as energy [eV, Hartree, etc.].
- [ ] **Spectral function A:** Dimensions of [1/energy]. Integral over ω gives dimensionless = 1.
- [ ] **Two-particle G:** Dimensions of [1/energy^2] or [time^2].

## Common Errors

| Error | Symptom | Fix |
|-------|---------|-----|
| Wrong analytic continuation direction | G^R has poles in upper half-plane | iω_n → ω + iη (plus, not minus) for retarded |
| Negative spectral function | A(k,ω) < 0 at some points | Check self-energy: Im Σ^R must have correct sign. MaxEnt artifacts. |
| Sum rule violation | ∫ A dω ≠ 1 | Missing spectral weight — check frequency cutoff, increase grid |
| Mixing retarded and time-ordered | Wrong sign in self-energy | T-ordered G has poles in BOTH half-planes; retarded only in lower |
| Double-counting in skeleton expansion | Self-energy too large | Use bare OR dressed propagators consistently, not mixed |
| Wrong Matsubara frequency | Fermion sum over boson frequencies or vice versa | Fermions: (2n+1)πT, Bosons: 2nπT. Verify. |

## Test Values

**Free electron gas (m=1, hbar=1):**
- G_0^R(k,ω) = 1/(ω - k^2/2 + iη)
- A_0(k,ω) = 2π δ(ω - k^2/2) — delta function at free-particle dispersion
- Im Σ = 0 (no interactions)

**Hubbard atom (single site, U=4, half-filling, T→0):**
- Two poles at ω = ±U/2 = ±2 with equal weight 1/2
- A(ω) = π[δ(ω-2) + δ(ω+2)] — Mott gap = U
- Spectral sum: ∫ A dω/(2π) = 1 ✓

**Lorentzian quasiparticle (ε_k=1, Γ=0.1):**
- G^R(ω) = Z/(ω - ε_k + iΓ) with Z = quasiparticle weight
- A(ω) = 2ZΓ/[(ω-ε_k)^2 + Γ^2] — Lorentzian peak
- Width Γ = quasiparticle lifetime: τ = hbar/(2Γ)
- Sum rule: ∫ A dω/(2π) = Z ≤ 1. Remaining weight (1-Z) is incoherent background.
