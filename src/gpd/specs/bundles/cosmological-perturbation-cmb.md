---
bundle_id: cosmological-perturbation-cmb
bundle_version: 1
title: Cosmological Perturbation and CMB
summary: Gauge-sensitive cosmology work with transfer-function discipline, Boltzmann-code benchmarks, and CMB or large-scale-structure observables.
selection_tags:
  - "framework:cosmological-perturbation-theory"
  - "work-mode:boltzmann-and-parameter-computation"
  - "validation:gauge-transfer-benchmarks"
trigger:
  any_terms:
    - cosmological perturbation
    - bardeen potential
    - comoving curvature
    - camb
    - class
    - cmb power spectrum
    - transfer function
    - boltzmann hierarchy
    - sachs wolfe
    - acoustic peak
  any_tags:
    - acceptance-kind:benchmark
    - acceptance-kind:cross_method
    - acceptance-kind:consistency
    - reference-role:benchmark
  min_term_matches: 2
  min_tag_matches: 1
  min_score: 10
assets:
  project_types:
    - path: templates/project-types/cosmology.md
      required: true
  subfield_guides:
    - path: references/subfields/gr-cosmology.md
      required: true
  verification_domains:
    - path: references/verification/domains/verification-domain-gr-cosmology.md
      required: true
  protocols_core:
    - path: references/protocols/cosmological-perturbation-theory.md
      required: true
    - path: references/protocols/numerical-computation.md
  protocols_optional:
    - path: references/protocols/de-sitter-space.md
    - path: references/protocols/effective-field-theory.md
  execution_guides:
    - path: references/execution/executor-subfield-guide.md
anchor_prompts:
  - State the gauge choice, time variable, and power-spectrum normalization before solving perturbations or comparing codes.
  - Surface the decisive benchmark, whether Planck best-fit, CLASS or CAMB parity, or an analytic super-Hubble or Sachs-Wolfe limit.
reference_prompts:
  - Keep CAMB, CLASS, Planck, and analytic baseline conventions visible through planning, execution, and verification.
  - Preserve Fourier, transfer-function, and normalization conventions when comparing across codes or literature.
estimator_policies:
  - Distinguish gauge-invariance checks, numerical integration tolerances, and parameter-estimation uncertainties instead of collapsing them into one error bar.
  - Report whether disagreement comes from background evolution, transfer functions, or likelihood and normalization choices.
decisive_artifact_guidance:
  - Produce code-comparison artifacts for C_l or P(k) against CLASS, CAMB, or a trusted benchmark cosmology.
  - Produce gauge-comparison or super-Hubble diagnostics whenever the claim depends on gauge-invariant observables.
  - Preserve background-consistency tables for H(z), distances, sound horizon, or related derived quantities when they anchor the result.
verifier_extensions:
  - name: gauge-invariance-and-superhubble-audit
    rationale: Cosmological perturbation work fails easily through gauge leakage or broken asymptotic behavior.
    check_ids:
      - "5.3"
      - "5.8"
      - "5.15"
  - name: boltzmann-benchmark-and-normalization-audit
    rationale: CMB and transfer-function claims need code-level benchmark parity and explicit normalization discipline.
    check_ids:
      - "5.5"
      - "5.6"
      - "5.16"
---

# Cosmological Perturbation and CMB Bundle

Use this bundle for gauge-sensitive cosmology projects where transfer functions,
CMB spectra, and Boltzmann-code agreement matter more than generic cosmology
background calculations alone.
