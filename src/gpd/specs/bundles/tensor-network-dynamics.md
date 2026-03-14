---
bundle_id: tensor-network-dynamics
bundle_version: 1
title: Tensor-Network Dynamics
summary: Bond-dimension-limited tensor-network calculations with entanglement-growth control, discarded-weight tracking, and benchmarked many-body observables.
selection_tags:
  - "framework:quantum-many-body"
  - "work-mode:tensor-network-simulation"
  - "validation:bond-dimension-entanglement-benchmarks"
trigger:
  any_terms:
    - tensor network
    - dmrg
    - matrix product state
    - mps
    - bond dimension
    - tebd
    - tdvp
    - entanglement growth
    - quench dynamics
    - peps
  any_tags:
    - acceptance-kind:convergence
    - acceptance-kind:benchmark
    - acceptance-kind:cross_method
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
    - path: references/subfields/quantum-info.md
  verification_domains:
    - path: references/verification/domains/verification-domain-condmat.md
      required: true
    - path: references/verification/domains/verification-domain-quantum-info.md
  protocols_core:
    - path: references/protocols/tensor-networks.md
      required: true
    - path: references/protocols/quantum-many-body.md
      required: true
    - path: references/protocols/variational-methods.md
  protocols_optional:
    - path: references/protocols/exact-diagonalization.md
  execution_guides:
    - path: references/execution/executor-subfield-guide.md
anchor_prompts:
  - State the tensor-network ansatz, bond-dimension schedule, and whether entanglement growth or finite-size effects are the hard limit.
  - Surface the decisive ED, Bethe-ansatz, CFT, or published tensor-network benchmark before extrapolating results.
reference_prompts:
  - Keep exact-diagonalization, Bethe-ansatz, or trusted tensor-network baselines visible through planning and verification.
  - Preserve boundary-condition, normalization, and observable-definition conventions when comparing tensor-network runs or literature.
estimator_policies:
  - Use discarded-weight or bond-dimension extrapolation for static quantities and report the reliable time window explicitly for dynamics.
  - Treat entanglement saturation and finite-chi ceilings as validity limits, not as generic larger error bars.
decisive_artifact_guidance:
  - Produce convergence tables versus bond dimension or discarded weight for every decisive observable.
  - Produce entanglement-entropy or truncation diagnostics that show where the reliable evolution window ends.
  - Preserve benchmark comparisons against ED, Bethe-ansatz, CFT scaling, or an independent tensor-network implementation.
verifier_extensions:
  - name: bond-dimension-and-truncation-audit
    rationale: Tensor-network results fail silently when finite-chi truncation or entanglement growth is left implicit.
    check_ids:
      - "5.5"
      - "5.15"
      - "5.19"
  - name: benchmark-and-validity-window-audit
    rationale: Many-body claims need an explicit benchmark or declared reliable window rather than unconverged late-time traces.
    check_ids:
      - "5.6"
      - "5.16"
---

# Tensor-Network Dynamics Bundle

Use this bundle for DMRG, MPS, TEBD, TDVP, and related tensor-network work
where bond-dimension convergence and entanglement growth determine the reliable
result window.
