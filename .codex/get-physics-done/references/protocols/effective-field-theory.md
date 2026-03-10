---
load_when:
  - "effective field theory"
  - "EFT"
  - "power counting"
  - "operator basis"
  - "Wilson coefficient"
  - "matching"
  - "integrate out"
tier: 2
context_cost: high
---

# Effective Field Theory Protocol

Effective field theory is the systematic framework for separating physics at different scales. Errors in EFT typically arise from incorrect power counting, incomplete operator bases, or wrong matching. This protocol ensures consistent EFT construction and application.

## Related Protocols

- See `perturbation-theory.md` for loop calculations in EFT and combinatorial factor handling
- See `renormalization-group.md` for RG running of Wilson coefficients between scales

## Step 1: Power counting

1. **Identify the expansion parameter:** What is the small ratio? Examples: p/Lambda (momentum over cutoff), m_light/m_heavy, alpha_s, v/c, 1/N. State it explicitly with its numerical value in the regime of interest.
2. **Assign scaling dimensions:** Every field, coupling, and operator has a scaling dimension. In standard relativistic EFT: [phi] = (d-2)/2, [psi] = (d-1)/2, [A_mu] = (d-2)/2. In non-relativistic EFT (NRQED, NRQCD): scaling is different because time and space scale differently.
3. **Determine the order of each operator:** An operator with dimension Delta contributes at order (p/Lambda)^{Delta - d} relative to the leading term. Enumerate operators order by order.
4. **Verify consistency:** The power counting must be self-consistent under loop corrections. A tree-level operator at order n should receive loop corrections at order n + (loop factor). If a loop correction is the same order as a tree-level term, the power counting is inconsistent --- revisit.

## Step 2: Operator basis

1. **Enumerate all operators at each order** consistent with the symmetries of the theory. For a given dimension, list all independent Lorentz scalars, gauge invariants, etc.
2. **Apply symmetry constraints:** Parity, charge conjugation, time reversal, flavor symmetries, and gauge symmetry all restrict the allowed operators. Use these to reduce the basis.
3. **Eliminate redundant operators:** Use the equations of motion (at leading order) to eliminate operators that are equivalent on-shell. Use integration by parts to eliminate total derivatives. Use field redefinitions to remove operators related by the EOM. The result is a minimal, non-redundant basis.
4. **Standard bases:** For well-known EFTs, use the established basis. For SMEFT: the Warsaw basis. For chiral perturbation theory: the Gasser-Leutwyler basis at O(p^4). For HQET: the standard HQET Lagrangian at each order in 1/m_Q. State which basis is used.

### Operator Basis Construction Decision Tree

```
1. Is this a well-known EFT with an established basis?
   ├── SMEFT (dimension 6): Use Warsaw basis (Grzadkowski et al. 2010)
   ├── HQET / NRQCD: Use velocity-dependent basis with 1/m_Q expansion
   ├── Chiral PT (O(p^4)): Use Gasser-Leutwyler basis (10 LECs for SU(3))
   ├── SCET: Use label-momentum basis with collinear/soft sectors
   └── No established basis → proceed to general construction:

2. General operator basis construction:
   a. List all dynamical fields and their quantum numbers
      (spin, gauge charges, flavor indices, mass dimension)
   b. List all symmetries the EFT must respect
      (gauge, Lorentz, discrete: C, P, T, flavor)
   c. Write ALL operators up to the target mass dimension
      consistent with the symmetries
   d. Apply equations of motion (at leading order) to eliminate
      redundant operators (EOM-vanishing operators are redundant on-shell)
   e. Apply integration by parts to eliminate total derivative operators
   f. Use field redefinitions to remove further redundancies
   g. Verify completeness: count remaining operators against
      Hilbert series prediction (Henning et al. 2017)
      - Hilbert series gives the number of independent operators
        at each mass dimension as a function of the field content
      - If your count disagrees: missed an operator or missed a relation
```

### Worked Matching Example: Integrating Out a Heavy Scalar

```
UV theory: L = L_SM + |D_mu Phi|^2 - M^2 |Phi|^2 - lambda_portal |Phi|^2 |H|^2

Step 1: Matching scale mu_match = M (heavy scalar mass)

Step 2: Tree-level matching (integrate out Phi at tree level):
  - Solve Phi EOM: Phi = -(lambda_portal / M^2) |H|^2 + O(1/M^4)
  - Substitute back: L_EFT = L_SM + (lambda_portal^2 / M^2) |H|^4 + O(1/M^4)
  - Wilson coefficient: C_6(M) = lambda_portal^2 / M^2

Step 3: One-loop matching (compute same observable in both theories):
  - UV: Higgs self-energy with Phi loop
  - EFT: Higgs self-energy with C_6 vertex
  - C_6(M) = lambda_portal^2 / M^2 + (lambda_portal^2 / (16 pi^2 M^2)) [...]

Step 4: RG running from M to observation scale mu_obs:
  - mu d(C_6)/d(mu) = gamma_6 * C_6 + mixing terms
  - C_6(mu_obs) = C_6(M) * (alpha_s(mu_obs)/alpha_s(M))^{gamma_6/beta_0}

Step 5: Verify: observable computed in UV theory at scale mu_obs
  must agree with EFT prediction to working order.
```

## Worked Example: Fermi Theory from the Standard Model — Matching and Running

**Problem:** Derive the Fermi theory of weak interactions by integrating out the W boson from the Standard Model. Compute the matching coefficient at tree level and one loop, run to low energy, and demonstrate that power counting controls the EFT uncertainty. This targets the most common EFT errors: wrong matching scale, incomplete operator basis, and neglected running.

### Step 1: Power Counting and Operator Basis

The expansion parameter is p/M_W where p ~ m_b ~ 5 GeV and M_W = 80.4 GeV, so p/M_W ~ 0.06. At dimension 6, the four-fermion operator basis for b → c transitions includes:

```
O_1 = (c-bar gamma^mu P_L b)(d-bar gamma_mu P_L u)     [color-singlet]
O_2 = (c-bar gamma^mu P_L T^a b)(d-bar gamma_mu P_L T^a u)  [color-octet]
```

These mix under renormalization. The full basis includes 10 operators (including penguin operators), but for tree-level matching only O_1 and O_2 contribute.

### Step 2: Tree-Level Matching at mu = M_W

In the full SM, the amplitude for b → c u d-bar at tree level is:

```
A_SM = (g^2 / (8 M_W^2)) * V_cb V_ud* * (c-bar gamma^mu P_L b)(d-bar gamma_mu P_L u) + O(p^2/M_W^4)
```

In the EFT (Fermi theory), the same amplitude is:

```
A_EFT = (G_F / sqrt(2)) * V_cb V_ud* * [C_1(mu) O_1 + C_2(mu) O_2]
```

Matching at mu = M_W (tree level): C_1(M_W) = 1, C_2(M_W) = 0, with G_F/sqrt(2) = g^2/(8 M_W^2).

### Step 3: One-Loop Matching and RG Running

At one loop, QCD corrections generate C_2(M_W) ≠ 0 through gluon exchange between the quark lines. The anomalous dimension matrix is:

```
gamma = (alpha_s / (4 pi)) * [[−2, 6], [6, −2]]
```

Running from M_W to mu = m_b:

| mu (GeV) | alpha_s(mu) | C_1(mu) | C_2(mu) |
|----------|-------------|---------|---------|
| 80.4     | 0.119       | 1.000   | 0.000   |
| 10       | 0.179       | 1.105   | -0.245  |
| 4.8      | 0.215       | 1.137   | -0.295  |

**Key observation:** C_2(m_b) = −0.295, generated entirely by RG running. Neglecting the running and using C_1 = 1, C_2 = 0 at mu = m_b gives a ~30% error in decay rates.

### Step 4: EFT Uncertainty Estimate

The dimension-8 operators contribute at O(p^2/M_W^2) ~ O(m_b^2/M_W^2) ~ 0.4%. For B meson decays, this is much smaller than other uncertainties (hadronic matrix elements, CKM elements). The EFT is under excellent control.

### Verification

1. **Matching scale independence.** The physical amplitude A = C_i(mu) * <O_i>(mu) must be mu-independent (to the working order). The mu-dependence of C_i(mu) from running must cancel against the mu-dependence of the matrix elements <O_i>(mu). Verify: d/d(ln mu) [C_i <O_i>] = 0 at one-loop order.

2. **Operator basis completeness.** At dimension 6, the Fierz identity relates different color structures. Verify: the two operators O_1, O_2 form a complete, non-redundant basis under QCD (they close under renormalization).

3. **Known limit.** At mu = M_W with alpha_s = 0 (no QCD corrections): C_1 = 1, C_2 = 0 — the original four-fermion theory is recovered. With QCD: C_1 and C_2 evolve but C_1 + C_2/3 is RG-invariant (at one loop) due to the color structure.

4. **Power counting.** The O(1/M_W^4) corrections enter at the ~0.4% level for B decays. If they were ~10%, the EFT expansion would not be trustworthy and dimension-8 operators would need to be included.

5. **Comparison.** The computed B → D(*) ℓ ν branching ratio using C_i(m_b) agrees with experiment to ~5% (limited by hadronic form factors, not the EFT expansion).

## Step 3: Matching

Match the UV (full) theory to the EFT at the matching scale mu_match:

1. **Choose the matching scale:** Typically mu_match ~ M_heavy, the mass of the particle being integrated out. This minimizes large logarithms in the matching coefficients.
2. **Compute the same observable** in both the full theory and the EFT, expanded to the desired order.
3. **Extract matching coefficients:** C_i(mu_match) = [full theory result] - [EFT result with C_i = 0], adjusted to the correct order.
4. **Verify matching:** After determining the C_i, the full theory and EFT must agree for ALL observables at the matching scale to the working order. Check at least two independent observables as a cross-check.
5. **Scheme consistency:** The matching must be done in the same renormalization scheme for both the full theory and the EFT. If using MS-bar in the full theory, use MS-bar in the EFT.

## Step 4: Running

RG-evolve the Wilson coefficients from the matching scale to the observation scale:

1. **Compute the anomalous dimension matrix** gamma\_{ij} for the operator basis. This requires the RG equations of the EFT.
2. **Solve the RG equations:** C_i(mu_obs) = [evolution matrix] \* C_i(mu_match). For multiple operators, this involves matrix exponentiation. Watch for operator mixing (see renormalization-group.md).
3. **Resum large logarithms:** The whole point of RG evolution is to resum log(mu_match/mu_obs) terms. Verify that the resummed result improves on the fixed-order result.
4. **Threshold corrections:** If there are intermediate scales (e.g., multiple heavy particles with different masses), match and run in stages. At each threshold, match to a new EFT with fewer degrees of freedom.

## Step 5: Estimate missing higher-order terms

Every EFT prediction must come with an uncertainty estimate from truncating the expansion:

1. **Naive dimensional analysis (NDA):** The coefficient of a dimension-Delta operator is expected to be of order Lambda^{d-Delta} / (4\*pi)^{(Delta-d)/2} (up to coupling constants). Use this to estimate unmeasured coefficients.
2. **Order-by-order convergence:** If you have results at orders n and n+1, the difference gives an estimate of the O(n+2) contribution. If the series is converging, each successive order should be smaller by a factor of the expansion parameter.
3. **Report the truncation uncertainty:** State explicitly: "This result is accurate to O((p/Lambda)^n). The estimated uncertainty from missing O((p/Lambda)^{n+1}) terms is +/- X."
4. **If the expansion parameter is not small** (e.g., p/Lambda ~ 0.5): the EFT is at the edge of its validity. State this clearly and estimate whether the truncation uncertainty is under control.

## Worked Example: Pion-Pion Scattering in Chiral Perturbation Theory

**Problem:** Compute the s-wave pion-pion scattering lengths a_0^0 (isospin 0) and a_0^2 (isospin 2) at leading order (LO) and next-to-leading order (NLO) in chiral perturbation theory (ChPT). Demonstrate the power counting, the role of low-energy constants, and the convergence of the chiral expansion. This targets the LLM error class of wrong chiral power counting — specifically, including operators at the wrong order or missing the leading contribution.

### Step 1: Identify the EFT and Power Counting

Chiral perturbation theory is the EFT of QCD at energies below the chiral symmetry breaking scale Lambda_chi ~ 4 pi f_pi ~ 1.2 GeV. The degrees of freedom are the pseudo-Goldstone bosons (pions, kaons, eta). The expansion parameter is:

```
epsilon ~ p / Lambda_chi ~ m_pi / Lambda_chi ~ 140 / 1200 ~ 0.12
```

**Weinberg power counting:** A diagram with L loops, N_d vertices from the order-d Lagrangian, and I internal pion lines counts as O(p^D) with:

```
D = 2 + 2L + sum_d (d - 2) N_d
```

- Leading order (D = 2): tree diagrams from L_2 (the leading-order Lagrangian)
- Next-to-leading order (D = 4): one-loop diagrams from L_2, plus tree diagrams from L_4

**The LLM power counting error:** Treating a one-loop diagram as LO (it is NLO, D = 4) or including an L_4 counterterm at LO (it enters at NLO). Getting the order wrong means including some NLO effects while dropping others of the same order — this violates the systematic nature of the EFT.

### Step 2: Leading Order (Tree Level from L_2)

The leading-order chiral Lagrangian:

```
L_2 = (f_pi^2 / 4) Tr[partial_mu U^dag partial^mu U + 2B_0 M (U + U^dag)]
```

where U = exp(2i pi^a T^a / f_pi), f_pi = 92.4 MeV (pion decay constant), and B_0 m_q = m_pi^2 / 2 relates quark masses to pion mass.

At tree level, the pi-pi scattering amplitude is:

```
A(s, t, u) = (s - m_pi^2) / f_pi^2
```

where s, t, u are Mandelstam variables with s + t + u = 4 m_pi^2.

Projecting onto isospin channels and taking the s-wave (l = 0):

```
a_0^0 = (7 m_pi^2) / (32 pi f_pi^2) = 0.16
a_0^2 = -(m_pi^2) / (16 pi f_pi^2) = -0.045
```

Numerically with m_pi = 140 MeV, f_pi = 92.4 MeV:

```
a_0^0 = 7 * (0.140)^2 / (32 * pi * (0.0924)^2) = 0.137 / 0.855 = 0.16
a_0^2 = -(0.140)^2 / (16 * pi * (0.0924)^2) = -0.0196 / 0.427 = -0.046
```

### Step 3: Next-to-Leading Order (One Loop + L_4 Counterterms)

At NLO, two contributions enter at O(p^4):

1. **One-loop diagrams** from L_2 vertices (calculated by Gasser and Leutwyler, 1984)
2. **Tree diagrams** from L_4 = sum l_i O_i^{(4)} with low-energy constants (LECs) l_1, l_2, l_3, l_4

The NLO correction to the scattering lengths:

```
a_0^0 (NLO) = a_0^0 (LO) * [1 + (m_pi^2 / (16 pi^2 f_pi^2)) * (corrections involving logs and LECs)]
```

Using the standard values of the LECs from Colangelo, Gasser, Leutwyler (2001):

```
a_0^0 = 0.220 +/- 0.005  (NLO ChPT)
a_0^2 = -0.0444 +/- 0.0010  (NLO ChPT)
```

The NLO correction to a_0^0 is large: (0.220 - 0.160) / 0.160 = 37%. This is because epsilon ~ 0.12 but the coefficient of the NLO correction is enhanced by factors of pi and chiral logs.

### Step 4: Convergence Assessment

| Order | a_0^0 | a_0^2 | Correction size |
|-------|-------|-------|-----------------|
| LO (O(p^2)) | 0.16 | -0.046 | -- |
| NLO (O(p^4)) | 0.220 | -0.0444 | 37% (I=0), 3% (I=2) |
| NNLO (O(p^6)) | 0.220 | -0.0444 | < 5% (estimated) |
| Exact (Roy equations) | 0.220 +/- 0.005 | -0.0444 +/- 0.0012 | -- |

**Key observation:** The I = 0 channel has a large NLO correction (37%) while the I = 2 channel has a small correction (3%). This is because the I = 0 channel is attractive (resonance: the sigma/f_0(500)), enhancing higher-order corrections. The I = 2 channel is repulsive (no resonance), so the perturbative expansion converges faster.

**Truncation uncertainty estimate:** The NNLO correction should be O(epsilon^2) ~ 1-2% of the NLO result for well-converging channels. For the I = 0 channel, the large NLO correction suggests the NNLO correction could be 5-10%. The actual NNLO calculation (Bijnens et al., 2004) confirms this.

### Verification

1. **Adler zero.** The pion scattering amplitude must vanish when any external pion momentum goes to zero (Adler's theorem, a consequence of spontaneously broken chiral symmetry). At LO: A(s, t, u) = (s - m_pi^2)/f_pi^2 vanishes at s = m_pi^2 (one pion at rest in the chiral limit m_pi -> 0 gives s -> 0). Verify this at every order — violation signals a wrong Lagrangian.

2. **Crossing symmetry.** The amplitude A(s, t, u) must be invariant under the exchange of any two Mandelstam variables (with appropriate isospin factors). This is an exact property. Verify that both LO and NLO amplitudes satisfy crossing.

3. **Unitarity.** At NLO, the imaginary part of the amplitude from one-loop diagrams must satisfy the optical theorem: Im(a_l^I) = |a_l^I|^2 * sigma (where sigma is the phase space factor). At LO, the amplitude is real (tree level), so this is automatically satisfied. At NLO, verify that the imaginary parts match.

4. **Weinberg's LO prediction.** Weinberg (1966) predicted a_0^0 - a_0^2 = 7 m_pi / (32 pi f_pi^2) * (1 + 1) - ... = 0.20. The combination a_0^0 - a_0^2 is particularly well determined because some uncertainties cancel. Experimental (NA48/2): a_0^0 - a_0^2 = 0.265 +/- 0.004. The LO prediction 0.20 is 25% low; NLO gives 0.264, in excellent agreement.

5. **Low-energy constant consistency.** The LECs l_1, ..., l_4 determined from pi-pi scattering must be consistent with those determined from other processes (pion form factor, pi -> e nu gamma, K -> pi pi). If they disagree, there is a systematic error in the calculation or the experimental extraction.
