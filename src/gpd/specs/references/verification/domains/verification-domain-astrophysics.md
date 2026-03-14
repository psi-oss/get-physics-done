---
load_when:
  - "astrophysics verification"
  - "stellar structure"
  - "accretion"
  - "Eddington luminosity"
  - "Jeans mass"
  - "nucleosynthesis"
  - "gravitational wave source"
  - "neutron star"
tier: 2
context_cost: large
---

# Verification Domain — Astrophysics

Stellar structure, accretion physics, gravitational wave sources, nuclear burning, and observational consistency checks for astrophysics.

**Load when:** Working on stellar evolution, compact objects, accretion disks, nucleosynthesis, gravitational wave source modeling, or galaxy dynamics.

**Related files:**
- `../core/verification-quick-reference.md` — compact checklist (default entry point)
- `../core/verification-core.md` — dimensional analysis, limiting cases, conservation laws
- `../core/verification-numerical.md` — convergence, statistical validation
- `references/verification/domains/verification-domain-gr-cosmology.md` — GR/cosmology (for relativistic astrophysics)
- `references/verification/domains/verification-domain-statmech.md` — statistical mechanics (for equation of state)

---

<stellar_structure>

## Stellar Structure and Equilibrium

**Hydrostatic equilibrium:**

```
Newtonian: dP/dr = -G*M(r)*rho(r)/r^2
TOV (relativistic): dP/dr = -G*(rho + P/c^2)*(M + 4*pi*r^3*P/c^2) / (r^2*(1 - 2*G*M/(r*c^2)))

Verification:
1. COMPUTE: Evaluate dP/dr at multiple radial shells. Must match -G*M*rho/r^2 (Newtonian)
   or TOV (compact objects). Deviation > 1% indicates model is not in equilibrium.
2. For neutron stars: Newtonian hydrostatic is WRONG by factors of 2-3.
   If TOV correction is neglected for rho > 10^14 g/cm^3: flag as error.
3. Surface boundary condition: P(R) = 0. If P(R) != 0: integration didn't reach the surface.
```

**Mass-luminosity relation:**

```
Main sequence: L ~ M^alpha where alpha ~ 3.5-4 (solar-type stars)
  L_sun = 3.83e26 W, M_sun = 1.99e30 kg

Verification:
1. COMPUTE: L(M) for your stellar model. Compare with known M-L relation.
2. For M >> M_sun: L -> L_Edd = 4*pi*G*M*c/kappa (Eddington limit). Verify L < L_Edd for stable stars.
3. For M << M_sun: fully convective. L/L_sun ~ (M/M_sun)^2.3 approximately.
```

**Chandrasekhar mass limit:**

```
M_Ch = 1.44 * (2/mu_e)^2 M_sun
where mu_e is the mean molecular weight per electron (mu_e = 2 for C/O white dwarfs).

Verification:
1. COMPUTE: Maximum mass from your WD EOS. Must agree with M_Ch within the model assumptions.
2. For electron degeneracy pressure: P = K_1 * rho^{5/3} (non-relativistic) or K_2 * rho^{4/3} (relativistic).
   The transition from 5/3 to 4/3 exponent is what produces the mass limit.
3. If your WD model exceeds M_Ch without including additional physics (rotation, magnetic fields): error.
```

</stellar_structure>

<accretion_physics>

## Accretion Physics

**Eddington luminosity:**

```
L_Edd = 4*pi*G*M*m_p*c / sigma_T = 1.26e38 * (M/M_sun) erg/s

Verification:
1. COMPUTE: L/L_Edd for your accreting system. Super-Eddington requires special treatment
   (radiation-driven outflows, photon trapping, slim disk models).
2. Eddington accretion rate: M_dot_Edd = L_Edd / (eta*c^2) where eta ~ 0.1 (radiative efficiency).
   M_dot > M_dot_Edd requires careful modeling of advection.
```

**Bondi accretion rate:**

```
M_dot_Bondi = 4*pi*lambda*(G*M)^2*rho_inf / c_s_inf^3
where lambda ~ 1/4 (for gamma = 5/3), rho_inf and c_s_inf are ambient density and sound speed.

Verification:
1. COMPUTE: Bondi radius r_B = G*M/c_s^2. Verify r_B is resolved in your simulation.
2. If grid resolution > r_B: the accretion rate is set by numerical resolution, not physics.
3. For rotating accretion: Bondi rate is an upper limit. Actual rate depends on angular momentum.
```

**Accretion disk efficiency:**

```
Thin disk (Shakura-Sunyaev): eta = 1 - E_ISCO/mc^2
  For Schwarzschild BH: r_ISCO = 6GM/c^2, eta = 1 - sqrt(8/9) ~ 0.057
  For maximally spinning Kerr (a = M): r_ISCO = GM/c^2, eta ~ 0.42

Verification:
1. COMPUTE: ISCO radius for your metric. Verify it matches known values.
2. COMPUTE: Radiative efficiency. Must be between 0 and 0.42 (Kerr bound).
   Efficiency > 0.42 violates the cosmic censorship expectation.
3. For thick disks: efficiency depends on accretion rate. At super-Eddington rates: eta << 0.1.
```

</accretion_physics>

<nuclear_burning>

## Nuclear Burning and Nucleosynthesis

**Nuclear reaction rates:**

```
Thermonuclear rate: <sigma*v> ~ S(E_0) / (E_0) * exp(-3*E_0/(k_B*T)) * sqrt(...) * Delta
where E_0 = (b*k_B*T/2)^{2/3} is the Gamow peak energy and Delta is the peak width.

Verification:
1. COMPUTE: Gamow peak energy for the dominant reaction (pp at solar core: E_0 ~ 6 keV).
   Verify E_0 is within the energy range of your rate tabulation.
2. COMPARE: Rate with JINA REACLIB, NACRE II, or Caughlan-Fowler tables at T = T_core.
   Disagreement > factor 2 indicates wrong rate compilation.
3. For CNO cycle: verify the rate is limited by the slowest reaction (14N(p,gamma)15O at solar conditions).
```

**Nuclear statistical equilibrium (NSE):**

```
At T > 5 * 10^9 K (~ 0.5 MeV): nuclear reactions are fast enough to maintain NSE.
The abundance of species (Z, A) is:
  Y(Z,A) ~ G(Z,A) * A^{3/2} * (rho/m_u)^{A-1} * (k_B*T/(2*pi*hbar^2/m_u))^{3(A-1)/2} * exp(B(Z,A)/(k_B*T))
where B is the binding energy.

Verification:
1. COMPUTE: NSE composition at T = 10^10 K. Should be dominated by iron-group (Ni-56, Fe-56).
2. At T > 10^10 K: NSE shifts to light elements (alpha particles, free nucleons).
3. COMPARE: NSE with tabulated nuclear partition functions (Rauscher & Thielemann).
```

</nuclear_burning>

<observational_checks>

## Observational Consistency

**Jeans mass and length:**

```
M_J = (5*k_B*T/(G*mu*m_H))^{3/2} * (3/(4*pi*rho))^{1/2}
lambda_J = c_s * sqrt(pi/(G*rho))

Verification:
1. COMPUTE: Jeans mass for your cloud conditions. For molecular clouds (T ~ 10 K, n ~ 10^3 cm^-3):
   M_J ~ 10 M_sun. If your fragmentation produces objects << M_J: resolution artifact.
2. Jeans length must be RESOLVED by simulation grid. If dx > lambda_J: artificial fragmentation.
```

**Virial theorem:**

```
2*K + U = 0 (time-averaged for bound system)
where K = kinetic energy (thermal + bulk motion), U = gravitational potential energy.

Virial parameter: alpha_vir = 2*K/|U|
  alpha_vir = 1: virialized
  alpha_vir < 1: collapsing (gravitationally bound)
  alpha_vir > 1: unbound (dispersing)

Verification:
1. COMPUTE: alpha_vir for your self-gravitating system. Verify consistency with observed dynamics.
2. For galaxy clusters: alpha_vir ~ 1 (virialized). If alpha_vir >> 1: system is unbound (check masses).
3. Including magnetic and cosmic ray pressure: 2*(K_th + K_turb + K_mag + K_CR) + U = 0.
```

**Gravitational wave source consistency:**

```
For compact binary inspiral:
1. Chirp mass determines frequency evolution: df/dt ~ M_c^{5/3} * f^{11/3}
2. Luminosity distance from amplitude: h ~ M_c^{5/3} * f^{2/3} / d_L
3. Mass ratio affects higher harmonics and merger waveform

Verification:
1. COMPUTE: Chirp mass from the inspiral waveform. Compare with component masses: M_c = (m1*m2)^{3/5}/(m1+m2)^{1/5}
2. COMPUTE: Energy radiated. Must equal integral of h^2(t) dt times geometric factors.
   Radiated energy typically ~ 5% of total mass for BBH mergers.
3. Final BH spin: a_f/M_f ~ 0.69 for equal-mass non-spinning merger (known NR result).
```

</observational_checks>

## Worked Examples

### Eddington limit violation reveals unphysical model

```python
import numpy as np

M_sun = 1.99e30  # kg
L_sun = 3.83e26  # W
sigma_T = 6.65e-29  # m^2 (Thomson cross section)
m_p = 1.67e-27  # kg
G = 6.674e-11   # m^3 kg^-1 s^-2
c = 3e8          # m/s

def L_eddington(M_solar):
    M = M_solar * M_sun
    return 4 * np.pi * G * M * m_p * c / sigma_T

# For a 10 M_sun star:
L_Edd = L_eddington(10)
print(f"L_Edd (10 M_sun) = {L_Edd:.2e} W = {L_Edd/L_sun:.0f} L_sun")
# ~ 3.2e31 W ~ 83,000 L_sun

# Main sequence 10 M_sun: L ~ 10^3.5 L_sun ~ 3200 L_sun  (well below Eddington)
# If your model gives L > 83,000 L_sun for 10 M_sun: either super-Eddington (needs outflow)
# or there is an error in the luminosity calculation
```

### Jeans resolution check for SPH simulation

```python
# Molecular cloud: T = 10 K, n_H = 10^4 cm^-3, mu = 2.33 (molecular hydrogen)
T, n_H, mu = 10, 1e4, 2.33
m_H = 1.67e-27  # kg
k_B = 1.38e-23  # J/K
rho = n_H * mu * m_H * 1e6  # kg/m^3 (convert cm^-3 to m^-3)

c_s = np.sqrt(k_B * T / (mu * m_H))  # sound speed
lambda_J = c_s * np.sqrt(np.pi / (G * rho))
M_J = (4/3) * np.pi * (lambda_J/2)**3 * rho / M_sun

print(f"Jeans length: {lambda_J:.2e} m = {lambda_J/3.086e16:.2f} pc")
print(f"Jeans mass: {M_J:.1f} M_sun")
# lambda_J ~ 0.1 pc, M_J ~ 1 M_sun for these conditions
# If SPH smoothing length > lambda_J / 4: Truelove criterion violated -> artificial fragmentation
```
