---
load_when:
  - "fluid dynamics"
  - "Navier-Stokes"
  - "MHD"
  - "magnetohydrodynamics"
  - "turbulence"
  - "Reynolds number"
  - "Alfven wave"
  - "viscosity"
  - "Kolmogorov"
  - "spectral method"
  - "CFD"
  - "Mach number"
  - "incompressible"
  - "Euler equation"
  - "vorticity"
  - "boundary layer"
  - "Stokes flow"
  - "plasma"
  - "Debye length"
tier: 2
context_cost: medium
---

# Fluid Dynamics and Magnetohydrodynamics Protocol

Fluid dynamics spans astrophysics (accretion disks, stellar convection), condensed matter (superfluids, active matter), soft matter (microfluidics), cosmology (baryon acoustic oscillations), and plasma physics. It is the single largest physics domain with zero prior protocol coverage.

**Core discipline:** Fluids are deceptive — the governing equations (Navier-Stokes) are simple to write but produce behavior spanning laminar creeping flow to fully developed turbulence. The Reynolds number determines everything. An analysis valid at Re = 10 is catastrophically wrong at Re = 10⁶. Every step below exists because regime misidentification is the #1 error in fluid dynamics.

## Related Protocols

- `numerical-computation.md` — CFL condition, convergence testing, error estimation
- `stochastic-processes.md` — Turbulence modeling, stochastic forcing
- `non-equilibrium-transport.md` — Transport coefficients, Boltzmann equation
- `order-of-limits.md` — Non-commuting limits (inviscid vs incompressible, etc.)
- `kinetic-theory.md` — Boltzmann equation derivation of viscosity, thermal conductivity, and other transport coefficients from molecular dynamics
- `references/verification/domains/verification-domain-fluid-plasma.md` — Concrete verification formulas: MHD equilibrium, reconnection rates, turbulence spectra, conservation laws

---

## Step 1: Identify the Flow Regime

Before any calculation, compute the relevant dimensionless numbers:

| Number | Definition | Physical Meaning | Critical Value |
|--------|-----------|-----------------|----------------|
| **Reynolds (Re)** | UL/ν | Inertia vs viscosity | Re > 2000 → turbulent (pipe); Re > 5×10⁵ (flat plate) |
| **Mach (Ma)** | U/c_s | Flow speed vs sound speed | Ma > 0.3 → compressibility matters |
| **Magnetic Reynolds (Rm)** | UL/η | Advection vs magnetic diffusion | Rm > 1 → frozen-in flux |
| **Prandtl (Pr)** | ν/α | Momentum vs thermal diffusivity | Pr ~ 0.7 (air), ~7 (water), ~0.01 (liquid metals) |
| **Knudsen (Kn)** | λ_mfp/L | Mean free path vs system size | Kn > 0.1 → rarefied gas, continuum invalid |

**CRITICAL:** If Re > 10⁴ and the flow is not explicitly laminar (channel, Couette), assume turbulence. Laminar solutions at high Re are physically unstable even if mathematically valid.

**Common LLM Error:** Applying Stokes' law (drag ∝ velocity) at high Reynolds number. Stokes drag is valid ONLY for Re ≪ 1. At Re > 1000, drag ∝ velocity² (turbulent drag).

---

## Step 2: Choose the Governing Equations

| Regime | Equations | Simplification |
|--------|----------|----------------|
| Incompressible, Newtonian | ∇·u = 0, ∂u/∂t + (u·∇)u = -∇p/ρ + ν∇²u | Full Navier-Stokes |
| Compressible | ∂ρ/∂t + ∇·(ρu) = 0, + momentum + energy | Include density and energy equations |
| Inviscid | Euler equations (ν = 0) | No viscous terms — valid far from boundaries |
| Creeping flow (Re ≪ 1) | Stokes equations | Drop nonlinear (u·∇)u term |
| Ideal MHD | NS + ∂B/∂t = ∇×(u×B), ∇·B = 0 | Infinite conductivity, frozen-in flux |
| Resistive MHD | + η∇²B diffusion term | Finite conductivity, reconnection possible |
| Boundary layer | Prandtl equations | Thin viscous layer near solid surfaces |

**Verification:**
- [ ] ∇·u = 0 satisfied for incompressible flow (divergence-free velocity field)
- [ ] ∇·B = 0 satisfied at ALL times for MHD (no magnetic monopoles)
- [ ] Energy conservation: ∫ ½ρu² dV = const for inviscid flow (Euler)

---

## Step 3: Turbulence Modeling

For Re > ~10⁴, direct numerical simulation (DNS) resolves all scales but is prohibitively expensive for most problems. Choose a modeling approach:

| Approach | Resolves | Models | Cost | When to Use |
|----------|---------|--------|------|-------------|
| **DNS** | All scales down to Kolmogorov η | Nothing | O(Re^{9/4}) in 3D | Re < ~10⁴, benchmark cases |
| **LES** | Large eddies (> filter scale Δ) | Subgrid stress | O((L/Δ)³) | Re up to ~10⁸, complex geometry |
| **RANS** | Mean flow only | All turbulent fluctuations | O(L/Δ_mesh)³ | Engineering, steady-state averages |
| **Spectral** | All resolved wavenumbers | Aliasing truncation | O(N³ log N) per step | Homogeneous turbulence, periodic domains |

### Kolmogorov Theory (K41)

For fully developed 3D turbulence at high Re:

- Energy spectrum: E(k) = C_K ε^{2/3} k^{-5/3} (inertial range)
- Kolmogorov length scale: η = (ν³/ε)^{1/4}
- Kolmogorov time scale: τ_η = (ν/ε)^{1/2}
- Energy dissipation rate: ε ~ U³/L (large-scale estimate)
- Number of degrees of freedom: N ~ (L/η)³ ~ Re^{9/4}

**Verification:**
- [ ] Energy spectrum has -5/3 slope in inertial range (log-log plot)
- [ ] Dissipation is concentrated at small scales (near η)
- [ ] Total energy dissipation rate ε is independent of viscosity at high Re (anomalous dissipation)

**Common LLM Error:** Applying K41 to 2D turbulence. In 2D, the energy cascade is INVERSE (large scales, -5/3 slope) and the enstrophy cascade is forward (small scales, -3 slope). Using the 3D cascade direction in 2D gives wrong predictions for everything.

---

## Step 4: Numerical Methods for Fluids

### CFL Condition (MANDATORY for explicit time-stepping)

Δt ≤ C × Δx / (|u| + c_s)

where C is the Courant number (C ≤ 1 for stability, typically C = 0.5 for safety).

For MHD, include the Alfven speed: Δt ≤ C × Δx / (|u| + c_s + v_A) where v_A = B/√(μ₀ρ).

**Common LLM Error:** Using CFL with only the flow speed |u|, forgetting the sound speed c_s. For subsonic flows (Ma < 1), the sound speed dominates the CFL constraint — the timestep is much smaller than the flow timescale. This is why incompressible solvers are preferred for low-Mach flows.

### Spatial Discretization

| Method | Accuracy | Conservation | Best For |
|--------|----------|-------------|----------|
| Finite difference | 2nd-6th order | Not inherently conservative | Simple geometries |
| Finite volume | 2nd order typical | Conservative by construction | Compressible flows, shocks |
| Spectral | Exponential (smooth) | Global conservation | Periodic, homogeneous turbulence |
| Finite element | Variable order | Weak conservation | Complex geometry |

### Numerical Diffusion

**ALL low-order upwind schemes add artificial diffusion.** The effective Reynolds number of the simulation is:

Re_eff = min(Re_physical, Re_numerical) where Re_numerical ~ U Δx / ν_numerical

If Re_numerical < Re_physical, the simulation is under-resolved and numerical diffusion dominates over physical viscosity. The flow appears more laminar than it should be.

**Detection:** Compare results at two resolutions. If the flow structure changes qualitatively (e.g., turbulence appears at higher resolution), the coarser simulation was under-resolved.

---

## Step 5: MHD-Specific Checks

### ∇·B = 0 Preservation

The divergence-free constraint ∇·B = 0 is an initial condition, not enforced by the induction equation. Numerical errors can create ∇·B ≠ 0 (magnetic monopoles), causing unphysical forces.

**Cleaning methods:**
- Constrained transport (CT): exactly preserves ∇·B = 0 on staggered grids
- Divergence cleaning (Dedner): hyperbolic/parabolic damping of ∇·B errors
- Projection: solve ∇²φ = ∇·B, then B → B - ∇φ after each step

**Verification:** Monitor max(|∇·B|)/max(|∇×B|) throughout the simulation. Should be < 10⁻⁸ (machine precision for CT) or < 10⁻³ (acceptable for cleaning).

### Alfven Speed and MHD Waves

Three MHD wave modes (verify dispersion relations):
- Fast magnetosonic: v_f² = ½(c_s² + v_A² + √((c_s² + v_A²)² - 4c_s²v_A²cos²θ))
- Slow magnetosonic: v_s² = ½(c_s² + v_A² - √(...))
- Alfven: v_A² = B²/(μ₀ρ), propagates along B

**Common LLM Error:** Confusing the Alfven speed v_A = B/√(μ₀ρ) with the fast magnetosonic speed v_f. In the limit B ≫ c_s√(μ₀ρ), v_f → v_A for perpendicular propagation, but they differ significantly for oblique angles.

---

## Worked Example: Poiseuille Flow Transition

**Problem:** Water (ν = 10⁻⁶ m²/s) flows through a pipe of diameter D = 2 cm. At what flow speed does the transition to turbulence occur? What is the pressure drop per meter for laminar and turbulent flow at U = 0.5 m/s?

### Solution

**Step 1:** Critical Reynolds number for pipe flow:
Re_c ≈ 2300 (empirical). U_c = Re_c × ν / D = 2300 × 10⁻⁶ / 0.02 = 0.115 m/s.

**Step 2:** At U = 0.5 m/s: Re = 0.5 × 0.02 / 10⁻⁶ = 10,000. Turbulent.

**Step 3:** Laminar pressure drop (Hagen-Poiseuille, for comparison):
Δp/L = 128 μ Q / (π D⁴) = 32 ν ρ U / D² = 32 × 10⁻⁶ × 1000 × 0.5 / (0.02)² = 40 Pa/m

**Step 4:** Turbulent pressure drop (Darcy-Weisbach + Moody friction factor):
f = 0.316 Re⁻⁰·²⁵ (Blasius, for smooth pipes, Re < 10⁵)
f = 0.316 × 10000⁻⁰·²⁵ = 0.0316
Δp/L = f ρ U² / (2D) = 0.0316 × 1000 × 0.25 / 0.04 = 198 Pa/m

**Verification:**
- [ ] Turbulent Δp > laminar Δp at same flow rate (198 > 40) ✓
- [ ] Re = 10,000 > 2300 → turbulent regime confirmed ✓
- [ ] Dimensional check: [Δp/L] = [Pa/m] = [kg/(m²·s²)] ✓
- [ ] Limiting case Re → 0: Δp/L → 0 (no flow, no pressure drop) ✓
- [ ] Turbulent scaling: Δp ∝ U^{1.75} (from Blasius) vs laminar Δp ∝ U ✓

---

## Verification Checklist

Before finalizing any fluid dynamics calculation:

- [ ] Reynolds number computed and flow regime identified
- [ ] Mach number checked (incompressible assumption valid if Ma < 0.3)
- [ ] Correct governing equations for the regime (Stokes, NS, Euler, MHD)
- [ ] ∇·u = 0 verified for incompressible flows
- [ ] ∇·B = 0 verified at all times for MHD
- [ ] CFL condition satisfied with correct wave speed (include c_s and v_A)
- [ ] Numerical diffusion vs physical viscosity ratio assessed
- [ ] Turbulence model appropriate for the Reynolds number
- [ ] Energy spectrum verified (K41 scaling in 3D inertial range)
- [ ] 2D vs 3D cascade direction correct (inverse energy cascade in 2D)
- [ ] Boundary conditions consistent with physics (no-slip, free-slip, periodic)
- [ ] Grid convergence demonstrated (results independent of resolution)
