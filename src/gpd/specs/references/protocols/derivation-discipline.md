---
load_when:
  - "derivation"
  - "proof"
  - "analytical calculation"
  - "sign tracking"
  - "convention annotation"
  - "simplification"
  - "approximation"
tier: 1
context_cost: medium
---

# Derivation Discipline

Every derivation step must be traceable, verifiable, and convention-explicit. The cost of writing two extra lines of annotation is negligible; the cost of a propagated sign error is catastrophic.

## Related Protocols

- See `integral-evaluation.md` for systematic integral handling during derivations
- See `perturbation-theory.md` for perturbative expansion bookkeeping
- See `order-of-limits.md` for identifying and handling non-commuting limits
- See `symmetry-analysis.md` for symmetry-based simplification and consistency checks

## Sign Tracking

- **Write the sign explicitly at every step.** Never write a term without its sign. Instead of "the interaction term is V(x)", write "+V(x)" or "-V(x)" with explicit justification.
- When performing integration by parts: write the boundary term explicitly, even when it vanishes. State WHY it vanishes (e.g., "vanishes for fields decaying at infinity", "vanishes by periodic boundary conditions").
- When commuting operators: write the commutator/anticommutator. `AB = BA + [A,B]`. Do not silently reorder.
- When Wick rotating: track the sign through `t = -i*tau` explicitly. Write `dt = -i*d(tau)`, substitute, and verify the Euclidean action is real and bounded below.
- When raising/lowering indices with the metric: write `g^{mu nu}` explicitly. The sign of the spatial components depends on convention.

## Convention Annotation

At every equation that involves a convention-dependent choice, annotate which convention is active:

```latex
% Convention: metric (+,-,-,-), Fourier e^{-ikx}, natural units hbar=c=1
G^R(k) = \frac{1}{k^2 - m^2 + i\epsilon}   % retarded: pole below real axis
```

When the convention matters for the sign or factor of the result, STATE IT:

- "Using Fourier convention e^{-ikx}, so the inverse transform has factor 1/(2pi)^d"
- "Metric (+,-,-,-) gives k^2 = k_0^2 - |k|^2, so on-shell k^2 = m^2 (positive)"
- "Normal ordering places creation operators left, so :a^dag a: = a^dag a (no subtraction)"

## Derivation Checkpointing

After every 3-4 derivation steps, STOP and perform a checkpoint:

1. **Dimensional analysis:** Does every term have the same dimensions? Check explicitly by restoring hbar, c, k_B if working in natural units.
2. **Evaluate at a test point:** Plug in a simple value (m=1, k=0, d=1, etc.) and verify the expression gives a sensible number.
3. **Check a known limit:** Take one accessible limit (free theory, classical, static, etc.) and verify it reproduces the known result.
4. **Verify symmetry:** Does the expression have the symmetries it should? (Hermiticity, Lorentz covariance, gauge invariance, etc.)

If ANY checkpoint fails: STOP. Do not proceed. Find the error. The error is in the last 3-4 steps.

## Simplification Discipline

When simplifying an expression:

- Write both the BEFORE and AFTER forms. Never skip intermediate steps in a simplification.
- When canceling terms: state which terms cancel and why.
- When using an identity: state the identity explicitly. "Using the Fierz identity: (bar{psi}\_1 gamma^mu psi_2)(bar{psi}\_3 gamma_mu psi_4) = ..."
- When combining fractions, completing squares, or performing partial fractions: show the algebra.
- The reader (including a future continuation agent) must be able to verify each step independently.

## Approximation Discipline

When making an approximation:

- State what is being approximated and the expansion parameter
- Write the full expression BEFORE the approximation
- Write the approximated expression AFTER
- Estimate the size of the first neglected term (the error)
- State the regime of validity: "valid for g << 1, specifically g < 0.3 for 5% accuracy"
- Never mix orders: if working to O(g^2), include ALL terms to O(g^2) before dropping O(g^3)

## Concrete Example: Propagated Sign Error in Integration by Parts

**Problem:** Compute the expectation value <x^2> for the quantum harmonic oscillator ground state.

**Wrong derivation (common LLM error):**

"The ground state is psi_0(x) = (m*omega/(pi*hbar))^{1/4} exp(-m*omega*x^2/(2*hbar)). So <x^2> = integral of x^2 |psi_0|^2 dx. Using integration by parts..."

Then the LLM performs integration by parts, silently drops the boundary term, and gets a sign error that propagates to the final answer.

**Correct derivation following this protocol:**

Step 1. State the integral with sign and conventions explicitly:
```
% Convention: natural units hbar = 1, alpha = m*omega
<x^2> = (alpha/pi)^{1/2} * integral_{-inf}^{+inf} x^2 exp(-alpha*x^2) dx   [positive, real integral]
```

Step 2. Use the Gaussian integral identity (state it explicitly, do NOT derive from scratch):
```
% Identity: integral x^{2n} exp(-alpha x^2) dx = (2n-1)!! / (2^n alpha^n) * sqrt(pi/alpha)
% For n=1: integral x^2 exp(-alpha x^2) dx = (1/(2*alpha)) * sqrt(pi/alpha)
```

Step 3. Substitute:
```
<x^2> = (alpha/pi)^{1/2} * (1/(2*alpha)) * sqrt(pi/alpha)
       = (alpha/pi)^{1/2} * sqrt(pi) / (2 * alpha^{3/2})
       = 1 / (2*alpha)
       = 1 / (2*m*omega)     [restoring dimensions: hbar / (2*m*omega)]
```

**Checkpoint:**
- Dimensional analysis: [x^2] = hbar/(m*omega) = (energy*time)/(mass*frequency) = length^2. Correct.
- Known limit: as omega -> 0 (floppy oscillator), <x^2> -> infinity. Correct (particle delocalizes).
- Known limit: as m -> infinity (heavy particle), <x^2> -> 0. Correct (classical localization).
- Cross-check: <x^2> = hbar/(2*m*omega) and E_0 = hbar*omega/2, so <V> = (1/2)*m*omega^2*<x^2> = hbar*omega/4 = E_0/2. This is the virial theorem for the harmonic oscillator. Correct.

**The wrong answer** (from the silent sign error in integration by parts) would typically give <x^2> = -1/(2*m*omega), which fails the positivity checkpoint immediately. That is why checkpointing works.

## Worked Example: Index Gymnastics Error in Electromagnetic Stress Tensor

**Problem:** Derive the Maxwell stress tensor T^{ij} from the electromagnetic Lagrangian and verify it reproduces the correct force on a charged surface. This targets the LLM error class of silently dropping terms during index contraction — particularly confusing free indices with summed indices, and misapplying the metric when raising/lowering indices.

### Step 1: State Conventions Explicitly

```
% Convention: SI units, metric diag(+1, +1, +1) for spatial indices (Euclidean 3-space)
% F_{ij} = d_i A_j - d_j A_i (spatial part of the field strength tensor)
% E_i = -d_i phi - dA_i/dt,  B_i = (1/2) epsilon_{ijk} F_{jk}
```

The electromagnetic energy-momentum tensor (symmetric, Belinfante form):

```
T^{ij} = epsilon_0 [E^i E^j + c^2 B^i B^j - (1/2) delta^{ij} (E^k E_k + c^2 B^k B_k)]
```

### Step 2: Expand Component by Component

For i = j = x (the T^{xx} component):

```
T^{xx} = epsilon_0 [E_x^2 + c^2 B_x^2 - (1/2)(E_x^2 + E_y^2 + E_z^2 + c^2(B_x^2 + B_y^2 + B_z^2))]
       = epsilon_0 [(1/2)(E_x^2 - E_y^2 - E_z^2) + (c^2/2)(B_x^2 - B_y^2 - B_z^2)]
```

**Checkpoint 1: Trace.** The trace T^{ii} = epsilon_0 [E^2 + c^2 B^2 - (3/2)(E^2 + c^2 B^2)] = -(1/2) epsilon_0 (E^2 + c^2 B^2). This should equal -(energy density), confirming T^{ii} = -u_EM. For the traceless part to be correct, this trace must be exact.

For i != j, say i = x, j = y:

```
T^{xy} = epsilon_0 [E_x E_y + c^2 B_x B_y]
```

No delta^{ij} contribution since i != j.

### Step 3: Apply to a Specific Geometry

**Charged parallel plate capacitor:** E = (sigma/epsilon_0) z_hat between plates, B = 0.

The force per unit area on the upper plate (normal n_hat = z_hat):

```
f_z = T^{zj} n_j = T^{zz} = epsilon_0 [(1/2) E_z^2 - 0 + 0]
    = epsilon_0 E_z^2 / 2
    = sigma^2 / (2 epsilon_0)
```

### Step 4: Cross-Check with Direct Coulomb Calculation

The electric field at the surface of a conductor with surface charge sigma is E_surface = sigma / (2 epsilon_0) (field from one plate, not both). The force per unit area:

```
f = sigma * E_surface = sigma * sigma / (2 epsilon_0) = sigma^2 / (2 epsilon_0)
```

Matches the stress tensor result.

**Checkpoint 2: Dimensions.** [T^{ij}] = [epsilon_0] [E^2] = (C^2/(N m^2)) * (V/m)^2 = (C^2 V^2)/(N m^4) = N/m^2 = Pa. The stress tensor has dimensions of pressure. Correct.

**Checkpoint 3: Sign.** The force on the upper plate should be attractive (toward the lower plate, in the -z direction if the lower plate is below). But we got f_z = +sigma^2/(2 epsilon_0) > 0. This is the force in the +z direction, meaning the plate is PUSHED outward. This is correct for the outer side of the plate: the field exerts a tension along the field lines, pulling the plate TOWARD the other plate from the INSIDE, and the stress tensor evaluated on the outside gives the NET outward force. The sign depends on which side of the surface you evaluate T and which direction n_hat points. The full analysis uses the discontinuity: f = T^{outside} - T^{inside}, with E = 0 inside the conductor.

### Verification

1. **Symmetry.** T^{ij} = T^{ji} (symmetric). Check: T^{xy} = epsilon_0 (E_x E_y + c^2 B_x B_y) = T^{yx}. Correct.

2. **Energy density.** -(1/3) T^{ii} = (1/6) epsilon_0 (E^2 + c^2 B^2). But the energy density is u = (1/2) epsilon_0 (E^2 + c^2 B^2). So u != -(1/3) T^{ii}. This is because the EM stress tensor is NOT traceless in 3D — it IS traceless in the 4D relativistic formulation (T^{mu}_{mu} = 0 for Maxwell). The 3D trace -(1/2) u is consistent with the 4D tracelessness: T^{00} + T^{ii} = u - u/2 - u/2... NO, T^{00} = u and T^{ii} = -u, so T^{mu}_{mu} = u - u = 0. Correct.

3. **Known result: radiation pressure.** For a plane wave with E = E_0, B = E_0/c: T^{zz} = epsilon_0 [(1/2)(0 - E_0^2) + (c^2/2)(E_0^2/c^2 - 0)] = 0? This is wrong for the direction ALONG propagation. The issue: for a z-propagating wave, E is in x, B is in y. So: T^{zz} = epsilon_0 [0 + 0 - (1/2)(E_0^2 + E_0^2)] = -epsilon_0 E_0^2. But we expect positive radiation pressure. The resolution: the MOMENTUM FLUX is -T^{zz} with proper sign convention, OR the issue is the averaging over one cycle. Time-averaged: <T^{zz}> = -(1/2) epsilon_0 E_0^2. The radiation pressure (force per area on a perfectly absorbing surface) is <S>/c = epsilon_0 E_0^2/2, which equals |<T^{zz}>|. The sign depends on the convention for which direction is "into" the surface.

**The typical LLM error:** Confusing the trace structure (writing T^{ii} = 0 as if 3D Maxwell is traceless), dropping the delta^{ij} term, or getting the factor of 1/2 wrong in the energy density term. The component-by-component expansion in Step 2 and the dimensional/trace checkpoints catch these errors.

## Worked Example: Mixed-Order Expansion in the Relativistic Kinetic Energy

**Problem:** Expand the relativistic kinetic energy T = (gamma - 1) m c^2 to order (v/c)^4 and verify that the result reproduces the non-relativistic limit plus the leading relativistic correction. This targets the LLM error class of including some terms at a given order while silently dropping others (mixing orders), which produces results that look plausible but are quantitatively wrong.

### Step 1: State the Full Expression and Expansion Parameter

```
% Convention: v = particle speed, c = speed of light, beta = v/c
% Expansion parameter: beta^2 = v^2/c^2 << 1 (non-relativistic regime)
T = mc^2 (1/sqrt(1 - beta^2) - 1)
```

### Step 2: Expand Systematically Using the Binomial Series

The binomial expansion of (1 - x)^{-1/2} for |x| < 1:

```
(1 - x)^{-1/2} = 1 + (1/2)x + (3/8)x^2 + (5/16)x^3 + ...
```

**State the identity explicitly:** This is the binomial series with exponent n = -1/2. The coefficients are C(-1/2, k) = (-1/2)(-3/2)...(-1/2 - k + 1)/k!

Substituting x = beta^2:

```
gamma = 1 + (1/2) beta^2 + (3/8) beta^4 + (5/16) beta^6 + O(beta^8)
```

Therefore:

```
T = mc^2 [(1/2) beta^2 + (3/8) beta^4 + (5/16) beta^6 + O(beta^8)]
  = (1/2) mv^2 + (3/8) mv^4/c^2 + (5/16) mv^6/c^4 + O(v^8/c^6)
```

### Step 3: The LLM Mixing-Order Error

**Common LLM error:** An LLM asked to compute the "next correction beyond Newtonian mechanics" often writes:

```
T_WRONG = (1/2) mv^2 + (3/8) mv^2 * (v/c)^2
```

This looks correct, but LLMs frequently then substitute v = p/m (the non-relativistic momentum relation) to get:

```
T_WRONG = p^2/(2m) + (3/8) p^4/(m^3 c^2)
```

**This is WRONG** because v = p/m is only the non-relativistic relation. The relativistic momentum is p = gamma m v, so:

```
v = p/(gamma m) = p/m * (1 - (1/2) beta^2 + ...) = p/m * (1 - p^2/(2m^2c^2) + ...)
```

Substituting consistently to O(p^4):

```
v^2 = p^2/m^2 - p^4/(m^4 c^2) + O(p^6)
v^4 = p^4/m^4 + O(p^6)
```

The CORRECT expansion in terms of momentum:

```
T = (1/2) m [p^2/m^2 - p^4/(m^4 c^2)] + (3/8) m [p^4/m^4]/c^2 + O(p^6)
  = p^2/(2m) - p^4/(2m^3 c^2) + 3 p^4/(8 m^3 c^2) + O(p^6)
  = p^2/(2m) - p^4/(8 m^3 c^2) + O(p^6)
```

**Checkpoint:** This should match the exact relativistic dispersion relation expanded to O(p^4):

```
E = sqrt(p^2 c^2 + m^2 c^4) = mc^2 sqrt(1 + p^2/(m^2c^2))
  = mc^2 [1 + p^2/(2m^2c^2) - p^4/(8m^4c^4) + ...]
T = E - mc^2 = p^2/(2m) - p^4/(8m^3c^2) + O(p^6)
```

Confirmed: the coefficient is **-1/8**, not **+3/8** as the naive substitution gives.

### Step 4: Identify the Discipline Violation

The error occurred because the LLM:

1. **Mixed orders in the v -> p substitution.** Used v = p/m (zeroth-order relation) in the O(v^4) correction term, but this introduces an O(v^4) error from the neglected correction to v = p/(gamma m). To get the v^4 term in T(p) correct, you need v(p) to O(v^3) or equivalently v^2(p) to O(p^4).

2. **Violated the approximation discipline.** The rule is: "include ALL terms at a given order before dropping higher-order corrections." At O(p^4), there are contributions from both the (3/8) mv^4/c^2 term AND the correction to v^2 = p^2/m^2 in the leading (1/2) mv^2 term. Keeping one and dropping the other is a mixed-order error.

### Verification

1. **Dimensional analysis.** [p^4/(m^3 c^2)] = (kg m/s)^4 / (kg^3 (m/s)^2) = kg m^2/s^2 = Joules. Correct.

2. **Sign check.** The relativistic correction -p^4/(8 m^3 c^2) is NEGATIVE: kinetic energy grows slower than p^2/(2m) at high momentum (because the velocity saturates at c). If the correction is positive, the energy grows faster than Newtonian, which violates relativity.

3. **Hydrogen atom cross-check.** The leading relativistic correction to the hydrogen atom energy levels is <-p^4/(8 m_e^3 c^2)>. Using the naive LLM answer <+3 p^4/(8 m_e^3 c^2)> gives the WRONG SIGN for the fine structure, predicting that relativistic effects shift levels UP instead of DOWN. The observed fine structure splitting has the correct (negative) sign.

4. **Order tracking.** Write every term with its order: T = p^2/(2m) [O(p^2)] - p^4/(8 m^3 c^2) [O(p^4)] + O(p^6). Each subsequent term is suppressed by (p/(mc))^2 ~ (v/c)^2. For v/c = 0.01: the correction is 1.25 x 10^{-5} of the leading term.

**The typical LLM error** produces a coefficient of +3/8 instead of -1/8 (or the wrong sign) for the p^4 correction, leading to wrong fine structure predictions. The checkpointing discipline catches this immediately: the sign must be negative (relativistic energy grows sublinearly with momentum), and the exact dispersion relation provides a simple cross-check.
