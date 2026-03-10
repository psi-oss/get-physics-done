---
load_when:
  - "integral"
  - "contour integral"
  - "residue"
  - "branch cut"
  - "dimensional regularization"
  - "cutoff regularization"
  - "convergence region"
tier: 2
context_cost: low
---

# Integral Evaluation Protocol

Integrals in physics are rarely straightforward. They may diverge, have branch cuts, require regularization, or be conditionally convergent. Treating them carelessly produces wrong answers that look right.

## Related Protocols

- See `analytic-continuation.md` for contour deformation and Wick rotation of integrals
- See `perturbation-theory.md` for loop integral evaluation in perturbative QFT
- See `derivation-discipline.md` for sign tracking and convention annotation during integration
- See `numerical-computation.md` for numerical quadrature and convergence testing of integrals

## Before Evaluating

1. **State the convergence region.** For which values of the parameters does this integral converge? Check both UV (large k or x) and IR (small k or x) behavior.

   - Power counting: if the integrand goes as k^{d-1} \* k^{-n} for large k, convergent when n > d.
   - If conditionally convergent: state the regularization that makes it absolutely convergent.

2. **Identify ALL poles.** Where does the integrand blow up?

   - For each pole: compute its residue.
   - Determine which poles are enclosed by the contour.
   - For poles on the real axis: specify the i\*epsilon prescription and justify it physically (retarded, advanced, Feynman, etc.).

3. **Describe the integration contour explicitly.**

   - For real-line integrals: state the direction and any deformation.
   - For contour integrals: describe the contour (which poles inside, which outside, contribution from arcs).
   - For integrals along branch cuts: specify the branch cut location and the discontinuity across it.

4. **Track branch cuts for multi-valued functions.**
   - log(z): branch cut typically on negative real axis. State which sheet.
   - sqrt(z): branch cut on negative real axis. State sign convention.
   - (z - z_0)^alpha for non-integer alpha: specify branch cut.
   - After evaluation: verify monodromy (going around the branch point returns to the correct sheet).

## During Evaluation

- When deforming a contour: verify no poles or branch cuts are crossed. If they are, account for their contributions.
- When using Cauchy's theorem: state which poles contribute and sum their residues.
- When performing a Wick rotation: verify the integrand has no poles in the quadrant being rotated through. Track the Jacobian: dk_0 = i\*dk_4 (the factor of i).
- When using integral tables (Gradshteyn-Ryzhik, etc.): state the formula number and verify parameter ranges.

## For Regularized Integrals

- **Dimensional regularization:** d = 4 - 2\*epsilon. Track the mass scale mu that enters to maintain correct dimensions. Write results in terms of 1/epsilon poles and finite parts.
- **Cutoff regularization:** State UV cutoff Lambda and/or IR cutoff lambda. Separate the result into Lambda-dependent and Lambda-independent parts.
- **Zeta function / analytic continuation:** State the analytic continuation explicitly. Verify it matches the original integral in the convergent region.
- **Scheme independence:** After regularizing, verify that physical observables (cross sections, binding energies, etc.) are scheme-independent. Verify that different schemes give the same answer for these quantities.

## After Evaluation

- **Check dimensions** of the result. An integral over d^d k of a function with dimensions [mass^{-n}] should give dimensions [mass^{d-n}].
- **Check known limits.** If the integral has a known value for special parameter choices, verify.
- **Check reality/positivity.** A probability, a cross section, a spectral weight must be real and non-negative.

## Concrete Example: Wrong Contour Integral from Missed Branch Cut

**Problem:** Evaluate I = integral_{-inf}^{+inf} dx / (x^2 + a^2)^{3/2} for real a > 0.

**Wrong approach (common LLM error):** "Close the contour in the upper half-plane, pick up the residue at x = ia."

This is wrong because (x^2 + a^2)^{3/2} has a BRANCH POINT at x = ia, not a pole. You cannot use the residue theorem directly.

**Correct approach following this protocol:**

1. **Convergence check:** Integrand ~ x^{-3} for large |x|, so the integral converges (no regularization needed).

2. **Identify singularity structure:** x^2 + a^2 = (x - ia)(x + ia). The function (x^2 + a^2)^{3/2} has branch points at x = +/- ia, not poles.

3. **Choose method:** For this integrand, use the substitution x = a*tan(theta):
   ```
   dx = a*sec^2(theta) d(theta)
   x^2 + a^2 = a^2*sec^2(theta)
   (x^2 + a^2)^{3/2} = a^3*|sec(theta)|^3
   ```

4. **Evaluate:**
   ```
   I = integral_{-pi/2}^{+pi/2} a*sec^2(theta) / (a^3 * sec^3(theta)) d(theta)
     = (1/a^2) * integral_{-pi/2}^{+pi/2} cos(theta) d(theta)
     = (1/a^2) * [sin(theta)]_{-pi/2}^{+pi/2}
     = (1/a^2) * (1 - (-1))
     = 2/a^2
   ```

**Checkpoint:**
- Dimensional analysis: [I] = [length / length^3] = [1/length^2] = 1/a^2. Correct.
- Scaling: I(lambda*a) = 2/(lambda*a)^2 = I(a)/lambda^2. The integrand scales as lambda^{-3} and the integration measure as lambda^1, giving lambda^{-2}. Correct.
- Numerical cross-check at a=1: I = 2. Numerical integration of 1/(x^2+1)^{3/2} gives 2.000. Correct.

**The typical LLM error** would give I = pi/a^2 or I = 1/a^2 from incorrect residue computation at a branch point, failing the numerical cross-check.

## Worked Example: Gaussian Integral with Linear Term — Completing the Square

**Problem:** Evaluate the d-dimensional Gaussian integral I = integral d^d k / (2pi)^d * exp(-a k^2 + b . k) where a > 0 and b is a d-dimensional vector. This targets the LLM error class of sign errors in completing the square, wrong factors of pi in Gaussian integrals, and incorrect dimensional scaling.

### Step 1: Complete the Square

```
-a k^2 + b . k = -a (k - b/(2a))^2 + b^2/(4a)
```

Shift k -> k + b/(2a). The measure d^d k is translation-invariant (no Jacobian needed for a linear shift).

```
I = exp(b^2/(4a)) * integral d^d k / (2pi)^d * exp(-a k^2)
```

### Step 2: Evaluate the Gaussian

The d-dimensional Gaussian integral:

```
integral d^d k exp(-a k^2) = (pi/a)^{d/2}
```

So:

```
I = (pi/a)^{d/2} / (2pi)^d * exp(b^2/(4a))
  = 1 / (4pi a)^{d/2} * exp(b^2/(4a))
```

### Step 3: Verify Special Cases

**d = 1:** I = 1/sqrt(4pi a) * exp(b^2/(4a)). Check: integral_{-inf}^{inf} dk/(2pi) * exp(-a k^2 + b k) = 1/(2pi) * sqrt(pi/a) * exp(b^2/(4a)) = 1/sqrt(4pi a) * exp(b^2/(4a)). Correct.

**b = 0:** I = 1/(4pi a)^{d/2}. This is the standard free propagator in position space at x = 0.

**d = 4 (Euclidean QFT):** I = 1/(4pi a)^2 * exp(b^2/(4a)) = 1/(16 pi^2 a^2) * exp(b^2/(4a)). This is the form that appears in one-loop Feynman integrals after Feynman parameterization.

### Verification

1. **Dimensional check:** [I] = [length^{-d}] (since k has dimensions of 1/length and the integral is over d^d k). [1/(4pi a)^{d/2}] = [1/a^{d/2}]. If a has dimensions of length^2: [I] = length^{-d}. Correct.

2. **Positivity:** I > 0 for all real a > 0 and real b. If I < 0, there is a sign error in the exponent.

3. **Saddle point check:** The exponent is maximized at k = b/(2a), giving the value b^2/(4a). The integral is dominated by the neighborhood of this saddle point. The prefactor (4pi a)^{-d/2} is the fluctuation determinant.

4. **Common LLM errors:** (a) Forgetting the (2pi)^d in the measure, giving (pi/a)^{d/2} instead of (pi/a)^{d/2}/(2pi)^d = (4pi a)^{-d/2}. (b) Getting the sign in the exponent wrong: writing exp(-b^2/(4a)) instead of exp(+b^2/(4a)). (c) Using sqrt(2pi a) instead of sqrt(pi/a) for the 1D Gaussian normalization.

## Worked Example: Wick Rotation of the Feynman Propagator — Pole Avoidance

**Problem:** Evaluate the momentum-space loop integral I = integral d^4k/(2pi)^4 * 1/((k^2 - m^2 + i epsilon)((k-p)^2 - m^2 + i epsilon)) in Minkowski space by Wick rotating to Euclidean space. This targets the LLM error class of rotating the k_0 contour through a pole (invalidating the Wick rotation), dropping the Jacobian factor of i from dk_0 = i dk_4, and using the wrong sign for the Euclidean propagator.

### Step 1: Locate the Poles in the k_0 Plane

The first propagator 1/(k^2 - m^2 + i epsilon) = 1/(k_0^2 - omega_k^2 + i epsilon) where omega_k = sqrt(k^2 + m^2). The poles are at:

```
k_0 = +omega_k - i epsilon    (slightly below the real axis)
k_0 = -omega_k + i epsilon    (slightly above the real axis)
```

The second propagator 1/((k-p)^2 - m^2 + i epsilon) has poles at:

```
k_0 = p_0 + omega_{k-p} - i epsilon    (below real axis, shifted by p_0)
k_0 = p_0 - omega_{k-p} + i epsilon    (above real axis, shifted by p_0)
```

**Checkpoint:** The Feynman i epsilon prescription places positive-energy poles slightly below the real axis and negative-energy poles slightly above. This ensures time-ordered propagation.

### Step 2: Verify the Wick Rotation is Valid

The Wick rotation rotates the k_0 contour from the real axis to the imaginary axis: k_0 -> i k_4. This is a 90-degree counterclockwise rotation in the k_0 plane.

**Critical check:** Are there poles in the first and third quadrants (the quadrants swept by the rotation)?

- First quadrant (Re k_0 > 0, Im k_0 > 0): The pole at k_0 = +omega_k - i epsilon is in the FOURTH quadrant (below real axis). The pole at k_0 = p_0 - omega_{k-p} + i epsilon is above the real axis but could be in the first or second quadrant depending on the sign of p_0 - omega_{k-p}.

**For p_0 < omega_{k-p}:** This pole has Re(k_0) < 0, so it is in the second quadrant. The first quadrant is clear. Wick rotation is valid.

**For p_0 > omega_{k-p} (timelike p with large energy):** This pole has Re(k_0) > 0 and Im(k_0) > 0, placing it in the FIRST quadrant. The Wick rotation sweeps through this pole, and its residue must be added separately.

For the standard case of spacelike or small timelike external momentum, the Wick rotation is safe.

### Step 3: Perform the Wick Rotation

Set k_0 = i k_4 with k_4 real. The Jacobian:

```
dk_0 = i dk_4
```

The Minkowski metric k^2 = k_0^2 - |k|^2 becomes:

```
k^2 = (i k_4)^2 - |k|^2 = -k_4^2 - |k|^2 = -k_E^2
```

where k_E^2 = k_4^2 + |k|^2 is the Euclidean momentum squared (positive definite).

The propagator transforms:

```
1/(k^2 - m^2 + i epsilon) -> 1/(-k_E^2 - m^2) = -1/(k_E^2 + m^2)
```

The measure transforms (including the Jacobian):

```
d^4k = dk_0 d^3k -> i dk_4 d^3k = i d^4k_E
```

### Step 4: Write the Euclidean Integral

```
I = i * integral d^4k_E/(2pi)^4 * 1/((k_E^2 + m^2)((k_E - p_E)^2 + m^2))
```

where p_E is the Euclidean version of the external momentum (p_4 = -i p_0, p_E^2 = p_4^2 + |p|^2 = -p^2 for spacelike p).

**Checkpoint:** The Euclidean propagator 1/(k_E^2 + m^2) is manifestly positive and has NO poles on the real k_4 axis. This is the whole point of Wick rotation — the Euclidean integral is well-defined without any i epsilon.

### Step 5: Common LLM Errors

**Error 1: Missing factor of i.** Forgetting dk_0 = i dk_4 drops the overall factor of i. The Euclidean integral must carry this factor: I_Minkowski = i * I_Euclidean. Forgetting it introduces a factor of i error that propagates to the imaginary part of the amplitude.

**Error 2: Wrong sign in Euclidean propagator.** Writing 1/(k_E^2 - m^2) instead of 1/(k_E^2 + m^2). The minus sign from k^2 = -k_E^2 flips the sign in front of m^2. With the wrong sign, the Euclidean propagator has poles at |k_E| = m, making the integral diverge along a sphere in Euclidean momentum space.

**Error 3: Rotating through a pole.** For timelike external momentum p^2 > 4m^2 (above threshold), poles from the second propagator enter the first quadrant. Blindly Wick-rotating without checking produces wrong results. The correct procedure: (a) verify pole locations, (b) if a pole is in the rotation quadrant, add its residue as a separate contribution, or (c) use Feynman parameterization first (which combines denominators and ensures all poles are in the correct quadrants).

### Verification

1. **Dimensional analysis.** In d = 4: [I] = [1/k^4] * [k^4] = dimensionless (in natural units where [k] = mass). With the measure factor: [d^4k/(2pi)^4 * 1/k^4] = [mass^0]. For m != 0, I depends on p^2/m^2 and is a dimensionless function of this ratio. Correct.

2. **UV behavior.** For large k_E: integrand ~ 1/k_E^4. The 4D measure gives d^4k_E ~ k_E^3 dk_E. So the integral ~ integral dk_E/k_E, which is logarithmically divergent. This is the standard logarithmic UV divergence of the one-loop scalar self-energy in phi^4 theory. Correct — this integral requires regularization (dimensional regularization gives a 1/epsilon pole).

3. **p = 0 limit.** I(0) = i * integral d^4k_E/(2pi)^4 * 1/(k_E^2 + m^2)^2. This is a standard integral: I(0) = i/(16 pi^2) * [1/epsilon - ln(m^2/mu^2) + finite]. The coefficient 1/(16 pi^2) is the canonical one-loop factor. If you get 1/(8 pi^2) or 1/(32 pi^2), there is a factor-of-2 error from the Wick rotation.

4. **Imaginary part check.** For p^2 > 4m^2 (above threshold), the Minkowski integral develops an imaginary part from the two-particle cut. The Euclidean integral is real, so the imaginary part comes entirely from the pole contribution that was bypassed during the Wick rotation (or equivalently, from the Feynman parameter integral's branch cut). Verify: Im[I] = 1/(16 pi) * sqrt(1 - 4m^2/p^2) * theta(p^2 - 4m^2). This is the optical theorem result.
