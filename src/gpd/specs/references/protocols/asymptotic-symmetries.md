---
load_when:
  - "asymptotic symmetry"
  - "BMS"
  - "Bondi gauge"
  - "Bondi-Sachs"
  - "null infinity"
  - "supertranslation"
  - "superrotation"
  - "memory effect"
  - "soft theorem"
  - "large gauge transformation"
  - "Wald-Zoupas"
  - "celestial holography"
  - "news tensor"
  - "CCE"
  - "Cauchy-characteristic extraction"
tier: 2
context_cost: medium
---

# Asymptotic Symmetries Protocol

Asymptotic symmetries are not ordinary bulk symmetries. They depend on boundary conditions, residual gauge freedom, the choice of asymptotic region, and whether the associated charges are finite and physically meaningful. Many mistakes come from identifying a residual gauge transformation before checking whether it preserves the phase space and carries a well-defined charge.

## Related Protocols

- See `symmetry-analysis.md` for general symmetry identification, representation theory, and anomaly checks
- See `general-relativity.md` for Killing vectors, horizons, and geometric conventions
- See `scattering-theory.md` for S-matrix conventions and infrared limits
- See `analytic-continuation.md` for contour choices and soft limits in momentum space
- See `numerical-relativity.md` for waveform extraction, memory, and null-infinity data

## Step 1: Declare the Asymptotic Region and Boundary Conditions

Before claiming any asymptotic symmetry, state:

1. **Theory and dimension:** Gravity, Yang-Mills, QED, Einstein-Maxwell, etc., and the spacetime dimension.
2. **Asymptotic region:** Future null infinity `I^+`, past null infinity `I^-`, spatial infinity, timelike infinity, or a horizon. Different regions have different symmetry groups and matching conditions.
3. **Gauge choice:** Bondi/Bondi-Sachs, Newman-Unti, radial gauge, or another explicit gauge. Do not mix conventions silently.
4. **Boundary conditions/falloffs:** State the asymptotic metric or gauge-field falloffs that define the phase space. The symmetry algebra depends on this choice.
5. **Charge prescription:** State whether charges are defined by covariant phase space, Wald-Zoupas, or Hamiltonian methods.

## Step 2: Identify the Residual Symmetry Algebra

1. **Residual transformations:** Solve for the gauge parameters or vector fields that preserve the chosen falloffs.
2. **Large vs small gauge transformations:** Small transformations are pure redundancies; large ones act non-trivially on asymptotic data and may carry charges.
3. **BMS structure in 4d gravity:** The standard asymptotic symmetry group is
   `BMS_4 = supertranslations semidirect Lorentz`.
   The `l = 0,1` spherical harmonic modes of a supertranslation reproduce ordinary spacetime translations; `l >= 2` are proper supertranslations.
4. **Gauge-theory analogs:** In electrodynamics or Yang-Mills, angle-dependent large gauge transformations at null infinity play the analogous role behind soft photon/gluon theorems.
5. **Extended BMS:** Superrotations or other extensions depend on weakened boundary conditions or singular generators. Do not assume them by default.

## Step 3: Track the Radiative Data, Charges, and Fluxes

1. **Bondi data:** In Bondi language, keep track of the shear `C_AB`, news tensor `N_AB = partial_u C_AB`, Bondi mass aspect, and angular-momentum aspect.
2. **Integrability matters:** Radiative phase spaces are often non-integrable. If a charge has a non-integrable variation, document the flux term instead of pretending the charge is conserved.
3. **Balance laws:** The change in asymptotic charge between two cuts of null infinity must equal the flux of radiation and matter through the intervening region.
4. **Mass loss:** In radiating asymptotically flat spacetimes, the Bondi mass decreases by the radiative flux. No-news configurations should have no radiative mass loss.
5. **Matching conditions:** For scattering problems, state how charges at `I^-` are matched to charges at `I^+` across spatial infinity.

## Step 4: Use the Infrared Triangle Correctly

1. **Leading soft theorem:** The leading soft graviton or photon theorem is the Ward identity of the corresponding asymptotic symmetry.
2. **Memory effect:** Memory is the classical, time-integrated imprint of the same conservation law on detector or waveform data.
3. **Subleading structure:** Subleading soft theorems and superrotation charges are more assumption-dependent than the leading soft/supertranslation story. State the boundary conditions and loop order explicitly.
4. **Numerical waveform extraction:** Integrating `Psi_4` to obtain strain introduces integration constants tied to memory and BMS frame freedom. Fix the frame before comparing waveforms.

## Step 5: Keep Celestial and Boundary Reformulations in Their Proper Status

1. **Celestial recasting:** Celestial amplitudes rewrite scattering data as correlators on the celestial sphere, where asymptotic symmetries become current-algebra constraints.
2. **What is mature:** Ward identities, current insertions, and the symmetry interpretation of soft modes are mature enough to use as consistency checks.
3. **What is not settled:** A full non-perturbative flat-space holographic dictionary is still open. Do not write celestial holography as if it were as complete as AdS/CFT.

## Step 6: Verification Checklist

| Check | Method | Catches |
|-------|--------|---------|
| Falloff preservation | Verify the residual transformation preserves the stated asymptotic boundary conditions | Fake symmetries from incompatible falloffs |
| Translation limit | Check that `l = 0,1` supertranslations reduce to ordinary translations | Wrong BMS decomposition |
| Charge finiteness | Verify charges are finite and specify any non-integrable flux terms | Formal charges with no physical meaning |
| Balance law | Check charge change between cuts equals flux through null infinity | Missing radiation or matter flux terms |
| No-news limit | Set `N_AB = 0` and verify no radiative memory or Bondi mass loss remains | Confusing radiative and Coulombic data |
| Soft-memory consistency | Match the Ward identity, soft factor, and memory observable in the same convention | Slogan-level infrared triangle errors |
| Frame fixing | Compare waveform or memory statements only in a fixed BMS frame or after CCE/extrapolation | Spurious differences from supertranslations |
| Extended-BMS caveat | Label superrotations or other extensions with their boundary-condition assumptions | Overstating speculative symmetry enhancements |

## Common LLM Errors in Asymptotic-Symmetry Work

1. **Treating every residual gauge transformation as a physical asymptotic symmetry without checking the charge.**
2. **Mixing Bondi-Sachs, Newman-Unti, and finite-radius waveform conventions.**
3. **Forgetting that only the `l = 0,1` modes of a supertranslation are ordinary translations.**
4. **Writing down a charge while ignoring non-integrable flux terms in a radiative phase space.**
5. **Treating superrotations as universally accepted smooth symmetries rather than boundary-condition-sensitive extensions.**
6. **Ignoring BMS frame fixing when comparing numerical waveforms, memory, or strain reconstructed from `Psi_4`.**
7. **Presenting celestial holography as a settled duality instead of an active asymptotic-symmetry program.**

## Standard References

- Bondi, van der Burg, and Metzner: *Gravitational Waves in General Relativity. VII. Waves from Axi-Symmetric Isolated Systems*
- Sachs: *Gravitational Waves in General Relativity. VIII. Waves in Asymptotically Flat Space-Time*
- Strominger: *Lectures on the Infrared Structure of Gravity and Gauge Theory*
- de Aguiar Alves: *Lectures on the Bondi--Metzner--Sachs Group and Related Topics in Infrared Physics*
- Mitman et al.: *A Review of Gravitational Memory and BMS Frame Fixing in Numerical Relativity*
- Donnay: *Celestial Holography: An Asymptotic Symmetry Perspective*
- Ciambelli et al.: *Cornering Quantum Gravity*
