---
load_when:
  - "de Sitter"
  - "dS"
  - "dS/CFT"
  - "de Sitter holography"
  - "cosmological horizon"
  - "Gibbons-Hawking"
  - "Bunch-Davies"
  - "static patch"
  - "alpha-vacua"
  - "Higuchi bound"
tier: 2
context_cost: medium
---

# de Sitter Space and de Sitter Holography Protocol

Calculations in de Sitter space are subtle because the spacetime has a positive cosmological constant, observer-dependent horizons, no globally accessible timelike boundary, and no global notion of conserved particle number. AdS intuition helps in places, but it also causes many systematic errors if imported without adjustment.

## Related Protocols

- See `derivation-discipline.md` for sign tracking and convention annotation in all derivations
- See `general-relativity.md` for curvature conventions, horizons, and geometric checks
- See `cosmological-perturbation-theory.md` for inflationary perturbations and late-time correlators
- See `analytic-continuation.md` for Euclidean continuation and contour choices
- See `effective-field-theory.md` for EFT of inflation and controlled low-energy expansions
- See `holography-ads-cft.md` for holographic comparison points and dictionary discipline

## Step 1: Declare the de Sitter Setup

Before writing any equation, state:

1. **Spacetime dimension and scales:** Declare the de Sitter radius `L`, Hubble parameter `H = 1/L`, and cosmological constant `Lambda = (d-1)(d-2)/(2L^2)` in `d` spacetime dimensions.
2. **Coordinate patch:** State whether you work in global, planar/flat slicing, conformal, or static-patch coordinates. Many statements are patch-dependent.
3. **Metric signature and analytic continuation:** Lock the signature and the Wick-rotation convention before comparing with Euclidean sphere results.
4. **Observable type:** Distinguish a static-patch observable, an in-in correlator, a wavefunction coefficient, and a boundary-CFT quantity. Do not move between them implicitly.
5. **State choice:** Default to the Bunch-Davies (Euclidean) state unless there is a stated reason to use a different initial state or excited state.
6. **Backreaction regime:** State whether the calculation is fixed-background QFT, semiclassical gravity, or a full quantum-gravity/holographic construction.

## Step 2: Fix the Geometry and Horizon Data

1. **Curvature normalization:** For pure de Sitter, verify `R_{mu nu} = (d-1)L^{-2} g_{mu nu}` and `R = d(d-1)L^{-2}`.
2. **Static patch:** In mostly-plus signature, the static patch metric is
   `ds^2 = -(1 - r^2/L^2) dt^2 + dr^2/(1 - r^2/L^2) + r^2 dOmega_{d-2}^2`,
   with cosmological horizon at `r = L`.
3. **Planar slicing:** In flat slicing, use `ds^2 = -dt^2 + e^{2Ht} dvec{x}^2` and keep track of which observables are tied to late times rather than the static patch.
4. **Thermodynamics:** The Gibbons-Hawking temperature and entropy are
   `T_dS = 1/(2pi L) = H/(2pi)` and `S_GH = A_H/(4 G_N)`.
5. **Consistency limits:** The limit `L -> infinity` must recover flat spacetime. Schwarzschild-de Sitter has separate black-hole and cosmological horizons, with the Nariai limit when they coincide.

## Step 3: Quantize Fields Carefully

1. **Scalar late-time weights:** For a scalar of mass `m`, use
   `Delta_pm = (d-1)/2 +/- sqrt((d-1)^2/4 - m^2 L^2)`.
   Light fields have real weights; heavy fields have complex weights.
2. **In-in formalism:** Use Schwinger-Keldysh/in-in techniques for expectation values. Flat-space in/out S-matrix intuition is usually not the right observable language.
3. **Bunch-Davies default:** The Bunch-Davies state is preferred because it is de Sitter invariant, Euclidean-analytic, and has the correct short-distance singularity structure.
4. **Non-standard vacua:** If using alpha-vacua or excited initial states, state the renormalization prescription and why locality/causality remain under control.
5. **Infrared subtleties:** Massless minimally coupled scalars, gravitons, and long-time observables can have zero-mode, memory, or infrared issues. Do not summarize them as "same as Minkowski with `H != 0`."
6. **Higher-spin consistency:** For spin-2 in `d = 4`, check the Higuchi bound `m^2 >= 2 H^2`. More generally, symmetric spin-`s` fields obey `m^2 >= H^2 (s-1)(s+d-4)`. Saturation corresponds to partially massless points; violation gives ghostlike helicities.

## Step 4: Separate dS/CFT from Static-Patch Holography

1. **dS/CFT dictionary:** The usual asymptotic proposal is `Psi_dS[varphi_0] <-> Z_CFT[varphi_0]`, with Euclidean boundary data at `I^+` or `I^-`.
2. **Boundary character:** The putative boundary theory is Euclidean and need not satisfy the same unitarity intuition as standard Lorentzian AdS/CFT examples.
3. **Representation theory matters:** Complex scaling dimensions for heavy fields are not automatically pathologies; they are tied to principal-series representations of the de Sitter group.
4. **Static-patch programs:** Worldline, stretched-horizon, and timelike-boundary versions of de Sitter holography are active research proposals, not settled dictionary entries.
5. **Entropy and extremal surfaces:** Horizon entropy is established, but entanglement-entropy and quantum-extremal-surface constructions in de Sitter remain substantially less settled than their AdS counterparts.

## Step 5: Connect Exact de Sitter to Inflation Carefully

1. **Gauge-invariant observables:** In quasi-de Sitter inflation, phrase predictions in terms of `zeta`, `gamma_ij`, or other gauge-invariant late-time data.
2. **Exact vs quasi-de Sitter:** Document which identities hold only in exact de Sitter and which survive slow-roll breaking.
3. **Short-distance behavior:** Verify the Bunch-Davies/subhorizon limit before trusting a primordial correlator or non-Gaussian template.
4. **Cosmological collider and bootstrap statements:** Distinguish exact de Sitter symmetry constraints from slow-roll or boost-breaking corrections used in phenomenology.

## Step 6: Treat String-Theory de Sitter Claims as a Controlled-Approximation Problem

1. **Construction data:** If claiming a stringy de Sitter vacuum, state the compactification, fluxes, moduli-stabilization mechanism, uplift ingredient, and tadpole/quantization conditions.
2. **No-go theorems:** Check whether the construction evades Gibbons/Maldacena-Nunez-type no-go theorems and under what assumptions.
3. **Control parameters:** State explicitly what suppresses `alpha'` corrections, string-loop corrections, and other backreaction effects.
4. **Current status:** Candidate controlled de Sitter vacua exist, but the survival of metastable solutions under subleading corrections remains an active and disputed question.

## Step 7: Verification Checklist

| Check | Method | Catches |
|-------|--------|---------|
| Flat-space limit | Take `L -> infinity`; recover Minkowski kinematics and vanishing curvature | Wrong sign of `Lambda`, wrong `H` normalization |
| Curvature normalization | Verify `R_{mu nu}` and `R` for the chosen metric | Radius/sign mistakes |
| Horizon thermodynamics | Compute `kappa`, `T_dS = H/(2pi)`, and `S_GH = A_H/(4G_N)` | Wrong Euclidean periodicity, factor-of-2 errors |
| State choice | Check Hadamard/Bunch-Davies short-distance structure of correlators | Unjustified alpha-vacuum default |
| Scalar weights | Verify `Delta_+ + Delta_- = d-1` and light/heavy classification | Wrong mass-dimension map |
| Higher-spin unitarity | Check Higuchi or partially massless bound | Ghostlike helicities in massive spin sectors |
| Gauge invariance | Express inflationary observables in `zeta`, `gamma_ij`, or equivalent invariant data | Gauge artifacts in cosmological predictions |
| String control | Quantify correction scales and metastability assumptions | Overclaiming controlled de Sitter vacua |

## Common LLM Errors in de Sitter Calculations

1. **Importing AdS formulas without flipping the sign of the cosmological constant.**
2. **Confusing global, planar, and static coordinates, especially horizon locations and time variables.**
3. **Using flat-space S-matrix language for observables that should be defined by in-in correlators or wavefunction coefficients.**
4. **Treating alpha-vacua as the default choice instead of a special, carefully justified construction.**
5. **Declaring complex late-time weights "non-unitary" without recognizing principal-series representations.**
6. **Ignoring the Higuchi bound in massive spin-2 or higher-spin inflationary model building.**
7. **Presenting swampland objections or KKLT-like constructions as settled rather than actively debated.**

## Standard References

- Gibbons and Hawking: *Cosmological Event Horizons, Thermodynamics, and Particle Creation* (foundational de Sitter thermodynamics)
- Spradlin, Strominger, and Volovich: *Les Houches Lectures on De Sitter Space* (classic geometry, QFT, and dS/CFT review)
- Baumann: *TASI Lectures on Inflation* (standard inflation/de Sitter perturbation reference)
- Akhmedov: *Lecture Notes on Interacting Quantum Fields in de Sitter Space* (infrared structure and interacting QFT issues)
- Galante: *Modave Lecture Notes on de Sitter Space & Holography* (modern overview with static-patch developments)
- McAllister, Moritz, Nally, and Schachner: *Candidate de Sitter Vacua* (2024 status of explicit KKLT-type candidates)
- Bena, Grana, and Van Riet: *Trustworthy de Sitter Compactifications of String Theory: A Comprehensive Review* (string-compactification control issues)
