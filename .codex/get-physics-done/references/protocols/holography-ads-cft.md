---
load_when:
  - "holography"
  - "AdS/CFT"
  - "anti-de Sitter"
  - "gauge/gravity duality"
  - "bulk-boundary"
  - "holographic"
  - "Ryu-Takayanagi"
  - "GKPW"
  - "entanglement entropy"
  - "Witten diagram"
tier: 2
context_cost: medium
---

# Holography / AdS-CFT Protocol

Holographic calculations connect gravitational theories in (d+1)-dimensional anti-de Sitter space to conformal field theories on the d-dimensional boundary. The duality maps strong coupling on one side to weak coupling on the other, making it a powerful computational tool — but also a source of subtle errors when conventions, normalizations, and the dictionary entries are misapplied.

## Related Protocols

- See `derivation-discipline.md` for sign tracking and convention annotation in all derivations
- See `effective-field-theory.md` for holographic EFT and derivative expansion
- See `renormalization-group.md` for holographic RG (radial evolution as RG flow)
- See `conformal-bootstrap.md` for CFT data extraction and crossing symmetry
- See `supersymmetry.md` for BPS bounds, indices, localization, and local-vs-global SUSY caveats
- See `numerical-relativity.md` for numerical solutions of bulk equations

For worldsheet derivations of the duality, D-brane constructions, or compactification input data, also load `references/subfields/string-theory.md`.

## Step 1: Declare Holographic Setup and Conventions

Before any holographic calculation, explicitly state:

1. **Bulk spacetime:** AdS_{d+1} with cosmological constant Lambda = -d(d-1)/(2L^2), where L is the AdS radius. State the coordinate system (Poincare, global, Fefferman-Graham, Eddington-Finkelstein).
2. **Metric signature:** State (+,-,...,-) or (-,+,...,+) and the sign of the cosmological constant. In (+,-,...,-): ds^2 = (L^2/z^2)(dt^2 - dx_i^2 - dz^2) for Poincare patch, boundary at z -> 0.
3. **Boundary CFT:** State the CFT dimension d, the central charge (or its holographic dual N^2), and the relevant operators with their conformal dimensions.
4. **Dictionary version:** State which form of the GKPW relation is used: Z_gravity[phi_0] = <exp(integral phi_0 O)>_CFT. The boundary condition phi_0 can be the leading or subleading mode depending on the quantization (standard vs alternative).
5. **Protected sector:** If supersymmetry is used, state the preserved supercharges, R-symmetry, and whether the observable is protected (index, localized partition function, BPS Wilson loop, short-multiplet data). Do not extrapolate non-protected weak-coupling quantities as though SUSY fixed them.

## Step 2: Holographic Dictionary Verification

The AdS/CFT dictionary maps bulk quantities to boundary quantities. Verify each entry used:

| Bulk (Gravity) | Boundary (CFT) | Relation |
|----------------|-----------------|----------|
| Bulk scalar field phi with mass m | CFT operator O with dimension Delta | Delta(Delta - d) = m^2 L^2 |
| Classical bulk action S_on-shell | Generating functional W[phi_0] = -ln Z_CFT | W = S_on-shell (at leading order in 1/N) |
| Bulk gauge field A_mu | Conserved current J^mu | <J^mu> = delta S / delta A_mu^{(0)} |
| Bulk metric g_{mu nu} | Stress tensor T^{mu nu} | <T^{mu nu}> = (2/sqrt{-g}) delta S / delta g_{mu nu}^{(0)} |
| Radial coordinate z | Energy scale (z ~ 1/E) | IR in CFT <-> deep bulk, UV in CFT <-> near boundary |
| Black hole horizon | Thermal state at T = T_Hawking | Thermodynamics of BH <-> thermal CFT |
| Minimal surface area (Ryu-Takayanagi) | Entanglement entropy S_A | S_A = Area(gamma_A) / (4 G_N) |

## Step 3: Mass-Dimension Relation

For a scalar field in AdS_{d+1} with mass m:
- Delta_+ = d/2 + sqrt(d^2/4 + m^2 L^2) (standard quantization, Delta_+ >= d/2)
- Delta_- = d/2 - sqrt(d^2/4 + m^2 L^2) (alternative quantization, valid when Delta_- >= (d-2)/2, i.e., unitarity bound)

**Verification:**
1. Check Delta_+ + Delta_- = d (always true).
2. For m^2 = 0: Delta_+ = d, corresponding to a marginal deformation.
3. For m^2 L^2 = -d^2/4 + 1 (BF bound + 1): Delta_+ = d/2 + 1.
4. **BF bound:** m^2 L^2 >= -d^2/4. Scalar fields below the BF bound are tachyonic and destabilize AdS. Verify all bulk masses satisfy this.

## Step 4: Holographic Renormalization

Near the AdS boundary (z -> 0), bulk fields have divergent contributions that require holographic renormalization:

1. **Asymptotic expansion:** Write phi(z, x) = z^{Delta_-} [phi_0(x) + z^2 phi_2(x) + ... + z^{2(Delta_+ - Delta_-)} psi_0(x) log(z) + ...].
2. **Counterterms:** Add local boundary counterterms to cancel divergences. The counterterm action S_ct depends on the boundary geometry and the asymptotic expansion coefficients.
3. **Renormalized one-point function:** <O(x)> = (2 Delta_+ - d) psi_0(x) + (local terms from S_ct).
4. **Conformal anomaly:** In even boundary dimension d, the trace of the stress tensor has a conformal anomaly: <T^mu_mu> = sum of central charges times curvature invariants. Verify the a and c coefficients match the dual CFT.

## Step 5: Holographic Entanglement Entropy

1. **Ryu-Takayanagi formula:** S_A = Area(gamma_A) / (4 G_N), where gamma_A is the minimal surface in the bulk anchored to the boundary of region A.
2. **Homology constraint:** gamma_A must be homologous to A (there exists a bulk region whose boundary is gamma_A union A).
3. **HRT generalization:** For time-dependent setups, use the Hubeny-Rangamani-Takayanagi formula with extremal (not minimal) surfaces.
4. **Quantum corrections:** Include bulk entanglement entropy across gamma_A: S_A = Area(gamma_A)/(4G_N) + S_bulk(Sigma_A) + O(G_N) (quantum extremal surface formula).

## Step 6: Verification Checklist

| Check | Method | Catches |
|-------|--------|---------|
| BF bound | m^2 L^2 >= -d^2/4 | Tachyonic instabilities |
| Unitarity bound | Delta >= (d-2)/2 for scalars, Delta >= d-1 for conserved currents | Unphysical operators |
| Large-N scaling | Free energy ~ N^2, correlators scale correctly | Wrong normalization |
| Protected observable matching | Match the same preserved supercharge/BPS sector on both sides of the duality | Overextending weak-coupling SUSY control to non-protected data |
| Conformal anomaly | Match a, c coefficients with known CFT | Wrong holographic renormalization |
| Thermodynamics | Bekenstein-Hawking entropy matches thermal CFT | Wrong black hole solution |
| Strong subadditivity | S_A + S_B >= S_{A union B} + S_{A intersect B} | Wrong entanglement entropy calculation |

## Common LLM Errors in Holography

1. **Wrong mass-dimension relation:** Using Delta = d/2 + m L instead of Delta(Delta - d) = m^2 L^2. The relation is quadratic, giving two solutions.
2. **Forgetting holographic renormalization:** Computing on-shell action without subtracting boundary counterterms, giving divergent results.
3. **Wrong normalization of Newton's constant:** The relation between G_N and CFT central charge depends on the specific duality (e.g., G_N^{(5)} = pi L^3 / (2 N^2) for AdS_5/CFT_4).
4. **Confusing Poincare and global AdS:** The Poincare patch covers only part of global AdS. Thermal states in the Poincare patch correspond to the Rindler wedge of global AdS.
5. **Wrong quantization choice:** Standard vs alternative quantization gives different boundary operators with different dimensions. The choice must be consistent throughout.

## Standard References

- Maldacena: *The Large N Limit of Superconformal Field Theories and Supergravity* (hep-th/9711200)
- Witten: *Anti De Sitter Space And Holography* (hep-th/9802150)
- Gubser, Klebanov, Polyakov: *Gauge Theory Correlators from Non-Critical String Theory* (hep-th/9802109)
- Aharony et al. (ABJM): *Large N Field Theories, String Theory and Gravity* (hep-th/9905111, comprehensive review)
- Skenderis: *Lecture Notes on Holographic Renormalization* (hep-th/0209067)
- Ryu & Takayanagi: *Holographic Derivation of Entanglement Entropy from AdS/CFT* (hep-th/0603001)
- Nishioka, Ryu, Takayanagi: *Holographic Entanglement Entropy: An Overview* (arXiv:0905.0932)
