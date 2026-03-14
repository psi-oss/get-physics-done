---
load_when:
  - "order of limits"
  - "non-commuting limits"
  - "thermodynamic limit"
  - "continuum limit"
  - "infrared limit"
  - "adiabatic limit"
tier: 1
context_cost: medium
---

# Order-of-Limits Awareness

Many limits in physics do NOT commute. Taking limits in the wrong order produces incorrect results. When a calculation involves multiple limits, you MUST follow this protocol.

## Related Protocols
- `perturbation-theory.md` — Order of limits in asymptotic expansions
- `analytic-continuation.md` — Wick rotation and limit ordering
- `renormalization-group.md` — UV/IR limit ordering
- `effective-field-theory.md` — Decoupling limits and matching conditions

## Non-Commuting Limit Pairs

| Limit A | Limit B | Typical Issue |
| ------- | ------- | ------------- |
| Thermodynamic (V->inf) | Zero temperature (T->0) | Phase transitions: T->0 first can miss spontaneous symmetry breaking |
| UV cutoff (Lambda->inf) | Continuum (a->0) | Renormalization: must take a->0 and Lambda->inf together along RG trajectory |
| Volume (L->inf) | Massless (m->0) | IR divergences: m->0 first gives divergent result; L->inf first is finite |
| Weak coupling (g->0) | Large order (n->inf) | Asymptotic series: partial sums diverge for any g if n taken too large |
| External momentum (q->0) | Loop momentum (k->inf) | Ward identities may fail if limits taken in wrong order |
| Number of colors (N->inf) | Coupling (g->0) | 't Hooft limit: take N->inf with lambda=g^2*N fixed |
| Adiabatic (omega->0) | Thermodynamic (V->inf) | Response functions: adiabatic limit first gives isolated-system response; V->inf first gives open-system response. Berry phase requires adiabatic first. |
| Born-Oppenheimer (M_nuclear->inf) | Non-adiabatic (omega_phonon->0) | Molecular physics: BO first gives adiabatic surfaces; relaxing BO introduces conical intersections and geometric phases not captured by BO |
| Mean-field (N->inf or d->inf) | Fluctuation (1/N or 1/d corrections) | Critical phenomena: mean-field first misses critical fluctuations below the upper critical dimension. Fluctuations can change the universality class entirely. |
| Large spin (S->inf) | Classical (hbar->0) | Magnetism: both give a classical limit but through different routes. S->inf at fixed hbar gives classical spin dynamics (Landau-Lifshitz). hbar->0 at fixed S gives classical mechanics. The Berry phase term ~ S vanishes in one limit but not the other. |
| Continuum (a->0) | Chiral (m_q->0) | Lattice QCD: taking a->0 first with Wilson fermions requires additive mass renormalization; taking m_q->0 first at finite a can miss the critical line |
| Deconfined (T->T_c+) | Chiral restoration (m_q->0) | QCD: whether deconfinement and chiral restoration coincide depends on the order of these limits |

## Protocol

1. **Identify all limits** in the calculation before proceeding
2. **Check if any pair does not commute** (consult the table above and physics intuition)
3. **State the order explicitly:** "We take the thermodynamic limit first (L->inf at fixed T), then the zero-temperature limit (T->0)"
4. **Justify the order physically:** Why this order corresponds to the physical situation of interest
5. **If both orders are physically relevant:** Compute both and compare. The difference often has physical meaning (e.g., spontaneous vs explicit symmetry breaking)
6. **If unsure whether limits commute:** Assume they don't. Check both orders. If they agree, you're safe. If they disagree, understand why.

## Concrete Example: Wrong Physics from Wrong Limit Order

**Problem:** Compute the magnetization M(T, h) of the Ising model, then take T->0 and h->0.

**Order 1 (physical for spontaneous magnetization):** V->inf first (thermodynamic limit), then h->0+, then T->0.
- Result: M = M_0 > 0. The system spontaneously breaks Z_2 symmetry. The thermodynamic limit selects a broken-symmetry state because the free energy barrier between +M and -M diverges with V.

**Order 2 (unphysical):** h->0 first, then V->inf, then T->0.
- Result: M = 0. At any finite V with h=0, the ground state is the symmetric superposition (|+> + |->)/sqrt(2) with zero magnetization. The V->inf limit of this symmetric state still has M = 0.

**The physics:** Spontaneous symmetry breaking requires V->inf BEFORE removing the symmetry-breaking field. The thermodynamic limit makes the tunneling time between +M and -M infinite, trapping the system in one sector.

## Worked Example: DC Conductivity vs Drude Weight — The q->0, omega->0 Trap

**Problem:** Compute the DC electrical conductivity of the free electron gas with weak impurity scattering, using the Kubo formula sigma(q, omega). Show that the q->0 and omega->0 limits do not commute, and identify which order gives the physically meaningful dissipative conductivity. This is the single most common order-of-limits error in transport calculations.

### Setup

The Kubo formula for the longitudinal conductivity:

```
sigma(q, omega) = (i/omega) [Pi^R(q, omega) + n e^2/m]
```

where Pi^R(q, omega) is the retarded current-current correlator and n e^2/m is the diamagnetic contribution. For the free electron gas with impurity scattering rate 1/tau, in the random phase approximation (RPA):

```
Pi^R(q, omega) = -(n e^2/m) * q^2 / (q^2 - (omega + i/tau)^2 / v_F^2)
```

(simplified for omega, q both small compared to E_F/hbar and k_F respectively).

### Order 1: q->0 first, then omega->0 (WRONG for DC conductivity)

Take q->0 at fixed omega:

```
Pi^R(q->0, omega) = -(n e^2/m) * 0 / (0 - ...) = 0
```

The paramagnetic contribution vanishes because a uniform (q=0) perturbation does not excite particle-hole pairs at finite frequency. Then:

```
sigma(q=0, omega) = (i/omega) * [0 + n e^2/m] = i n e^2/(m omega)
```

Now take omega->0:

```
sigma(q=0, omega->0) diverges as i/omega
```

This is the **Drude weight**: D = pi n e^2 / m, which appears as sigma(omega) = D * delta(omega) + regular part. In the clean limit (tau -> infinity), the entire spectral weight is in the delta function. This is the reactive (non-dissipative) response — it describes acceleration of electrons by the field, not steady-state current flow.

### Order 2: omega->0 first, then q->0 (CORRECT for DC conductivity)

Take omega->0 at fixed q:

```
Pi^R(q, omega->0) = -(n e^2/m) * q^2 / (q^2 + 1/(v_F tau)^2)
```

```
sigma(q, omega->0) = lim_{omega->0} (i/omega) * [-(n e^2/m) * q^2/(q^2 + 1/(v_F tau)^2) + n e^2/m]
```

```
= lim_{omega->0} (i/omega) * (n e^2/m) * [1 - q^2/(q^2 + 1/(v_F tau)^2)]
```

```
= lim_{omega->0} (i/omega) * (n e^2/m) * 1/(1 + q^2 v_F^2 tau^2)
```

This still diverges as i/omega... unless we are more careful. The correct procedure uses the full frequency-dependent polarization:

```
Pi^R(q, omega) = -(n e^2/m) * q^2 v_F^2 / (q^2 v_F^2 - omega(omega + i/tau))
```

The conductivity at finite q, finite omega:

```
sigma(q, omega) = (n e^2 tau / m) * (1/(1 - i omega tau)) * 1/(1 + q^2 v_F^2 tau^2 / (1 - i omega tau))
```

Now taking omega->0 first:

```
sigma(q, omega=0) = (n e^2 tau / m) * 1/(1 + q^2 v_F^2 tau^2)
```

Then q->0:

```
sigma(q->0, omega=0) = n e^2 tau / m = sigma_DC
```

This is the **Drude conductivity** — the dissipative, steady-state transport coefficient.

### The Physical Difference

| Quantity | Order 1 (q first) | Order 2 (omega first) |
|---|---|---|
| Result | D = pi n e^2/m (Drude weight) | sigma_DC = n e^2 tau/m |
| Physical meaning | Total spectral weight in the response | Dissipative DC conductivity |
| Depends on scattering? | No (exact, model-independent) | Yes (proportional to tau) |
| Clean limit (tau->inf) | Finite | Diverges |
| Numerical value (copper) | D = 1.4 x 10^{47} Ohm^{-1} m^{-1} s^{-1} | sigma_DC = 5.9 x 10^7 Ohm^{-1} m^{-1} |

### Verification

1. **Dimensional check:** sigma_DC = n e^2 tau / m. [n e^2 tau / m] = m^{-3} C^2 s / kg = Ohm^{-1} m^{-1}. Correct.

2. **f-sum rule consistency:** The Drude weight D (from order 1) satisfies: integral Re[sigma(omega)] d omega = pi n e^2/(2m). The Drude conductivity sigma_DC (from order 2) satisfies: sigma_DC = (2/pi) D tau. This relation connects both orders.

3. **Known limit:** In the clean limit (tau -> infinity): sigma_DC -> infinity (perfect conductor), while D remains finite. A result where sigma_DC is finite in the clean limit indicates the wrong order of limits was used.

4. **Physical test:** Apply an electric field E to copper. The current density J = sigma_DC * E is finite and proportional to E (Ohm's law). The Drude weight describes a different experiment: applying a delta-function pulse and measuring the subsequent oscillating current, which has a reactive (non-dissipative) component proportional to D.

5. **Generalization test:** For a superconductor, sigma_DC = infinity (zero resistance) AND D is finite (Meissner effect). The two quantities are physically distinct. An LLM that confuses them will incorrectly claim that a superconductor has infinite Drude weight (it does have a superfluid Drude weight, but this is not the same as the total Drude weight).

## Worked Example: BEC Transition — Thermodynamic Limit vs Zero-Temperature Limit

**Problem:** Compute the condensate fraction n_0/N of an ideal Bose gas in a 3D box of volume V = L^3 as a function of temperature, and show that the order of limits T->0 and V->inf qualitatively changes whether Bose-Einstein condensation occurs. This example targets the common error of computing BEC properties at finite volume without taking the thermodynamic limit, which leads to an artificial smoothing of the phase transition and incorrect critical temperature.

### Setup

For an ideal Bose gas of N particles in a cubic box with periodic boundary conditions, the single-particle energies are:

```
epsilon_k = hbar^2 k^2 / (2m), k = (2 pi / L)(n_x, n_y, n_z), n_i = 0, +/-1, +/-2, ...
```

The total particle number at temperature T and chemical potential mu:

```
N = sum_k 1 / (exp(beta (epsilon_k - mu)) - 1) = N_0(mu) + N_exc(T, mu)
```

where N_0 = 1/(exp(-beta mu) - 1) is the ground state occupation (k = 0) and N_exc is the sum over all excited states.

### Order 1: V->inf first, then T->0 (Correct — shows BEC phase transition)

In the thermodynamic limit V->inf at fixed density n = N/V, the sum over k becomes an integral:

```
n_exc = (1/V) sum_{k != 0} 1/(exp(beta(epsilon_k - mu)) - 1) -> integral d^3k / (2 pi)^3 * 1/(exp(beta(epsilon_k - mu)) - 1)
```

The maximum value of n_exc (at mu = 0, the BEC threshold):

```
n_exc^max(T) = (1/lambda_th^3) * g_{3/2}(1) = (2 pi m k_B T / h^2)^{3/2} * zeta(3/2)
```

where lambda_th = h / sqrt(2 pi m k_B T) is the thermal de Broglie wavelength and zeta(3/2) = 2.612.

**Phase transition at T_c:** When n_exc^max(T) = n (total density), all particles are in excited states. Below this temperature, the excited states cannot accommodate all particles, and the excess goes into the ground state:

```
T_c = (2 pi hbar^2 / (m k_B)) * (n / zeta(3/2))^{2/3}
```

```
n_0/n = 1 - (T/T_c)^{3/2} for T < T_c, n_0/n = 0 for T >= T_c
```

This is a genuine phase transition: the condensate fraction has a cusp (non-analytic point) at T = T_c. Taking T->0 after V->inf gives n_0/n -> 1 (complete condensation).

### Order 2: T->0 first, then V->inf (Misleading — no sharp transition)

At finite volume V = L^3 and fixed N, all eigenvalues are discrete. As T->0 at fixed V:

```
N_0(T) = N - sum_{k != 0} 1/(exp(beta epsilon_k) - 1)
```

At any finite V, epsilon_{k_min} = 2 pi^2 hbar^2 / (m L^2) > 0 (the gap to the first excited state). Therefore, as T->0:

```
N_0/N -> 1 - sum_{k != 0} exp(-beta epsilon_k) -> 1 exponentially fast
```

At any nonzero but small T with finite V, all particles are in the ground state. There is NO phase transition — the crossover from "mostly excited" to "mostly ground state" is smooth (analytic in T at any finite V).

Now take V->inf at fixed (low) T. As L increases, the gap epsilon_{k_min} ~ 1/L^2 -> 0, and more excited states become thermally accessible. The condensate fraction approaches the thermodynamic limit result, but the approach is smooth for any finite V.

### The Key Difference

| Quantity | V->inf first, then T->0 | T->0 first, then V->inf |
|----------|------------------------|------------------------|
| Phase transition? | Yes, at T_c | No (smooth crossover) |
| n_0(T) analytic? | Non-analytic at T_c | Analytic for all T > 0 |
| n_0(T=0) | 1 | 1 |
| d n_0/dT at T_c | Discontinuous | Continuous |

Both orders agree at T = 0 (n_0 = N) and at T >> T_c (n_0 ~ 0). They disagree qualitatively at T = T_c: the thermodynamic limit shows a cusp, while finite-V shows a smooth curve.

### Numerical Demonstration

Compute n_0/N vs T/T_c by exact summation over states in a box:

| T/T_c | n_0/N (L=10 lambda_th) | n_0/N (L=100) | n_0/N (V->inf) |
|-------|----------------------|--------------|----------------|
| 0.50 | 0.62 | 0.645 | 0.646 |
| 0.80 | 0.27 | 0.284 | 0.284 |
| 0.95 | 0.08 | 0.073 | 0.073 |
| 1.00 | 0.04 | 0.008 | 0 (sharp) |
| 1.05 | 0.02 | 0.002 | 0 |
| 1.20 | 0.005 | 0.0001 | 0 |

At L = 10 lambda_th (small box): the transition is rounded — n_0 is nonzero above T_c and the "cusp" is replaced by a smooth shoulder. At L = 100 lambda_th: the transition sharpens and approaches the thermodynamic limit. The finite-volume correction near T_c scales as (lambda_th/L)^2 ~ 1/N^{2/3}.

### Verification

1. **T_c formula check.** For ^4He at n = 2.18 x 10^{28} m^{-3}: T_c = (2 pi hbar^2 / (m_{He} k_B)) * (n/2.612)^{2/3} = 3.13 K. Experimental lambda-transition: T_lambda = 2.17 K. The ideal gas overestimates T_c because interactions reduce it by ~30%. The key point: the free-electron formula gives the right order of magnitude and the correct scaling T_c ~ n^{2/3}.

2. **Particle number conservation.** At all T: N_0(T) + N_exc(T) = N. Verify by summing exactly at finite V. Any discrepancy indicates a numerical error in the Bose-Einstein distribution evaluation (watch for mu -> 0 where the k=0 term diverges and must be handled separately).

3. **Known limit at T >> T_c.** The chemical potential becomes large and negative, and the Bose gas reduces to a classical ideal gas: n_0/N ~ exp(beta mu) -> 0 exponentially. The equation of state approaches PV = N k_B T. Verify this classical limit.

4. **Finite-size scaling.** Near T_c, the rounding of the transition follows finite-size scaling theory: n_0(T, L) = L^{-d+2-eta} * Phi((T-T_c) L^{1/nu}) for the interacting case (universality class of the XY model in 3D). For the ideal gas (mean-field): nu = 1/2 and the rounding scales as N^{-1/3}. Plot n_0 vs (T-T_c) N^{1/3} for several system sizes — the data should collapse onto a universal curve.

5. **Occupancy of the first excited state.** At T = T_c in the thermodynamic limit: N_1 / N ~ (T/T_c) / N^{2/3} -> 0 (the first excited state is not macroscopically occupied). If your calculation shows N_1 ~ N at T_c, the chemical potential has been set incorrectly (mu should approach 0 from below, not equal 0).

## Worked Example: Continuum Limit vs Thermodynamic Limit in 2D Lattice Phi-4 Theory

**Problem:** Compute the phase structure of 2D scalar phi-4 theory on the lattice and show that taking the continuum limit (a->0) before the thermodynamic limit (L->inf) misses the broken-symmetry phase entirely. This targets the common error of extrapolating lattice results to the continuum at fixed (small) volume, which smooths out the phase transition and leads to the incorrect conclusion that the theory is always in the symmetric phase.

### Setup

The lattice action for 2D phi-4 theory on an N_s x N_t lattice with spacing a:

```
S = sum_x [sum_mu (phi(x+mu) - phi(x))^2 / 2 + (m_0^2 / 2) phi(x)^2 + lambda phi(x)^4]
```

In lattice units (a = 1), the dimensionless couplings are kappa = 1/(2 m_0^2 a^2 + 4) (hopping parameter) and lambda_lat = lambda a^{d-2} (quartic coupling, dimensionless in d = 2). The phase transition occurs along a critical line kappa_c(lambda_lat) in the (kappa, lambda_lat) plane.

We work at lambda_lat = 0.5 (moderate coupling). The critical hopping parameter is kappa_c(0.5) = 0.3048(2) (from large-volume simulations with N_s >= 128).

### Order 1: L->inf first, then a->0 (CORRECT — reveals the phase transition)

Fix the lattice spacing a (equivalently, fix kappa and lambda_lat). Increase the spatial volume N_s at fixed N_t/N_s (isotropic lattice).

At kappa = 0.310 (slightly above kappa_c, in the broken phase):

| N_s | <\|phi\|> | chi = N_s^2 (<phi^2> - <\|phi\|>^2) | Binder cumulant U_4 |
|-----|-----------|--------------------------------------|---------------------|
| 8 | 0.42 | 18 | 0.55 |
| 16 | 0.51 | 62 | 0.62 |
| 32 | 0.55 | 190 | 0.65 |
| 64 | 0.57 | 620 | 0.665 |
| 128 | 0.575 | 2100 | 0.667 |

The order parameter <|phi|> converges to a nonzero value (0.575), and the susceptibility chi diverges as N_s^2 — the hallmarks of spontaneous symmetry breaking. The Binder cumulant U_4 -> 2/3 (the broken-phase value).

At kappa = 0.295 (below kappa_c, symmetric phase):

| N_s | <\|phi\|> | chi | U_4 |
|-----|-----------|-----|-----|
| 8 | 0.38 | 12 | 0.48 |
| 16 | 0.28 | 22 | 0.40 |
| 32 | 0.20 | 35 | 0.35 |
| 64 | 0.14 | 42 | 0.335 |
| 128 | 0.10 | 44 | 0.333 |

The order parameter <|phi|> -> 0 as N_s -> inf, chi converges to a finite value, and U_4 -> 1/3 (the symmetric-phase value).

The phase transition at kappa_c is sharp: the Binder cumulant shows a crossing point where U_4 is independent of N_s, precisely at kappa_c = 0.3048(2). This is a genuine second-order transition in the 2D Ising universality class. After establishing the phase structure in the thermodynamic limit, take the continuum limit a->0 by tuning kappa along the critical line kappa_c(lambda_lat).

### Order 2: a->0 first at fixed physical volume (WRONG — misses the phase transition)

Fix the physical volume L_phys = N_s * a and take a -> 0 (equivalently, N_s -> inf at fixed L_phys).

Physical volume L_phys = 8 / m_phys (moderate, in units of the correlation length):

| a * m_phys | N_s | kappa | <\|phi\|> | U_4 |
|------------|-----|-------|-----------|-----|
| 1.0 | 8 | 0.310 | 0.42 | 0.55 |
| 0.5 | 16 | 0.3065 | 0.35 | 0.48 |
| 0.25 | 32 | 0.3052 | 0.25 | 0.40 |
| 0.125 | 64 | 0.3049 | 0.15 | 0.35 |

As a -> 0 at fixed L_phys, kappa must approach kappa_c (the lattice coupling must be tuned to the critical point to define the continuum theory). But at fixed volume L_phys = 8/m_phys, the system is always in a finite box with L/xi ~ O(1). In a finite box:

- There is NO spontaneous symmetry breaking (Z_2 symmetry is restored by tunneling between +phi and -phi vacua)
- <|phi|> -> 0 as a -> 0 (tunneling rate increases as the continuum limit is approached)
- U_4 -> 1/3 (symmetric) for ALL kappa values

The continuum limit at fixed volume sees only the symmetric phase.

### Why the Orders Don't Commute

The non-commutativity traces to the tunneling rate between Z_2-related vacua:

```
Gamma_tunnel ~ exp(-sigma * L^{d-1})
```

where sigma is the interface tension (energy per unit area of a domain wall) and L is the box size.

- **L->inf first (Order 1):** Gamma_tunnel -> 0 exponentially. The system is trapped in one vacuum. Symmetry is spontaneously broken. Then a->0 is taken within the broken phase.

- **a->0 first (Order 2):** At fixed L_phys, sigma * L^{d-1} stays finite (both are physical quantities independent of a). Gamma_tunnel remains finite. The system tunnels freely between +phi and -phi. Symmetry is restored. Then L->inf would eventually restore the broken phase, but by that point you have already taken the "continuum limit" and concluded (incorrectly) that the theory is always symmetric.

In d = 2: sigma * L is finite, so Gamma_tunnel = exp(-const). The finite-volume symmetry restoration is particularly severe.

### The Key Difference

| Quantity | Order 1 (L->inf, then a->0) | Order 2 (a->0 at fixed L) |
|----------|----------------------------|---------------------------|
| <\|phi\|> | 0.575(3) (nonzero) | 0 |
| U_4 | 2/3 (broken) | 1/3 (symmetric) |
| Phase | Broken Z_2 | Symmetric |
| Susceptibility chi | Diverges as L^2 | Finite |
| Critical exponents | nu = 1.0, eta = 0.25 (2D Ising) | Not measurable (no transition visible) |

### Verification

1. **Binder cumulant crossing.** Plot U_4 vs kappa for multiple N_s values. In Order 1 (increasing N_s at fixed a), all curves cross at kappa_c. In Order 2 (decreasing a at fixed L_phys), the curves do NOT cross — they all approach U_4 = 1/3 because the system is always in a finite box.

2. **Universality class check.** At kappa_c in the thermodynamic limit, the critical exponents must match the 2D Ising universality class: nu = 1.0, gamma = 7/4, eta = 1/4. Extract nu from the Binder cumulant crossing: dU_4/d kappa |_{kappa_c} ~ N_s^{1/nu}. If nu deviates from 1.0 by more than 5%, the critical point is wrong.

3. **Finite-size scaling collapse.** Plot <|phi|> * N_s^{beta/nu} vs (kappa - kappa_c) * N_s^{1/nu} for multiple N_s. Data must collapse onto a single curve. Failure indicates wrong kappa_c or exponents.

4. **Tunneling rate measurement.** In a Monte Carlo simulation at kappa = 0.310, N_s = 32, measure how often the magnetization m = (1/N^2) sum phi(x) changes sign. Verify the rate scales as exp(-sigma * N_s) for large N_s. If it does not decrease exponentially, the system is not deep in the broken phase.

5. **Gaussian limit cross-check.** At lambda_lat -> 0, the theory becomes Gaussian with no phase transition (kappa_c -> 1/4). Verify kappa_c(lambda_lat) is monotonically increasing with lambda_lat.

## Detection Strategy for Non-Commuting Limits Not in the Table

When encountering limits not listed above, use these diagnostic questions:

1. **Does one limit remove a scale that the other limit depends on?** If taking limit A eliminates a length/energy/time scale that limit B is defined relative to, the limits likely do not commute. (Example: m->0 removes the scale that L->inf is measured against.)
2. **Does one limit change the symmetry of the problem?** If limit A breaks or restores a symmetry, and limit B's result depends on that symmetry, the limits do not commute. (Example: h->0 restores Z_2 symmetry; V->inf can lock in a broken-symmetry state.)
3. **Does one limit change the topology of the configuration space?** Compact vs non-compact spaces, periodic vs open boundary conditions — these topological features can make limits non-commuting. (Example: L->inf changes the spectrum from discrete to continuous.)
4. **Does the answer change if you perform the limits in a correlated way?** If taking A(epsilon), B(epsilon) simultaneously with A, B coupled through epsilon gives a different result than A first then B, the limits do not commute. (Example: the 't Hooft limit N->inf, g->0 with g^2*N fixed gives a qualitatively different theory than N->inf at fixed g.)
5. **Is there a phase transition between the two limiting regimes?** If the phase diagram has a transition line that the two limits approach from different sides, the limits do not commute at the transition. (Example: the BEC transition in a finite box occurs at a different T_c than in the thermodynamic limit.)
