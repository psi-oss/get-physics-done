---
load_when:
  - "Lagrangian"
  - "Hamiltonian"
  - "canonical transformation"
  - "Hamilton-Jacobi"
  - "Poisson bracket"
  - "Legendre transform"
  - "constraints"
  - "action principle"
  - "symplectic"
  - "phase space"
  - "generating function"
  - "Dirac bracket"
tier: 2
context_cost: medium
---

# Hamiltonian Mechanics Protocol

The Hamiltonian formulation is the bridge between classical and quantum physics: canonical quantization replaces Poisson brackets with commutators, path integrals weight by exp(iS/hbar), and constrained systems require Dirac's procedure before quantization makes sense. Errors in this formulation -- wrong Legendre transforms, missed constraints, incorrect canonical transformations -- silently corrupt every downstream quantum calculation. This protocol provides step-by-step algorithms with verification at each stage.

## Related Protocols
- `classical-mechanics.md` -- Formulation choice, generalized coordinates, constraints overview, conservation laws
- `derivation-discipline.md` -- Sign tracking, convention annotation, derivation checkpointing
- `symmetry-analysis.md` -- Noether's theorem, symmetry breaking, anomalies

## Step 1: Legendre Transform (Lagrangian to Hamiltonian)

### 1.1 The Standard Procedure

Given a Lagrangian L(q, q-dot, t) with N generalized coordinates:

1. **Define conjugate momenta.** p_i = dL/dq-dot_i for each i = 1, ..., N.

2. **Check the Hessian.** Compute the Hessian matrix W_ij = d^2L / dq-dot_i dq-dot_j. If det(W) != 0, the Legendre transform is regular and you can solve for all q-dot_i in terms of (q, p, t). If det(W) = 0, the system has constraints -- go to Step 2 (Dirac procedure).

3. **Invert.** Solve p_i = dL/dq-dot_i for q-dot_i = q-dot_i(q, p, t). This is the step LLMs most frequently skip or do incorrectly.

4. **Construct H.** H(q, p, t) = sum_i p_i q-dot_i(q, p, t) - L(q, q-dot(q, p, t), t). Every occurrence of q-dot must be eliminated in favor of (q, p, t). If any q-dot remains, the Legendre transform is incomplete.

5. **Write Hamilton's equations.**
```
q-dot_i = dH/dp_i
p-dot_i = -dH/dq_i
```

### 1.2 Verification of the Legendre Transform

After computing H, perform ALL of these checks:

1. **Variable check.** H must be a function of (q, p, t) only. Search the expression for any q-dot. If present, the inversion in step 3 was incomplete.

2. **Hamilton's equations reproduce Euler-Lagrange.** Compute q-dot = dH/dp and p-dot = -dH/dq, then substitute p = dL/dq-dot. The result must be d/dt(dL/dq-dot) - dL/dq = 0.

3. **Dimension check.** H has dimensions of energy. Every term in H must have dimensions of energy.

4. **Known limits.** For a standard kinetic-energy-plus-potential system (L = T - V with T = (1/2) g_ij q-dot^i q-dot^j and V = V(q)):
   - p_i = g_ij q-dot^j
   - q-dot^i = g^{ij} p_j (where g^{ij} is the inverse metric)
   - H = (1/2) g^{ij} p_i p_j + V(q) = T + V
   - If your H does not reduce to T + V in this case, there is an error.

5. **Energy conservation.** dH/dt = dH/dt|_explicit (partial derivative with respect to explicit time dependence). If L has no explicit time dependence, H is conserved. Verify this.

### 1.3 Common LLM Error: Incomplete Velocity Elimination

**The error:** The most common Legendre transform mistake is writing H = p q-dot - L and then failing to eliminate q-dot in favor of p. The result looks like a Hamiltonian but is actually a mixed function of (q, q-dot, p) that gives wrong equations of motion.

**Example:** For L = (1/2) m q-dot^2 - V(q):

Wrong: "p = m q-dot, so H = p q-dot - (1/2) m q-dot^2 + V = p q-dot - (1/2) m q-dot^2 + V."

This still contains q-dot. The correct step is to substitute q-dot = p/m:

Correct: H = p (p/m) - (1/2) m (p/m)^2 + V = p^2/m - p^2/(2m) + V = p^2/(2m) + V.

**Detection:** After writing H, scan every term for q-dot. If it appears anywhere, the transform is incomplete.

### 1.4 Common LLM Error: Wrong Sign in Legendre Transform

**The error:** Writing H = sum p_i q-dot_i + L instead of H = sum p_i q-dot_i - L. This flips the sign of the potential.

**Detection:** For a free particle, H must be positive (kinetic energy). If H = -p^2/(2m), the sign is wrong. For a harmonic oscillator, H = p^2/(2m) + (1/2)k q^2 must give positive-definite energy for real (q, p).

## Step 2: Constrained Systems (Dirac Procedure)

When the Hessian det(W_ij) = 0, the standard Legendre transform fails. This occurs in gauge theories (electrodynamics, Yang-Mills, general relativity), systems with redundant coordinates, and any system where some "velocities" are not true dynamical variables.

### 2.1 Primary Constraints

1. **Identify primary constraints.** From p_i = dL/dq-dot_i, if some momenta cannot be expressed as independent functions of the velocities, there are relations phi_a(q, p) ~ 0 (using Dirac's weak equality notation). These are the primary constraints.

2. **Count.** If the Hessian has rank r < N, there are N - r primary constraints.

3. **Construct the total Hamiltonian.** H_T = H_c + u^a phi_a, where H_c is the canonical Hamiltonian (obtained by the Legendre transform using any consistent inversion of the invertible momenta) and u^a are undetermined multipliers.

### 2.2 Secondary Constraints and Consistency

1. **Demand consistency.** Each constraint must be preserved in time: phi-dot_a = {phi_a, H_T} ~ 0. This gives either:
   - A new constraint (secondary constraint) if the equation is independent of the multipliers u^a
   - A determination of some multiplier u^a
   - An identity (0 ~ 0)

2. **Iterate.** Apply the consistency condition to any new secondary constraints. Continue until no new constraints emerge and all multipliers are determined or remain free.

3. **Count physical degrees of freedom:**
```
DOF_physical = N - (number of second-class constraints)/2 - (number of first-class constraints)
```
where first-class constraints have weakly vanishing Poisson brackets with all other constraints, and second-class constraints do not.

### 2.3 First-Class vs Second-Class Constraints

| Type | Definition | Significance | Treatment |
|---|---|---|---|
| **First-class** | {phi_a, phi_b} ~ 0 for all constraints phi_b | Generates gauge transformations | Fix gauge or use Dirac bracket on gauge-fixed surface |
| **Second-class** | {phi_a, phi_b} != 0 for some phi_b | Reduces phase space dimension | Replace Poisson brackets with Dirac brackets |

**Dirac bracket:** For second-class constraints phi_a with matrix C_{ab} = {phi_a, phi_b}:

```
{A, B}_D = {A, B} - sum_{a,b} {A, phi_a} (C^{-1})_{ab} {phi_b, B}
```

After introducing the Dirac bracket, the constraints can be set strongly to zero (phi_a = 0, not just ~ 0).

### 2.4 Verification of Constraint Analysis

1. **Constraint algebra closure.** Compute ALL Poisson brackets {phi_a, phi_b}. The result must be either zero (weakly) or a linear combination of constraints and known functions. If the algebra does not close, a constraint was missed.

2. **DOF count.** The number of physical DOF computed from constraints must agree with physical intuition. For electrodynamics in 3+1 dimensions: 4 field components - 2 first-class constraints = 2 physical polarizations.

3. **Gauge invariance.** Each first-class constraint generates a gauge transformation via {q, phi_a}. Verify that the transformation leaves the action invariant.

4. **Dirac bracket consistency.** The Dirac bracket must satisfy the Jacobi identity. For simple cases, verify {A, {B, C}_D}_D + cyclic = 0 for a few test functions.

## Step 3: Poisson Brackets

### 3.1 Definition and Fundamental Brackets

The Poisson bracket of two phase-space functions A(q, p, t) and B(q, p, t) is:

```
{A, B} = sum_i (dA/dq_i dB/dp_i - dA/dp_i dB/dq_i)
```

Fundamental brackets: {q_i, q_j} = 0, {p_i, p_j} = 0, {q_i, p_j} = delta_{ij}.

### 3.2 Properties (All Must Hold)

1. **Antisymmetry:** {A, B} = -{B, A}
2. **Linearity:** {aA + bB, C} = a{A, C} + b{B, C}
3. **Leibniz rule:** {AB, C} = A{B, C} + {A, C}B
4. **Jacobi identity:** {A, {B, C}} + {B, {C, A}} + {C, {A, B}} = 0

**Verification protocol:** After computing any set of Poisson brackets, verify the Jacobi identity for at least one non-trivial triple. If it fails, there is an error in the bracket computation or the coordinates are not canonical.

### 3.3 Time Evolution

For any phase-space function A:

```
dA/dt = {A, H} + dA/dt|_explicit
```

This is the fundamental equation of Hamiltonian mechanics. Constants of motion satisfy {A, H} = 0 (for functions without explicit time dependence).

**Common LLM error:** Forgetting the partial derivative term dA/dt|_explicit when A has explicit time dependence. For time-independent A, dA/dt = {A, H} is sufficient.

### 3.4 Angular Momentum Poisson Brackets

For orbital angular momentum L_i = epsilon_{ijk} q_j p_k:

```
{L_i, L_j} = epsilon_{ijk} L_k
```

This is the SO(3) algebra. Verify: {L_x, L_y} = L_z, {L_y, L_z} = L_x, {L_z, L_x} = L_y.

**Common LLM error:** Getting the sign or cyclic ordering wrong. The structure constants are +epsilon_{ijk}, not -epsilon_{ijk}. This sign determines the correspondence with quantum commutators: [L_i, L_j] = i hbar epsilon_{ijk} L_k.

## Step 4: Canonical Transformations

### 4.1 Definition and Test

A transformation (q, p) -> (Q, P) is canonical if and only if it preserves the fundamental Poisson brackets:

```
{Q_i, Q_j} = 0,  {P_i, P_j} = 0,  {Q_i, P_j} = delta_{ij}
```

where the brackets are computed using the OLD variables (q, p).

**Equivalently:** The transformation preserves Hamilton's equations. The new Hamiltonian K(Q, P, t) satisfies Q-dot = dK/dP, P-dot = -dK/dQ.

### 4.2 Generating Functions

There are four types, depending on which variables are treated as independent:

| Type | Independent Variables | Generating Function | Relations |
|---|---|---|---|
| F1 | (q, Q) | F1(q, Q, t) | p = dF1/dq, P = -dF1/dQ, K = H + dF1/dt |
| F2 | (q, P) | F2(q, P, t) | p = dF2/dq, Q = dF2/dP, K = H + dF2/dt |
| F3 | (p, Q) | F3(p, Q, t) | q = -dF3/dp, P = -dF3/dQ, K = H + dF3/dt |
| F4 | (p, P) | F4(p, P, t) | q = -dF4/dp, Q = dF4/dP, K = H + dF4/dt |

The relations between types are Legendre transforms: F2 = F1 + Q_i P_i, etc.

**Important:** The identity transformation Q = q, P = p is generated by F2 = q_i P_i (NOT F1, which would be singular for the identity).

### 4.3 Verification of Canonical Transformations

After finding a canonical transformation, verify ALL of:

1. **Poisson bracket test.** Compute {Q_i, P_j} using the original (q, p) variables. It must give delta_{ij}.

2. **Symplectic condition.** The Jacobian matrix M of the transformation (Q, P) = M (q, p) must satisfy M^T J M = J, where J = [[0, I], [-I, 0]] is the symplectic matrix. This is equivalent to the Poisson bracket test but is often easier to check for linear transformations.

3. **Hamilton's equations in new variables.** Verify Q-dot = dK/dP and P-dot = -dK/dQ with the new Hamiltonian K.

4. **Invertibility.** The transformation must be invertible: you can express (q, p) in terms of (Q, P). If det(M) = 0, the transformation is degenerate.

### 4.4 Common LLM Errors in Canonical Transformations

**Error 1: Wrong generating function type.** Using F1 when the transformation requires F2, or vice versa. The symptom is that the partial derivatives give inconsistent results.

**Fix:** If the transformation (q, p) -> (Q, P) has Q = Q(q, p) with dQ/dp != 0 (Q depends nontrivially on p), then F1(q, Q) is appropriate. If Q = Q(q) only (point transformation), F2(q, P) is usually easier.

**Error 2: Forgetting K = H + dF/dt.** For time-dependent generating functions, the new Hamiltonian K differs from H by the partial time derivative of the generating function. Forgetting this term gives wrong equations of motion in the new variables.

**Error 3: Sign errors in F3 and F4.** The minus signs in q = -dF3/dp and q = -dF4/dp are frequently dropped.

## Step 5: Hamilton-Jacobi Theory

### 5.1 Hamilton's Principal Function

The Hamilton-Jacobi equation is obtained by seeking a canonical transformation to new variables (Q, P) where the new Hamiltonian K = 0, so that Q and P are all constants of motion.

The generating function F2 = S(q, P, t) (Hamilton's principal function) satisfies:

```
H(q, dS/dq, t) + dS/dt = 0
```

This is the Hamilton-Jacobi equation: a single first-order PDE for S, replacing Hamilton's 2N first-order ODEs.

### 5.2 Separation of Variables

The power of the HJ equation is separation of variables. If the Hamiltonian is separable:

1. **Time separation.** If H has no explicit time dependence: S(q, alpha, t) = W(q, alpha) - E t, where W is Hamilton's characteristic function and E = H (energy). The HJ equation becomes H(q, dW/dq) = E.

2. **Coordinate separation.** If H(q_1, ..., q_N, p_1, ..., p_N) can be written so that q_1 and p_1 appear only in a combination that can be set equal to a separation constant alpha_1, then W = W_1(q_1, alpha) + W_rest(q_2, ..., q_N, alpha). Repeat for each separable coordinate.

3. **Complete integral.** A solution S containing N independent constants of integration (alpha_1, ..., alpha_N) (in addition to an additive constant) is a complete integral. From it, the full solution follows: Q_i = dS/d(alpha_i) = beta_i (constants), p_i = dS/dq_i.

### 5.3 Action-Angle Variables

For periodic or quasi-periodic systems (bounded orbits):

1. **Action variables.** J_i = (1/(2*pi)) oint p_i dq_i, where the integral is over one complete period of the i-th coordinate. J_i are constants of motion.

2. **Angle variables.** theta_i are the conjugate coordinates to J_i. They increase linearly in time: theta_i(t) = omega_i t + theta_i(0), where omega_i = dH/dJ_i are the fundamental frequencies.

3. **Verification:** The frequencies omega_i must be independent of the angle variables. If omega_i depends on theta_j, the action-angle transformation is incorrect.

4. **Integrability criterion.** A system with N DOF is completely integrable if there exist N independent constants of motion (J_1, ..., J_N) that are in involution: {J_i, J_j} = 0 for all i, j (Liouville's theorem).

### 5.4 Common LLM Errors in Hamilton-Jacobi

**Error 1: Confusing S and W.** Hamilton's principal function S depends on time: S(q, alpha, t). Hamilton's characteristic function W does not: W(q, alpha). They are related by S = W - Et only for time-independent Hamiltonians. Using W where S is needed (or vice versa) gives the wrong time dependence.

**Error 2: Wrong separation ansatz.** Attempting to separate variables in coordinates where the Hamiltonian is not separable. The HJ equation for the Kepler problem separates in spherical coordinates but NOT in Cartesian. The Stark effect (Kepler + uniform electric field) separates in parabolic coordinates but NOT in spherical. Always verify that each separated equation depends on only one coordinate.

**Error 3: Wrong action integral contour.** The action integral J = (1/(2pi)) oint p dq must be taken over one COMPLETE period. For a libration (bounded oscillation), this is a closed curve in phase space. For a rotation (unbounded motion, e.g., a pendulum going over the top), the integral is over one full cycle of the angle variable (0 to 2*pi). Confusing these gives wrong frequencies.

## Step 6: Symplectic Structure

### 6.1 Phase Space Geometry

Hamiltonian mechanics is the study of symplectic manifolds. Phase space (q_1, ..., q_N, p_1, ..., p_N) carries the symplectic 2-form:

```
omega = sum_i dp_i ^ dq_i
```

This form is closed (d*omega = 0) and non-degenerate (det(omega) != 0). These two properties define a symplectic manifold.

### 6.2 Liouville's Theorem

The phase-space volume element is preserved by Hamiltonian flow:

```
d/dt (dq_1 ... dq_N dp_1 ... dp_N) = 0
```

**Verification:** For any canonical transformation, compute the Jacobian determinant. It must equal +1 (not just +/-1; symplectic transformations are orientation-preserving).

**Physical consequence:** A cloud of initial conditions in phase space can change shape but not volume. This is the classical origin of the uncertainty principle and the foundation of statistical mechanics (Boltzmann's equal a priori probability postulate).

### 6.3 Poincare Invariants

The integral of the symplectic form over any 2-surface in phase space is invariant under Hamiltonian evolution:

```
oint (sum_i p_i dq_i) = invariant along orbits
```

This is the Poincare-Cartan integral invariant. For one DOF, it reduces to conservation of phase-space area enclosed by any orbit.

## Step 7: Verification Checklist

For every Hamiltonian mechanics calculation, verify:

1. **Hamilton's equations reproduce Euler-Lagrange.** Derive the EOM both ways. They must agree.

2. **Energy conservation.** If L has no explicit time dependence, verify dH/dt = 0 along solutions of Hamilton's equations.

3. **Poisson bracket consistency.** For any claimed constant of motion C, verify {C, H} = 0 explicitly.

4. **Canonical transformation validity.** Verify {Q_i, P_j} = delta_{ij} in the original variables.

5. **Constraint completeness.** If the Hessian is singular, verify all constraints (primary and secondary) have been found by checking that the consistency algorithm terminates.

6. **DOF count.** Physical DOF = N - (second-class)/2 - (first-class). This must match the expected physical content.

7. **Dimension check.** [H] = energy, [p_i q-dot_i] = energy, [S] = action = energy * time, [J_i] = action.

8. **Symplectic structure.** For canonical transformations, verify M^T J M = J or equivalently det(M) = 1.

## Worked Example: Kepler Problem via Hamilton-Jacobi

**Problem:** Solve the Kepler problem (particle in a 1/r potential) using the Hamilton-Jacobi method, deriving the orbit equation and frequencies.

### Setup

Lagrangian in spherical coordinates (planar motion, theta = pi/2):
```
L = (1/2) m (r-dot^2 + r^2 phi-dot^2) + k/r
```
where k = GMm for gravity (k > 0 for attraction).

**Step 1: Legendre transform.**
- p_r = dL/dr-dot = m r-dot
- p_phi = dL/dphi-dot = m r^2 phi-dot

Hessian: W = diag(m, m r^2), det(W) = m^2 r^2 != 0. Regular transform.

- r-dot = p_r / m
- phi-dot = p_phi / (m r^2)

```
H = p_r^2/(2m) + p_phi^2/(2mr^2) - k/r
```

**Checkpoint:** H depends only on (r, phi, p_r, p_phi). No velocities remain. [H] = energy. Setting k = 0 gives free particle in polar coordinates. Correct.

### Step 2: Hamilton-Jacobi equation.

Since H has no explicit t or phi dependence:
```
S = W_r(r) + L phi - E t
```
where E (energy) and L (angular momentum = p_phi) are the separation constants.

The HJ equation H(r, dS/dr, dS/dphi) + dS/dt = 0 becomes:
```
(1/(2m))(dW_r/dr)^2 + L^2/(2mr^2) - k/r = E
```

Solving: dW_r/dr = sqrt(2m(E + k/r) - L^2/r^2) = sqrt(2mE + 2mk/r - L^2/r^2).

### Step 3: Orbit equation.

The orbit equation comes from dS/dL = beta (constant):
```
beta = dW_r/dL + phi = -integral of (L / (r^2 sqrt(2mE + 2mk/r - L^2/r^2))) dr + phi
```

Substituting u = 1/r and performing the integral:
```
phi - beta = arccos( (L^2 u/mk - 1) / sqrt(1 + 2EL^2/(mk^2)) )
```

Inverting:
```
r = L^2/(mk) * 1/(1 + e cos(phi - beta))
```
where e = sqrt(1 + 2EL^2/(mk^2)) is the eccentricity.

### Step 4: Verification.

1. **Orbit shape.** r = p/(1 + e cos(phi)) is a conic section. e < 1: ellipse (E < 0). e = 0: circle. e = 1: parabola (E = 0). e > 1: hyperbola (E > 0). Correct.

2. **Circular orbit limit.** E = -mk^2/(2L^2) gives e = 0, r = L^2/(mk) = const. The orbital frequency is omega = L/(mr^2) = mk^2/L^3. From Kepler's third law: omega^2 = k/(mr^3) -> omega = sqrt(k/m) / r^{3/2}. Substituting r = L^2/(mk): omega = m^2 k^2 / (m L^3) = mk^2/L^3. Consistent.

3. **Action variables.** For a bound orbit (E < 0):
   - J_phi = L (angular momentum)
   - J_r = (1/(2pi)) oint p_r dr = -L + mk/sqrt(-2mE)

   Total action: J_r + J_phi = mk/sqrt(-2mE), so E = -mk^2/(2(J_r + J_phi)^2).

4. **Frequencies.** omega_r = dE/dJ_r = mk^2/(J_r + J_phi)^3 = omega_phi = dE/dJ_phi. The two frequencies are equal: omega_r = omega_phi. This means the orbit closes after one radial period -- correct for the 1/r potential (Bertrand's theorem: only 1/r and r^2 potentials produce closed orbits).

5. **Degeneracy.** The equality omega_r = omega_phi reflects the hidden SO(4) symmetry of the Kepler problem (the Laplace-Runge-Lenz vector). If omega_r != omega_phi for a 1/r potential, there is an error.

## Worked Example: Constrained System — The Relativistic Free Particle

**Problem:** Derive the Hamiltonian for a free relativistic particle starting from the reparametrization-invariant action. Demonstrate the Dirac constraint procedure for a singular Legendre transform. This targets the LLM error class of applying the standard Legendre transform to a system with a singular Hessian, which produces a Hamiltonian that is identically zero — and then declaring the system "has no dynamics."

### Setup

The reparametrization-invariant action for a free relativistic particle:
```
S = -m integral d tau sqrt(-eta_{mu nu} dx^mu/d tau  dx^nu/d tau)
```
where eta = diag(-1, +1, +1, +1) (mostly-plus convention) and tau is an arbitrary worldline parameter.

Treating x^mu (tau) as 4 generalized coordinates with velocities x-dot^mu = dx^mu/d tau:
```
L = -m sqrt(-eta_{mu nu} x-dot^mu x-dot^nu) = -m sqrt(x-dot_0^2 - x-dot_i^2)
```

### Step 1: Conjugate Momenta

```
p_mu = dL / dx-dot^mu = m eta_{mu nu} x-dot^nu / sqrt(-eta_{rho sigma} x-dot^rho x-dot^sigma)
```

This gives: p_mu = m x-dot_mu / sqrt(-x-dot^2), where x-dot^2 = eta_{mu nu} x-dot^mu x-dot^nu.

### Step 2: Check the Hessian (SINGULAR)

The Hessian W_{mu nu} = d^2 L / dx-dot^mu dx-dot^nu has rank 3, not 4. This is because L is homogeneous of degree 1 in x-dot^mu (reparametrization invariance: L(lambda x-dot) = lambda L(x-dot) for lambda > 0). By Euler's theorem: p_mu x-dot^mu = L, so H = p_mu x-dot^mu - L = 0 identically.

**det(W) = 0. The standard Legendre transform fails.**

**The typical LLM error:** Compute H = p_mu x-dot^mu - L = 0 and conclude "the Hamiltonian vanishes, so there is no time evolution." This is wrong — the system has dynamics, but it is expressed through constraints.

### Step 3: Dirac Constraint Procedure

Since the 4 momenta p_mu depend on only 3 independent ratios of the 4 velocities x-dot^mu, there must be a relation among the momenta alone. Squaring the momentum:
```
p_mu p^mu = m^2 eta_{mu nu} x-dot^mu x-dot^nu / (-eta_{rho sigma} x-dot^rho x-dot^sigma) = -m^2
```

This gives the **primary constraint**:
```
phi = p_mu p^mu + m^2 = 0     (mass-shell condition)
```

The total Hamiltonian in Dirac's formalism is:
```
H_T = H_canonical + lambda phi = 0 + lambda (p^2 + m^2) = lambda (p^2 + m^2)
```
where lambda(tau) is an undetermined Lagrange multiplier.

### Step 4: Equations of Motion

Hamilton's equations with H_T:
```
x-dot^mu = dH_T / dp_mu = 2 lambda p^mu
p-dot_mu = -dH_T / dx^mu = 0
```

So p_mu = const (free particle: momentum is conserved) and x^mu(tau) = x^mu(0) + 2 lambda p^mu tau. The multiplier lambda parametrizes the gauge freedom (choice of worldline parameter tau).

**Gauge fixing:** Choose tau = x^0 / (2 lambda p^0) (proper time gauge). Then x^0 = tau' (reparametrized), and the spatial trajectory is x^i(tau') = x^i(0) + (p^i / p^0) tau'. This is uniform motion in a straight line, as expected.

### Step 5: Constraint Classification

Check the constraint algebra:
```
{phi, phi} = {p^2 + m^2, p^2 + m^2} = 0
```

The constraint phi has vanishing Poisson bracket with itself: it is **first-class**. A first-class constraint generates a gauge symmetry (here: reparametrization of the worldline parameter tau).

**DOF count:** Start with 4 coordinates x^mu and 4 momenta p_mu (8 phase space variables). Subtract 2 per first-class constraint (1 constraint equation + 1 gauge condition): 8 - 2 = 6 phase space variables = 3 physical DOF. This is correct: a massive relativistic particle has 3 spatial DOF.

### Verification

1. **Mass-shell condition.** The constraint p^2 + m^2 = 0 expands to -E^2 + p_vec^2 + m^2 = 0, giving E = sqrt(p_vec^2 + m^2). This is the relativistic energy-momentum relation. If p^2 + m^2 = 0 does not reproduce E^2 = p^2 c^2 + m^2 c^4 (restoring c), the metric signature convention is wrong.

2. **Non-relativistic limit.** With p << m: E = m + p^2/(2m) + O(p^4/m^3). The Hamiltonian (after gauge fixing x^0 = t) becomes H = sqrt(p^2 + m^2) ~ m + p^2/(2m). Subtracting the rest mass: H_NR = p^2/(2m). Correct.

3. **Hamilton's equations reproduce Newton's first law.** dx^i/dt = dH/dp_i = p_i/E, dp_i/dt = -dH/dx_i = 0. So x^i(t) = x^i(0) + (p_i/E) t — uniform rectilinear motion. Correct.

4. **Gauge invariance.** Under tau -> tau' = f(tau), the physics (worldline in spacetime) is unchanged. The Lagrange multiplier transforms as lambda -> lambda * (d tau/d tau'). The constraint phi = 0 is tau-independent. Correct.

5. **Quantization check.** Promoting the first-class constraint to an operator: (p-hat^2 + m^2) |psi> = 0 gives the Klein-Gordon equation (-hbar^2 Box + m^2) phi = 0. This confirms the constraint procedure is consistent with the known quantum theory.
