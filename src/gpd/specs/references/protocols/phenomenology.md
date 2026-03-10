---
load_when:
  - "phenomenology"
  - "global fit"
  - "likelihood"
  - "recast"
  - "reinterpretation"
  - "SMEFT"
  - "Wilson coefficient"
  - "public likelihood"
  - "pyhf"
  - "flavio"
tier: 2
context_cost: medium
---

# Phenomenology Protocol

Phenomenology is not just "compute an amplitude and compare with data." It is a pipeline: choose a model or EFT parameterization, define the experimental observable correctly, propagate theory and experimental uncertainties with their correlations, build a likelihood, and only then draw a constraint or best-fit statement. Many wrong phenomenology results look reasonable because each individual ingredient is plausible while the full inference chain is inconsistent.

## Related Protocols

- See `effective-field-theory.md` for EFT basis choice, matching, and running
- See `perturbation-theory.md` for fixed-order matrix elements and loop calculations
- See `renormalization-group.md` for scale evolution and large-log resummation
- See `scattering-theory.md` for cross sections, phase space, and S-matrix conventions
- See `numerical-computation.md` for convergence, interpolation, and emulator validation

## Step 1: Declare the Phenomenology Question

Before computing anything, state:

1. **Model or EFT parameterization:** UV model, simplified model, SMEFT, WET, kappa-framework, etc. State the operator basis and normalization conventions.
2. **Target observable set:** Single observable, likelihood scan, global fit, exclusion contour, or forecast. Distinguish collider, flavor, neutrino, Higgs, electroweak, and dark-matter observables.
3. **Experimental definition:** Inclusive, fiducial, unfolded, detector-level, particle-level, or pseudo-observable. Do not compare different definitions as if they were interchangeable.
4. **Perturbative order and scales:** LO, NLO, NNLO, resummed, matched shower, etc., together with renormalization/factorization scales and PDF set.
5. **Inference target:** Best-fit point, confidence interval, Bayes posterior, or expected sensitivity. The statistical object matters.

## Step 2: Build the Theory-to-Observable Prediction Chain

1. **Short-distance theory:** Compute or import the hard process, Wilson coefficients, or low-energy amplitudes at the stated order.
2. **Running and matching:** If EFTs or multi-scale problems are involved, evolve parameters to the measurement scale before comparing with data.
3. **Non-perturbative or detector layer:** For colliders, include showering, hadronization, detector response, and analysis cuts as needed. For flavor/nuclear observables, include hadronic matrix elements, form factors, or lattice inputs at the right scale.
4. **Acceptance and efficiencies:** Recasting requires validated acceptance/efficiency information. A parton-level number is not a detector-level prediction.
5. **Binning and observables:** Match the published binning, asymmetry definition, angular basis, and normalization conventions exactly.

## Step 3: Propagate Uncertainties and Correlations

1. **Experimental covariance:** Use the published covariance matrix or public likelihood whenever available.
2. **Theory systematics:** Track scale variation, PDFs, missing higher orders, hadronic uncertainties, and interpolation/emulator error separately from experimental systematics.
3. **Parametric inputs:** Propagate CKM elements, masses, `alpha_s`, lattice inputs, and branching fractions consistently through the full prediction.
4. **Correlations matter:** Do not add correlated uncertainties in quadrature as if they were independent.
5. **Avoid double counting:** If a likelihood already includes a nuisance treatment, do not reapply the same uncertainty by hand.

## Step 4: Build the Likelihood and Fit Strategy Explicitly

1. **Prefer public statistical objects:** Use public likelihoods, HistFactory/pyhf models, or collaboration-supplied covariance information when available instead of reverse-engineering a `chi^2` from a summary plot.
2. **State the inference framework:** Frequentist profile likelihood, Bayesian posterior, or another explicit statistical procedure.
3. **Nuisance treatment:** Profile or marginalize nuisance parameters consistently; state priors or penalty terms if used.
4. **Global vs single-parameter fits:** One-operator-at-a-time or one-coupling-at-a-time bounds are not generic constraints when correlations or flat directions are present.
5. **Goodness of fit and tensions:** Quote pull values, likelihood ratios, posterior compatibility, or equivalent diagnostics instead of only reporting best-fit central values.

## Step 5: Check EFT Validity and Reinterpretation Assumptions

1. **Basis and truncation:** State the operator basis and whether predictions are kept linear in `1/Lambda^2`, include quadratic terms, or mix orders.
2. **Scale separation:** Verify the fitted events or observables probe energies where the EFT is still under control. If `E ~ Lambda`, discuss the breakdown explicitly.
3. **Running across scales:** For collider-plus-flavor or electroweak-plus-low-energy fits, evolve Wilson coefficients consistently between scales.
4. **Recasting validation:** Reproduce published benchmark cutflows, acceptances, or SM yields before using a recast for new points.
5. **Model-agnostic likelihoods:** If the experimental result assumed SM kinematics, check whether reinterpretation requires reweighting or a model-agnostic likelihood treatment rather than a naive substitution of cross sections.

## Step 6: Cross-Check Against Standard Candles

1. **SM limit:** Recover the Standard Model or reference-model prediction before turning on new parameters.
2. **Published benchmark:** Reproduce at least one published exclusion, fit point, or likelihood slice from the same analysis chain.
3. **Alternative implementations:** Where feasible, compare two generators, two PDF sets, two form-factor inputs, or two statistical implementations.
4. **Sector-specific controls:** Use Drell-Yan, `Z`, `W`, top, Higgs, or well-tested flavor observables as sanity checks for collider/flavor pipelines.

## Step 7: Verification Checklist

| Check | Method | Catches |
|-------|--------|---------|
| Observable definition | Match fiducial/inclusive, detector/particle/unfolded, and binning conventions | Comparing theory to the wrong published number |
| Prediction chain | State hard process, running, shower/hadronization or hadronic input, and detector/reconstruction layer | Missing acceptance, matrix-element, or hadronic factors |
| Covariance use | Use the published covariance or public likelihood | Fake precision from neglecting correlations |
| Theory uncertainty bookkeeping | Separate scale/PDF/hadronic/parametric errors and avoid double counting | Artificially narrow or inflated constraints |
| Likelihood specification | State the exact likelihood object and nuisance treatment | Summary-plot reverse engineering masquerading as a fit |
| EFT validity | Check basis, truncation, and `E/Lambda` control | Overstated SMEFT or WET constraints |
| Recast validation | Reproduce benchmark efficiencies or limits first | Unvalidated reinterpretation pipeline |
| Global-fit degeneracies | Inspect correlations and flat directions | Misleading one-parameter bounds |

## Common LLM Errors in Phenomenology

1. **Comparing a theory number to the wrong experimental observable definition** (for example detector-level vs fiducial vs unfolded).
2. **Using only central values and adding all errors in quadrature** even when the dominant systematics are correlated.
3. **Treating one-operator-at-a-time EFT bounds as model-independent** in the presence of flat directions and correlations.
4. **Ignoring EFT validity** in high-energy tails where `E` approaches the cutoff scale.
5. **Applying a K-factor or detector efficiency from one process to a different signal without validation.**
6. **Recasting an analysis without reproducing a benchmark cutflow or SM yield first.**
7. **Mixing theory-input uncertainties already absorbed into the public likelihood with separately added nuisance terms.**

## Standard References

- Brivio and Trott: *The Standard Model as an Effective Field Theory* (SMEFT/HEFT review)
- de Blas et al.: *Electroweak Precision Observables and Higgs-Boson Signal Strengths in the Standard Model and Beyond: Present and Future* (HEPfit-based precision-fit example)
- Straub: *flavio: a Python Package for Flavour and Precision Phenomenology in the Standard Model and Beyond*
- van Dyk et al.: *EOS -- A Software for Flavor Physics Phenomenology*
- Giani, Magni, and Rojo: *SMEFiT: a Flexible Toolbox for Global Interpretations of Particle Physics Data with Effective Field Theories*
- Gartner et al.: *Constructing Model-Agnostic Likelihoods, a Method for the Reinterpretation of Particle Physics Results*
- Mildner: *An EWPD SMEFT Likelihood for the LHC -- and How to Improve it with Measurements of W and Z Boson Properties*
