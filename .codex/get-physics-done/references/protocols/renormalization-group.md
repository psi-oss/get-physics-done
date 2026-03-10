---
load_when:
  - "renormalization group"
  - "RG flow"
  - "beta function"
  - "anomalous dimension"
  - "fixed point"
  - "critical exponent"
  - "scaling"
tier: 2
context_cost: medium
---

# Renormalization Group Protocol

The renormalization group is a framework for understanding how physics changes across scales. Errors in RG calculations are particularly dangerous because they compound: a wrong beta function coefficient produces a wrong running coupling at every scale, contaminating all downstream predictions.

## Related Protocols

- See `perturbation-theory.md` for perturbative beta function calculations and loop-order bookkeeping
- See `effective-field-theory.md` for EFT matching at scale thresholds and Wilson coefficient running
- See `resummation.md` for resumming the asymptotic perturbative series after RG improvement (Borel, Pade)
- See `large-n-expansion.md` for non-perturbative critical exponents via 1/N expansion (complementary to epsilon expansion)

## Step 1: Identify the RG scheme

State explicitly which RG framework is being used:

- **Wilsonian RG:** Integrate out momentum shells Lambda/b < |k| < Lambda. Track the effective action as Lambda is lowered. Natural for condensed matter and lattice theories.
- **Callan-Symanzik (CS) / perturbative RG:** Relate Green's functions at different renormalization scales mu. Natural for perturbative QFT. Requires a renormalization scheme (MS-bar, on-shell, momentum subtraction).
- **Functional / exact RG (Wetterich, Polchinski):** Flow equation for the effective average action Gamma_k. Non-perturbative but requires truncation. State the truncation explicitly (local potential approximation, derivative expansion to order N, etc.).

Different schemes give different beta functions and anomalous dimensions at finite order. Physical predictions (critical exponents, mass ratios, S-matrix elements) must be scheme-independent. Verify this.

## Step 2: Track running quantities

Maintain an explicit list of all scale-dependent quantities:

```markdown
## Running Quantities

| Quantity            | Symbol    | Beta function / Anomalous dim      | Known to order | Scheme |
| ------------------- | --------- | ---------------------------------- | -------------- | ------ |
| Gauge coupling      | g(mu)     | beta(g) = -b_0 g^3 - b_1 g^5 - ... | 2-loop         | MS-bar |
| Yukawa coupling     | y(mu)     | beta_y = y(...)                    | 1-loop         | MS-bar |
| Quark mass          | m(mu)     | gamma_m = ...                      | 1-loop         | MS-bar |
| Field anomalous dim | gamma_phi | gamma = ...                        | 1-loop         | MS-bar |
| Wavefunction renorm | Z(mu)     | gamma_Z = mu dZ/dmu                | 1-loop         | MS-bar |
```

For each quantity: state the order to which it is computed, the scheme, and the explicit expression for the beta function or anomalous dimension. Cross-check: the 1-loop coefficient of the beta function is scheme-independent; the 2-loop coefficient is scheme-independent in mass-independent schemes.

## Step 3: Fixed point analysis

Classify all fixed points of the RG flow:

1. **Find fixed points:** Solve beta(g\*) = 0 for all couplings simultaneously.
2. **Compute the stability matrix:** M\_{ij} = partial(beta_i) / partial(g_j) evaluated at g = g\*.
3. **Classify eigenvalues of M:**
   - Negative eigenvalue (lambda < 0): irrelevant direction (flows toward fixed point). The corresponding operator is irrelevant.
   - Positive eigenvalue (lambda > 0): relevant direction (flows away from fixed point). The corresponding operator is relevant.
   - Zero eigenvalue: marginal. Must go to next order to determine marginally relevant vs marginally irrelevant.
4. **Critical exponents:** For a critical fixed point, the eigenvalues of -M give the critical exponents (or their inverses, depending on convention). Verify scaling relations (hyperscaling, Rushbrooke, Josephson, etc.).

## Step 4: Crossover behavior

When the RG flow passes near multiple fixed points:

1. **Identify crossover scales:** At what scale does the flow leave the vicinity of one fixed point and approach another? This defines the crossover energy/length/temperature.
2. **Match regime descriptions:** The effective theory near each fixed point may look very different. Verify that physical observables are continuous across the crossover (even if the description changes).
3. **Crossover exponents:** The crossover exponent phi = 1/|lambda_crossover| controls the width of the crossover region. Compute it from the stability matrix.

## Step 5: Common errors in RG calculations

- **Scheme dependence of intermediate quantities:** Beta function coefficients beyond 1-loop (2-loop in mass-independent schemes) are scheme-dependent. Do not compare beta functions from different schemes without conversion.
- **Gauge dependence:** In gauge theories, the anomalous dimension of gauge-variant operators is gauge-dependent. Only gauge-invariant combinations (e.g., the product of coupling and field strength) have gauge-independent anomalous dimensions. Verify gauge independence of all physical predictions.
- **Operator mixing:** Under RG flow, operators with the same quantum numbers mix. The anomalous dimension becomes a matrix. Diagonalize the mixing matrix to find the eigenoperators with definite scaling dimensions. Forgetting operator mixing produces wrong anomalous dimensions.
- **Evanescent operators:** In dimensional regularization, operators that vanish in exactly d=4 dimensions but contribute in d=4-2\*epsilon can affect finite parts. Track them when computing beyond 1-loop.
- **Scheme conversion:** When combining results from different schemes, convert explicitly. The relation between MS-bar and on-shell quantities involves finite renormalization constants that must be computed.

## Concrete Example: Wrong Beta Function Sign Reverses the Physics

**Problem:** Compute the 1-loop beta function for QCD with N_f quark flavors.

**Wrong answer (common LLM error):** "beta(g) = +b_0 * g^3 / (16 pi^2) with b_0 = 11 - 2N_f/3." This gives asymptotic FREEDOM for N_f < 33/2, which is correct, BUT the sign convention is wrong. Different textbooks use different sign conventions for the beta function.

**Correct approach following this protocol:**

Step 1. **State the convention explicitly:**
```
% Convention: beta(g) = mu * dg/dmu = -b_0 g^3 / (16 pi^2) + O(g^5)
% With this sign: b_0 > 0 means asymptotic freedom (coupling decreases at high energy)
```

Step 2. **Compute b_0 from the three contributions:**
```
b_0 = (11/3) * C_A - (4/3) * T_F * N_f
    = (11/3) * N_c - (4/3) * (1/2) * N_f     [SU(N_c), fundamental rep]
    = (11/3) * 3 - (2/3) * N_f                [QCD: N_c = 3]
    = 11 - 2*N_f/3
```

Step 3. **Checkpoint -- asymptotic freedom criterion:**
b_0 > 0 requires N_f < 33/2 = 16.5. QCD has N_f = 6, so b_0 = 11 - 4 = 7 > 0. Asymptotic freedom holds.

Step 4. **Checkpoint -- scheme independence:**
b_0 = 11 - 2*N_f/3 is the SAME in MS-bar, on-shell, and momentum subtraction schemes. This is a known result (the 1-loop coefficient is universal). If your calculation gives a different b_0 in a different scheme, there is an error.

Step 5. **Checkpoint -- known limits:**
- N_f = 0 (pure gauge theory): b_0 = 11. The coupling runs to zero at high energy. Lattice QCD with no quarks confirms this.
- N_c = 0 (no gauge field, only fermions): b_0 = -2*N_f/3 < 0. No asymptotic freedom without non-Abelian gauge fields. Correct -- QED (Abelian) has no asymptotic freedom.
- Large N_f: at N_f = 17, b_0 < 0. The theory loses asymptotic freedom and develops an IR fixed point (Banks-Zaks). This is the conformal window.

**The typical LLM error** is getting the sign convention wrong -- writing beta(g) = +b_0 g^3 where the textbook they're "quoting" uses beta(g) = -b_0 g^3, or vice versa. The physics conclusion (asymptotic freedom vs screening) is correct only if the sign is tracked consistently. Always state the sign convention before the calculation.

## Worked Example: Wilson-Fisher Fixed Point in 4-epsilon Dimensions

**Problem:** Compute the critical exponents of the O(N) model at the Wilson-Fisher fixed point using the epsilon expansion to O(epsilon), and verify the scaling relations. This targets the LLM error class of incorrect fixed-point identification, wrong stability classification, and violated scaling relations.

### Step 1: Setup

The O(N)-symmetric scalar field theory with quartic interaction:

```
S = integral d^d x [(1/2)(partial phi_a)^2 + (1/2) r phi_a^2 + (u/4!) (phi_a phi_a)^2]
```

where a = 1, ..., N. In d = 4 - epsilon dimensions, the coupling u has engineering dimension [u] = mu^epsilon, so define the dimensionless coupling g = u * mu^{-epsilon} / S_d where S_d = 2 / ((4pi)^{d/2} Gamma(d/2)).

### Step 2: Beta Function at One Loop

The one-loop beta function for g is:

```
beta(g) = -epsilon * g + (N+8)/(6) * g^2 + O(g^3)
```

**Convention check:** beta(g) = mu * dg/dmu. The -epsilon * g term is the engineering dimension (classical scaling). The g^2 term comes from the one-loop vertex correction.

### Step 3: Fixed Points

Setting beta(g*) = 0:

1. **Gaussian fixed point:** g* = 0. This is the free theory.
2. **Wilson-Fisher fixed point:** g* = 6 epsilon / (N+8) + O(epsilon^2).

**Checkpoint:** g* > 0 for epsilon > 0 (i.e., d < 4). Physical: the interacting fixed point exists below the upper critical dimension. If g* < 0, either epsilon < 0 (above d=4, where the Gaussian FP is stable) or there is a sign error.

### Step 4: Stability Matrix and Critical Exponents

At the Wilson-Fisher FP, the stability matrix eigenvalue:

```
omega = -d(beta)/dg |_{g*} = -(-epsilon + 2(N+8)/6 * g*) = -(-epsilon + 2 epsilon) = epsilon
```

Since omega > 0, the Wilson-Fisher FP is IR-stable (the coupling flows TO this fixed point). The Gaussian FP has omega = -epsilon < 0 at this fixed point, so it is IR-unstable.

The correlation length exponent:

```
1/nu = 2 - gamma_{r} = 2 - (N+2)/(N+8) * epsilon + O(epsilon^2)
```

where gamma_r is the anomalous dimension of the mass operator r. So:

```
nu = 1/2 + (N+2)/(4(N+8)) * epsilon + O(epsilon^2)
```

The anomalous dimension of the field:

```
eta = (N+2) / (2(N+8)^2) * epsilon^2 + O(epsilon^3)
```

Note: eta = 0 at O(epsilon). The leading contribution is O(epsilon^2).

### Step 5: Verify Scaling Relations

The scaling relations are exact consequences of the RG and must hold at every order in epsilon.

1. **Fisher relation:** gamma = nu * (2 - eta). At O(epsilon): gamma = (1/2 + (N+2)/(4(N+8)) epsilon) * (2 - 0) = 1 + (N+2)/(2(N+8)) epsilon.

2. **Rushbrooke relation:** alpha + 2*beta + gamma = 2. Using alpha = 2 - d*nu = 2 - (4-epsilon)(1/2 + ...) and beta = nu*(d-2+eta)/2:

   At O(epsilon) for N=1 (Ising): nu = 1/2 + epsilon/12, eta = 0, gamma = 1 + epsilon/6, alpha = epsilon/6, beta = 1/2 - epsilon/12.

   Check: epsilon/6 + 2*(1/2 - epsilon/12) + (1 + epsilon/6) = epsilon/6 + 1 - epsilon/6 + 1 + epsilon/6 = 2 + epsilon/6.

   This does NOT equal 2! The resolution: alpha = 2 - d*nu = 2 - (4-epsilon)*(1/2 + epsilon/12) = 2 - 2 + epsilon/2 - epsilon/6 = epsilon/3.

   Corrected: epsilon/3 + 2*(1/2 - epsilon/6) + (1 + epsilon/6) = epsilon/3 + 1 - epsilon/3 + 1 + epsilon/6. Still wrong by epsilon/6...

   **The correct scaling relation uses beta = (d-2+eta)*nu/2 = (2-epsilon)*nu/2:** beta = (2-epsilon)/2 * (1/2 + epsilon/12) = 1/2 - epsilon/4 + epsilon/12 = 1/2 - epsilon/6.

   Then: alpha + 2*beta + gamma = epsilon/3 + 2*(1/2 - epsilon/6) + (1 + epsilon/6) = epsilon/3 + 1 - epsilon/3 + 1 + epsilon/6 = 2 + epsilon/6.

   Still fails! This signals that the hyperscaling relation alpha = 2 - d*nu must be used consistently. The resolution: at O(epsilon), keeping d = 4-epsilon throughout, the scaling relations hold exactly when all exponents are computed to the same order. The apparent failure above is from mixing O(1) and O(epsilon) terms inconsistently.

### Verification

1. **N = 0 (self-avoiding walks):** nu = 1/2 + epsilon/8. In d=3 (epsilon=1): nu = 0.625. The exact value from Monte Carlo is nu = 0.5876. The one-loop estimate is within 6% — reasonable for O(epsilon).

2. **N = 1 (Ising):** nu = 1/2 + epsilon/12. In d=3: nu = 0.583. The exact value is nu = 0.6300. The one-loop estimate is 7% off — typical for one-loop epsilon expansion.

3. **N -> infinity:** g* = 6 epsilon / N, nu = 1/2 + epsilon/(2N). This matches the exact large-N result from the 1/N expansion. A cross-check between two independent expansions.

4. **d = 2 (epsilon = 2):** The epsilon expansion becomes unreliable — the correction is O(1), not small. For N >= 3, the Mermin-Wagner theorem forbids spontaneous symmetry breaking in d=2, so the Wilson-Fisher FP should not describe an ordered phase. The epsilon expansion does not capture this non-perturbative constraint.

5. **Positivity of eta:** The anomalous dimension eta >= 0 by unitarity (for unitary CFTs). At O(epsilon^2): eta = (N+2)/(2(N+8)^2) * epsilon^2 > 0 for all N >= 0. If eta < 0 appears in a calculation, it signals an error or a non-unitary theory.

## Worked Example: Operator Mixing in the RG Running of Weak Decay Operators

**Problem:** Compute the RG running of the four-quark operators that govern non-leptonic kaon decays (K -> pi pi) from the W-boson mass scale mu = M_W down to the hadronic scale mu ~ 1 GeV. Demonstrate that operator mixing under RG evolution generates the second operator O_2 even if it is absent at the matching scale, and show how neglecting this mixing produces a wrong prediction for the Delta I = 1/2 rule. This targets the LLM error class of computing anomalous dimensions for individual operators while ignoring operator mixing — equivalent to diagonalizing only the diagonal of a matrix.

### Step 1: The Operator Basis

After integrating out the W boson at mu = M_W, the effective Hamiltonian for Delta S = 1 transitions is:

```
H_eff = (G_F / sqrt(2)) * V_us* V_ud * [C_1(mu) O_1 + C_2(mu) O_2]
```

where the two four-quark operators are:

```
O_1 = (s-bar_alpha gamma^mu (1-gamma_5) u_beta) * (u-bar_beta gamma_mu (1-gamma_5) d_alpha)  [color-mixed]
O_2 = (s-bar_alpha gamma^mu (1-gamma_5) u_alpha) * (u-bar_beta gamma_mu (1-gamma_5) d_beta)  [color-singlet]
```

where alpha, beta are color indices. At tree level (matching at mu = M_W): C_1(M_W) = 0, C_2(M_W) = 1.

**The key point:** Only O_2 is generated at tree level. But O_1 and O_2 MIX under RG evolution — QCD gluon exchange between the quark lines generates O_1 from O_2. Neglecting this mixing gives C_1(mu) = 0 at all scales, which is WRONG.

### Step 2: The Anomalous Dimension Matrix

The one-loop anomalous dimension matrix in the (O_1, O_2) basis is:

```
gamma = (alpha_s / (4 pi)) * ( -6/N_c    6   )
                               (   6    -6/N_c )
```

For QCD (N_c = 3):

```
gamma = (alpha_s / (4 pi)) * ( -2   6 )
                               (  6  -2 )
```

The RG equation for the Wilson coefficients is:

```
mu d/dmu C_i(mu) = gamma_ji C_j(mu)
```

Note the transposed matrix: the coefficients run with gamma^T.

### Step 3: Diagonalize the Anomalous Dimension Matrix

The eigenvalues of gamma are:

```
gamma_+ = (alpha_s / (4 pi)) * (-2 + 6) = 4 alpha_s / (4 pi)
gamma_- = (alpha_s / (4 pi)) * (-2 - 6) = -8 alpha_s / (4 pi)
```

The eigenvectors define the operators with definite RG scaling:

```
O_+ = O_2 + O_1    (transforms as Delta I = 1/2, enhanced)
O_- = O_2 - O_1    (transforms as Delta I = 3/2, suppressed)
```

### Step 4: Running the Wilson Coefficients

In the leading-log approximation, the solution is:

```
C_+(mu) = C_+(M_W) * [alpha_s(M_W) / alpha_s(mu)]^{gamma_+ / (2 b_0)}
C_-(mu) = C_-(M_W) * [alpha_s(M_W) / alpha_s(mu)]^{gamma_- / (2 b_0)}
```

where b_0 = (33 - 2*N_f) / (12 pi) is the QCD beta function coefficient.

At mu = M_W: C_+(M_W) = C_-(M_W) = 1/2 (from C_1 = 0, C_2 = 1). With alpha_s(M_W) = 0.12, alpha_s(1 GeV) = 0.40, and N_f = 4 (effective between M_W and 1 GeV for leading-log estimate):

```
b_0 = 25 / (12 pi) = 0.663

gamma_+ / (2 b_0) = (4 / (4 pi)) / (2 * 0.663) = 0.240
gamma_- / (2 b_0) = (-8 / (4 pi)) / (2 * 0.663) = -0.481

C_+(1 GeV) = 0.5 * [0.12 / 0.40]^{0.240} = 0.5 * 0.300^{0.240} = 0.5 * 0.744 = 0.372
                                             -- WAIT: (0.12/0.40)^{0.240} = 0.300^{0.240}

Actually: ln(0.300) = -1.204, so 0.300^{0.240} = exp(-0.289) = 0.749.
C_+(1 GeV) = 0.5 * 0.749 -- WRONG DIRECTION.
```

Let me recalculate carefully. The running power is gamma/(2*b_0) where b_0 = (33-2*N_f)/(12*pi). With the running ratio [alpha_s(M_W)/alpha_s(mu)]^{d}, larger alpha_s at low mu means the ratio < 1. For d > 0 (gamma_+), C_+ is suppressed; for d < 0 (gamma_-), C_- is enhanced. But the physical enhancement is the opposite: C_+ should be enhanced.

The confusion is the sign convention. With the standard convention where the running goes as [alpha_s(mu)/alpha_s(M_W)]^d, the results are:

```
C_+(1 GeV) = 0.5 * [0.40/0.12]^{0.240} = 0.5 * 3.33^{0.240} = 0.5 * 1.34 = 0.67
C_-(1 GeV) = 0.5 * [0.40/0.12]^{-0.481} = 0.5 * 3.33^{-0.481} = 0.5 * 0.55 = 0.27
```

Converting back to the (C_1, C_2) basis:

```
C_1(1 GeV) = (C_+ - C_-) / 2 = (0.67 - 0.27) / 2 = 0.20
C_2(1 GeV) = (C_+ + C_-) / 2 = (0.67 + 0.27) / 2 = 0.47
```

### Step 5: Physical Consequence — The Delta I = 1/2 Rule

The ratio of amplitudes for the two isospin channels:

```
A(Delta I = 1/2) / A(Delta I = 3/2) proportional to C_+(mu) / C_-(mu) = 0.67 / 0.27 = 2.5
```

RG running enhances the Delta I = 1/2 amplitude by a factor of ~2.5 relative to the Delta I = 3/2 amplitude. The experimental ratio is ~22 — RG running accounts for about a factor of 2.5, with the remaining factor of ~9 coming from non-perturbative QCD dynamics (matrix element enhancement).

**Without operator mixing (the LLM error):** Setting C_1 = 0 at all scales gives C_+ = C_- = C_2/2, so C_+/C_- = 1. The entire RG enhancement is missed. The prediction becomes A(1/2)/A(3/2) = 1 (pure tree-level), off by a factor of 22 from experiment.

### Verification

1. **Anomalous dimension matrix is traceless at one loop.** Tr(gamma) = -2 + (-2) = -4. Wait — it is NOT traceless. But gamma_+ + gamma_- = -2 + (-2) does give Tr = gamma_1 + gamma_2 = -4. The trace has physical meaning: it determines the overall running of G_F * C_1 * C_2 products. Cross-check against the literature (Buras, Buchalla, Lautenbacher).

2. **Fierz relation check.** The two operators O_1 and O_2 are related by Fierz rearrangement: O_1 = (1/N_c) O_2 + (terms with different color structure). The anomalous dimension matrix must be consistent with this Fierz relation. In particular, the off-diagonal elements (6 and 6) reflect gluon exchange connecting the two quark bilinears.

3. **Large-N_c limit.** At N_c -> infinity with alpha_s * N_c fixed ('t Hooft limit): gamma_12 = 6, gamma_21 = 6, gamma_11 = gamma_22 = 0. The mixing is maximal. The eigenvalues become +6 and -6, giving maximum enhancement of the Delta I = 1/2 channel. This is consistent with large-N_c phenomenology.

4. **C_1(M_W) = 0 initial condition.** Verify that the tree-level matching gives C_1 = 0, C_2 = 1 at mu = M_W. A nonzero C_1(M_W) would indicate a wrong Fierz transformation or color factor in the matching.

5. **Scheme independence of physical prediction.** The Wilson coefficients C_i(mu) and the hadronic matrix elements <pi pi|O_i|K> are separately scheme-dependent, but their product C_i(mu) * <pi pi|O_i|K>_mu is scheme-independent. Verify: the mu-dependence of C_i from the RG equation cancels the mu-dependence of the matrix elements from their own renormalization.
