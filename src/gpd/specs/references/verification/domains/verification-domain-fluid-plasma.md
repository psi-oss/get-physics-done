---
load_when:
  - "fluid dynamics verification"
  - "MHD verification"
  - "Alfven wave"
  - "magnetic reconnection"
  - "Kelvin-Helmholtz"
  - "Rayleigh-Taylor"
  - "tearing mode"
  - "turbulence spectrum"
  - "plasma beta"
  - "Lundquist number"
  - "div B"
  - "CFL condition"
tier: 2
context_cost: large
---

# Verification Domain — Fluid Dynamics and Plasma Physics

MHD equilibrium, stability, magnetic reconnection, turbulence spectra, conservation laws, and numerical diagnostics for fluid and plasma calculations.

**Load when:** Working on MHD equilibria, fluid instabilities, turbulence, magnetic reconnection, plasma transport, or any calculation involving the Navier-Stokes or MHD equations.

**Related files:**
- `../core/verification-quick-reference.md` — compact checklist (default entry point)
- `../core/verification-core.md` — dimensional analysis, limiting cases, conservation laws
- `../core/verification-numerical.md` — convergence, statistical validation
- `references/protocols/fluid-dynamics-mhd.md` — step-by-step calculation protocol
- `references/subfields/fluid-plasma.md` — tools, methods, research frontiers

---

<mhd_equilibrium>

## MHD Equilibrium and Force Balance

**Static MHD equilibrium (force balance):**

```
J x B = grad(p) + rho * grad(Phi)   (with gravity)
J x B = grad(p)                      (without gravity)

where J = curl(B)/mu_0, and the magnetic force decomposes as:
  J x B = -grad(B^2/(2*mu_0)) + (B . grad)B/mu_0
        = -grad(magnetic pressure) + magnetic tension

Verification:
1. COMPUTE: |J x B - grad(p)| / |J x B| at multiple points. Must be < 10^{-3} for
   a claimed equilibrium. If > 0.01: the state is NOT in equilibrium.
2. For cylindrical geometry (z-pinch, theta-pinch):
   d/dr(p + B_z^2/(2*mu_0)) = -B_theta^2/(mu_0*r) + B_theta*B_z'/(mu_0)
   Verify this radial balance at each grid point.
3. Plasma beta = 2*mu_0*p/B^2. If beta >> 1: pressure-dominated, magnetic effects are perturbative.
   If beta << 1: magnetically dominated, pressure gradients are perturbative.
```

**Grad-Shafranov equation (axisymmetric MHD):**

```
R * d/dR(1/R * dpsi/dR) + d^2(psi)/dZ^2 = -mu_0 * R^2 * dp/dpsi - F * dF/dpsi

where psi(R,Z) is the poloidal flux function, p(psi) is pressure, F(psi) = R*B_phi.

Verification:
1. COMPUTE: Substitute solution psi(R,Z) back into the GS equation. The residual
   |LHS - RHS| / max(|LHS|) should be < 10^{-6} for a numerically converged solution.
2. COMPUTE: Safety factor q(psi) = 1/(2*pi) * oint(B_phi/(R*B_p)) dl.
   For tokamaks: q(0) > 1 for stability against internal kink mode.
   If q(0) < 1: the m=1 internal kink is unstable (Kruskal-Shafranov condition).
3. COMPUTE: Shafranov shift Delta(r). For circular cross-section:
   Delta ~ a * beta_p / 2 where beta_p = 2*mu_0*<p>/(B_p^2).
   If Delta > a/3: the large-aspect-ratio expansion breaks down.
```

</mhd_equilibrium>

<waves_and_dispersion>

## MHD Waves and Dispersion Relations

**Alfven wave:**

```
omega = k_parallel * v_A
v_A = B_0 / sqrt(mu_0 * rho_0)

Verification:
1. COMPUTE: v_A from equilibrium B_0 and rho_0. Check units: [T] / sqrt([H/m] * [kg/m^3]) = [m/s].
2. For a propagating Alfven wave in simulation: measure phase velocity from space-time diagram.
   Must match v_A within 1%. Deviation indicates numerical dispersion or wrong Rm.
3. COMPUTE: Alfven crossing time t_A = L/v_A. This is the fundamental MHD timescale.
   If your simulation runtime < t_A: you have not evolved long enough for MHD dynamics.
```

**Magnetosonic waves:**

```
Fast: v_f^2 = (1/2)(c_s^2 + v_A^2 + sqrt((c_s^2 + v_A^2)^2 - 4*c_s^2*v_A^2*cos^2(theta)))
Slow: v_s^2 = (1/2)(c_s^2 + v_A^2 - sqrt(...))
Sound: c_s = sqrt(gamma * p / rho)

Verification:
1. COMPUTE: v_f and v_s for your equilibrium parameters at theta = 0 and theta = pi/2.
   At theta = 0: v_f = max(c_s, v_A), v_s = min(c_s, v_A).
   At theta = pi/2: v_f = sqrt(c_s^2 + v_A^2), v_s = 0.
2. CFL constraint uses the FAST speed: dt < dx / v_f.
   Using only c_s or only v_A underestimates the required timestep for low or high beta.
3. For low beta (beta << 1): v_f ~ v_A, v_s ~ c_s * cos(theta). Fast wave is magnetically dominated.
   For high beta (beta >> 1): v_f ~ c_s, v_s ~ v_A * cos(theta). Fast wave is sound-like.
```

</waves_and_dispersion>

<stability>

## Stability Analysis

**Rayleigh-Taylor instability (MHD):**

```
Growth rate (uniform gravity g, interface between rho_1 < rho_2 with B along interface):
gamma^2 = k * g * (rho_2 - rho_1)/(rho_2 + rho_1) - (k_parallel * v_A)^2 * 2*rho_1*rho_2/(rho_2 + rho_1)^2

where k_parallel = k * cos(alpha) is the component of k along B.

Verification:
1. COMPUTE: Atwood number A = (rho_2 - rho_1)/(rho_2 + rho_1). Must be 0 < A < 1 for instability.
2. Magnetic field stabilizes modes with k_parallel != 0. Critical wavenumber:
   k_crit = g * (rho_2 - rho_1) * (rho_2 + rho_1) / (2 * rho_1 * rho_2 * v_A^2 * cos^2(alpha))
   Modes with k > k_crit are stable. Only modes with k_parallel ~ 0 (perpendicular to B) are unstable.
3. If growth rate from simulation exceeds gamma_hydro = sqrt(k*g*A): error (magnetic field cannot enhance RT).
```

**Kelvin-Helmholtz instability:**

```
Growth rate (velocity shear V_0 across interface, uniform B along flow):
gamma = k * V_0/2 * sqrt(1 - (2*k_parallel*v_A/k/V_0)^2)    (equal density)

Verification:
1. COMPUTE: Maximum growth rate gamma_max = k*V_0/2 (hydro limit, zero magnetic field).
   Magnetic field parallel to flow STABILIZES KH for v_A > V_0/2 (equal density).
2. COMPUTE: Critical Alfvenic Mach number M_A = V_0/v_A. For M_A < 2 (equal density):
   KH is completely stabilized for modes along B. Only oblique modes may survive.
3. In compressible flow: KH is stabilized for supersonic shear (M_s = V_0/c_s > 2 for equal density).
   Check: if your simulation shows KH at M_s > 2, verify the growth rate carefully.
```

**Tearing mode instability:**

```
For Harris current sheet B_x = B_0 * tanh(y/a), the tearing mode growth rate:
gamma ~ (k*a)^{2/5} * S^{-3/5} * (v_A/a)    for Delta' * a >> 1
gamma ~ Delta'^{4/5} * (k*a)^{2/5} * S^{-3/5} * (v_A/a)    general

where S = v_A * a / eta is the Lundquist number,
Delta' = [psi'(0+) - psi'(0-)] / psi(0) from the outer solution.
For Harris sheet: Delta' = 2*(1/(k*a) - k*a), so unstable for k*a < 1.

Verification:
1. COMPUTE: S from your parameters. For S < 10^4: FKR scaling gamma ~ S^{-3/5}.
   For S > 10^4: plasmoid instability may onset, giving faster rates gamma ~ S^{-1/2} or faster.
2. COMPUTE: Resistive layer width delta ~ a * S^{-2/5}. This must be RESOLVED by the grid.
   If dx > delta: the tearing mode is resolved by numerical resistivity, not physical eta.
3. COMPUTE: Delta' from the outer solution. If Delta' < 0: the mode is stable.
   For Harris sheet: Delta' changes sign at k*a = 1. Modes with k*a > 1 are stable.
4. Reference: Furth, Killeen, Rosenbluth (1963) for the FKR scaling law.
```

**MHD energy principle:**

```
delta_W = integral( |Q_perp|^2/(mu_0) + B^2/(mu_0) * |div(xi_perp) + 2*xi_perp . kappa|^2
          + gamma*p*|div(xi)|^2 - 2*(xi_perp . grad(p))*(kappa . xi_perp*)
          - J_parallel * (xi_perp* x B) . Q_perp/B^2 ) dV

where Q = curl(xi x B) is the perturbed magnetic field, kappa = (b . grad)b is field curvature.

Verification:
1. delta_W > 0 for ALL trial functions xi: system is STABLE.
   delta_W < 0 for ANY trial function: system is UNSTABLE.
2. COMPUTE: Individual terms. Identify the destabilizing terms:
   - Pressure-curvature: -2*(xi . grad p)*(kappa . xi) — drives interchange/ballooning
   - Current-driven: -J_parallel term — drives kink modes
   Stabilizing terms: field line bending (|Q_perp|^2), compression (gamma*p*|div xi|^2)
3. If delta_W and growth rate calculation disagree (one says stable, other says unstable): error.
```

</stability>

<reconnection>

## Magnetic Reconnection

**Sweet-Parker reconnection:**

```
Reconnection rate: M_A_in = v_in / v_A = S^{-1/2}
Sheet dimensions: delta/L = S^{-1/2} (width/length)
Outflow speed: v_out ~ v_A

where S = L * v_A / eta is the Lundquist number.

Verification:
1. COMPUTE: S for your simulation. Sweet-Parker gives v_in/v_A ~ S^{-1/2}.
   For S = 10^6: v_in/v_A ~ 10^{-3}. This is VERY slow — if you measure faster reconnection,
   it may be numerical (grid-scale) reconnection or plasmoid-mediated.
2. COMPUTE: Current sheet width delta ~ L * S^{-1/2}. Must be resolved by the grid.
   If dx > delta: reconnection rate is set by numerical resistivity.
3. COMPUTE: Reconnection electric field E_z = eta * J_z at X-point.
   Normalized rate: E_z / (v_A * B_0). Compare with Sweet-Parker prediction.
```

**Petschek reconnection:**

```
Reconnection rate: M_A_in ~ pi / (8 * ln(S))
Much faster than Sweet-Parker for large S.

Verification:
1. Petschek requires localized resistivity at the X-point. With uniform resistivity,
   MHD simulations typically collapse to Sweet-Parker, NOT Petschek.
2. If you measure reconnection rates faster than S^{-1/2} with uniform eta:
   check for plasmoid instability (S > ~10^4) or numerical reconnection.
3. COMPUTE: Energy conversion efficiency. Magnetic energy should convert to
   kinetic energy (outflow jets) + thermal energy (Ohmic heating).
   Total energy must be conserved: delta(E_mag) = delta(E_kin) + delta(E_th).
```

</reconnection>

<turbulence>

## Turbulence Spectra and Scaling

**Kolmogorov (hydrodynamic, 3D):**

```
E(k) = C_K * epsilon^{2/3} * k^{-5/3}    (inertial range)
C_K ~ 1.5 (Kolmogorov constant)
Kolmogorov length: eta = (nu^3/epsilon)^{1/4}
Dissipation range: k > 1/eta

Verification:
1. COMPUTE: E(k) from velocity field. Fit slope in inertial range (k_forcing < k < k_dissipation).
   Slope should be -5/3 +/- 0.1 for developed 3D turbulence.
   Steeper than -5/3: turbulence is not fully developed or numerical dissipation is too strong.
   Shallower than -5/3: possible bottleneck effect near dissipation scale.
2. COMPUTE: epsilon = nu * <|grad u|^2>. Compare with energy injection rate.
   In statistically stationary turbulence: injection rate = dissipation rate.
3. In 2D: INVERSE energy cascade (E(k) ~ k^{-5/3} at k < k_forcing)
   and FORWARD enstrophy cascade (E(k) ~ k^{-3} at k > k_forcing).
   Using the 3D cascade direction in 2D is WRONG.
```

**MHD turbulence:**

```
Iroshnikov-Kraichnan (isotropic): E(k) ~ (epsilon * v_A)^{1/2} * k^{-3/2}
Goldreich-Sridhar (anisotropic, strong): E(k_perp) ~ epsilon^{2/3} * k_perp^{-5/3}
with anisotropy: k_parallel ~ k_perp^{2/3}

Verification:
1. COMPUTE: E(k_perp) and E(k_parallel) separately. MHD turbulence is inherently ANISOTROPIC
   with respect to the local magnetic field direction.
2. For strong MHD turbulence (delta_B/B_0 ~ 1): expect -5/3 perpendicular spectrum (GS95).
   For weak MHD turbulence (delta_B/B_0 << 1): expect -3/2 isotropic spectrum (IK).
3. COMPUTE: Residual energy E_v - E_B. In MHD turbulence, magnetic energy slightly exceeds
   kinetic energy: E_B > E_v. If E_v >> E_B: check if the magnetic field is too weak to
   be dynamically important (then it is hydro turbulence, not MHD turbulence).
4. COMPUTE: Cross-helicity H_c = <v . B>. Measures imbalance between counter-propagating
   Alfven wave packets. High |H_c|/(E_v + E_B) ~ 1: turbulence is imbalanced (solar wind-like).
```

</turbulence>

<conservation>

## Conservation Laws

**Mass conservation:**

```
d/dt integral(rho dV) = -surface_integral(rho * v . dA)

Verification:
1. COMPUTE: Total mass at each output time. For periodic or closed boundaries:
   |M(t) - M(0)| / M(0) should be < 10^{-10} (machine precision for conservative schemes).
2. For open boundaries: mass change should equal the net flux through boundaries.
   COMPUTE: mass flux and compare with mass change. Must balance.
```

**Energy conservation:**

```
E_total = E_kinetic + E_thermal + E_magnetic + E_gravitational
E_kinetic = integral(rho * v^2 / 2 dV)
E_magnetic = integral(B^2 / (2*mu_0) dV)
E_thermal = integral(p / (gamma - 1) dV)

Ideal MHD (no dissipation, periodic boundaries): dE_total/dt = 0.
Resistive MHD: dE_total/dt = -integral(eta * J^2 dV) (Ohmic dissipation, always negative).

Verification:
1. COMPUTE: All energy components at each output time. Plot time evolution.
2. For ideal MHD: |E_total(t) - E_total(0)| / E_total(0) < 10^{-6} (spectral), < 10^{-3} (finite volume).
   If energy grows: numerical instability. If energy decays too fast: excessive numerical dissipation.
3. For resistive MHD: E_total should DECREASE monotonically (dissipation is positive-definite).
   If E_total increases: conservation error. Check div(B) and boundary conditions.
```

**Magnetic helicity:**

```
H_m = integral(A . B dV) where B = curl(A)

Ideal MHD: dH_m/dt = 0 (exactly conserved).
Resistive MHD: dH_m/dt = -2*eta * integral(J . B dV).
Taylor's conjecture: H_m decays much slower than energy (H_m decays as S^{-1} while energy decays as S^{0}).

Verification:
1. COMPUTE: H_m at each output time. For ideal MHD: H_m must be constant.
   For resistive MHD: H_m should decay much more slowly than magnetic energy.
2. If H_m GROWS in any simulation: there is a numerical error. Magnetic helicity is a
   topological invariant — it cannot be created without reconnection, and reconnection only destroys it.
3. COMPUTE: Relative helicity when boundaries are not periodic:
   H_rel = integral((A - A_ref) . (B - B_ref) dV) with reference field B_ref.
```

**Rankine-Hugoniot jump conditions (across shocks):**

```
[rho * v_n] = 0                                    (mass flux)
[rho * v_n^2 + p + B_t^2/(2*mu_0)] = 0            (normal momentum)
[rho * v_n * v_t - B_n * B_t / mu_0] = 0           (tangential momentum)
[B_n] = 0                                           (normal B continuous)
[v_n * B_t - B_n * v_t] = 0                         (tangential electric field)

where [X] = X_2 - X_1 denotes jump across the shock, n = normal, t = tangential.

Verification:
1. COMPUTE: All five jump conditions at each identified shock front. Each should be
   satisfied to within the numerical scheme's truncation error.
2. COMPUTE: Compression ratio rho_2/rho_1. For a strong gas-dynamic shock (gamma = 5/3):
   rho_2/rho_1 -> (gamma+1)/(gamma-1) = 4 as Mach -> infinity.
   If compression > 4 without additional physics (radiation, CR): error.
3. COMPUTE: Entropy jump. Entropy MUST increase across a shock (s_2 > s_1).
   If entropy decreases: the shock is an expansion shock (unphysical) — check scheme.
```

</conservation>

<numerical_diagnostics>

## Numerical Diagnostics

**CFL condition:**

```
dt < C * dx / max(|v| + c_f)
where c_f is the fast magnetosonic speed:
c_f = sqrt(c_s^2 + v_A^2)    (upper bound, actual depends on propagation angle)

Verification:
1. COMPUTE: CFL number at each cell at each timestep. Report max CFL.
   If max CFL > 1 at any point: the simulation is potentially unstable.
2. For MHD in low-beta plasma: v_A >> c_s, so c_f ~ v_A.
   Using only c_s in CFL underestimates the constraint by v_A/c_s ~ 1/sqrt(beta) >> 1.
3. For adaptive timestep: verify dt history. Sudden drops in dt indicate local v_A spikes
   (e.g., density cavities where v_A ~ B/sqrt(rho) diverges).
```

**Divergence constraint (div B):**

```
Verification:
1. COMPUTE: max(|div(B)| * dx / |B|) at each output time. This is the normalized monopole error.
   - Constrained transport: < 10^{-14} (machine precision)
   - Divergence cleaning (Dedner): < 10^{-4} acceptable, < 10^{-6} good
   - Projection: < 10^{-8} after cleaning, but can drift between cleanings
2. If div(B) error grows monotonically: the scheme is accumulating monopole errors.
   This creates unphysical parallel forces F_monopole ~ B * div(B) / mu_0.
3. COMPUTE: integral(|div B| dV) / integral(|curl B| dV). This global ratio should be < 10^{-4}.
   If comparable to 1: magnetic field topology is unreliable.
```

**Negative pressure / density:**

```
Verification:
1. MONITOR: min(p) and min(rho) at each timestep. Both must remain positive.
2. If p < 0 appears: this typically occurs in strong rarefaction waves or where magnetic
   pressure subtraction in conservative schemes loses precision.
   Fix: positivity-preserving limiters, dual-energy formulation, or reduced timestep.
3. If rho < 0 appears: the scheme is non-conservative or has excessive dispersion errors.
   This is always a code bug or extreme CFL violation.
```

</numerical_diagnostics>

## Worked Examples

### Alfven wave propagation test

```python
import numpy as np

# Equilibrium: uniform B_0 along x, uniform rho_0
B_0 = 1.0        # Tesla
rho_0 = 1.0e3    # kg/m^3
mu_0 = 4 * np.pi * 1e-7  # H/m

v_A = B_0 / np.sqrt(mu_0 * rho_0)
print(f"Alfven speed: v_A = {v_A:.2f} m/s")
# v_A ~ 28.2 m/s

# Alfven wave: B_y = delta_B * sin(k*x - omega*t), v_y = -delta_B/(sqrt(mu_0*rho_0)) * sin(k*x - omega*t)
# omega = k * v_A (dispersion relation)

L = 1.0  # domain length (m)
k = 2 * np.pi / L
omega = k * v_A
period = 2 * np.pi / omega
print(f"Alfven crossing time: L/v_A = {L/v_A:.4f} s")
print(f"Wave period: {period:.4f} s")

# After one period, the wave should return to initial state.
# Measure: |B_y(t=T) - B_y(t=0)| / max(|B_y|) should be < 10^{-4} for a good code.
# This tests: dispersion error, numerical dissipation, div(B) control.
```

### Sweet-Parker reconnection rate check

```python
# Harris current sheet: B_x = B_0 * tanh(y/a)
B_0 = 0.01        # Tesla
rho_0 = 1.0e-12   # kg/m^3 (coronal plasma)
a = 1.0e6          # m (current sheet half-width, ~1000 km)
eta = 1.0           # m^2/s (Spitzer resistivity for T ~ 10^6 K)

v_A = B_0 / np.sqrt(mu_0 * rho_0)
S = v_A * a / eta
print(f"Alfven speed: v_A = {v_A:.2e} m/s")
print(f"Lundquist number: S = {S:.2e}")
# v_A ~ 2.8e5 m/s, S ~ 2.8e11

# Sweet-Parker prediction:
v_in_SP = v_A / np.sqrt(S)
delta_SP = a / np.sqrt(S)
print(f"Sweet-Parker inflow: v_in = {v_in_SP:.2e} m/s")
print(f"Sweet-Parker sheet width: delta = {delta_SP:.2e} m")
# v_in ~ 0.5 m/s (very slow!), delta ~ 1.9 m (very thin!)

# To resolve delta in a simulation: need dx < delta.
# For S = 10^6 (feasible simulation): delta/a = S^{-1/2} = 10^{-3}, so need 1000+ cells across a.
# For S = 10^{11} (solar corona): delta/a ~ 3e-6, need ~300,000 cells. Not feasible -> plasmoid regime.

# Plasmoid onset: S > S_crit ~ 10^4.
# At S > S_crit: sheet fragments into plasmoid chain, reconnection rate ~ 0.01 v_A (fast, independent of S).
if S > 1e4:
    print(f"S > 10^4: plasmoid instability expected. Rate ~ 0.01 * v_A = {0.01*v_A:.2e} m/s")
```
