---
load_when:
  - "path integral"
  - "functional integral"
  - "saddle point"
  - "instanton"
  - "Faddeev-Popov"
  - "gauge fixing"
  - "Fujikawa"
tier: 2
context_cost: medium
---

# Path Integral Protocol

Path integrals are powerful but fraught with subtleties: the measure is formally ill-defined, saddle points may not dominate, and Wick rotation can fail for non-standard actions. This protocol ensures systematic and correct evaluation.

## Related Protocols

- See `analytic-continuation.md` for Wick rotation details and analytic continuation between Euclidean and Minkowski signatures
- See `monte-carlo.md` for lattice path integral evaluation via importance sampling
- See `perturbation-theory.md` for perturbative expansion around the saddle point
- See `stochastic-processes.md` for the MSR (Martin-Siggia-Rose) path integral formalism connecting stochastic dynamics to field theory

## Step 1: Measure and integration

Define the path integral measure explicitly:

1. **Discretized measure:** Write the lattice or time-sliced version of the measure. For a scalar field: D[phi] = prod\_{x} d(phi(x)) / N, where N is a normalization constant. State N.
2. **Jacobians:** When changing field variables (phi -> chi(phi)), compute the Jacobian det(delta chi / delta phi) explicitly. For fermionic fields, the Jacobian enters inversely (Berezin integration). For gauge fields, the Faddeev-Popov determinant is a Jacobian --- derive it, do not quote it.
3. **Gauge fixing:** For gauge theories, the naive measure over-counts gauge orbits. Insert the Faddeev-Popov determinant and gauge-fixing condition. State the gauge choice and verify that the FP determinant is correct by checking BRST invariance of the gauge-fixed action.
4. **Anomalies from the measure:** The measure itself can break classical symmetries (chiral anomaly, conformal anomaly). Check whether the symmetries of the classical action survive in the quantum measure. If not, compute the anomaly coefficient.

## Step 2: Saddle point / stationary phase

When evaluating the path integral by saddle-point expansion:

1. **Find classical solutions:** Solve the classical equations of motion delta S / delta phi = 0. Enumerate all solutions (there may be multiple saddle points --- instantons, bounces, sphalerons).
2. **Compute the classical action:** Evaluate S[phi_cl] at each saddle point. This gives the leading exponential contribution.
3. **Fluctuation determinant:** Expand phi = phi_cl + eta, compute the quadratic action S^(2)[eta] = (1/2) eta^T M eta, where M = delta^2 S / delta phi^2 evaluated at phi_cl. The one-loop correction is det(M)^{-1/2} (bosons) or det(M)^{+1/2} (fermions).
4. **Zero modes:** If M has zero eigenvalues (from symmetries broken by the saddle point), treat them separately. Integrate over the zero-mode collective coordinates with the correct Jacobian. Common zero modes: translations (give a volume factor), rotations (give an angular integral), gauge transformations (give a gauge volume).
5. **Negative modes:** If M has negative eigenvalues, the saddle point is unstable. For tunneling problems (bounce solutions), exactly one negative mode is expected --- it gives the imaginary part of the energy (decay rate). More than one negative mode signals an error in the saddle-point identification.

## Step 3: Wick rotation

Reference the existing Wick rotation error in the common physics error taxonomy (Sign Errors in Wick Rotation). In addition:

- Verify that the Wick rotation contour does not cross poles or branch cuts of the integrand. If it does, account for the additional contributions (residues or discontinuities).
- For fermions at finite temperature: verify that anti-periodic boundary conditions in Euclidean time are correctly implemented (psi(0) = -psi(beta)).
- For theories with a sign problem (finite-density QCD, frustrated spin systems): Wick rotation may not render the action real. Document the sign problem explicitly and state the method used to handle it (reweighting, complex Langevin, Lefschetz thimble, etc.).

## Step 4: Regularization

- **UV regulator:** State the UV regularization scheme (dimensional, lattice, Pauli-Villars, proper-time, zeta-function). Verify it preserves the symmetries needed for the calculation (gauge invariance, chiral symmetry, etc.).
- **IR regulator:** If the theory is massless or has IR divergences, state the IR regulator (finite volume, mass regulator, dimensional). Track which results depend on the IR regulator and verify they cancel in physical observables.
- **Track regulator dependence:** Every intermediate result should be labeled with its regulator dependence. Physical observables must be regulator-independent. Verify this explicitly.

## Step 5: Fujikawa Method for Anomalies

The Fujikawa method computes quantum anomalies directly from the path integral measure, avoiding the ambiguities of perturbative regularization. Use this when anomaly coefficients are needed.

1. **Setup.** Consider a classical symmetry phi -> phi + delta phi with infinitesimal parameter alpha. Under this transformation, the action is invariant (delta S = 0) but the measure may not be.
2. **Jacobian of the measure.** Expand the fields in eigenmodes of the Dirac operator (or the relevant kinetic operator): phi = sum_n a_n phi_n where D phi_n = lambda_n phi_n. The measure transforms as: D[phi] -> D[phi'] = J * D[phi] where J = det(delta phi' / delta phi).
3. **Regularize the Jacobian.** The determinant is formally divergent. Regulate using a Gaussian cutoff:
   ln J = -2i alpha * sum_n phi_n^dag gamma_5 phi_n * exp(-lambda_n^2 / M^2)
   where M is a UV regulator. The sum converges for finite M and has a well-defined M -> infinity limit.
4. **Evaluate the trace.** Using the heat kernel expansion or the eigenmode sum:
   sum_n phi_n^dag gamma_5 phi_n exp(-lambda_n^2 / M^2) = (1/16 pi^2) integral d^4x epsilon^{mu nu rho sigma} F_{mu nu} F_{rho sigma} + O(1/M^2)
   The M -> infinity limit gives the anomaly coefficient exactly.
5. **Result.** The anomalous Ward identity acquires an extra term:
   d_mu J^mu_5 = 2i m psi-bar gamma_5 psi + (e^2 / 16 pi^2) F_{mu nu} F*^{mu nu}
   The second term is the axial (ABJ) anomaly. The coefficient (1/16 pi^2 per flavor) is exact to all orders in perturbation theory.
6. **Cross-checks.** (a) The anomaly coefficient must be an integer (topological invariant) times a universal factor. If a fractional coefficient appears, there is an error in the eigenmode expansion or regularization. (b) Verify against the perturbative triangle diagram calculation — the results must agree. (c) For non-abelian gauge fields, the anomaly involves tr(T^a {T^b, T^c}) and must satisfy the Wess-Zumino consistency condition.

## Step 6: Ward identities from path integral

Before computing Feynman diagrams or correlation functions, derive symmetry constraints from the path integral:

1. **Perform the symmetry transformation** phi -> phi + delta phi inside the path integral.
2. **Use the invariance of the measure** (if non-anomalous) to derive the Ward identity relating different correlation functions.
3. **Check the result:** The Ward identity constrains the answer before you compute it. Use it as a cross-check on explicit calculations.
4. **If the measure is NOT invariant** (anomalous symmetry): the Ward identity acquires an anomaly term. Compute it from the Jacobian of the measure transformation.

## Concrete Example: Wrong Wick Rotation Sign Changes the Propagator

**Problem:** Derive the Euclidean propagator from the Minkowski path integral for a free scalar field.

**Wrong approach (common LLM error):** "Set t = i*tau, so the Minkowski action S_M = integral dt [(1/2)(d phi/dt)^2 - (1/2)m^2 phi^2] becomes S_E = integral d tau [-(1/2)(d phi/d tau)^2 - (1/2)m^2 phi^2]."

This gives the WRONG sign for the kinetic term, producing a non-convergent Euclidean path integral.

**Correct approach following this protocol:**

Step 1. **Track the Wick rotation sign explicitly.** The Minkowski action is:
```
S_M = integral d^4x [(1/2)(partial_mu phi)(partial^mu phi) - (1/2)m^2 phi^2]
    = integral dt d^3x [(1/2)(d phi/dt)^2 - (1/2)(nabla phi)^2 - (1/2)m^2 phi^2]
```

Step 2. **Wick rotate: t = -i*tau** (NOT t = +i*tau). This gives:
```
dt = -i * d(tau)
(d phi/dt)^2 = (d phi / (-i d tau))^2 = -(d phi/d tau)^2
```

Step 3. **Substitute into the action:**
```
S_M = integral (-i d tau) d^3x [(1/2)(-(d phi/d tau)^2) - (1/2)(nabla phi)^2 - (1/2)m^2 phi^2]
    = -i * integral d tau d^3x [-(1/2)(d phi/d tau)^2 - (1/2)(nabla phi)^2 - (1/2)m^2 phi^2]
```

Step 4. **Define S_E:**
The path integral weight is exp(i*S_M). After Wick rotation:
```
i * S_M = i * (-i) * integral d^4x_E [-(1/2)(partial_E phi)^2 - (1/2)m^2 phi^2]
        = -integral d^4x_E [(1/2)(partial_E phi)^2 + (1/2)m^2 phi^2]
        = -S_E
```

So **S_E = integral d^4x_E [(1/2)(partial_E phi)^2 + (1/2)m^2 phi^2]** with ALL POSITIVE signs.

Step 5. **Checkpoint:**
- S_E > 0 for all field configurations. This ensures exp(-S_E) is bounded, making the Euclidean path integral well-defined. If you got negative signs in S_E, the path integral diverges -- this means you made a sign error.
- The Euclidean propagator is G_E(k) = 1/(k_E^2 + m^2), which is positive for all Euclidean momenta. This is required by Osterwalder-Schrader reflection positivity.
- Setting m = 0: G_E(k) = 1/k_E^2, which is the Green's function of the Laplacian in 4D. Correct.

**The typical LLM error** is using t = +i*tau instead of t = -i*tau, which produces wrong signs in S_E (kinetic term negative), leading to a non-convergent Euclidean path integral. The convergence checkpoint catches this immediately.

## Worked Example: Instanton Tunneling Rate in the Double-Well Potential

**Problem:** Compute the ground-state energy splitting Delta E due to quantum tunneling in the symmetric double-well potential V(x) = lambda * (x^2 - a^2)^2, using the instanton (Euclidean bounce) solution. This targets the LLM error class of incorrect saddle-point evaluation — wrong zero-mode treatment, missing Jacobians, and wrong prefactors in the fluctuation determinant.

### Step 1: Classical Euclidean Solution

The Euclidean action (after Wick rotation t -> -i*tau):

```
S_E = integral d tau [(1/2)(dx/d tau)^2 + V(x)]
```

Note the + sign in front of V(x) — the Euclidean potential is INVERTED relative to Minkowski. The instanton is a classical solution in the inverted potential -V(x), which has maxima at x = +/- a.

The instanton equation of motion:

```
d^2 x / d tau^2 = dV/dx = 4 lambda x (x^2 - a^2)
```

The instanton solution (kink from -a to +a):

```
x_cl(tau) = a * tanh(omega * (tau - tau_0) / 2)
```

where omega = 2a * sqrt(2 lambda) is the frequency of small oscillations around a minimum, and tau_0 is the center of the instanton (a collective coordinate).

### Step 2: Classical Action

```
S_0 = integral d tau [(1/2)(dx_cl/d tau)^2 + V(x_cl)]
```

Using the BPS-like identity (dx/d tau)^2 = 2V(x) along the instanton trajectory:

```
S_0 = integral d tau (dx_cl/d tau)^2 = integral_{-a}^{+a} dx * sqrt(2V(x))
    = integral_{-a}^{a} dx * sqrt(2 lambda) * (a^2 - x^2)
    = (2 sqrt(2 lambda) / 3) * (2a^3) = (4/3) * a^3 * sqrt(2 lambda)
    = omega^3 / (12 lambda)
```

**Checkpoint:** S_0 must be positive (Euclidean action is positive for a tunneling solution). S_0 ~ 1/lambda: the tunneling rate is exponentially suppressed for weak coupling. If S_0 ~ lambda (linear in coupling), there is an error.

### Step 3: Fluctuation Determinant

Expand x = x_cl + eta. The quadratic fluctuation operator:

```
M = -d^2/d tau^2 + V''(x_cl) = -d^2/d tau^2 + omega^2 [1 - 3/(2 cosh^2(omega tau/2))]
```

This is a Poschl-Teller potential with known spectrum:
- One zero mode: eta_0 = dx_cl/d tau (from translational invariance, tau_0)
- One bound state: at eigenvalue omega^2 * (1 - 1/4) = 3 omega^2/4
- Continuum: starting at omega^2

### Step 4: Zero Mode Treatment

The zero mode (eta_0 proportional to dx_cl/d tau) arises because the instanton can be centered at any tau_0. Do NOT include it in the determinant. Instead:

1. **Remove the zero eigenvalue** from det(M).
2. **Integrate over tau_0** with the correct Jacobian:

```
integral d tau_0 * ||eta_0|| = integral d tau_0 * sqrt(S_0) = T * sqrt(S_0)
```

where T is the total Euclidean time and ||eta_0||^2 = S_0 (the norm of the zero mode equals the classical action).

**Checkpoint:** The Jacobian factor sqrt(S_0) has dimensions of [action]^{1/2}. If the Jacobian is missing, the final answer has wrong dimensions.

### Step 5: Assemble the Tunneling Rate

The energy splitting from a dilute instanton gas:

```
Delta E = 2 * omega * sqrt(S_0 / (2 pi)) * (det'(M) / det(M_0))^{-1/2} * exp(-S_0)
```

where det'(M) is the determinant with the zero mode removed, and M_0 = -d^2/d tau^2 + omega^2 is the fluctuation operator around the minimum (no instanton).

For the Poschl-Teller potential, the ratio of determinants is known exactly:

```
det'(M) / det(M_0) = 1/12
```

So:

```
Delta E = 2 omega * sqrt(S_0 / (2 pi)) * sqrt(12) * exp(-S_0)
        = 2 omega * sqrt(6 S_0 / pi) * exp(-S_0)
```

### Verification

1. **Dimensional check:** [Delta E] = [energy]. omega has dimensions of [energy]/hbar. S_0 is dimensionless (in units where hbar = 1). exp(-S_0) is dimensionless. sqrt(S_0) is dimensionless. So [Delta E] = [omega] = [energy]. Correct.

2. **WKB cross-check:** The WKB tunneling formula gives Delta E ~ omega * exp(-integral_{-a}^{a} dx * sqrt(2m V(x)) / hbar). With m = 1, hbar = 1: the exponent is S_0. The prefactor from WKB should match the instanton prefactor. If they disagree by more than O(1), there is an error in the zero-mode treatment.

3. **Weak coupling limit:** As lambda -> 0 (shallow barrier), S_0 -> 0 and Delta E -> omega (the splitting approaches the oscillation frequency — the two wells merge into one). As lambda -> infinity (deep barrier), S_0 -> infinity and Delta E -> 0 exponentially (tunneling is suppressed). Both limits are physical.

4. **Positivity:** Delta E > 0 for the ground-state splitting (the symmetric state is lower). If Delta E < 0, there is a sign error in the instanton calculation (likely from incorrect treatment of the negative mode of the anti-instanton).

5. **Numerical test:** For a = 1, lambda = 8 (so omega = 2a*sqrt(2*lambda) = 8, S_0 = omega^3/(12*lambda) = 512/96 = 16/3 ~ 5.3): Delta E / omega ~ 2 * sqrt(6*S_0/pi) * exp(-S_0) ~ 2 * sqrt(32/pi) * exp(-16/3) ~ 2 * 3.19 * 0.0049 ~ 0.031. The semiclassical approximation requires S_0 >> 1; for S_0 ~ O(1) (shallow barriers), the instanton gas is not dilute and exact diagonalization should be used instead.

## Worked Example: Faddeev-Popov Quantization of Non-Abelian Gauge Theory

**Problem:** Derive the Faddeev-Popov ghost action for SU(N) Yang-Mills theory in covariant gauge, and show that the ghost loop contributes to the gluon self-energy with the correct sign to produce asymptotic freedom. This targets the LLM error class of omitting the Faddeev-Popov determinant (or its sign), which destroys gauge invariance and produces wrong physical predictions including the wrong sign of the QCD beta function.

### Step 1: The Problem with Naive Gauge-Field Path Integrals

The Yang-Mills partition function:

```
Z = integral DA_mu exp(i S_YM[A])
```

is ill-defined because the integral includes gauge-equivalent configurations A_mu and A_mu^g = g A_mu g^{-1} + (i/g_s) g partial_mu g^{-1}, which all give the same physics. The integral over the gauge orbit volume diverges.

**The common LLM error:** "Just pick a gauge condition F[A] = 0 and insert delta(F[A]) into the path integral." This misses the Jacobian factor — inserting a delta function without the correct Jacobian produces gauge-DEPENDENT results for physical observables.

### Step 2: Faddeev-Popov Procedure

Insert the identity:

```
1 = Delta_FP[A] * integral Dg * delta(F[A^g])
```

where Delta_FP[A] is the Faddeev-Popov determinant and the integral is over gauge transformations g. For infinitesimal transformations g = 1 + i theta^a T^a:

```
Delta_FP[A] = det(delta F^a / delta theta^b)
```

For the Lorentz gauge condition F^a[A] = partial_mu A_mu^a - omega^a (where omega^a is an arbitrary function):

```
delta F^a / delta theta^b = partial_mu D_mu^{ab} = partial_mu (partial_mu delta^{ab} + g_s f^{abc} A_mu^c)
```

This is a differential operator — the determinant is a functional determinant.

### Step 3: Ghost Action

Represent the determinant as a Grassmann (ghost) path integral:

```
det(partial_mu D_mu) = integral Dc-bar Dc * exp(i S_ghost)
```

where:

```
S_ghost = integral d^4x * c-bar^a * (-partial_mu D_mu^{ab}) * c^b
        = integral d^4x * c-bar^a * (-partial^2 delta^{ab} - g_s f^{abc} partial_mu A_mu^c) * c^b
```

**Critical:** c and c-bar are anticommuting scalar fields (spin 0, Grassmann statistics). They are NOT physical particles — they are bookkeeping devices that ensure gauge invariance. They violate the spin-statistics theorem (spin 0 but Fermi statistics) and appear only in loops, never as external states.

The ghost-gluon vertex from S_ghost is:

```
V^{abc}_mu(k) = g_s f^{abc} k_mu
```

where k is the outgoing ghost momentum. Note: the vertex depends on momentum (derivative coupling), unlike the gluon self-coupling.

### Step 4: Ghost Loop Contribution to the Gluon Self-Energy

The ghost loop diagram contributes to the gluon vacuum polarization at one loop:

```
Pi_ghost^{mu nu, ab}(q) = (-1) * integral d^d k / (2 pi)^d * (g_s f^{ace} k^mu) * (i / k^2) * (g_s f^{bce} (k-q)^nu) * (i / (k-q)^2)
```

The (-1) comes from the closed Grassmann loop (same rule as fermion loops). Using f^{ace} f^{bce} = N delta^{ab} (for SU(N)):

```
Pi_ghost^{mu nu, ab}(q) = -g_s^2 N delta^{ab} * integral d^d k / (2 pi)^d * k^mu (k-q)^nu / (k^2 (k-q)^2)
```

After evaluation in dimensional regularization:

```
Pi_ghost(q^2) = -(g_s^2 N) / (48 pi^2) * (1/epsilon + finite)
```

This contributes to the gluon self-energy with a NEGATIVE sign (relative to the gluon and fermion loop contributions).

### Step 5: Effect on the Beta Function

The one-loop gluon self-energy has three contributions:

| Contribution | Sign | Coefficient (proportional to) |
|-------------|------|-------------------------------|
| Gluon loop | - | -10/3 * C_A |
| Ghost loop | - | -1/3 * C_A |
| Fermion loop | + | +4/3 * T_F * N_f |

For SU(3): C_A = 3, T_F = 1/2.

The beta function coefficient: b_0 = (10/3 + 1/3) * 3 - 4/3 * 1/2 * N_f = 11 - 2N_f/3.

**Without ghosts (the LLM error):** b_0 = 10/3 * 3 - 2N_f/3 = 10 - 2N_f/3. This gives the WRONG coefficient. For N_f = 6: b_0_wrong = 6 vs b_0_correct = 7. The 1/3 * C_A contribution from ghosts is essential for the correct beta function.

**Even worse:** in axial gauges (no ghosts needed), the gluon loop gives a different split between transverse and longitudinal components but the SAME total b_0 = 11 - 2N_f/3. This is a consistency check: physical observables must not depend on whether ghosts are used. If they do, the ghost action is wrong.

### Verification

1. **BRST invariance.** The combined gauge-fixed + ghost action must be invariant under the BRST transformation: delta A_mu^a = D_mu^{ab} c^b * epsilon, delta c^a = -(g_s/2) f^{abc} c^b c^c * epsilon, delta c-bar^a = (1/xi) partial_mu A_mu^a * epsilon (where xi is the gauge parameter). Verify BRST invariance of the total action. If it fails, the ghost action is wrong.

2. **Ghost number conservation.** The ghost action has a global U(1) symmetry: c -> e^{i alpha} c, c-bar -> e^{-i alpha} c-bar. This assigns ghost number +1 to c and -1 to c-bar. Physical observables have ghost number 0. Verify that every Feynman diagram contributing to a physical observable has equal numbers of c and c-bar propagators.

3. **Slavnov-Taylor identities.** The non-Abelian generalization of Ward identities: q_mu Pi^{mu nu}(q) = 0 for the gluon self-energy. This requires the ghost loop contribution. If ghosts are omitted, q_mu Pi^{mu nu} is nonzero — gauge invariance is violated and the gluon acquires an unphysical mass.

4. **Abelian limit.** For U(1) (QED), f^{abc} = 0, so the ghost-gluon vertex vanishes. Ghosts decouple completely. The QED beta function has no ghost contribution. If the ghost loop contributes to the QED beta function, there is an error in the color algebra.

5. **Gauge parameter independence.** The beta function b_0 must be independent of the gauge parameter xi. Compute Pi_ghost in Feynman gauge (xi = 1) and R_xi gauge (general xi). The xi-dependent terms must cancel between gluon and ghost contributions. If they do not cancel, the Faddeev-Popov procedure was applied incorrectly.
