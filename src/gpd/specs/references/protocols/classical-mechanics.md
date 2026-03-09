---
load_when:
  - "classical mechanics"
  - "Lagrangian mechanics"
  - "Hamiltonian mechanics"
  - "Poisson bracket"
  - "canonical transformation"
  - "Hamilton-Jacobi"
  - "rigid body"
  - "central force"
  - "orbital mechanics"
  - "phase space"
tier: 2
context_cost: medium
---

# Classical Mechanics Protocol

Classical mechanics underpins all of physics. Errors here propagate into quantum mechanics (via canonical quantization), statistical mechanics (via phase space), and field theory (via the classical action). LLMs commonly make errors in generalized coordinates, constraint handling, and the transition between Lagrangian and Hamiltonian formulations.

## Related Protocols
- `hamiltonian-mechanics.md` -- Deep Hamiltonian formulation: Legendre transform, Dirac constraints, canonical transformations, Hamilton-Jacobi, symplectic structure
- `derivation-discipline.md` -- Rigorous step-by-step derivation practices
- `symmetry-analysis.md` -- Noether's theorem connects symmetries to conservation laws
- `order-of-limits.md` -- Classical limit (hbar -> 0) and its subtleties
- `variational-methods.md` -- Variational principles in classical mechanics

## Step 1: Formulation Choice

Choose the formulation BEFORE computing:

| Formulation | Best For | Watch Out For |
|---|---|---|
| **Newtonian** (F = ma) | Simple systems, few constraints, intuitive force analysis | Constraint forces must be tracked; vector equations can hide structure |
| **Lagrangian** (L = T - V) | Constrained systems, generalized coordinates, symmetry analysis | Sign of V (L = T - V, not T + V); correct kinetic energy in curvilinear coords |
| **Hamiltonian** (H, phase space) | Canonical transformations, quantum connection, integrable systems | Legendre transform requires invertibility of p = dL/dq-dot; H != T + V for velocity-dependent potentials |
| **Hamilton-Jacobi** | Separation of variables, action-angle variables, classical limit of QM | Generating function must be correct type (F1, F2, F3, F4); Hamilton's principal function vs characteristic function |

## Step 2: Generalized Coordinates

1. **Count degrees of freedom.** N particles in 3D with k holonomic constraints: DOF = 3N - k. The number of generalized coordinates MUST equal the DOF.
2. **Choose coordinates that respect constraints.** Good coordinates make constraints disappear from the equations of motion. Bad coordinates require Lagrange multipliers.
3. **Verify completeness.** Can every configuration be reached by varying the generalized coordinates? If not, coordinates are incomplete.
4. **Verify independence.** Are any coordinates redundant? If the Hessian matrix d^2L/dq-dot_i dq-dot_j is singular, the coordinates are not independent.

### Common Errors in Generalized Coordinates

- **Wrong kinetic energy.** In curvilinear coordinates, T is NOT simply (1/2)m(q-dot_1^2 + q-dot_2^2 + ...). The metric tensor g_ij matters: T = (1/2) m g_ij q-dot^i q-dot^j. In spherical coordinates: T = (1/2)m(r-dot^2 + r^2 theta-dot^2 + r^2 sin^2(theta) phi-dot^2).
- **Forgetting cross terms.** When the kinetic energy involves cross terms (e.g., Coriolis terms in rotating frames), the mass matrix is not diagonal. The Euler-Lagrange equations will have extra terms.
- **Non-inertial frame errors.** In rotating frames with angular velocity Omega: L = (1/2)m|v_rot + Omega x r|^2 - V. This produces Coriolis (2m v x Omega) and centrifugal (m Omega x (Omega x r)) terms. Do NOT add these by hand to the Newtonian equations and then also include them in the Lagrangian.

## Step 3: Constraints

| Constraint Type | Example | Method |
|---|---|---|
| **Holonomic** | Particle on sphere: x^2 + y^2 + z^2 = R^2 | Eliminate via generalized coordinates (theta, phi) |
| **Non-holonomic** | Rolling without slipping: v = R omega (involves velocities, not integrable) | Lagrange multipliers or d'Alembert principle; cannot simply reduce coordinates |
| **Rheonomic** | Time-dependent constraint: bead on rotating hoop | L depends explicitly on t; energy is NOT conserved (H != const) |

**Critical check:** For non-holonomic constraints, verify the constraint is actually non-holonomic. Many constraints that look non-holonomic (involving velocities) are actually holonomic in disguise (integrable to a configuration-space constraint).

## Step 4: Equations of Motion

### Lagrangian Path

1. Write L = T - V in generalized coordinates.
2. Compute d/dt(dL/dq-dot_i) - dL/dq_i = 0 for each coordinate.
3. **Verify:** Number of equations = number of DOF.
4. **Check dimensions:** Each term in the equation must have the same dimensions.
5. **Check limiting cases:** Reduce to known results (small oscillations, free particle, etc.).

### Hamiltonian Path

1. From L, compute conjugate momenta: p_i = dL/dq-dot_i.
2. **Check invertibility:** Can you solve for all q-dot_i in terms of (q, p)? If not, the Legendre transform is singular (indicates gauge symmetry or constraint).
3. Compute H = sum_i p_i q-dot_i - L, expressed entirely in terms of (q, p).
4. Hamilton's equations: q-dot_i = dH/dp_i, p-dot_i = -dH/dq_i.
5. **Verify:** {q_i, H} = q-dot_i and {p_i, H} = p-dot_i using Poisson brackets.

## Step 5: Conservation Laws

For every ignorable coordinate q_i (dL/dq_i = 0), the conjugate momentum p_i is conserved.

| Symmetry | Conserved Quantity | Noether Current |
|---|---|---|
| Time translation | Energy H (if L has no explicit t dependence) | H = T + V only if V is velocity-independent and coordinates are natural |
| Space translation | Linear momentum p | p_i = m v_i only in Cartesian coordinates |
| Rotation | Angular momentum L | L = r x p = r x (m v) in Cartesian; in other coordinates, use p_i = dL/dq-dot_i |
| Galilean boost | Center of mass motion | K = m R_cm - p t |

**Common LLM error:** Stating H = T + V without checking. H = T + V only when: (a) the kinetic energy is a homogeneous quadratic function of the velocities (T = (1/2) g_ij q-dot^i q-dot^j with g_ij independent of q-dot), AND (b) the potential V does not depend on velocities. For a charged particle in a magnetic field (velocity-dependent potential A . v), H != T + V.

## Step 6: Small Oscillations

1. Find equilibrium: dV/dq_i = 0 at q = q_0.
2. Expand: V ~ (1/2) V_ij (q_i - q_0_i)(q_j - q_0_j) where V_ij = d^2V/dq_i dq_j evaluated at q_0.
3. Similarly expand T = (1/2) T_ij q-dot_i q-dot_j (T_ij evaluated at q_0).
4. Normal modes: solve det(V - omega^2 T) = 0 for eigenfrequencies omega.
5. **Check:** All omega^2 must be non-negative for stable equilibrium. If any omega^2 < 0, the equilibrium is unstable.
6. **Check:** Number of normal modes = number of DOF. Zero-frequency modes correspond to flat directions (symmetries of V).

## Concrete Example: Wrong Hamiltonian from Velocity-Dependent Potential

**Problem:** Find H for a charged particle in electromagnetic fields.

**Wrong approach (common LLM error):** "L = T - V = (1/2)mv^2 - q*phi, so H = T + V = (1/2)mv^2 + q*phi."

This misses the magnetic field entirely.

**Correct approach:**

The Lagrangian is L = (1/2)m v^2 - q phi + q A . v, where A is the vector potential.

The canonical momentum is p = dL/dv = m v + q A. Note p != m v.

The Hamiltonian is H = p . v - L = (p - qA)^2 / (2m) + q phi.

In terms of canonical variables: H = |p - qA|^2 / (2m) + q phi.

**Verification:**
- Hamilton's equations give m dv/dt = q(E + v x B): correct Lorentz force.
- H is the total energy (kinetic + potential), but the kinetic energy is (p - qA)^2/(2m) = mv^2/2, NOT p^2/(2m).
- Setting A = 0 recovers H = p^2/(2m) + q phi: correct electrostatics.

## Concrete Example: Constraint Forces and Lagrange Multipliers

**Problem:** Bead of mass m sliding on a frictionless hoop of radius R rotating about its vertical axis with angular velocity omega.

**Setup:** Holonomic constraint fixes r = R and phi = omega*t. One DOF: theta (polar angle from top of hoop).

L = (1/2)m R^2 (theta-dot^2 + omega^2 sin^2(theta)) - mgR(1 - cos(theta))

Equation of motion: R theta-double-dot = (omega^2 cos(theta) - g/R) sin(theta)

**Equilibria:** sin(theta) = 0 gives theta = 0 (top) and theta = pi (bottom). If omega^2 R > g, there is a third equilibrium at cos(theta_0) = g/(omega^2 R).

**Verification:**
- omega -> 0: Reduces to simple pendulum, theta-double-dot = -(g/R) sin(theta). Correct.
- g -> 0: theta-double-dot = omega^2 cos(theta) sin(theta). Bead pushed to equator by centrifugal force. Correct.
- The new equilibrium appears precisely when centrifugal acceleration omega^2 R exceeds g. At this bifurcation, the bottom equilibrium becomes unstable. This is a classic pitchfork bifurcation.

**Energy:** H is NOT conserved because the constraint is rheonomic (time-dependent phi = omega*t). The hoop does work on the bead. The Jacobi integral h = T_2 - V (where T_2 is the part of T quadratic in theta-dot) IS conserved: h = (1/2)mR^2 theta-dot^2 - (1/2)mR^2 omega^2 sin^2(theta) + mgR(1-cos(theta)).

## Worked Example: Double Pendulum Normal Modes With Correct Mass Matrix

**Problem:** Find the normal mode frequencies of a double pendulum (two identical masses m, two identical rods of length l) for small oscillations about the downward equilibrium. This targets the LLM error class of writing the wrong kinetic energy in generalized coordinates — specifically, omitting the cross-terms in the mass matrix.

### Step 1: Generalized Coordinates

Two DOF: theta_1 (angle of upper rod from vertical) and theta_2 (angle of lower rod from vertical). Note: theta_2 is measured from the vertical, NOT from the upper rod.

Position of mass 1: (x_1, y_1) = (l sin theta_1, -l cos theta_1)
Position of mass 2: (x_2, y_2) = (l sin theta_1 + l sin theta_2, -l cos theta_1 - l cos theta_2)

### Step 2: Kinetic Energy (the critical step)

Velocity of mass 1:
```
x_1_dot = l theta_1_dot cos theta_1
y_1_dot = l theta_1_dot sin theta_1
T_1 = (1/2) m l^2 theta_1_dot^2
```

Velocity of mass 2:
```
x_2_dot = l theta_1_dot cos theta_1 + l theta_2_dot cos theta_2
y_2_dot = l theta_1_dot sin theta_1 + l theta_2_dot sin theta_2
T_2 = (1/2) m (x_2_dot^2 + y_2_dot^2)
   = (1/2) m l^2 [theta_1_dot^2 + theta_2_dot^2 + 2 theta_1_dot theta_2_dot cos(theta_1 - theta_2)]
```

Total kinetic energy:
```
T = T_1 + T_2 = (1/2) m l^2 [2 theta_1_dot^2 + theta_2_dot^2 + 2 theta_1_dot theta_2_dot cos(theta_1 - theta_2)]
```

**The common LLM error:** Writing T = (1/2) m l^2 (theta_1_dot^2 + theta_2_dot^2) — MISSING the cross-term 2 theta_1_dot theta_2_dot cos(theta_1 - theta_2) AND the factor of 2 on theta_1_dot^2 (mass 2 also moves when theta_1 changes). This produces completely wrong normal mode frequencies.

### Step 3: Potential Energy

```
V = -m g l cos theta_1 - m g (l cos theta_1 + l cos theta_2)
  = -m g l (2 cos theta_1 + cos theta_2)
```

### Step 4: Linearize for Small Oscillations

Expand to quadratic order: cos theta ~ 1 - theta^2/2, cos(theta_1 - theta_2) ~ 1.

Mass matrix T_ij (from T = (1/2) T_ij theta_i_dot theta_j_dot):
```
T = m l^2 [2    1]
           [1    1]
```

Stiffness matrix V_ij (from V = const + (1/2) V_ij theta_i theta_j):
```
V = m g l [2    0]
           [0    1]
```

### Step 5: Eigenvalue Problem

Solve det(V - omega^2 T) = 0:
```
det([2mgl - 2ml^2 omega^2,    -ml^2 omega^2     ]) = 0
   ([-ml^2 omega^2,            mgl - ml^2 omega^2])
```

Let lambda = l omega^2 / g:

```
det([2 - 2 lambda,    -lambda    ]) = 0
   ([-lambda,          1 - lambda])

(2 - 2 lambda)(1 - lambda) - lambda^2 = 0
2 - 4 lambda + 2 lambda^2 - lambda^2 = 0
lambda^2 - 4 lambda + 2 = 0
lambda = 2 +/- sqrt(2)
```

Normal mode frequencies:
```
omega_1^2 = (2 - sqrt(2)) g/l    (slow mode: in-phase oscillation)
omega_2^2 = (2 + sqrt(2)) g/l    (fast mode: out-of-phase oscillation)
```

### Verification

1. **Dimension check.** [omega^2] = [g/l] = [acceleration/length] = [1/time^2]. Correct.

2. **Product of frequencies.** omega_1^2 * omega_2^2 = (4 - 2) g^2/l^2 = 2 g^2/l^2. From the eigenvalue equation: product of eigenvalues = det(V)/det(T) = (2mgl)(mgl) / (m^2 l^4 (2-1)) = 2g^2/l^2. Matches.

3. **Sum of frequencies.** omega_1^2 + omega_2^2 = 4 g/l. From the eigenvalue equation: sum of eigenvalues = trace(T^{-1} V) = trace of [1, -1; -1, 2] . [2g/l, 0; 0, g/l] = trace of [2g/l, -g/l; -2g/l, 2g/l] = 4g/l. Matches.

4. **Limiting cases.**
   - g -> 0: both omega -> 0 (no restoring force). Correct.
   - Rigid lower rod (theta_2 = theta_1, single pendulum of total mass 2m and effective length): the in-phase mode frequency omega_1^2 = (2 - sqrt(2)) g/l ~ 0.586 g/l, which is close to but not exactly g/(2l) because the double pendulum is NOT equivalent to a simple pendulum. The exact simple-pendulum-of-length-2l frequency would be g/(2l) = 0.5 g/l. The difference is physical.

5. **The wrong answer** from the missing cross-term would be: det(V - omega^2 T_wrong) = 0 with T_wrong = ml^2 * I, giving omega^2 = 2g/l and omega^2 = g/l. These are the frequencies of two INDEPENDENT pendula, missing all coupling effects. The in-phase/out-of-phase splitting is absent, which is the tell-tale sign of a missing cross-term.

## Worked Example: Precession of a Symmetric Top via Euler Equations

**Problem:** A symmetric top (moments I_1 = I_2 = I, I_3) spins about its symmetry axis with angular velocity Omega_3 and is tilted at angle theta from the vertical. Compute the precession rate using the Euler equations. This targets the LLM error class of confusing body-frame and lab-frame angular velocities, and incorrect application of the Euler equations.

### Step 1: Euler Equations

For a torque-free symmetric top in the body frame:

```
I_1 dOmega_1/dt - (I_2 - I_3) Omega_2 Omega_3 = N_1
I_2 dOmega_2/dt - (I_3 - I_1) Omega_3 Omega_1 = N_2
I_3 dOmega_3/dt - (I_1 - I_2) Omega_1 Omega_2 = N_3
```

For gravity acting on the center of mass at distance l from the pivot: N = M g l sin(theta) (torque about a horizontal axis). In the body frame: N_1 = Mgl sin(theta), N_2 = 0, N_3 = 0 (for steady precession about the vertical).

### Step 2: Steady Precession Ansatz

For uniform precession at rate omega_p with constant tilt theta: Omega_1 = omega_p sin(theta), Omega_2 = 0, Omega_3 = constant (spin about symmetry axis). The derivatives dOmega_1/dt = dOmega_2/dt = 0 for steady precession.

From Euler equation 2: -(I_3 - I_1) Omega_3 * omega_p sin(theta) = 0 is not zero unless we account for the time-dependent body-frame components properly. For steady precession the correct approach uses:

```
I_1 * 0 - (I - I_3) * 0 * Omega_3 = Mgl sin(theta) ... (wrong)
```

The subtlety: in the body frame during steady precession, Omega_1 and Omega_2 are time-dependent (they rotate). The correct approach uses the angular momentum:

### Step 3: Angular Momentum Method (Cleaner)

The angular momentum vector: L = I omega_p sin(theta) (horizontal component) and L_3 = I_3 Omega_3 (component along symmetry axis).

The total angular momentum magnitude: L_z = I_3 Omega_3 cos(theta) + I omega_p sin^2(theta).

For steady precession, the torque equals the rate of change of angular momentum:

```
N = dL/dt = omega_p x L
```

The horizontal component of L precesses at rate omega_p. The torque magnitude Mgl sin(theta) must equal omega_p * L_horizontal:

```
Mgl sin(theta) = omega_p * I_3 Omega_3 sin(theta)
```

Canceling sin(theta):

```
omega_p = Mgl / (I_3 Omega_3)
```

This is the **fast-spinning top approximation** (gyroscopic limit), valid when I_3 Omega_3 >> I omega_p (spin angular momentum dominates).

### Verification

1. **Dimensional check:** [omega_p] = [M g l / (I_3 Omega_3)] = kg * m/s^2 * m / (kg m^2 * rad/s) = rad/s. Correct.

2. **Fast spin limit:** As Omega_3 increases, omega_p decreases (faster spin = slower precession). This matches physical intuition: a faster-spinning gyroscope precesses more slowly.

3. **theta independence:** The precession rate is independent of tilt angle (in the gyroscopic limit). This is counterintuitive but correct for fast tops.

4. **Known limit — sleeping top:** When Omega_3 > Omega_crit = sqrt(4MglI/(I_3^2)), the vertical position (theta = 0) is stable and the top does not precess. Below this spin, it precesses and nutates.

5. **Nutation check:** The full solution includes fast nutation at frequency omega_n ~ I_3 Omega_3 / I on top of the slow precession. If your solution shows only precession, it is the time-averaged result (valid for omega_n >> omega_p).
