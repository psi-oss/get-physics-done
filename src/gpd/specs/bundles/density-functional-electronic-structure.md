---
bundle_id: density-functional-electronic-structure
bundle_version: 1
title: Density-Functional Electronic Structure
summary: DFT and DFT+U electronic-structure work with explicit functional choice, Brillouin-zone convergence, and benchmarked materials observables.
selection_tags:
  - "framework:electronic-structure"
  - "work-mode:density-functional-theory"
  - "validation:functional-kmesh-benchmarks"
trigger:
  any_terms:
    - density functional theory
    - kohn sham
    - pseudopotential
    - exchange correlation
    - k-point mesh
    - band gap
    - dft u
    - hybrid functional
    - plane-wave cutoff
    - electronic structure
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
    - path: templates/project-types/condensed-matter.md
      required: true
  subfield_guides:
    - path: references/subfields/condensed-matter.md
      required: true
  verification_domains:
    - path: references/verification/domains/verification-domain-condmat.md
      required: true
  protocols_core:
    - path: references/protocols/density-functional-theory.md
      required: true
    - path: references/protocols/numerical-computation.md
  protocols_optional:
    - path: references/protocols/variational-methods.md
    - path: references/protocols/many-body-perturbation-theory.md
  execution_guides:
    - path: references/execution/executor-subfield-guide.md
anchor_prompts:
  - State the functional family, pseudopotential choice, and convergence targets before trusting any electronic observable.
  - Ask whether the decisive claim depends on a Kohn-Sham proxy, a quasiparticle observable, or a benchmark structure or property.
reference_prompts:
  - Keep experimental or high-level benchmark structures, gaps, and lattice parameters visible when choosing functionals.
  - Preserve k-mesh, smearing, pseudopotential, and U-value conventions across code or literature comparisons.
estimator_policies:
  - Converge the target property, not just the total energy, over k-mesh, cutoff, smearing, and slab or supercell size.
  - Treat Kohn-Sham gaps versus quasiparticle gaps as a model-family choice that must be surfaced, not hidden inside a generic uncertainty.
decisive_artifact_guidance:
  - Produce convergence tables for k-mesh, cutoff, smearing, and any property-specific control parameter tied to the claim.
  - Produce benchmark comparison tables against experiment or a higher-level reference for the decisive observable.
  - Preserve functional-family or U-value sensitivity when the claim depends on correlated or gapped behavior.
verifier_extensions:
  - name: basis-and-brillouin-zone-convergence-audit
    rationale: Electronic-structure claims are unreliable when the target observable is not converged in basis, cutoff, and k-space sampling.
    check_ids:
      - "5.5"
      - "5.6"
      - "5.16"
  - name: proxy-gap-and-functional-family-audit
    rationale: Kohn-Sham proxies and functional-family choices must not silently substitute for the decisive physical observable.
    check_ids:
      - "5.17"
      - "5.19"
---

# Density-Functional Electronic Structure Bundle

Use this bundle for DFT, DFT+U, and hybrid-functional projects where
functional choice, Brillouin-zone convergence, and proxy-versus-observable
discipline determine whether the result is publishable.
