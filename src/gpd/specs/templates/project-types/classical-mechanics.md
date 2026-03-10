---
template_version: 1
---

# Classical Mechanics Project Template

Default project structure for Hamiltonian dynamics, perturbation theory, KAM theory, Lyapunov analysis, symplectic integration, and bifurcation theory.

---

## Default Roadmap Phases

```markdown
## Phases

- [ ] **Phase 1: System Definition and Literature** - Define the Hamiltonian/Lagrangian, identify symmetries, catalogue known results
- [ ] **Phase 2: Equilibria and Linear Stability** - Find fixed points, compute linearized dynamics, classify stability
- [ ] **Phase 3: Perturbation Theory** - Canonical perturbation theory, normal forms, resonance analysis
- [ ] **Phase 4: Numerical Integration** - Symplectic integrators, long-time dynamics, Poincare sections
- [ ] **Phase 5: Chaos and Invariant Structures** - Lyapunov exponents, KAM tori, homoclinic tangles, bifurcation diagrams
- [ ] **Phase 6: Validation and Physical Interpretation** - Cross-check analytical vs numerical, verify conservation laws, interpret phase space structure
- [ ] **Phase 7: Paper Writing** - Draft manuscript

## Phase Details

### Phase 1: System Definition and Literature

**Goal:** Define the dynamical system precisely and catalogue what is known
**Success Criteria:**

1. [Hamiltonian/Lagrangian written with all degrees of freedom and parameters identified]
2. [Symmetries identified: continuous (Noether), discrete (time-reversal, parity)]
3. [Conserved quantities enumerated: energy, angular momentum, adiabatic invariants]
4. [Integrability status known: integrable, near-integrable, or fully chaotic]
5. [Prior analytical and numerical results catalogued]

Plans:

- [ ] 01-01: [Define system, identify symmetries and conserved quantities]
- [ ] 01-02: [Survey literature for known results and analytical solutions]

### Phase 2: Equilibria and Linear Stability

**Goal:** Map the fixed point structure and classify linear stability
**Success Criteria:**

1. [All equilibrium points found (analytically or numerically)]
2. [Linearized equations of motion derived around each equilibrium]
3. [Eigenvalues of stability matrix computed and classified]
4. [Stable, unstable, and center manifolds identified]
5. [Bifurcation parameter values identified where stability changes]

Plans:

- [ ] 02-01: [Find equilibria and compute stability matrices]
- [ ] 02-02: [Classify equilibria and identify bifurcation points]

### Phase 3: Perturbation Theory

**Goal:** Analytical treatment of near-integrable dynamics
**Success Criteria:**

1. [Unperturbed integrable system identified with action-angle variables]
2. [Canonical perturbation theory applied to target order]
3. [Resonances identified and their widths estimated (Chirikov criterion)]
4. [Secular terms removed via averaging or normal form transformation]
5. [KAM applicability conditions checked: twist condition, non-degeneracy]

Plans:

- [ ] 03-01: [Transform to action-angle variables, apply canonical perturbation theory]
- [ ] 03-02: [Analyze resonances, compute widths, check KAM conditions]

### Phase 4: Numerical Integration

**Goal:** Long-time numerical integration with symplectic methods
**Success Criteria:**

1. [Symplectic integrator implemented and energy conservation verified]
2. [Time step chosen for target energy error bound]
3. [Poincare sections computed for representative initial conditions]
4. [Phase space portraits showing regular and chaotic regions]
5. [Long-time stability verified for regular orbits]

Plans:

- [ ] 04-01: [Implement symplectic integrator, verify energy conservation]
- [ ] 04-02: [Compute Poincare sections and phase space portraits]

### Phase 5: Chaos and Invariant Structures

**Goal:** Quantify chaos and map invariant phase space structures
**Success Criteria:**

1. [Lyapunov exponents computed with convergence verified]
2. [KAM tori identified and their breakdown parameter values determined]
3. [Homoclinic/heteroclinic intersections detected if applicable]
4. [Bifurcation diagram constructed as function of control parameter]
5. [Fractal dimension or other chaos measures computed if relevant]

Plans:

- [ ] 05-01: [Compute Lyapunov exponents and identify chaotic regions]
- [ ] 05-02: [Map KAM tori, bifurcation diagram, and invariant structures]

### Phase 6: Validation and Physical Interpretation

**Goal:** Cross-validate analytical and numerical results
**Success Criteria:**

1. [Perturbative predictions agree with numerics in appropriate regime]
2. [Conservation laws verified numerically (energy, angular momentum to machine precision for symplectic integrators)]
3. [KAM theory predictions match observed torus structure]
4. [Chirikov resonance overlap predicts onset of chaos correctly]
5. [Physical interpretation of phase space structure provided]

Plans:

- [ ] 06-01: [Compare perturbative vs numerical results]
- [ ] 06-02: [Verify conservation laws and interpret phase space structure]

### Phase 7: Paper Writing

**Goal:** Produce publication-ready manuscript

See paper templates: `templates/paper/manuscript-outline.md`, `templates/paper/figure-tracker.md`, `templates/paper/cover-letter.md` for detailed paper artifacts.

**Success Criteria:**

1. [Complete manuscript with phase space figures]
2. [Analytical results with validity ranges clearly stated]
3. [Numerical methods fully described (integrator, step size, convergence)]
```

### Mode-Specific Phase Adjustments

**Explore mode:**
- Phase 2: Survey equilibria across the full parameter space; classify all bifurcation types before focusing on specific parameter values
- Phase 4: Compare integrators (Stormer-Verlet, Yoshida 4th/6th, Ruth) on energy conservation and phase space fidelity for the target system
- Phase 4: Scan multiple initial conditions spanning regular, near-separatrix, and chaotic regions to map the full phase space structure
- Phase 5: Compute Lyapunov exponents, NAFF frequency analysis, and Poincare sections in parallel to cross-validate chaos diagnostics

**Exploit mode:**
- Phase 2: Analyze only the equilibria and bifurcations relevant to the target parameter regime
- Phase 4: Use the validated symplectic integrator (e.g., Yoshida 4th order) with known step size requirements
- Phase 4: Run focused parameter study at pre-identified initial conditions
- Phase 5: Apply the established chaos diagnostic (e.g., maximal Lyapunov exponent) at target points only

**Adaptive:** Explore phase space structure and integrator performance first, then exploit the validated setup for production runs and targeted parameter studies.

---

## Standard Verification Checks for Classical Mechanics

See `references/verification/core/verification-core.md` for universal checks (dimensional analysis, limiting cases, conservation laws, order-of-magnitude) and `references/verification/core/verification-numerical.md` for numerical verification (energy conservation in symplectic integrators, convergence testing, Lyapunov exponent validation).

---

## Methods

### Analytical Methods

| Method | When to Use | Limitations | Key Reference |
|--------|-------------|-------------|---------------|
| Canonical perturbation theory | Near-integrable systems, small perturbation | Breaks down at resonances, secular terms | Goldstein Ch. 12; Lichtenberg & Lieberman |
| Lie series / Deprit method | Same as canonical PT, but avoids mixed-variable generating functions | Higher-order algebra complex | Deprit (1969), Celest. Mech. 1, 12 |
| Birkhoff normal form | Near elliptic fixed points | Divergent in general, but asymptotic | Meyer & Hall, Intro to Hamiltonian Dynamics |
| KAM theory | Proving persistence of invariant tori | Requires twist condition, sufficient irrationality | Kolmogorov (1954), Arnold (1963), Moser (1962) |
| Nekhoroshev theory | Stability time estimates for near-integrable | Exponentially long but finite stability | Nekhoroshev (1977) |
| Chirikov resonance overlap | Predicting chaos onset | Empirical criterion, not rigorous | Chirikov (1979), Phys. Rep. 52 |
| Melnikov method | Detecting homoclinic chaos | Requires explicit separatrix solution | Guckenheimer & Holmes, Ch. 4 |
| Averaging | Slow-fast systems, adiabatic invariants | Requires time-scale separation | Arnold, Mathematical Methods, Ch. 10 |

### Numerical Methods

| Method | Order | Symplectic | Best For |
|--------|-------|-----------|----------|
| Stormer-Verlet (leapfrog) | 2 | Yes | Simple Hamiltonian systems, molecular dynamics |
| Yoshida 4th order | 4 | Yes | General separable Hamiltonians |
| Yoshida 6th/8th order | 6/8 | Yes | High-accuracy long-time integration |
| Ruth's method | 3 | Yes | Compact 3-stage symplectic |
| Gauss-Legendre (implicit) | 2s | Yes | Non-separable Hamiltonians |
| Dormand-Prince (RK45) | 4-5 | No | Short-time, adaptive step, non-Hamiltonian |

**When to use symplectic vs non-symplectic:**
- Symplectic: Long-time dynamics, energy conservation matters, phase space structure
- Non-symplectic (RK45): Short integration times, dissipative systems, adaptive stepping needed

---

## Common Pitfalls

1. **KAM theorem applicability**: KAM theory requires the twist condition (frequency depends on action) and sufficient irrationality of frequency ratios. Systems with degenerate frequencies (e.g., Kepler problem, harmonic oscillators) need separate treatment. The standard KAM theorem does not apply directly.

2. **Numerical chaos detection**: Finite-time Lyapunov exponents can be misleading. Short integrations may give positive exponents for regular orbits near separatrices (sticky orbits). Always verify convergence by computing Lyapunov exponents for increasing integration times. Cross-check with Poincare sections and frequency analysis (NAFF).

3. **Lyapunov exponent convergence**: The maximal Lyapunov exponent converges as 1/t for regular orbits and approaches a constant for chaotic orbits. Must integrate long enough to distinguish. Typical requirement: t > 10^4 / lambda_max. Renormalize the deviation vector periodically to avoid overflow.

4. **Symplectic integrator energy drift**: Symplectic integrators do not conserve the exact Hamiltonian but a nearby shadow Hamiltonian. Energy oscillates but does not drift secularly. If you see secular energy drift, the integrator is not symplectic (check implementation) or step size is too large (outside convergence radius).

5. **Resonance islands vs chaos**: Near a resonance, phase space has islands of stability surrounded by thin chaotic layers. The island width scales as sqrt(perturbation strength). Confusing island chains with chaos leads to wrong conclusions about integrability.

6. **Canonical transformation pitfalls**: Generating functions must be non-degenerate (det(d^2 F / dq dP) ≠ 0). Type-1 vs Type-2 generating functions cover different regions. Near separatrices, action-angle variables become singular. Use regularized variables or switch generating function type.

7. **Adiabatic invariant breaking**: Adiabatic invariants are conserved only when the parameter changes slowly compared to the orbital period. At separatrix crossings, the adiabatic invariant jumps by an amount exponentially small in the slowness parameter but can accumulate over many crossings.

8. **Bifurcation classification**: At bifurcation points, the normal form must include all relevant terms (don't truncate too early). Codimension-1 bifurcations (saddle-node, period-doubling, Hopf) are generic; higher codimension bifurcations require parameter tuning and are less robust.

---

## Key Tools

| Tool | Purpose | When to Use |
|------|---------|------------|
| **scipy.integrate** | ODE integration (solve_ivp, odeint) | Quick prototyping, non-symplectic systems |
| **REBOUND** | N-body orbital mechanics | Celestial mechanics, planetary dynamics |
| **galpy** | Galactic dynamics | Stellar orbits, galactic potentials |
| **sympy** | Symbolic mechanics | Deriving equations of motion, canonical transformations |
| **sympy.physics.mechanics** | Automated Lagrangian/Hamiltonian mechanics | Complex multi-body systems |
| **PyDSTool** | Dynamical systems toolkit | Bifurcation analysis, continuation methods |
| **AUTO-07p** | Numerical continuation and bifurcation | Periodic orbit families, bifurcation diagrams |
| **matplotlib** | Phase space visualization | Poincare sections, bifurcation diagrams, orbit plots |
| **JAX** | Differentiable dynamics | Sensitivity analysis, variational integrators |

---

## Default Conventions

See `templates/conventions.md` for the full conventions ledger template. Classical mechanics projects should populate:

- **Unit System:** Natural units or SI with explicit dimensional analysis
- **Coordinate Convention:** Generalized coordinates with explicit definitions
- **Discretization Convention:** Symplectic integrator type and order
- **Boundary Conditions:** Phase space topology (bounded, periodic, open)

---

## Computational Environment

**Symbolic mechanics:**

- `sympy.physics.mechanics` — Lagrangian/Hamiltonian mechanics, Kane's method, linearization
- `sympy.physics.vector` — Reference frames, angular velocity, vector calculus in rotating frames
- Mathematica `VariationalMethods` — Euler-Lagrange equations, constraints

**Numerical integration:**

- `scipy.integrate` — `solve_ivp` with RK45, DOP853, Radau (stiff), BDF (stiff)
- `diffeq.jl` (Julia) — High-performance ODE/DAE solvers (DifferentialEquations.jl)
- Custom symplectic integrators — Stormer-Verlet (2nd order), Ruth (4th order), Yoshida (higher order)

**Dynamical systems:**

- `scipy.optimize` — Fixed point finding, bifurcation detection
- `PyDSTool` (Python) — Continuation and bifurcation analysis
- `AUTO-07p` — Numerical continuation for ODEs and PDEs

**Visualization:**

- `matplotlib` — Phase portraits, Poincare sections, bifurcation diagrams
- `manim` / `vpython` — 3D animations of mechanical systems

**Setup:**

```bash
pip install numpy scipy sympy matplotlib
```

---

## Bibliography Seeds

| Reference | What it provides | When to use |
|-----------|-----------------|-------------|
| Goldstein, Poole & Safko, *Classical Mechanics* | Comprehensive treatment, Lagrangian/Hamiltonian formalism | Standard reference |
| Arnold, *Mathematical Methods of Classical Mechanics* | Geometric mechanics, symplectic geometry, KAM theory | Mathematical rigor |
| Strogatz, *Nonlinear Dynamics and Chaos* | Bifurcations, strange attractors, phase portraits | Dynamical systems |
| Landau & Lifshitz, *Mechanics* | Concise, elegant, symmetry-first | Short derivations |
| Tabor, *Chaos and Integrability in Nonlinear Dynamics* | Integrable systems, Painleve analysis, Melnikov method | Chaos and integrability |
| Hairer, Lubich & Wanner, *Geometric Numerical Integration* | Symplectic integrators, structure-preserving methods | Numerical methods |

---

## Worked Example: Double Pendulum Chaos and Lyapunov Exponents

**Phase 1 — Setup:** Double pendulum with masses m1, m2 and lengths l1, l2. Lagrangian L = T - V with T = (1/2)(m1+m2)l1^2 theta1_dot^2 + (1/2)m2 l2^2 theta2_dot^2 + m2 l1 l2 theta1_dot theta2_dot cos(theta1-theta2) and V = -(m1+m2)g l1 cos(theta1) - m2 g l2 cos(theta2). Conventions: SI units, angles from vertical, positive counterclockwise.

**Phase 2 — Integration:** Derive Euler-Lagrange equations (4 coupled first-order ODEs in theta1, theta2, p1, p2). Integrate with symplectic Stormer-Verlet (dt=0.001s, total time 100s). Compute Lyapunov exponent: evolve two nearby trajectories (delta_0 = 1e-9), measure exponential divergence lambda = lim (1/t) ln(|delta(t)|/|delta_0|). For m1=m2=1, l1=l2=1, E/E_max > 0.5: expect lambda > 0 (chaotic).

**Phase 3 — Validation:** Energy conservation: |E(t) - E(0)|/|E(0)| < 1e-10 for symplectic integrator (no secular drift). Small-angle limit: frequencies omega_1, omega_2 match linearized normal mode analysis omega^2 = g/l * (1 ± 1/sqrt(2)) for equal masses/lengths. Poincare section (theta2=0, theta2_dot>0): shows transition from regular (KAM tori) to chaotic (scattered dots) as energy increases. Lyapunov exponent lambda ~ 1-3 s^{-1} for fully chaotic regime — compare with published values.
