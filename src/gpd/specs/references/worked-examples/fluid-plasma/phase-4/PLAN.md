# Phase 4: Stability Analysis — Plan

## Goal

Determine the linear stability of the magnetized shear layer, derive the dispersion relation gamma(k, M_A), and map stability boundaries.

## Convention Assertion

```
ASSERT_CONVENTION: units=alfven_normalized(L=a,V=v_A,rho=rho_0), metric=cartesian_2D, equation_of_state=adiabatic(gamma=5/3), mhd_model=ideal, perturbation_ansatz=normal_mode(exp(ikx+gamma*t)*f(y))
```

## Tasks

### 04-01: Linearize MHD equations about shear equilibrium

**Input:** Equilibrium from Phase 3: v_x0 = M_A * tanh(y), rho_0 = 1, p_0 = 1/(gamma * M_s^2), B_x0 = 1.

**Method:**
1. Write perturbations: v = v_0 + v_1, B = B_0 + B_1, rho = rho_0 + rho_1, p = p_0 + p_1
2. Substitute into ideal compressible MHD equations
3. Linearize: keep only first-order terms in perturbation quantities
4. Apply normal-mode ansatz: all perturbations ~ exp(i k x) f(y) exp(gamma t)
5. Reduce to a system of ODEs in y for the perturbation amplitudes

**Verification:**
- [ ] Setting B_0 = 0 recovers the hydrodynamic Rayleigh equation
- [ ] Setting v_0 = 0 recovers the MHD wave equation (fast/slow/Alfven modes)
- [ ] Equations are symmetric under y -> -y for tanh profile (sinuous and varicose modes decouple)

**Expected output:** Eigenvalue problem: A(y) * d^2(f)/dy^2 + B(y) * d(f)/dy + C(y) * f = gamma * D(y) * f

### 04-02: Solve eigenvalue problem numerically

**Input:** Linearized equations from 04-01.

**Method:**
1. Use Dedalus eigenvalue solver (spectral discretization in y, Chebyshev basis)
2. Domain: y in [-L_y/2, L_y/2] with L_y = 20a (large enough to approximate infinite domain)
3. Boundary conditions: perturbations decay as y -> +/- infinity (implemented as f -> 0 at y = +/- L_y/2)
4. Scan over k*a from 0.01 to 2.0 in steps of 0.01
5. For each k, find all eigenvalues gamma; identify the unstable mode (Re(gamma) > 0)
6. Repeat for M_A = {0.5, 1.0, 1.414, 2.0, 5.0, 100.0 (proxy for infinity)}

**Verification:**
- [ ] Hydro limit (M_A -> infinity): gamma_max * a / V_0 ~ 0.2 at k*a ~ 0.4 (Michalke 1964)
- [ ] Resolution convergence: double Chebyshev modes (N=128 -> 256), growth rate changes < 0.1%
- [ ] Domain convergence: increase L_y from 20a to 40a, growth rate changes < 0.01%
- [ ] Eigenvalues come in conjugate pairs (gamma, gamma*) for real equilibrium

**Expected output:** Table of gamma(k, M_A) and plot of growth rate curves.

### 04-03: Map stability boundaries

**Input:** Growth rate data from 04-02.

**Method:**
1. For each M_A, find the maximum growth rate gamma_max and corresponding k_max
2. Find the marginal wavenumber k_crit where gamma(k_crit) = 0
3. Find the critical M_A where gamma_max = 0 (complete stabilization)
4. Compare with analytic prediction: k_crit * a = sqrt(M_A^2 - 2) / 1 for sinuous mode
5. Compare critical M_A with Chandrasekhar result: M_A_crit = sqrt(2) for equal density

**Verification:**
- [ ] Stability boundary k_crit(M_A) matches analytic formula within 1%
- [ ] Critical M_A = sqrt(2) = 1.414... within 0.5%
- [ ] For M_A < M_A_crit: ALL modes are stable (gamma < 0 for all k)
- [ ] Growth rate is real (no oscillatory instability) for this symmetric profile

**Expected output:** Stability diagram in (k*a, M_A) plane, and comparison table with Chandrasekhar (1961).
