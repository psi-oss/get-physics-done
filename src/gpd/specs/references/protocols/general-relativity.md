---
load_when:
  - "general relativity"
  - "Einstein equation"
  - "Christoffel"
  - "Riemann tensor"
  - "Ricci tensor"
  - "geodesic"
  - "black hole"
  - "Schwarzschild"
  - "Kerr"
  - "Penrose diagram"
  - "Hawking radiation"
  - "surface gravity"
  - "Killing vector"
  - "covariant derivative"
  - "metric tensor"
  - "Einstein-Hilbert"
  - "ADM"
  - "Kruskal"
  - "Birkhoff"
  - "Penrose process"
tier: 2
context_cost: medium
---

# General Relativity Core Calculations Protocol

GR calculations are uniquely error-prone because of the interplay of index gymnastics, sign conventions (metric signature, Riemann tensor sign), and the distinction between coordinate artifacts and physical effects. A wrong sign in a Christoffel symbol propagates to every tensor built from it.

**Core discipline:** In GR, every index placement matters. Every factor of the metric matters. The difference between covariant and partial derivatives matters. Compute carefully, verify obsessively, and always check that coordinate singularities are not confused with physical singularities.

## Related Protocols

- `derivation-discipline.md` — General derivation rigor (sign tracking, dimensional analysis)
- `symmetry-analysis.md` — Killing vectors, isometry groups
- `numerical-relativity.md` — 3+1 decomposition, constraint equations, gauge conditions
- `cosmological-perturbation-theory.md` — Perturbations around FRW backgrounds
- `order-of-limits.md` — Non-commuting limits (e.g., r→0 vs M→0 in Schwarzschild)

---

## Step 1: Establish Conventions

Before ANY GR calculation, lock these conventions (even for "obvious" cases):

| Convention | Choice A | Choice B | Impact If Mixed |
|-----------|----------|----------|-----------------|
| Metric signature | (-,+,+,+) [MTW, Wald, Carroll] | (+,-,-,-) [Weinberg, Landau] | EVERY sign in EVERY equation flips |
| Riemann tensor | R^ρ_{σμν} = ∂_μΓ^ρ_{νσ} - ∂_νΓ^ρ_{μσ} + ΓΓ - ΓΓ [MTW] | Opposite sign [Weinberg] | Ricci tensor and Einstein equation signs flip |
| Ricci tensor contraction | R_{μν} = R^ρ_{μρν} [MTW, Wald] | R_{μν} = R^ρ_{ρμν} [Landau] | Sign of Ricci tensor flips |
| Einstein equation | G_{μν} + Λg_{μν} = 8πG T_{μν} [MTW] | G_{μν} = 8πG T_{μν} - Λg_{μν} | Cosmological constant sign |
| Covariant derivative | ∇_μ V^ν = ∂_μV^ν + Γ^ν_{μρ}V^ρ | Same (universal) | N/A |

**Verification:** Compute R_{μν} for flat space. It MUST be zero in ALL conventions. If not, the sign convention is internally inconsistent.

---

## Step 2: Metric and Christoffel Symbols

### 2a. Write the metric explicitly

For a given spacetime, write g_{μν} as a matrix with ALL components visible. Example (Schwarzschild):

```
ds² = -(1-2M/r)dt² + (1-2M/r)^{-1}dr² + r²dθ² + r²sin²θ dφ²
```

**Verification:**
- [ ] Metric has correct signature (count positive and negative eigenvalues)
- [ ] At spatial infinity (r→∞), metric reduces to Minkowski η_{μν}
- [ ] Determinant g = det(g_{μν}) is nonzero away from known singularities

### 2b. Compute Christoffel symbols

Γ^ρ_{μν} = ½g^{ρσ}(∂_μ g_{νσ} + ∂_ν g_{μσ} - ∂_σ g_{μν})

**MANDATORY checks after computing Christoffels:**
- [ ] Symmetry: Γ^ρ_{μν} = Γ^ρ_{νμ} (torsion-free connection)
- [ ] Count: In 4D, there are at most 40 independent components (4 × 10 symmetric pairs). For diagonal metrics, far fewer are nonzero.
- [ ] Flat space limit: ALL Christoffels → 0 when the metric is Minkowski
- [ ] Known result: For Schwarzschild, Γ^r_{tt} = M(1-2M/r)/r² and Γ^t_{tr} = M/[r(r-2M)]

**Common LLM Error:** Index placement confusion. Γ^r_{tt} is NOT the same as Γ_r^{tt} or Γ_{rtt}. The upper index is the FREE index from the inverse metric g^{ρσ}. Always write Christoffels with one upper and two lower indices.

---

## Step 3: Riemann, Ricci, and Scalar Curvature

### 3a. Riemann tensor

R^ρ_{σμν} = ∂_μΓ^ρ_{νσ} - ∂_νΓ^ρ_{μσ} + Γ^ρ_{μλ}Γ^λ_{νσ} - Γ^ρ_{νλ}Γ^λ_{μσ}

**MANDATORY symmetry checks:**
- [ ] Antisymmetry on last pair: R^ρ_{σμν} = -R^ρ_{σνμ}
- [ ] Antisymmetry on first pair (when lowered): R_{ρσμν} = -R_{σρμν}
- [ ] Pair symmetry: R_{ρσμν} = R_{μνρσ}
- [ ] First Bianchi identity: R^ρ_{[σμν]} = 0
- [ ] In 4D: 20 independent components (not 256)

### 3b. Ricci tensor and scalar

R_{μν} = R^ρ_{μρν} (contraction on 1st and 3rd indices with the convention above)

R = g^{μν}R_{μν}

**Verification:**
- [ ] R_{μν} is symmetric: R_{μν} = R_{νμ}
- [ ] For vacuum (T_{μν} = 0): R_{μν} = 0 (Einstein equation in vacuum)
- [ ] Kretschmann scalar K = R_{μνρσ}R^{μνρσ} is finite away from physical singularities (if K → ∞, it's a physical singularity; if only coordinate components diverge but K is finite, it's a coordinate singularity)

---

## Step 4: Einstein Equation

G_{μν} = R_{μν} - ½g_{μν}R = 8πG T_{μν}

### Conservation law check

∇_μ G^{μν} = 0 identically (contracted Bianchi identity). This implies ∇_μ T^{μν} = 0 (energy-momentum conservation).

**Verification:** After solving, compute ∇_μ T^{μν} numerically at several points. It must vanish to machine precision. If it doesn't, the solution is WRONG.

---

## Step 5: Geodesic Equation

d²x^μ/dτ² + Γ^μ_{νρ}(dx^ν/dτ)(dx^ρ/dτ) = 0

### Key distinctions

| Type | Parameter | Normalization | Use |
|------|----------|--------------|-----|
| Timelike | Proper time τ | g_{μν}u^μu^ν = -1 (mostly plus) | Massive particles |
| Null | Affine parameter λ | g_{μν}k^μk^ν = 0 | Light rays |
| Spacelike | Proper distance s | g_{μν}n^μn^ν = +1 (mostly plus) | Spatial curves |

**Common LLM Error:** Using proper time τ for null geodesics. Photons have dτ = 0 along their worldline — proper time is meaningless. Use an affine parameter λ instead.

**Verification:**
- [ ] The normalization condition is preserved along the geodesic (it's a first integral)
- [ ] In the Newtonian limit (weak field, slow motion), the spatial geodesic equation reduces to d²x^i/dt² = -∂Φ/∂x^i where Φ = -M/r

---

## Step 6: Killing Vectors and Conservation Laws

If ξ^μ is a Killing vector (∇_{(μ}ξ_{ν)} = 0), then along a geodesic:

E = -ξ^μ_{(t)} u_μ (energy, from time translation symmetry)
L = ξ^μ_{(φ)} u_μ (angular momentum, from rotational symmetry)

are conserved.

**Common LLM Error:** Wrong sign for the energy. With the (-,+,+,+) convention and ξ^μ_{(t)} = (1,0,0,0), the conserved energy is E = -g_{tμ}u^μ = -g_{tt}u^t. For a particle at rest at infinity, E = 1 (rest mass energy in geometric units). The minus sign is from the metric signature.

---

## Step 7: Black Hole Physics

### Surface gravity

For a Killing horizon with Killing vector χ^μ:

κ² = -½(∇_μχ_ν)(∇^μχ^ν) evaluated at the horizon

For Schwarzschild: κ = 1/(4M) (geometric units G = c = 1)

### Hawking temperature

T_H = κ/(2π) = 1/(8πM) (geometric units with k_B = 1)

**Common LLM Error:** Factor of 2 error. Some derivations define surface gravity differently, giving κ = 1/(2M) (wrong — this is the acceleration, not the surface gravity). The correct Hawking temperature for a Schwarzschild black hole of mass M is:

T_H = ℏc³/(8πGMk_B) (SI units)

**Verification:**
- [ ] T_H → 0 as M → ∞ (large black holes are cold)
- [ ] T_H → ∞ as M → 0 (small black holes are hot — leads to evaporation)
- [ ] Dimensional check: [T_H] = [energy] in natural units = [mass] in geometric units

### Bekenstein-Hawking entropy

S = A/(4G) = 4πM² (geometric units, Schwarzschild)

where A = 4π(2M)² = 16πM² is the horizon area.

**Verification:**
- [ ] First law: dM = T_H dS = (1/8πM)(8πM dM) = dM ✓
- [ ] S > 0 for M > 0 ✓
- [ ] S is proportional to area, not volume (holographic principle)

---

## Common LLM Error Patterns

| Error | LLM Symptom | Detection | Error Class |
|-------|-------------|-----------|-------------|
| Metric signature mix-up | Sign errors in propagator, geodesic equation, energy | Check p² = ±m² and compare with declared convention | #37 |
| Coordinate vs physical singularity | Claims r = 2M is a singularity in Schwarzschild | Compute Kretschmann scalar — finite at r=2M, infinite at r=0 | #10 |
| Wrong Christoffel index placement | Γ_{μνρ} instead of Γ^ρ_{μν} | Check symmetry in lower indices, verify inverse metric was used | #38, #39 |
| Riemann tensor sign error | Wrong sign from swapped partial derivative order | Check antisymmetry: R^ρ_{σμν} = -R^ρ_{σνμ} | #2 |
| Hawking temperature factor of 2 | T_H = 1/(4πM) instead of 1/(8πM) | Verify first law dM = TdS gives consistent entropy | #1 |
| Covariant vs partial derivative | Uses ∂_μ where ∇_μ is needed for tensors | Check: does the expression transform correctly under coordinates? | #38 |
| Non-affine null geodesic | Uses proper time for null rays | Check g_{μν}dx^μdx^ν = 0 along the geodesic | #46 |
| Wrong Newtonian limit | g_{00} ≈ -(1+2Φ) instead of -(1+2Φ/c²) | Check units: Φ/c² is dimensionless in SI | #15, #33 |

---

## Verification Checklist

Before finalizing any GR calculation:

- [ ] Metric signature explicitly declared and consistent throughout
- [ ] Christoffel symbols symmetric in lower indices
- [ ] Riemann tensor satisfies all algebraic symmetries (antisymmetry, pair symmetry, Bianchi)
- [ ] Ricci tensor is symmetric
- [ ] Flat space limit gives zero curvature
- [ ] Kretschmann scalar computed to classify singularities
- [ ] Geodesic normalization preserved along trajectories
- [ ] Killing vector conservation laws have correct signs
- [ ] Newtonian limit recovered (g_{00} ≈ -(1+2Φ) with correct units)
- [ ] Energy-momentum conservation ∇_μT^{μν} = 0 verified
- [ ] Black hole thermodynamic first law dM = TdS + ΩdJ + ΦdQ satisfied
- [ ] Hawking temperature has correct factor (1/8πM, not 1/4πM)
