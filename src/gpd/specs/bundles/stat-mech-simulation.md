---
bundle_id: stat-mech-simulation
bundle_version: 1
title: Statistical Mechanics Simulation
summary: Benchmark-anchored simulation work with thermalization, autocorrelation, finite-size scaling, and universality checks.
selection_tags:
  - "framework:statistical-mechanics"
  - "work-mode:numerical-simulation"
  - "validation:benchmark-and-scaling"
trigger:
  any_terms:
    - monte carlo
    - finite-size scaling
    - binder cumulant
    - autocorrelation
    - thermalization
    - universality class
  any_tags:
    - theoretical-framework:statistical-mechanics
    - acceptance-kind:benchmark
    - reference-role:benchmark
  exclusive_with:
    - lattice-gauge-monte-carlo
  min_term_matches: 2
  min_tag_matches: 1
  min_score: 10
assets:
  project_types:
    - path: templates/project-types/stat-mech-simulation.md
      required: true
  subfield_guides:
    - path: references/subfields/stat-mech.md
      required: true
  verification_domains:
    - path: references/verification/domains/verification-domain-statmech.md
      required: true
  protocols_core:
    - path: references/protocols/monte-carlo.md
      required: true
    - path: references/protocols/stochastic-processes.md
    - path: references/protocols/numerical-computation.md
  protocols_optional:
    - path: references/protocols/statistical-inference.md
    - path: references/protocols/renormalization-group.md
  execution_guides:
    - path: references/execution/executor-subfield-guide.md
anchor_prompts:
  - Surface an exact solution, trusted literature benchmark, or known thermodynamic limit before scaling up production runs.
  - Ask which observable definitions and finite-size conventions are decisive if multiple normalizations exist.
reference_prompts:
  - Keep exact or high-precision benchmark references visible through planning, execution, and verification.
  - Track whether prior simulation baselines and reference datasets remain comparable after preprocessing or normalization changes.
estimator_policies:
  - Name the estimator family for each observable and record how autocorrelation or effective sample size is handled.
  - Require jackknife, bootstrap, or comparable uncertainty estimation whenever observables depend on correlated samples.
decisive_artifact_guidance:
  - Produce a benchmark comparison table with uncertainty bars and normalization notes.
  - Produce finite-size scaling figures or collapse plots tied directly to the phase claim, not just raw traces.
  - Preserve raw measurement datasets and metadata needed to reproduce thermalization and autocorrelation checks.
verifier_extensions:
  - name: detailed-balance-and-thermalization-audit
    rationale: Simulation correctness depends on sampling the intended equilibrium distribution before interpreting observables.
    check_ids:
      - "5.4"
      - "5.14"
      - "5.16"
  - name: finite-size-scaling-and-universality-audit
    rationale: Critical claims need convergence across sizes plus comparison against decisive benchmark behavior.
    check_ids:
      - "5.5"
      - "5.6"
      - "5.15"
      - "5.16"
---

# Statistical Mechanics Simulation Bundle

Use this bundle for benchmark-anchored Monte Carlo and critical-phenomena work
where thermalization, autocorrelation, finite-size scaling, and universality
checks are decisive.
