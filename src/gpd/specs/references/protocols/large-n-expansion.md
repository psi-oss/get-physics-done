---
load_when:
  - "large N"
  - "1/N expansion"
  - "planar diagram"
  - "'t Hooft limit"
  - "saddle point"
  - "mean field"
  - "matrix model"
  - "vector model"
tier: 2
context_cost: medium
---

# Large-N Expansion Protocol

The large-N expansion treats N (the number of field components, colors, or flavors) as a large parameter and expands physical quantities in powers of 1/N. At leading order in 1/N, path integrals are dominated by saddle points, making previously intractable problems exactly solvable. This protocol covers vector models (O(N)), gauge theories (SU(N) 't Hooft limit), and matrix models.

## Related Protocols

- See `perturbation-theory.md` for organizing the perturbative expansion within each 1/N order
- See `path-integrals.md` for saddle-point evaluation of the large-N effective action
- See `resummation.md` for resumming the 1/N series itself (which is also generically asymptotic)
- See `renormalization-group.md` for RG at large N (critical exponents in 1/N expansion)

## When to Use

1. **O(N) vector models:** N-component scalar or spin systems (sigma models, Heisenberg magnets). Leading order is mean-field-like; 1/N corrections give fluctuations.
2. **SU(N) gauge theories:** QCD-like theories in the 't Hooft limit (N -> inf, g^2 * N = lambda fixed). Planar diagrams dominate.
3. **Matrix models:** Random matrices, 2D quantum gravity, topological string theory. Genus expansion is a 1/N^2 expansion.
4. **Sachdev-Ye-Kitaev (SYK) model:** N Majorana fermions with random couplings. Large N gives exact two-point function.
5. **CP(N-1) models:** 2D sigma models with topological features analogous to 4D gauge theories.
6. **Critical phenomena:** Critical exponents in d dimensions via 1/N expansion complement the epsilon-expansion.

## Counting Rules: Which Diagrams Survive at Each Order

### O(N) Vector Models

**Setup:** phi = (phi_1, ..., phi_N), action S = integral (d_mu phi)^2 + m^2 phi^2 + (lambda/N) (phi^2)^2.

**Key:** The coupling is lambda/N, ensuring the action is O(N) at large N.

**Rules:**
- Each closed index loop contributes a factor N (trace over internal indices).
- Each vertex contributes lambda/N.
- A diagram with V vertices and L index loops contributes ~ (lambda)^V * N^{L-V}.
- Leading order: maximize L-V. For vacuum diagrams, the leading diagrams are "bubble chains" (cactus/daisy diagrams) with L-V = 1, giving O(N) contribution.
- Subleading: L-V = 0 gives O(1), etc.

**Result at leading order:** Introduce auxiliary field sigma = (lambda/N) * phi^2. The effective action for sigma is:

```
S_eff[sigma] = N * [ (1/2) Tr ln(-nabla^2 + m^2 + sigma) - integral sigma^2 / (4*lambda) ]
```

Since S_eff ~ N, the path integral over sigma is dominated by the saddle point at large N. The saddle-point equation is the **gap equation**.

### SU(N) Gauge Theories ('t Hooft Limit)

**Setup:** SU(N) gauge theory with g_YM^2 * N = lambda ('t Hooft coupling) held fixed as N -> inf.

**Rules:**
- Draw diagrams on a surface of genus h. Each diagram contributes ~ N^{2-2h} * f(lambda).
- **Planar diagrams** (genus 0, h=0): contribute N^2. These dominate at large N.
- **Torus diagrams** (genus 1, h=1): contribute N^0 = O(1). First subleading correction.
- Higher genus: contribute N^{2-2h}, increasingly suppressed.

**Quark loops:** Each quark loop boundary contributes N^{-1} (fundamental representation index loop gives N, but with a boundary = handle, reducing the Euler character). Quenched approximation (no quark loops) is exact at leading order for N_f << N.

**Double-line notation ('t Hooft):** Replace each gluon propagator with a double line (one for color index, one for anti-color). Then:
- Each face of the double-line diagram gives a factor N.
- The power of N is N^{F-E+V} = N^{chi} where chi = 2 - 2h is the Euler characteristic.

### Matrix Models

**Setup:** Integral over N x N Hermitian matrices M with action S = N * Tr[V(M)] where V(M) = M^2/2 + g_3 * M^3/3 + g_4 * M^4/4 + ...

**Rules:**
- Same as 't Hooft: genus expansion in 1/N^2.
- Leading (planar) contribution computable by saddle point: eigenvalue density rho(x) satisfies an integral equation solvable by the resolvent method.
- The resolvent W(z) = (1/N) * Tr[1/(z-M)] satisfies a quadratic equation (loop equation) at large N.

## Step-by-Step Procedure

### Step 1: Rescale the Action

Ensure the action is O(N) so that the large-N limit gives a saddle-point problem:

- Vector models: coupling lambda/N in front of interaction
- Gauge theories: 1/g^2 = N/lambda in front of F^2
- Matrix models: overall factor of N in front of Tr[V(M)]

**Checkpoint:** If the action is not O(N), the large-N limit is not a saddle point, and the expansion does not simplify. Redefine couplings to absorb the N dependence.

### Step 2: Identify the Large-N Saddle Point

Derive the saddle-point equation by varying the effective action:

- Vector models: gap equation for the auxiliary field sigma
- Gauge theories: classical equations of motion for planar master field
- Matrix models: eigenvalue density from the loop equation or resolvent

**Checkpoint:** Verify the saddle-point solution exists and is stable (second variation is positive definite). If multiple saddle points exist, identify the dominant one (lowest free energy).

### Step 3: Compute the Leading-Order Result

Evaluate the action at the saddle point to get the O(N) contribution (or O(N^2) for gauge theories):

```
F_leading = S_eff[sigma_saddle]
```

Physical quantities (masses, correlators, critical exponents) are extracted from the saddle-point solution.

### Step 4: Compute 1/N Corrections

Expand around the saddle point to quadratic order:

```
S_eff[sigma] = S_eff[sigma_saddle] + (1/2) * delta_sigma * S''_eff * delta_sigma + ...
```

The Gaussian integral gives the O(1) correction (one-loop around the saddle):

```
F_{1/N} = (1/2) * Tr ln S''_eff
```

This is an O(1) correction to the O(N) leading result, i.e., it is suppressed by 1/N.

**Checkpoint:** The 1/N correction must be finite. If it diverges, either the saddle point is unstable or the regularization is incomplete. Renormalization at large N may differ from the standard renormalization.

### Step 5: Verify Against Exact Results

For models with known exact solutions (e.g., 2D Ising at N=1, O(3) sigma model), verify:
1. The 1/N expansion at N = physical value gives reasonable results.
2. Critical exponents approach the exact values as more 1/N terms are included.
3. The series in 1/N is well-behaved (not wildly oscillating).

## Common Pitfalls

1. **Forgetting the coupling rescaling.** The interaction must be lambda/N (not lambda) for the large-N limit to give a saddle point. Without the 1/N in the coupling, the action grows as N^2 and the saddle point is trivial (free theory).

2. **Confusing vector and matrix large-N.** O(N) vector models have 1/N expansion (saddle point is mean-field). SU(N) gauge theories have 1/N^2 expansion (planar diagrams). They are different expansions with different counting rules. Never apply vector-model counting to a gauge theory or vice versa.

3. **Non-planar contamination.** When summing planar diagrams, it is easy to accidentally include a non-planar diagram (especially for diagrams with many vertices). Use double-line notation rigorously and count faces, edges, vertices to verify genus.

4. **Unstable saddle point.** The large-N saddle may be a maximum rather than minimum of the effective action. This signals a phase transition or symmetry breaking at large N. Check the second variation S''_eff.

5. **Quenched approximation errors.** For SU(N) gauge theories with N_f quarks: quark loop effects are suppressed by N_f/N. At physical N=3, N_f=6, this suppression is only 2x — the quenched approximation may be quantitatively poor.

6. **Subleading effects dominating physics.** Some physical effects are entirely absent at leading order in 1/N (e.g., baryons in large-N QCD require N quarks and are exponentially heavy ~ e^N). Confinement and chiral symmetry breaking appear at leading order, but theta dependence is subleading.

7. **Critical exponent extrapolation.** The 1/N expansion for critical exponents is asymptotic. Truncating at 1/N^2 and evaluating at N=1, 2, 3 can give large errors. Use Pade or Borel resummation of the 1/N series (see `resummation.md`).

## Worked Example: Critical Exponents of the O(N) Model via 1/N Expansion

**Problem:** Compute the anomalous dimension eta and the correlation length exponent nu for the O(N) model in d=3 dimensions at leading and subleading order in 1/N.

### Step 1: Rescaled Action

```
S = integral d^d x [ (1/2)(d_mu phi_a)^2 + (m^2/2) phi_a phi_a + (lambda/(4N)) (phi_a phi_a)^2 ]
```

where a = 1, ..., N. Introduce the auxiliary (Hubbard-Stratonovich) field sigma:

```
S = integral d^d x [ (1/2)(d_mu phi_a)^2 + (sigma/2) phi_a phi_a - N sigma^2 / (4 lambda) ]
```

### Step 2: Integrate Out phi (Exact in N)

The phi integral is Gaussian:

```
S_eff[sigma] = (N/2) Tr ln(-nabla^2 + sigma) - N integral sigma^2 / (4 lambda)
```

This is O(N), confirming the large-N saddle-point structure.

### Step 3: Saddle-Point Equation (Leading Order)

At the critical point (m^2 tuned to criticality), the gap equation is:

```
sigma_0 / (2 lambda) = (1/2) integral d^d k / (2pi)^d * 1/(k^2 + sigma_0)
```

At criticality, sigma_0 = 0 (massless propagator). The sigma propagator (inverse of S''_eff) at the critical saddle point gives the sigma two-point function:

```
D_sigma(q) = 1 / [ Pi(q) ]    where    Pi(q) = integral d^d k / (2pi)^d * 1/((k^2)(k+q)^2)
```

### Step 4: Extract Critical Exponents

**Leading order (N = inf):**

The phi propagator is free: <phi_a phi_b>(q) ~ delta_{ab} / q^2. Therefore:
- eta = 0 at leading order (phi has canonical scaling dimension)
- nu = 1/(d-2) at leading order (from the sigma propagator scaling)

In d = 3: nu_LO = 1.

**First 1/N correction:**

The anomalous dimension receives its first contribution at O(1/N):

```
eta = 8(d-2) / (d * N) * Gamma(d-1) / (Gamma(d/2)^2 * Gamma(2-d/2)) * sin(pi*d/2) / pi + O(1/N^2)
```

In d = 3:
```
eta = 8 / (3*pi^2 * N) + O(1/N^2) = 0.2702 / N
```

For the correlation length exponent:
```
1/nu = (d-2) + (d-2)(d+2) / (d * (d-1)) * eta + O(1/N^2)
```

In d = 3: 1/nu = 1 + (5/6) * eta.

### Step 5: Verification

1. **N = inf check:** eta = 0 and nu = 1. The O(N) model at N = inf is mean-field-like in d=3 (upper critical dimension for the O(N) model is d=4, so d=3 has fluctuations, but the N = inf saddle point captures them exactly). Mean-field gives nu = 1/2 for FINITE N, but N = inf is different — it resums an infinite class of diagrams (all bubble chains).

2. **Comparison with exact/numerical results at physical N:**
   - N=1 (Ising): eta(1/N) = 0.270 vs exact 0.0362. The 1/N expansion is poor at N=1 for eta (needs resummation).
   - N=2 (XY): eta(1/N) = 0.135 vs numerical 0.0381. Still poor.
   - N=10: eta(1/N) = 0.027 vs numerical ~0.025. Now reasonable.
   - The 1/N expansion converges slowly for small N. Higher-order 1/N^2 and 1/N^3 corrections improve the comparison significantly.

3. **Dimensional consistency:** [eta] = dimensionless (anomalous dimension). The formula depends on d but not on any dimensionful parameter — correct at the critical point where the only scale is the IR cutoff.

4. **Ward identity:** The O(N) symmetry is exact. The Goldstone theorem requires that in the broken phase (T < T_c), there are N-1 massless Goldstone modes. At the critical point, all N modes are massless. The 1/N expansion must preserve this — verify that the sigma propagator (radial mode) develops a mass while the Goldstone modes remain massless.

5. **Known limit d = 4:** At d = 4 (upper critical dimension), eta_LO = 0 and nu_LO = 1/2, recovering mean-field exponents. The O(1/N) correction is proportional to (d-2), so it vanishes smoothly as d -> 2 (lower critical dimension of the O(N) model for N >= 3), consistent with the Mermin-Wagner theorem.
