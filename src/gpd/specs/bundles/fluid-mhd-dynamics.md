---
bundle_id: fluid-mhd-dynamics
bundle_version: 1
title: Fluid and MHD Dynamics
summary: Regime-aware fluid or MHD simulations with divergence control, conservation diagnostics, and benchmarked spectra or instability behavior.
selection_tags:
  - "framework:fluid-and-plasma-dynamics"
  - "work-mode:continuum-simulation"
  - "validation:regime-conservation-benchmarks"
trigger:
  any_terms:
    - navier stokes
    - reynolds number
    - magnetohydrodynamics
    - mhd
    - alfven wave
    - cfl condition
    - turbulence spectrum
    - magnetic reconnection
    - div b
    - lundquist number
  any_tags:
    - acceptance-kind:convergence
    - acceptance-kind:benchmark
    - acceptance-kind:consistency
    - reference-role:benchmark
  min_term_matches: 2
  min_tag_matches: 1
  min_score: 10
assets:
  project_types:
    - path: templates/project-types/fluid-plasma.md
      required: true
  subfield_guides:
    - path: references/subfields/fluid-plasma.md
      required: true
  verification_domains:
    - path: references/verification/domains/verification-domain-fluid-plasma.md
      required: true
  protocols_core:
    - path: references/protocols/fluid-dynamics-mhd.md
      required: true
    - path: references/protocols/numerical-computation.md
  protocols_optional:
    - path: references/protocols/non-equilibrium-transport.md
    - path: references/protocols/stochastic-processes.md
    - path: references/protocols/kinetic-theory.md
  execution_guides:
    - path: references/execution/executor-subfield-guide.md
anchor_prompts:
  - State the flow regime from dimensionless numbers before choosing equations, numerics, or turbulence assumptions.
  - Surface the decisive instability, spectrum, conservation law, or wave-speed benchmark that will make the run trustworthy.
reference_prompts:
  - Keep canonical scaling laws, analytic dispersion relations, and trusted CFD or MHD benchmarks visible while tuning numerics.
  - Preserve unit conventions, boundary conditions, and normalization choices when comparing with literature or prior runs.
estimator_policies:
  - Separate physical dissipation from numerical dissipation through explicit resolution and regime studies.
  - Report CFL limits, divergence-cleaning diagnostics, and spectral-fit windows as part of the estimator choice.
decisive_artifact_guidance:
  - Produce a regime table with Reynolds, Mach, magnetic Reynolds, beta, or Lundquist numbers tied to the governing equations.
  - Produce convergence, conservation, and div B diagnostics for every decisive simulation claim.
  - Produce spectrum, instability-growth, or reconnection-rate comparisons against analytic or literature benchmarks.
verifier_extensions:
  - name: conservation-and-divergence-audit
    rationale: Fluid and MHD claims fail quickly when conservation drift or div B contamination is left unmeasured.
    check_ids:
      - "5.4"
      - "5.5"
      - "5.8"
  - name: regime-and-spectrum-benchmark-audit
    rationale: Turbulence and instability claims need the right regime and benchmark family, not just plausible-looking flow fields.
    check_ids:
      - "5.6"
      - "5.16"
      - "5.18"
---

# Fluid and MHD Dynamics Bundle

Use this bundle for Navier-Stokes, turbulence, and MHD projects where regime
identification, divergence control, and benchmarked nonlinear dynamics are
decisive.
