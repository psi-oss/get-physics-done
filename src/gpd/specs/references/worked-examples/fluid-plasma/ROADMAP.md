# Roadmap: Kelvin-Helmholtz Instability in Compressible MHD

## Phases

- [x] **Phase 1: Literature and Setup** - Establish conventions, identify parameter regime, catalogue prior KH results
- [x] **Phase 2: Governing Equations** - Write ideal compressible MHD equations, non-dimensionalize, specify boundary conditions
- [x] **Phase 3: Equilibrium Analysis** - Verify Harris-like shear profile satisfies force balance, compute equilibrium profiles
- [x] **Phase 4: Stability Analysis** - Linearize MHD equations, derive dispersion relation, map stability boundaries
- [ ] **Phase 5: Nonlinear Dynamics** - Analyze nonlinear saturation, vortex merging, mixing layer growth
- [ ] **Phase 6: Numerical Simulation** - Configure Athena++ or Dedalus, run convergence study, production runs
- [ ] **Phase 7: Validation** - Check conservation laws, compare with analytic growth rates, benchmark against literature
- [ ] **Phase 8: Paper Writing** - Draft manuscript

## Phase Details

### Phase 1: Literature and Setup

**Goal:** Fix conventions and identify parameter space
**Status:** COMPLETE

**Success Criteria:**
1. [x] Physical system defined: 2D periodic box, shear layer, uniform B along flow
2. [x] Dimensionless parameters: M_s = 0.5, M_A = 0.5 to infinity, Re = infinity (ideal)
3. [x] Conventions: SI units, Alfven normalization, gamma = 5/3
4. [x] Prior work: Chandrasekhar (1961) analytic, Miura & Pritchett (1982) simulation, Frank et al. (1996) compressible MHD

Plans:
- [x] 01-01: Survey KH literature in compressible MHD
- [x] 01-02: Fix conventions in NOTATION_GLOSSARY.md

### Phase 2: Governing Equations

**Goal:** Write complete MHD equation set in dimensionless form
**Status:** COMPLETE

**Success Criteria:**
1. [x] Ideal compressible MHD: continuity + momentum + energy + induction
2. [x] Adiabatic EOS: p = rho^gamma with gamma = 5/3
3. [x] Boundary conditions: periodic in x, periodic in y (large enough domain)
4. [x] Non-dimensionalized: L = a (shear width), V = v_A, rho = rho_0

Plans:
- [x] 02-01: Write equations in conservation form
- [x] 02-02: Non-dimensionalize and derive control parameters: M_s, M_A

### Phase 3: Equilibrium Analysis

**Goal:** Verify shear equilibrium satisfies all governing equations
**Status:** COMPLETE

**Success Criteria:**
1. [x] Equilibrium: v_x = M_A * tanh(y), rho = 1, p = 1/(gamma * M_s^2), B_x = 1
2. [x] Force balance: trivially satisfied (no y-gradients in p + B^2/2)
3. [x] Equilibrium self-consistent: induction equation d(B)/dt = 0 for steady state with v_y = 0

Plans:
- [x] 03-01: Verify force balance analytically
- [x] 03-02: Compute derived quantities: c_s, v_A, plasma beta

### Phase 4: Stability Analysis

**Goal:** Linear stability of KH with magnetic field
**Status:** COMPLETE

**Success Criteria:**
1. [x] Linearized equations derived with normal-mode ansatz
2. [x] Dispersion relation: gamma(k, M_A) obtained
3. [x] Stabilization: modes with k*a > k_crit(M_A) are stable
4. [x] Critical M_A for complete stabilization: M_A_crit = sqrt(2)
5. [x] Growth rates match Chandrasekhar analytic result

Plans:
- [x] 04-01: Linearize MHD equations about shear equilibrium
- [x] 04-02: Solve eigenvalue problem numerically with Dedalus
- [x] 04-03: Map stability boundaries in (k*a, M_A) space

### Phase 5: Nonlinear Dynamics

**Goal:** Characterize nonlinear saturation and mixing
**Status:** PENDING

**Success Criteria:**
1. [ ] Saturation amplitude vs M_A measured
2. [ ] Mixing layer width delta(t) characterized
3. [ ] Vortex pairing dynamics identified
4. [ ] Magnetic field amplification quantified

Plans:
- [ ] 05-01: Analyze simulation output from single-mode perturbation runs
- [ ] 05-02: Characterize mixing layer growth law: delta(t) ~ t (linear) or t^2 (self-similar)
- [ ] 05-03: Quantify magnetic field amplification and its effect on saturation

### Phase 6: Numerical Simulation

**Goal:** Run validated MHD simulations
**Status:** PENDING

**Success Criteria:**
1. [ ] Code: Athena++ with HLLD Riemann solver, constrained transport
2. [ ] Resolution: 512 x 1024 baseline, 1024 x 2048 convergence check
3. [ ] CFL satisfied with fast magnetosonic speed throughout
4. [ ] div(B) < 10^{-14} (constrained transport)

Plans:
- [ ] 06-01: Configure Athena++ problem generator for KH shear layer
- [ ] 06-02: Run convergence study at M_A = 2 (unstable case)
- [ ] 06-03: Parameter scan: M_A = {0.5, 1.0, 1.5, 2.0, 5.0, infinity}

### Phase 7: Validation

**Goal:** Verify simulation results
**Status:** PENDING

Plans:
- [ ] 07-01: Compare linear growth rates (simulation vs analytic)
- [ ] 07-02: Check conservation laws: energy, momentum, magnetic flux
- [ ] 07-03: Compare with Frank et al. (1996) and Lecoanet et al. (2016) results

### Phase 8: Paper Writing

**Goal:** Draft manuscript
**Status:** PENDING
