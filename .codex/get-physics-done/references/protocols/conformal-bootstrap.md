---
load_when:
  - "conformal bootstrap"
  - "conformal field theory"
  - "CFT"
  - "crossing symmetry"
  - "OPE"
  - "conformal block"
  - "semidefinite programming"
tier: 3
context_cost: high
---

# Conformal Bootstrap Protocol

The conformal bootstrap extracts non-perturbative information about conformal field theories (CFTs) using only symmetry, unitarity, and crossing symmetry — no Lagrangian required. It has produced the most precise determinations of critical exponents for the 3D Ising model and O(N) models, surpassing both experiment and other theoretical methods.

## Related Protocols

- See `renormalization-group.md` for perturbative approaches to critical exponents (epsilon expansion, fixed-dimensional methods)
- See `symmetry-analysis.md` for identifying the symmetry group and representations of a CFT
- See `numerical-computation.md` for convergence analysis of the semidefinite programming approach
- See `large-n-expansion.md` for 1/N expansion of critical exponents in O(N) and related models (complementary non-perturbative approach)

## Overview

The conformal bootstrap relies on three ingredients:

1. **Conformal symmetry** fixes the form of two- and three-point functions up to a finite number of parameters (scaling dimensions Δ and OPE coefficients λ).
2. **Unitarity** imposes lower bounds on scaling dimensions: Δ ≥ (d-2)/2 for scalars, Δ ≥ d-1 for conserved spin-1 currents, Δ = d for the stress tensor.
3. **Crossing symmetry** of four-point functions provides an infinite set of constraints (the bootstrap equations) that restrict the allowed space of CFT data.

| Method | Input | Output | Precision |
|---|---|---|---|
| Numerical bootstrap (SDPB) | Crossing equations + unitarity | Rigorous bounds on Δ, λ | 6-8 significant digits for 3D Ising |
| Extremal functional method | Numerical bootstrap at boundary | Approximate spectrum extraction | Moderate (depends on truncation) |
| Analytic bootstrap | Crossing + Regge limit + lightcone | Large-spin expansion, anomalous dimensions | Exact at leading order in 1/J |
| Epsilon expansion | RG near upper critical dimension | ε-series for critical exponents | 5-loop known; Borel resummation needed |

## Step 1: Set Up the Crossing Equation

For four identical scalar operators φ of dimension Δ_φ, the crossing equation is:

```
Σ_{O} λ²_{φφO} [v^{Δ_φ} g_{Δ,ℓ}(u,v) - u^{Δ_φ} g_{Δ,ℓ}(v,u)] = 0
```

where u, v are the conformal cross-ratios, g_{Δ,ℓ} are conformal blocks, and the sum runs over all primary operators O of dimension Δ and spin ℓ appearing in the φ × φ OPE.

**Checklist:**

1. **Identify the correct conformal block normalization.** Multiple conventions exist (Dolan-Osborn, Kos-Poland-Simmons-Duffin). The normalization affects the OPE coefficients λ but not the dimensions Δ. State the convention explicitly and verify against the known identity block (Δ=0, ℓ=0, the unit operator).
2. **Include the identity operator.** The unit operator (Δ=0, ℓ=0) always appears in the OPE of identical operators with λ²_{φφ1} = 1 (by convention, with standard two-point function normalization). Forgetting it changes the crossing equation.
3. **Enumerate all relevant crossing equations.** For a single scalar φ, there is one crossing equation. For multiple operators (φ, ψ, ...) or operators with spin, there are multiple independent crossing equations from different four-point functions. Using all available equations gives stronger constraints.
4. **Verify the conformal block asymptotics.** For large Δ at fixed ℓ: g_{Δ,ℓ}(u,v) ~ u^{Δ/2} (in the OPE limit u → 0). For large ℓ at fixed twist τ = Δ - ℓ: the blocks have known asymptotic expansions. These provide consistency checks on numerical conformal block computation.

## Step 2: Conformal Block Computation

Conformal blocks are known in closed form only in even dimensions (d = 2, 4, 6):

- **d = 2:** Virasoro blocks (infinite-dimensional conformal symmetry); global blocks are hypergeometric functions.
- **d = 4:** Dolan-Osborn formula: g_{Δ,ℓ}(u,v) = (z z̄)/(z - z̄) × [k_{Δ+ℓ}(z) k_{Δ-ℓ-2}(z̄) - (z ↔ z̄)] where k_β(z) = z^{β/2} ₂F₁(β/2, β/2; β; z).
- **General d:** Recursion relations (Zamolodchikov-type), series expansions, or Casimir differential equations.

**Checklist:**

1. **Use the correct spacetime dimension d.** The conformal blocks, unitarity bounds, and OPE structure all depend on d. The 3D Ising bootstrap uses d = 3 blocks, not d = 4. This sounds obvious but is a real error source when adapting code from one dimension to another.
2. **Verify conformal blocks against known limits.** At z = z̄ (diagonal limit), blocks simplify. At z → 0 (OPE limit), blocks → z^{Δ/2} × (known power series). Check numerical computation against these limits.
3. **For 2D: distinguish global vs local (Virasoro) conformal symmetry.** In 2D, the conformal group is infinite-dimensional (Virasoro algebra). The global conformal group SL(2,C) is a finite-dimensional subgroup. Global conformal blocks are simpler; Virasoro blocks include contributions from descendants at all levels. Using global blocks when Virasoro blocks are needed underestimates the OPE — you miss the contribution of Virasoro descendants.

## Step 3: Numerical Bootstrap (Semidefinite Programming)

The numerical conformal bootstrap converts crossing equations into a semidefinite program (SDP) and solves for the boundary of the allowed region.

**Checklist:**

1. **Choose the derivative truncation order Λ.** The crossing equation is evaluated as a Taylor expansion around the crossing-symmetric point z = z̄ = 1/2, keeping derivatives up to order Λ. Higher Λ gives tighter bounds but increases computational cost (roughly as Λ^{3d} for the SDP). Standard values: Λ = 19-43 for high-precision 3D Ising bootstrap.
2. **Verify convergence in Λ.** Bounds should converge monotonically as Λ increases. If they oscillate or fail to converge, suspect a bug in the conformal block computation or the SDP setup. Plot the bound vs Λ and check for systematic convergence.
3. **Use SDPB (Semidefinite Program Bootstrap).** The standard solver for bootstrap SDPs is SDPB (Simmons-Duffin). It uses arbitrary-precision arithmetic to handle the large condition numbers inherent in bootstrap problems. Standard floating-point SDP solvers (CSDP, SeDuMi) are insufficient for bootstrap precision.
4. **Check that the identity operator is included.** The unit operator contributes a fixed, known term to the crossing equation. It must be separated from the search over unknown operators.

**Common error modes (numerical bootstrap):**

- Insufficient derivative order Λ → weak bounds that miss the actual CFT
- Wrong unitarity bounds for the spacetime dimension → allowing unphysical operators
- Incorrect conformal block normalization → wrong OPE coefficients (dimensions unaffected)
- Not verifying convergence in Λ → unreliable bounds
- Confusing rigorous bounds (allowed regions) with approximate results (spectrum extraction)

## Step 4: Extremal Functional Method

At the boundary of the allowed region, the bootstrap functional becomes extremal, and the spectrum can be approximately extracted.

**Checklist:**

1. **Identify kinks and islands.** Sharp features (kinks) in the boundary of the allowed region correspond to known CFTs. The 3D Ising model sits at a prominent kink in the (Δ_σ, Δ_ε) plane. Islands (closed allowed regions) with mixed correlators can isolate specific CFTs.
2. **Extract the spectrum from the extremal functional.** The zeros of the extremal functional give the scaling dimensions of operators in the spectrum. This is an approximate method — verify by checking that the extracted spectrum satisfies the crossing equation to the precision claimed.
3. **Estimate uncertainties.** Bootstrap bounds are rigorous (the true CFT must lie within the allowed region). Spectrum extraction from the extremal functional is approximate — estimate the uncertainty by varying Λ and checking stability.

## Step 5: Analytic Bootstrap

Complementary to the numerical approach, the analytic bootstrap exploits crossing symmetry in specific kinematic limits.

**Checklist:**

1. **Lightcone bootstrap (large spin).** In the lightcone limit (z → 0, z̄ fixed), the crossing equation is dominated by the identity operator and the stress tensor. This gives the large-spin expansion of anomalous dimensions: γ(ℓ) = γ₀/ℓ^τ_min + γ₁/ℓ^{τ_min+1} + ..., where τ_min is the minimal twist in the crossed channel.
2. **Regge limit.** The limit z, z̄ → 0 with z/z̄ fixed constrains the high-energy behavior. Boundedness of the correlator in the Regge limit (unitarity) gives rigorous constraints on the spectrum.
3. **Inversion formula.** The Lorentzian inversion formula (Caron-Huot) extracts OPE data from the double-discontinuity of the four-point function. It is exact for spin ℓ ≥ 2 and approximate for ℓ = 0, 1.

## Worked Example: Upper Bound on the Leading Scalar Dimension in the 3D Ising Model

**Problem:** Use the numerical conformal bootstrap to derive an upper bound on the dimension Delta_epsilon of the first Z_2-even scalar operator as a function of Delta_sigma in a 3D CFT with Z_2 symmetry. Identify the kink corresponding to the 3D Ising model. This example targets three common errors: wrong unitarity bounds for the spacetime dimension, missing the identity operator contribution, and confusing rigorous bounds with spectrum extraction.

### Step 1: Set Up the Crossing Equation

For the four-point function <sigma sigma sigma sigma> in d = 3, only Z_2-even operators appear in the sigma x sigma OPE:

```
sigma x sigma = 1 + epsilon + epsilon' + T_{mu nu} + ...
```

The crossing equation:

```
sum_{O in Z_2-even} lambda^2_{sigma sigma O} F_{Delta,ell}(u,v) = 0
```

where F_{Delta,ell} = v^{Delta_sigma} g_{Delta,ell}(u,v) - u^{Delta_sigma} g_{Delta,ell}(v,u).

**Checklist verification:**
- Identity operator: lambda^2_{sigma sigma 1} = 1 (standard normalization). If this is omitted, the crossing equation has no solution and the SDP reports all points as excluded.
- Unitarity bounds for d = 3: scalars have Delta >= (d-2)/2 = 0.5, spin-ell operators have Delta >= d + ell - 2 for ell >= 1. The stress tensor saturates Delta = d = 3 at ell = 2. Using d = 4 unitarity bounds (Delta_scalar >= 1) would wrongly exclude free-field theories and produce nonsensical exclusion plots.
- Conformal blocks: computed via Zamolodchikov recursion for d = 3 (no closed form exists).

### Step 2: SDP Setup and Derivative Truncation

Expand F_{Delta,ell} in derivatives around the crossing-symmetric point z = z_bar = 1/2, up to order Lambda. The bootstrap question: for a given Delta_sigma, can a consistent set of {Delta_O, lambda_O^2 >= 0} satisfy the crossing equation with Delta_epsilon <= Delta_max?

This is an SDP: search for a linear functional alpha such that alpha(F_{0,0}) > 0 (identity) and alpha(F_{Delta,ell}) >= 0 for all allowed (Delta, ell). If such alpha exists, the point (Delta_sigma, Delta_max) is excluded.

Solve using SDPB (arbitrary-precision SDP solver). Standard floating-point solvers (CSDP, SeDuMi) cannot handle the condition numbers involved (> 10^{20}).

### Step 3: Compute the Exclusion Boundary

Scan Delta_sigma from 0.50 to 0.60 in steps of 0.001. For each Delta_sigma, binary-search for the maximum allowed Delta_epsilon at multiple Lambda values:

| Lambda | Delta_sigma at kink | Delta_epsilon at kink | CPU hours (per point) |
|---|---|---|---|
| 11 | 0.518(1) | 1.42(1) | 0.5 |
| 19 | 0.5182(1) | 1.413(1) | 5 |
| 27 | 0.51815(5) | 1.4126(3) | 50 |
| 35 | 0.51815(2) | 1.41263(5) | 500 |

**Key observations:**
- The bound tightens monotonically with Lambda (mandatory for consistency — non-monotonic behavior signals a bug)
- A sharp kink appears near Delta_sigma ~ 0.518, converging to the known 3D Ising value
- Below the kink: the bound is nearly flat (many allowed CFTs)
- Above the kink: the bound drops sharply (strong constraint)

### Step 4: Spectrum Extraction

At the kink, apply the extremal functional method. The zeros of the functional give approximate operator dimensions:

| Operator | Spin | Delta (extracted, Lambda=35) | Delta (high-precision) |
|---|---|---|---|
| epsilon | 0 | 1.41263(5) | 1.412625(10) |
| T_{mu nu} | 2 | 3.000(1) | 3 (exact) |
| epsilon' | 0 | 3.83(1) | 3.8303(18) |

**The stress tensor MUST appear at Delta = 3 exactly.** If it appears at 2.98 or 3.02, there is an error in the conformal block computation. This is the strongest single consistency check available.

**Important distinction:** The exclusion boundary is a rigorous bound (the true CFT must lie inside the allowed region). The spectrum extraction from the extremal functional is approximate (not rigorous). Do not quote spectrum extraction results as rigorous bounds.

### Verification

1. **Convergence in Lambda:** Delta_epsilon at the kink converges monotonically: 1.42 -> 1.413 -> 1.4126 -> 1.41263. Oscillation would indicate a conformal block computation error.

2. **Free scalar limit:** At Delta_sigma = 0.5, the bound gives Delta_epsilon = 1.0 (dimension of sigma^2 in free theory, Delta = 2*0.5 = 1.0). This exact result must be reproduced; failure indicates wrong unitarity bounds or missing the identity operator.

3. **Stress tensor dimension:** Extracted at Delta = 3.000 (exact for d = 3). Protected by conformal symmetry — any deviation indicates a systematic error.

4. **Critical exponents:** From the bootstrap: eta = 2*Delta_sigma - (d-2) = 2*0.51815 - 1 = 0.0363, nu = 1/(d - Delta_epsilon) = 1/(3 - 1.41263) = 0.6300. These must agree with Borel-resummed epsilon expansion: eta = 0.0362(5), nu = 0.6300(4).

5. **Crossing residual:** With the extracted spectrum, evaluate the crossing equation. Residual should be < 10^{-Lambda/2}.

## Worked Example: Mixed-Correlator Bootstrap Island for the 3D O(2) Model

**Problem:** Use the mixed-correlator bootstrap with the operators phi (fundamental scalar, O(2) vector) and s (singlet scalar, the lowest Z_2-even operator) to isolate the 3D O(2) CFT as a small island in the (Delta_phi, Delta_s) plane. Demonstrate that the single-correlator bootstrap gives only a weak bound, while mixed correlators produce a closed island. This example targets two common errors: relying on single-correlator bounds when mixed correlators are needed, and misidentifying the symmetry representations in the OPE.

### Step 1: Symmetry and OPE Structure

The 3D O(2) model has a continuous symmetry group. The fundamental field phi_i (i = 1,2) transforms as a vector. The OPE structure:

```
phi_i x phi_j = delta_{ij} [1 + s + s' + ...] + [t_{ij} + t'_{ij} + ...] + antisymmetric: [epsilon_{ij} (nothing for O(2))]
```

where:
- **Singlet sector (S):** delta_{ij} times singlet operators. Includes the identity (Delta = 0), s (lowest singlet scalar), the stress tensor T_{mu nu} (Delta = 3, spin 2).
- **Symmetric traceless sector (T):** Rank-2 symmetric traceless O(2) tensors. The charge-2 operator t_{ij} is the lowest.
- **Antisymmetric sector (A):** For O(2), the antisymmetric tensor epsilon_{ij} is a singlet, so the conserved O(2) current J_mu (Delta = 2, spin 1) appears here.

**Common error: wrong sector assignment.** The conserved current J_mu is in the ANTISYMMETRIC sector of phi x phi, NOT the singlet sector. Placing it in the singlet sector adds a spurious constraint and invalidates the bounds. For O(N) with N >= 3, this distinction is even more important because the antisymmetric sector contains the adjoint representation.

### Step 2: Single-Correlator Bound (Insufficient)

Using only <phi phi phi phi>, the single-correlator bound on Delta_s as a function of Delta_phi gives a slowly-varying curve with NO sharp kink at the O(2) model location. The bound is:

| Delta_phi | Delta_s upper bound (Lambda = 27) |
|-----------|----------------------------------|
| 0.510 | 1.65 |
| 0.515 | 1.58 |
| 0.519 | 1.53 |
| 0.522 | 1.50 |
| 0.525 | 1.48 |

The O(2) model has Delta_phi = 0.51926(32) and Delta_s = 1.5117(25). The single-correlator bound at Delta_phi = 0.519 gives Delta_s < 1.53 — this is a valid bound but provides no precision. There is no kink to identify the O(2) model (unlike the 3D Ising model, which has a prominent kink in the single-correlator bound because it has a Z_2 symmetry that reduces the parameter space).

### Step 3: Mixed-Correlator Bootstrap Island

Include three four-point functions: <phi phi phi phi>, <phi phi s s>, and <s s s s>. The crossing equations now constrain operators appearing in three OPEs: phi x phi, phi x s, and s x s.

The key additional constraint: the OPE coefficient lambda_{phi phi s} appears in BOTH <phi phi phi phi> (as the coefficient of the singlet scalar s) and <phi phi s s> (as the coefficient of the identity in the phi x s OPE). This ties together information from different correlators, drastically reducing the allowed region.

**Island at Lambda = 27 (mixed correlators):**

The allowed region shrinks from a line (single-correlator bound) to a small island:

```
Delta_phi in [0.51905, 0.51945]  (width 0.0004)
Delta_s in [1.5100, 1.5135]      (width 0.0035)
```

At Lambda = 43:

```
Delta_phi in [0.51920, 0.51932]  (width 0.00012)
Delta_s in [1.5112, 1.5122]      (width 0.0010)
```

The O(2) model is isolated: no other CFT occupies this island. The precision is 2-3 orders of magnitude better than single-correlator bounds.

### Step 4: Spectrum Extraction from the Island

At the center of the island, extract the spectrum via the extremal functional:

| Operator | Sector | Spin | Delta (extracted) | Known value |
|----------|--------|------|------------------|-------------|
| phi | V | 0 | 0.51926(6) | 0.51926(32) |
| s | S | 0 | 1.5117(5) | 1.5117(25) |
| J_mu | A | 1 | 2.000(1) | 2 (exact) |
| T_{mu nu} | S | 2 | 3.000(1) | 3 (exact) |
| t | T | 0 | 1.237(2) | 1.2354(32) |
| s' | S | 0 | 3.80(2) | 3.795(10) |

### Verification

1. **Conserved current at Delta = 2.** The O(2) model has a conserved U(1) current. It MUST appear at Delta = d - 1 = 2 exactly. If the extracted Delta_J differs from 2 by more than 0.01, there is an error in the conformal block computation or the symmetry decomposition. This is the single strongest check.

2. **Stress tensor at Delta = 3.** The stress tensor appears in the singlet sector at Delta = d = 3 exactly. Same verification as for the Ising model example.

3. **Critical exponents cross-check.** From the bootstrap:
   - eta = 2 Delta_phi - (d-2) = 2(0.51926) - 1 = 0.0385
   - nu = 1/(d - Delta_s) = 1/(3 - 1.5117) = 0.672
   Monte Carlo values (Hasenbusch 2019): eta = 0.0381(2), nu = 0.6717(1). Agreement within bootstrap error bars.

4. **Lambda convergence of the island.** The island must shrink monotonically as Lambda increases. If it expands at some Lambda, there is a bug. Plot the island area vs Lambda.

5. **Comparison with O(N) family.** The O(2) results should be consistent with the O(N) interpolation: Delta_phi(N) is a smooth function of N. At N = 1 (Ising): Delta_sigma = 0.5181. At N = 2: Delta_phi = 0.5193. At N = 3: Delta_phi = 0.5190. The N-dependence is weak and non-monotonic (this is physical, not an error).

6. **Do not confuse the island with a rigorous determination.** The island defines the ALLOWED REGION consistent with the bootstrap constraints at derivative order Lambda. The true O(2) model lies somewhere inside the island. The island is not a confidence interval in the statistical sense — it is a rigorous exclusion: nothing outside the island is consistent with crossing symmetry + unitarity at this Lambda.

## Worked Example: Crossing Symmetry Violation from Truncated OPE — The Dangerous Shortcut

**Problem:** Demonstrate that truncating the OPE to a finite number of operators violates crossing symmetry and produces inconsistent results for four-point functions. Compute the crossing equation residual for the 3D Ising model with the spectrum truncated to the first 2, 5, and 10 operators, and show how the residual converges as operators are added. This targets the LLM error class of claiming a specific OPE decomposition "satisfies crossing symmetry" when only a finite number of operators are included — crossing symmetry is an infinite sum identity that cannot be verified by finite truncation.

### Step 1: The Crossing Equation

The four-point function of the spin field sigma in the 3D Ising model satisfies:

```
sum_O lambda_{sigma sigma O}^2 F_{Delta_O, l_O}(u, v) = 0
```

where the sum runs over ALL operators O in the sigma x sigma OPE, and F_{Delta, l}(u, v) = v^{Delta_sigma} g_{Delta,l}(u,v) - u^{Delta_sigma} g_{Delta,l}(v,u) is the crossing-antisymmetric combination of conformal blocks. The cross-ratios are u = z z-bar, v = (1-z)(1-z-bar).

This equation must hold for ALL values of (u, v), or equivalently for all (z, z-bar). Evaluate at the symmetric point z = z-bar = 1/2 (u = v = 1/4) where the crossing constraint is strongest.

### Step 2: Truncated OPE

Use the known 3D Ising spectrum (from bootstrap and Monte Carlo):

| Operator | Delta | Spin l | (lambda_{sigma sigma O})^2 |
|----------|-------|--------|---------------------------|
| 1 (identity) | 0 | 0 | 1 |
| epsilon | 1.4126 | 0 | 1.0518 |
| T_{mu nu} | 3 | 2 | 0.3266 |
| epsilon' | 3.8303 | 0 | 0.0529 |
| T' | 5.022 | 2 | 0.0196 |
| C_{mu nu rho sigma} | 5.023 | 4 | 0.00687 |
| epsilon'' | 6.896 | 0 | 0.0022 |
| ... | ... | ... | ... |

### Step 3: Crossing Residual vs Number of Operators

Evaluate the crossing equation at z = z-bar = 1/2:

```
R(N_ops) = |sum_{O=1}^{N_ops} lambda^2_O F_{Delta_O, l_O}(1/4, 1/4)|
```

| N_ops | Operators included | R(N_ops) | R / R(1) |
|-------|-------------------|----------|----------|
| 1 | identity only | 1.000 | 1.00 |
| 2 | + epsilon | 0.312 | 0.31 |
| 3 | + T | 0.087 | 0.087 |
| 5 | + epsilon', T' | 0.024 | 0.024 |
| 10 | + next 5 operators | 0.0031 | 0.0031 |
| 20 | + next 10 operators | 2.8e-4 | 2.8e-4 |
| 50 | + next 30 operators | 1.1e-6 | 1.1e-6 |

The residual converges to zero but NEVER exactly vanishes at finite truncation. Even with 50 operators, crossing is violated at the 10^{-6} level.

### Step 4: Why This Matters

**Scenario 1: Consistency check failure.** An LLM claims to have "verified crossing symmetry" by summing 3 operators and getting R = 0.087. This 9% residual is NOT small — it means the truncated sum is wrong at the 9% level. Any physical prediction derived from this truncated sum (OPE coefficients, scaling dimensions) inherits this error.

**Scenario 2: Fitting the wrong spectrum.** Suppose we fit the leading scalar dimension Delta_epsilon by minimizing the crossing residual with only the identity and epsilon included. The minimum of R(Delta_epsilon) occurs at Delta_epsilon = 1.55, not the true value 1.4126. The 10% error in Delta_epsilon comes from absorbing the effect of all missing operators (T, epsilon', ...) into the wrong value of Delta_epsilon.

**Scenario 3: The bootstrap does it correctly.** The conformal bootstrap does NOT truncate the OPE. Instead, it derives rigorous bounds by requiring crossing symmetry for ALL possible spectra above the unitarity bound. The SDP (semidefinite programming) constraint involves an infinite-dimensional function space, discretized via the derivative expansion at z = z-bar = 1/2. This is fundamentally different from truncation.

### Verification

1. **Convergence rate.** The OPE converges as |rho|^{Delta_n} where rho = z/(1+sqrt(1-z))^2 is the conformal radius and Delta_n is the dimension of the nth operator. At z = 1/2: |rho| = 0.172. The nth operator contributes ~ (0.172)^{Delta_n}. Since Delta_n grows roughly linearly with n, convergence is exponentially fast. But the first few operators contribute most of the residual.

2. **Derivative expansion cross-check.** Evaluate crossing at z = z-bar = 1/2 + epsilon for small epsilon. The derivatives d^n R / dz^n should also converge to zero. If the residual at z = 1/2 is small but the first derivative is large, the spectrum is not consistent (the crossing equation is pinned at one point but not satisfied globally).

3. **Comparison with the free field.** For a free scalar (Delta_phi = 0.5 in d = 3): the four-point function is exactly computable, crossing symmetry is exact, and the OPE is fully known. The free-field crossing residual MUST be exactly zero at any truncation that includes all operators up to a given twist. If it is not, there is a bug in the conformal block computation.

4. **Lambda dependence in the bootstrap.** The bootstrap bound depends on the derivative order Lambda (number of derivatives of the crossing equation evaluated at z = 1/2). As Lambda increases from 11 to 43, the allowed region for (Delta_sigma, Delta_epsilon) shrinks from a large region to the narrow "Ising island." The island at Lambda = 43 has width ~ 10^{-4} in Delta_sigma. If the island does not shrink with Lambda, the numerical precision of the SDP solver is insufficient.

**The typical LLM error** reports a crossing residual from a truncated OPE and declares it "consistent with crossing symmetry." The correct statement is: "the truncated sum has a residual of X, which decreases as more operators are included, and is consistent with the expected convergence rate of the OPE at z = 1/2."

## Verification Criteria

1. **Unitarity bounds.** In d dimensions: scalar Δ ≥ (d-2)/2 (free field saturation). Spin-ℓ current: Δ ≥ d + ℓ - 2 (for ℓ ≥ 1). Stress tensor: Δ = d exactly. Any violation indicates an error (`references/verification/errors/llm-physics-errors.md` #40, scaling dimension errors).
2. **OPE convergence.** The OPE must converge inside the range |ρ| < 1 where ρ = z/(1+√(1-z))². Verify that the sum over operators converges for the cross-ratios used.
3. **Known CFT data.** For the 3D Ising model: Δ_σ = 0.5181489(10), Δ_ε = 1.412625(10) (Kos, Poland, Simmons-Duffin, Vichi 2016). For the free scalar in d dimensions: Δ_φ = (d-2)/2 exactly. Use these as benchmarks.
4. **Crossing symmetry residual.** After solving, evaluate the crossing equation with the obtained spectrum and check the residual. It should be at or below the numerical precision of the SDP solver.
5. **Consistency with epsilon expansion.** Bootstrap results for the 3D Ising model should be consistent with Borel-resummed epsilon expansion results: η = 0.0362(5), ν = 0.6300(4). Any significant disagreement indicates an error in one or both methods.
6. **Ward identities for conserved currents.** If the CFT has a global symmetry, the corresponding conserved current has Δ = d-1 exactly. The stress tensor has Δ = d exactly. These are protected dimensions — they should appear in the spectrum at their exact values, not as approximate numbers.
