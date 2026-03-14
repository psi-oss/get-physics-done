---
bundle_id: numerical-relativity
bundle_version: 1
title: Numerical Relativity
summary: Constraint-controlled GR simulations with gauge stability, waveform extraction, and benchmarked strong-field validation.
selection_tags:
  - "framework:general-relativity"
  - "work-mode:numerical-relativity"
  - "validation:constraints-waveforms-benchmarks"
trigger:
  any_terms:
    - numerical relativity
    - bssn
    - moving puncture
    - apparent horizon
    - gravitational waveform
    - constraint propagation
    - 3+1 decomposition
    - adm formalism
  any_tags:
    - acceptance-kind:convergence
    - acceptance-kind:benchmark
    - reference-role:benchmark
  min_term_matches: 2
  min_tag_matches: 1
  min_score: 10
assets:
  project_types:
    - path: templates/project-types/general-relativity.md
      required: true
  subfield_guides:
    - path: references/subfields/gr-cosmology.md
      required: true
  verification_domains:
    - path: references/verification/domains/verification-domain-gr-cosmology.md
      required: true
  protocols_core:
    - path: references/protocols/numerical-relativity.md
      required: true
    - path: references/protocols/numerical-computation.md
      required: true
  protocols_optional:
    - path: references/protocols/general-relativity.md
    - path: references/protocols/asymptotic-symmetries.md
    - path: references/protocols/order-of-limits.md
  execution_guides:
    - path: references/execution/executor-subfield-guide.md
anchor_prompts:
  - State the evolution formulation, gauge conditions, and waveform-extraction strategy before interpreting dynamics.
  - Surface the decisive waveform, horizon, or perturbative benchmark expected to validate the run.
reference_prompts:
  - Keep SXS, perturbative, or analytic benchmark waveforms visible through planning, execution, and verification.
  - Preserve extraction-radius, gauge, and normalization conventions when comparing waveforms or remnant properties.
estimator_policies:
  - Report convergence order for constraint norms and waveform phase or amplitude separately.
  - Quantify extraction-radius and gauge-parameter sensitivity explicitly rather than folding them into a generic error bar.
decisive_artifact_guidance:
  - Produce constraint-norm histories at multiple resolutions with observed convergence factors.
  - Produce waveform comparison artifacts that show phase or amplitude differences, extraction radii, and benchmark alignment.
  - Preserve ADM or Bondi balance summaries plus remnant mass and spin estimates tied to the phase claim.
verifier_extensions:
  - name: constraint-and-gauge-stability-audit
    rationale: Numerical-relativity claims are not credible if constraints drift or gauge pathologies masquerade as physics.
    check_ids:
      - "5.4"
      - "5.5"
      - "5.8"
  - name: waveform-and-balance-benchmark-audit
    rationale: Strong-field claims need converged waveform extraction plus benchmark or balance-law agreement.
    check_ids:
      - "5.6"
      - "5.15"
      - "5.16"
---

# Numerical Relativity Bundle

Use this bundle for BSSN or related GR evolution work where constraint
propagation, gauge stability, waveform extraction, and benchmarked convergence
determine whether the result is believable.
