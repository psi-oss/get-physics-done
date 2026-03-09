---
load_when:
  - "many-body"
  - "Hartree-Fock"
  - "DMFT"
  - "dynamical mean-field"
  - "BCS"
  - "superconductivity"
  - "Green function"
  - "self-consistency"
  - "Dyson equation"
  - "quasiparticle"
  - "Fermi liquid"
  - "Luttinger"
  - "sign problem"
  - "quantum Monte Carlo"
  - "self-energy"
  - "spectral function"
  - "Matsubara"
  - "Hubbard"
  - "Anderson model"
  - "Kondo"
tier: 2
context_cost: medium
---

# Quantum Many-Body Methods Protocol

Quantum many-body physics sits at the heart of condensed matter, nuclear physics, and quantum chemistry. The methods here — Hartree-Fock, Green's functions, DMFT, quantum Monte Carlo, BCS theory — are the workhorses of modern materials science and strongly correlated electron physics.

**Core discipline:** Many-body systems have exponentially large Hilbert spaces. Every method makes approximations to tame this complexity. The art is knowing WHICH approximation is valid WHERE. Using mean-field theory for a strongly correlated system, or perturbation theory when the coupling is order unity, gives plausible-looking but wrong results.

## Related Protocols

- `many-body-perturbation-theory.md` — Diagrammatic perturbation theory, Feynman rules for condensed matter
- `density-functional-theory.md` — DFT for electronic structure (single-particle framework)
- `exact-diagonalization.md` — Small-system exact solutions (benchmark)
- `tensor-networks.md` — DMRG, MPS for 1D systems
- `bethe-ansatz.md` — Exact solutions for integrable 1D models (spin chains, Hubbard, Lieb-Liniger)
- `large-n-expansion.md` — 1/N expansion for O(N) and SU(N) models, saddle-point methods
- `monte-carlo.md` — General MCMC methodology
- `finite-temperature-field-theory.md` — Matsubara formalism, imaginary time

---

## Step 1: Classify the Problem

| Regime | Characteristic | Appropriate Methods |
|--------|---------------|-------------------|
| **Weakly correlated** | U/t < 1, Fermi liquid | DFT, HF, perturbation theory, GW |
| **Moderately correlated** | U/t ~ 1-4 | DMFT, cluster DMFT, GW+DMFT |
| **Strongly correlated** | U/t > 4 | QMC, ED, tensor networks, slave particles |
| **Near quantum critical point** | ξ → ∞ | RG, conformal bootstrap, QMC with careful finite-size scaling |
| **Superconducting** | Attractive interaction channel | BCS/BdG, Eliashberg, DMFT+phonons |

where U = interaction strength, t = hopping/bandwidth.

**CRITICAL:** DFT and Hartree-Fock are mean-field theories. They fail qualitatively for Mott insulators (predict metals), heavy fermion systems (miss Kondo physics), and unconventional superconductors (miss pairing mechanism). Always check if the system is in the mean-field validity regime.

---

## Step 2: Green's Function Formalism

The single-particle Green's function is the central object:

### Matsubara (imaginary time, finite T)

G(k, iωₙ) = 1/(iωₙ - εₖ - Σ(k, iωₙ))

where ωₙ = (2n+1)πT (fermions) or 2nπT (bosons), εₖ = bare dispersion, Σ = self-energy.

### Retarded (real frequency)

G^R(k, ω) = 1/(ω - εₖ - Σ^R(k, ω) + iη)

**CRITICAL RELATIONS:**
- Spectral function: A(k, ω) = -Im G^R(k, ω) / π
- Sum rule: ∫ A(k, ω) dω = 1 (for each k)
- Causality: Im Σ^R(k, ω) ≤ 0 (quasiparticle decay rate is non-negative)
- Kramers-Kronig: Re G^R and Im G^R are related by Hilbert transform

**Common LLM Error:** Confusing Matsubara and retarded Green's functions. G(k, iωₙ) is defined at discrete imaginary frequencies. G^R(k, ω) is defined on the real axis. They are related by analytic continuation: G^R(ω) = G(iωₙ → ω + iη). But analytic continuation of noisy numerical data is an ill-posed problem — small errors in G(iωₙ) produce large errors in A(ω).

### Dyson Equation

G = G₀ + G₀ Σ G (operator equation)
G⁻¹ = G₀⁻¹ - Σ (matrix equation)

**Sign convention WARNING:** Some references define Σ with opposite sign: G⁻¹ = G₀⁻¹ + Σ. Check which convention your references use and be consistent. Mixing sign conventions between producer (derivation) and consumer (numerical code) phases is error class #2.

---

## Step 3: Self-Consistent Methods

### Hartree-Fock

The simplest self-consistent method. Replace interaction with a mean field:

1. Start with initial density matrix ρ⁰
2. Construct Fock matrix: F[ρ] = h + J[ρ] - K[ρ] (Coulomb + exchange)
3. Diagonalize: F φᵢ = εᵢ φᵢ
4. Build new density: ρ¹ = Σᵢ f(εᵢ) |φᵢ⟩⟨φᵢ|
5. If ||ρ¹ - ρ⁰|| < ε_tol → converged. Else ρ⁰ ← mix(ρ⁰, ρ¹) and go to 2.

**Convergence tricks:**
- Linear mixing: ρ_new = α ρ_out + (1-α) ρ_in with α = 0.1-0.3
- DIIS (Pulay mixing): extrapolate from history of density matrices
- Level shifting: add constant to virtual orbital energies to stabilize convergence

**Common LLM Error:** Not mixing the density matrix. Using ρ_out directly as the new ρ_in almost always diverges. Linear mixing with α ~ 0.2 is the minimum requirement.

### DMFT (Dynamical Mean-Field Theory)

DMFT maps a lattice problem to a self-consistent impurity problem:

1. Start with initial self-energy Σ⁰(iωₙ)
2. Compute local Green's function: G_loc(iωₙ) = Σₖ 1/(iωₙ - εₖ - Σ(iωₙ))
3. Extract Weiss field: G₀⁻¹(iωₙ) = G_loc⁻¹(iωₙ) + Σ(iωₙ)
4. Solve impurity problem: G_imp(iωₙ) = F[G₀] (using ED, QMC, NRG, etc.)
5. Extract new self-energy: Σ_new = G₀⁻¹ - G_imp⁻¹
6. If ||Σ_new - Σ⁰|| < ε_tol → converged. Else Σ⁰ ← Σ_new and go to 2.

**MANDATORY checks at each DMFT iteration:**
- [ ] Im Σ(iωₙ) ≤ 0 for all ωₙ (causality)
- [ ] Σ(iωₙ → ∞) → U⟨n⟩ (high-frequency tail, Hartree shift)
- [ ] G_loc satisfies sum rule: -G_loc(τ → 0⁻) = ⟨n⟩
- [ ] Convergence metric decreasing monotonically

**Common LLM Error:** Using a bath discretization with too few bath sites in ED-based DMFT. The impurity solver needs enough bath sites to represent the continuous bath. Minimum: N_bath ≥ 4-6 for single-orbital models, ≥ 8-12 for multi-orbital.

---

## Step 4: Quantum Monte Carlo

### Auxiliary-Field QMC (AFQMC)

Decomposes the interaction via Hubbard-Stratonovich transformation, then samples the auxiliary field.

**The sign problem:** For generic fermion systems, the weight w(σ) = det(M_↑(σ)) × det(M_↓(σ)) can be negative, causing exponentially growing statistical errors. The average sign ⟨sign⟩ ~ exp(-βΔF N) where ΔF is the free energy difference.

**Sign-problem-free cases:**
- Half-filled Hubbard model with particle-hole symmetry
- Attractive Hubbard model (pairing channel)
- Some frustrated magnets with specific lattice geometries

**Verification:**
- [ ] Monitor ⟨sign⟩ throughout the simulation. If ⟨sign⟩ < 0.1, results are unreliable.
- [ ] Imaginary-time correlation functions must be positive (for density-density) or have correct symmetry
- [ ] Finite-size scaling: results at L and 2L should be consistent within error bars (away from phase transitions)

### Determinantal QMC

Similar to AFQMC but works with the determinant directly:

G(τ) = ⟨Tτ c(τ) c†(0)⟩ computed from the ratio of determinants.

**Common LLM Error:** Updating the Green's function matrix incorrectly after a single-spin flip. The Sherman-Morrison formula gives the rank-1 update:

G_new = G_old + (G_old[:,i] - δ[:,i]) ⊗ (G_old[i,:] × R) / (1 + R × G_old[i,i])

where R = exp(Δs × V) - 1 and i is the flipped site. Getting the indices or the ratio wrong corrupts all subsequent measurements.

---

## Step 5: BCS / BdG Theory

For superconductivity, the BCS mean-field decoupling:

H_BdG = Σₖ (εₖ c†ₖ↑ cₖ↑ + εₖ c†₋ₖ↓ c₋ₖ↓ + Δₖ c†ₖ↑ c†₋ₖ↓ + Δₖ* c₋ₖ↓ cₖ↑)

Bogoliubov quasiparticles: Eₖ = √(εₖ² + |Δₖ|²)

**Self-consistency (gap equation):**

Δₖ = -Σₖ' Vₖₖ' Δₖ'/(2Eₖ') × tanh(Eₖ'/(2T))

**MANDATORY checks:**
- [ ] Gap equation is self-consistent (converged Δₖ satisfies the equation)
- [ ] Δ → 0 at T = T_c (defines the critical temperature)
- [ ] Eₖ > 0 for all k (quasiparticle spectrum is gapped in the superconducting state)
- [ ] At T = 0: Δ₀ = 1.764 × T_c for weak-coupling BCS (s-wave)
- [ ] Specific heat jump at T_c: ΔC/γT_c = 1.43 (BCS universal ratio)

**Common LLM Error:** Using the BCS gap equation above T_c. The self-consistent solution is Δ = 0 for T > T_c. Running the gap equation iteration above T_c with a nonzero initial guess will converge to Δ = 0 (correctly), but the convergence can be slow and misleading.

---

## Step 6: Analytic Continuation

Converting from Matsubara to real frequencies is the final step in many calculations. This is numerically ill-conditioned.

| Method | Reliability | Best For |
|--------|-----------|---------|
| **Padé approximants** | Low (sensitive to noise) | Quick estimates, few Matsubara points |
| **Maximum entropy (MaxEnt)** | Medium (requires default model) | General spectral functions |
| **Stochastic analytic continuation** | Medium-high | When MaxEnt default model is uncertain |
| **Nevanlinna** | High (preserves causality) | When causality is paramount |

**CRITICAL:** Analytic continuation amplifies noise. If G(iωₙ) has 0.1% error at each Matsubara frequency, A(ω) can have 100%+ errors at some frequencies. Always:
- [ ] Check that ∫ A(ω) dω = 1 (sum rule)
- [ ] Check A(ω) ≥ 0 for all ω (spectral positivity)
- [ ] Compare results from 2+ different continuation methods
- [ ] If results disagree qualitatively → increase Matsubara accuracy before re-continuing

---

## Worked Example: Single-Band Hubbard Model at Half-Filling

**Problem:** Determine whether the half-filled Hubbard model on a square lattice with U/t = 8 is a metal or a Mott insulator at T = 0.

### Solution

**Step 1:** Classify: U/t = 8 > 4 → strongly correlated. DFT/HF will predict a metal (wrong). Need DMFT or QMC.

**Step 2:** DMFT approach:
- Lattice: square, half-bandwidth W = 4t, density of states: semi-elliptical (Bethe lattice approximation for DMFT)
- Self-consistency: Σ(iωₙ) → G_loc → G₀ → impurity solver → Σ_new
- Impurity solver: ED with N_bath = 6

**Step 3:** Key observable: spectral function A(ω) at the Fermi level.
- If A(ω = 0) > 0 → metal (quasiparticle peak at Fermi level)
- If A(ω = 0) = 0 → Mott insulator (gap at Fermi level)

**Step 4:** At U/t = 8 with Bethe lattice DOS, DMFT gives:
- Mott gap: Δ_Mott ≈ U - W = 8t - 4t = 4t (rough estimate)
- More precisely: the gap opens at U_c2 ≈ 5.8t (Bethe lattice), so U/t = 8 is well inside the Mott phase
- Self-energy: Im Σ(ω → 0) diverges (no quasiparticle at Fermi level)

**Verification:**
- [ ] At U = 0: metallic (free electrons) ✓
- [ ] At U → ∞: Mott insulator (localized spins) ✓
- [ ] Mott transition at U_c ≈ 5.8t (Bethe lattice, zero T, DMFT): U/t = 8 > U_c → insulator ✓
- [ ] Spectral sum rule ∫ A(k, ω) dω = 1 ✓
- [ ] Im Σ(iωₙ) < 0 for all ωₙ (causality) ✓
- [ ] Luttinger theorem: in metallic phase, Fermi surface volume = electron density. In Mott phase: violated (Luttinger surface) ✓

---

## Common LLM Error Patterns

| Error | LLM Symptom | Detection | Error Class |
|-------|-------------|-----------|-------------|
| Green's function type confusion | Uses Matsubara G at real frequency | Check: G(iωₙ) vs G^R(ω), analytic continuation required | #3 |
| Self-energy sign convention | G⁻¹ = G₀⁻¹ - Σ vs G⁻¹ = G₀⁻¹ + Σ | Check Hartree limit: Σ → U⟨n⟩ with correct sign | #2 |
| Mean field for strong coupling | HF/DFT for U/t > 4 | Check U/t ratio; if > 2, question mean-field validity | #5 |
| Missing self-consistency | One-shot perturbation theory | Check: is the self-energy fed back into G? | #5 |
| QMC sign problem ignored | Reports QMC results with ⟨sign⟩ < 0.01 | Monitor ⟨sign⟩; reject results if < 0.1 | #27 |
| Wrong BCS ratio | Δ₀/T_c ≠ 1.764 for weak-coupling s-wave | Compute ratio and compare with BCS prediction | #1 |
| Analytic continuation noise | Sharp features in A(ω) from noisy Matsubara data | Compare Padé vs MaxEnt; if they disagree, data is too noisy | #27, #28 |
| Density matrix not converged | Reports HF/DMFT after 3 iterations | Check convergence metric; require < 10⁻⁶ | #27 |

---

## Verification Checklist

Before finalizing any quantum many-body calculation:

- [ ] Interaction regime identified (weak/moderate/strong) and method is appropriate
- [ ] Self-consistency converged (density matrix, self-energy, or gap function)
- [ ] Green's function type explicit (Matsubara vs retarded vs time-ordered)
- [ ] Self-energy sign convention declared and consistent
- [ ] Causality: Im Σ^R(ω) ≤ 0 for all ω
- [ ] Spectral sum rule: ∫ A(k, ω) dω = 1
- [ ] Spectral positivity: A(k, ω) ≥ 0
- [ ] High-frequency tails correct (Σ → U⟨n⟩, G → 1/iωₙ)
- [ ] Luttinger theorem checked (Fermi surface volume = density for Fermi liquids)
- [ ] For QMC: ⟨sign⟩ monitored and > 0.1
- [ ] For BCS: Δ₀/T_c ratio compared with BCS prediction
- [ ] Analytic continuation validated by 2+ methods
- [ ] Known limits reproduced (U → 0 gives free electrons, U → ∞ gives atomic limit)
