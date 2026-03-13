---
load_when:
  - "verification checklist"
  - "which checks to run"
  - "physics validation"
  - "quick verification"
tier: 1
context_cost: medium
---

# Verification Quick Reference

Compact reference for physics verification. This file is the conceptual checklist; the stable machine-facing verifier registry lives in `gpd.core.verification_checks` and the `gpd-verification` MCP server. For full procedures, worked examples, and code templates, see the modular verification files: `references/verification/core/verification-core.md` (universal checks), `references/verification/core/verification-numerical.md` (convergence/statistics), `../domains/verification-domain-qft.md` (QFT/particle), `../domains/verification-domain-condmat.md` (condensed matter), `../domains/verification-domain-statmech.md` (stat mech/cosmo), `../domains/verification-domain-gr-cosmology.md` (GR/cosmology), `../domains/verification-domain-amo.md` (AMO/quantum optics), `../domains/verification-domain-nuclear-particle.md` (nuclear/particle), `../domains/verification-domain-astrophysics.md` (astrophysics/stellar), `../domains/verification-domain-mathematical-physics.md` (mathematical physics), `../domains/verification-domain-algebraic-qft.md` (algebraic QFT/operator algebras), `../domains/verification-domain-string-field-theory.md` (string field theory), `../domains/verification-domain-quantum-info.md` (quantum information/computing), `../domains/verification-domain-soft-matter.md` (soft matter/biophysics), `../domains/verification-domain-fluid-plasma.md` (fluid dynamics/MHD/plasma).

---

## Verification Checklist (14 Checks)

| # | Check | What It Catches | When to Use |
|---|-------|-----------------|-------------|
| 1 | **Dimensional analysis** | Wrong powers of c, hbar, k_B; natural unit leaks into SI | Every derived equation, every numerical expression |
| 2 | **Limiting cases** | General result that doesn't reduce to known special cases | After every general derivation (hbar→0, c→∞, g→0, T→0, T→∞) |
| 3 | **Symmetry verification** | Gauge dependence, broken Lorentz invariance, wrong CPT behavior | After constructing Lagrangians, computing amplitudes |
| 4 | **Conservation laws** | Energy/momentum/charge drift in dynamics or numerics | Every simulation, scattering calc, quantum evolution |
| 5 | **Numerical convergence** | Unconverged results reported as final; wrong convergence order | Every numerical result before reporting |
| 6 | **Cross-check with literature** | Systematic errors invisible to internal checks | Before reporting any numerical value |
| 7 | **Order-of-magnitude estimation** | Results off by powers of 10 (sign in exponent, missing scale) | Before and after every detailed calculation |
| 8 | **Physical plausibility** | Negative probabilities, superluminal signals, E < E_min | After every calculation, especially in unfamiliar regimes |
| 9 | **Ward identities / sum rules** | Approximations that break gauge invariance; missing spectral weight | After computing response/Green's functions; after renormalization |
| 10 | **Unitarity bounds** | Cross sections violating Froissart bound; \|S_l\| > 1 | Every scattering calculation, every time evolution |
| 11 | **Causality constraints** | G^R(t<0) != 0; poles in upper half-plane; v_signal > c | Every response function, propagator, dispersion relation |
| 12 | **Positivity constraints** | Negative spectral weight, negative cross sections, non-PSD density matrix | Every spectral function, density matrix, cross section |
| 13 | **Kramers-Kronig consistency** | Inconsistent Re/Im parts of response functions; bad analytic continuation | After computing complex response functions; after Matsubara continuation |
| 14 | **Statistical validation** | Underestimated errors from autocorrelation; unthermalized MC | Every Monte Carlo result, every fit, every stochastic method |

---

## Decision Tree: Which Checks to Run

```
What type of result do you have?
│
├─ Analytical derivation (symbolic equation)
│  ├─ ALWAYS: #1 dimensional analysis, #2 limiting cases, #7 order-of-magnitude
│  ├─ If amplitude/cross section: #3 symmetry, #10 unitarity, #8 plausibility
│  ├─ If Green's function: #9 Ward identities, #11 causality, #12 positivity
│  └─ If thermodynamic quantity: #4 conservation, #8 plausibility (C_V > 0, S ≥ 0)
│
├─ Numerical calculation (computed number)
│  ├─ ALWAYS: #5 convergence, #6 literature cross-check, #7 order-of-magnitude
│  ├─ If response function: #9 sum rules, #13 Kramers-Kronig, #12 positivity
│  ├─ If eigenvalue problem: #8 plausibility (real eigenvalues, bounded below)
│  └─ If time evolution: #4 conservation, #10 unitarity (norm preservation)
│
├─ Simulation (trajectory / ensemble)
│  ├─ ALWAYS: #4 conservation, #5 convergence, #14 statistical validation
│  ├─ If Monte Carlo: #14 (thermalization, autocorrelation, binning analysis)
│  ├─ If molecular dynamics: #4 (energy conservation to integrator tolerance)
│  └─ If phase transition: #5 finite-size scaling, #6 compare known exponents
│
└─ Paper-ready result (final number for publication)
   └─ Run every relevant live verifier-registry check (current registry: 5.1-5.19).
       Minimum: dimensional analysis, numerical spot-checks, limiting cases, literature cross-check, and every contract-aware check required by the plan. Add domain-specific checks from above.
```

---

## Verification Theater vs Real Verification

The difference between checking that a result *exists* and checking that the *physics is correct*.

| Verification Theater (Looks Good, Proves Nothing) | Real Verification (Actually Tests Physics) |
|---------------------------------------------------|--------------------------------------------|
| "The code runs without errors" | "Energy is conserved to 1e-10 across 10^6 timesteps" |
| "The equation has the right form" | "Every term has dimensions [M L^{-1} T^{-2}] and the hbar→0 limit gives Newton's law" |
| "The answer is a number" | "The number is 13.6 eV, matching hydrogen ground state to 0.1%" |
| "The integral converged" | "Richardson extrapolation gives convergence order 2.0 ± 0.1, matching the method" |
| "The plot looks reasonable" | "The spectral function satisfies the f-sum rule to 0.3% and is non-negative everywhere" |
| "We used the Feynman rules" | "The amplitude satisfies the optical theorem and is crossing-symmetric" |
| "The simulation thermalized (it ran long)" | "Binning analysis shows τ_int = 50, we discarded 500 sweeps, N_eff = 10^4" |
| "The error bars are small" | "Bootstrap with 10^4 resamples; autocorrelation time accounted for; χ²/dof = 1.1" |
| "The partition function sums over all states" | "Z → (number of states) at T→∞ and Z → exp(-βE_0) at T→0" |
| "The Green's function was analytically continued" | "KK relations satisfied to 2% after continuation; spectral weight sum rule holds" |
| "The symmetry was imposed" | "Same observable computed in two gauges; results agree to 10^{-12}" |
| "The wavefunction is normalized" | "⟨ψ|ψ⟩ = 1, Δx·Δp ≥ hbar/2, and eigenvalues of ρ are in [0,1]" |

---

## In-Execution Validation (Catch Errors During the Calculation)

Don't wait until the end. Validate after every intermediate step:

| After This | Check This | How |
|---|---|---|
| Deriving an equation | Dimensions of every new expression | Count [M], [L], [T] powers |
| Computing an integral | Special values, limiting cases | Substitute known parameter values |
| Writing numerical code | Test on analytically solvable case | Compare to known result |
| Solving an eigenvalue problem | Spectrum properties (real, bounded, trace) | Numerical checks |
| Computing a correlation function | Symmetry properties, asymptotics | Check specific limits |
| Performing a Fourier transform | Parseval's theorem, reality conditions | Numerical cross-check |

**If a check fails mid-execution:** Stop. Record the failure. Diagnose before proceeding. A sign error in step 1 becomes unrecoverable by step 5.

---

## Domain Quick-Checks

### QFT
- Ward identities after vertex corrections
- Optical theorem after amplitude computation
- Gauge independence (compute in two gauges)
- UV divergence structure matches power counting

### Condensed Matter
- f-sum rule for optical conductivity
- Luttinger theorem (Fermi surface volume = electron count)
- Kramers-Kronig for all response functions
- Goldstone modes match broken symmetry count

### Statistical Mechanics
- Z → (number of states) at high T
- Critical exponents match universality class
- Finite-size scaling collapse with correct exponents
- Detailed balance: W(A→B)P_eq(A) = W(B→A)P_eq(B)

### Cosmology
- Friedmann + continuity equations consistent throughout
- Comoving vs physical distance factors of (1+z)
- CMB spectrum matches Planck best-fit to sub-percent
- σ_8 consistent between CMB and direct measurement

### Quantum Information
- Tr(ρ) = 1, eigenvalues in [0,1], ρ = ρ†
- Quantum channels are CPTP (Choi matrix positive semidefinite)
- Fidelity F ∈ [0,1]
- No-cloning: any apparent cloning must violate unitarity

### Algebraic Quantum Field Theory
- Isotony, locality, covariance, and the relevant duality/split assumptions are stated explicitly
- The state, GNS representation, and cyclic/separating vector are fixed before modular theory is used
- Any type `I/II/III` claim is justified by factor and modular criteria, not finite-dimensional intuition
- Local algebras are not treated as ordinary tensor factors with naive reduced density matrices

### String Field Theory
- `Q_B^2 = 0` in the chosen background and Hilbert space
- Ghost number and picture number match every field, vertex, and gauge parameter
- Gauge-invariant observables stabilize under increasing truncation level
- Tachyon-vacuum or marginal-deformation benchmarks match canonical SFT results

---

## Common LLM Error Patterns (Top 5)

1. **Missing factors** (2, π, 2π, 1/N!): Caught by limiting cases and sum rules
2. **Sign errors** (relative signs between channels, metric signature): Caught by crossing symmetry
3. **Convention mixing** (Fourier, units, metric): Caught by dimensional analysis and sum rules
4. **Forgetting quantum statistics** (identical particles, Fermi/Bose): Caught by spot-checks at special kinematics
5. **Numerical artifacts reported as physics** (unconverged, unthermalized): Caught by convergence tests and statistical validation

For the full catalog of 104 LLM physics error classes, see `../errors/llm-physics-errors.md` (index) or load specific parts: `../errors/llm-errors-core.md` (#1-25), `../errors/llm-errors-field-theory.md` (#26-51), `../errors/llm-errors-extended.md` (#52-81, #102-104), `../errors/llm-errors-deep.md` (#82-101). For a compact summary of HIGH-risk classes, see `../audits/verification-gap-summary.md`.

---

## See Also

- `references/verification/core/verification-patterns.md` — Index pointing to modular verification files
- `references/verification/core/verification-core.md` — Universal checks: dimensional analysis, limiting cases, conservation laws, symmetry
- `references/verification/core/verification-numerical.md` — Convergence testing, statistical validation, automated verification
- `../domains/verification-domain-qft.md` — QFT, particle physics, GR, mathematical physics checks
- `../domains/verification-domain-algebraic-qft.md` — AQFT, local nets, modular theory, von Neumann factor-type checks
- `../domains/verification-domain-string-field-theory.md` — String field theory, BRST, ghost/picture, truncation checks
- `../domains/verification-domain-condmat.md` — Condensed matter, quantum information, AMO checks
- `../domains/verification-domain-statmech.md` — Statistical mechanics, cosmology checks
- `../domains/verification-domain-fluid-plasma.md` — Fluid dynamics, MHD, plasma physics checks
- `../errors/llm-physics-errors.md` — Catalog of LLM-specific error classes with detection strategies
- `../../physics-subfields.md` — Subfield-specific methods, tools, and pitfalls
- `references/orchestration/checkpoints.md` — Pre-checkpoint automation and computational environment management
