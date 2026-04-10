---
phase: 01
plan: anchor-observable-audit-and-vocabulary-lock
title: "Anchor observable audit and vocabulary lock"
objective: "Convert the bootstrap literature corpus into a canonical Phase 01 summary that preserves observable tags, model differences, and the resolution-versus-encoding distinction without upgrading the provisional synthesis."
type: execute
wave: 1
depends_on: []
files_modified:
  - CONTEXT.md
  - SUMMARY.md
interactive: false
conventions:
  metric_signature: "(-,+,+,+) and mostly-plus AdS_5 extension when needed by the cited paper"
  natural_units: "hbar=c=k_B=1"
  coordinate_system: "boundary time t, FRW proper time tau, and explicit AdS radial coordinate only when fixed by the cited paper"
approximations:
  - name: "Observable-first bootstrap comparison"
    parameter: "fidelity of source-level observable tagging across non-identical holographic models"
    validity: "Useful only when each claim is tied to a specific observable, access class, or explicit absence of such evidence"
    breaks_when: "The comparison collapses distinct evidentiary levels into a single narrative of holographic success"
    check: "Reject any summary sentence that omits the observable basis for a singularity claim"
  - name: "Semiclassical large-N literature interpretation"
    parameter: "control of 1/N and strong-coupling corrections in the cited constructions"
    validity: "Adequate for Phase 01 anchor locking and qualitative comparison"
    breaks_when: "The phase tries to infer UV singularity resolution from semiclassical geometry alone"
    check: "Keep direct resolution claims fail-closed unless the cited paper states an observable incompatibility with an unresolved singularity"
contract:
  schema_version: 1
  scope:
    question: "What anchor commitments and observable-first distinctions must be locked in Phase 01 before later phases compare singularity resolution against encoding and access?"
    in_scope:
      - "Audit all five anchor papers for explicit observable, access, or reconstruction claims"
      - "Lock a Phase 01 summary that preserves the difference between resolution, encoding, and observer-limited access"
      - "Carry forward the strongest loopholes and overclaim risks into canonical phase output"
    out_of_scope:
      - "Declaring a candidate singularity criterion"
      - "Verifying R-01-DIAGNOSTIC-SPLIT"
      - "Claiming a new bulk mechanism that resolves the cosmological singularity"
  context_intake:
    must_read_refs:
      - Ref-1810
      - Ref-2102
      - Ref-2206
      - Ref-2405
      - Ref-2507
    must_include_prior_outputs:
      - GPD/literature/PRIOR-WORK.md
      - GPD/literature/SUMMARY.md
      - GPD/literature/SINGULARITY-DIAGNOSTICS.md
      - GPD/literature/PITFALLS.md
      - GPD/phases/01-core-holographic-constructions-and-anchor-papers/CONTEXT.md
    user_asserted_anchors:
      - arXiv:1810.10601
      - arXiv:2507.10649
    known_good_baselines:
      - GPD/literature/SINGULARITY-DIAGNOSTICS.md
      - arXiv:1810.10601
    context_gaps:
      - "The anchor literature still lacks a single stable observable definition of singularity resolution across all constructions"
    crucial_inputs:
      - "Large-subsystem entanglement probes of interior FRW evolution"
      - "BCFT strip realization of braneworld big-bang or big-crunch cosmology"
      - "Closed-universe final-state wavefunction dictionary and coarse-grained observables"
  claims:
    - id: claim-phase01-lock
      statement: "Phase 01 can produce a grounded canonical summary only if each anchor claim is tagged by its observable or access basis and the resulting summary preserves the distinction between singularity resolution, encoding, and observer-limited access."
      claim_kind: result
      deliverables:
        - deliv-phase-summary
      acceptance_tests:
        - test-anchor-observables
        - test-no-overclaim
      references:
        - Ref-1810
        - Ref-2102
        - Ref-2206
        - Ref-2405
        - Ref-2507
  deliverables:
    - id: deliv-phase-summary
      kind: note
      path: GPD/phases/01-core-holographic-constructions-and-anchor-papers/SUMMARY.md
      description: "Canonical Phase 01 summary that locks anchor observables, vocabulary, and loopholes for downstream planning and verification"
      must_contain:
        - "per-anchor observable or access tag"
        - "resolution versus encoding distinction"
        - "explicit strongest loopholes"
    - id: deliv-diagnostics-baseline
      kind: report
      path: GPD/literature/SINGULARITY-DIAGNOSTICS.md
      description: "Existing diagnostics matrix used as a baseline for overclaim checks during Phase 01 summary drafting"
      must_contain:
        - "per-paper observables"
        - "boundary observable access"
        - "working diagnostic"
  references:
    - id: Ref-1810
      kind: paper
      locator: "arXiv:1810.10601"
      role: benchmark
      why_it_matters: "Primary anchor for entanglement-sensitive probes of behind-the-horizon FRW dynamics."
      applies_to:
        - claim-phase01-lock
      must_surface: true
      required_actions:
        - read
        - compare
        - cite
      carry_forward_to:
        - planning
        - execution
        - verification
        - writing
    - id: Ref-2102
      kind: paper
      locator: "arXiv:2102.05057"
      role: background
      why_it_matters: "Conceptual origin of the confinement-cosmology and cosmology-wormhole link."
      applies_to:
        - claim-phase01-lock
      must_surface: true
      required_actions:
        - read
        - compare
        - cite
      carry_forward_to:
        - planning
        - execution
        - verification
        - writing
    - id: Ref-2206
      kind: paper
      locator: "arXiv:2206.14821"
      role: benchmark
      why_it_matters: "Antonini-led anchor connecting entangled boundary states to accelerating cosmology."
      applies_to:
        - claim-phase01-lock
      must_surface: true
      required_actions:
        - read
        - compare
        - cite
      carry_forward_to:
        - planning
        - execution
        - verification
        - writing
    - id: Ref-2405
      kind: paper
      locator: "arXiv:2405.18465"
      role: benchmark
      why_it_matters: "Most explicit BCFT or braneworld realization of big-bang or big-crunch cosmology in the current anchor set."
      applies_to:
        - claim-phase01-lock
      must_surface: true
      required_actions:
        - read
        - compare
        - cite
      carry_forward_to:
        - planning
        - execution
        - verification
        - writing
    - id: Ref-2507
      kind: paper
      locator: "arXiv:2507.10649"
      role: benchmark
      why_it_matters: "Latest Antonini-led anchor on closed-universe encoding, final-state projection, and coarse-grained observables."
      applies_to:
        - claim-phase01-lock
      must_surface: true
      required_actions:
        - read
        - compare
        - cite
      carry_forward_to:
        - planning
        - execution
        - verification
        - writing
  acceptance_tests:
    - id: test-anchor-observables
      subject: claim-phase01-lock
      kind: human_review
      procedure: "Check that the Phase 01 summary names every anchor paper and tags each one with an explicit observable, access class, or explicit absence of a direct boundary probe."
      pass_condition: "All five anchors are present and none is summarized as a singularity claim without an observable or access basis."
      evidence_required:
        - deliv-phase-summary
        - Ref-1810
        - Ref-2102
        - Ref-2206
        - Ref-2405
        - Ref-2507
      automation: human
    - id: test-no-overclaim
      subject: claim-phase01-lock
      kind: consistency
      procedure: "Review the Phase 01 summary and ensure that encoding, access, and direct resolution claims are not conflated."
      pass_condition: "No sentence upgrades a reconstruction or determination claim into direct singularity resolution without explicit support."
      evidence_required:
        - deliv-phase-summary
        - deliv-diagnostics-baseline
        - Ref-1810
        - Ref-2507
      automation: human
  forbidden_proxies:
    - id: fp-generic-holography
      subject: claim-phase01-lock
      proxy: "Treating the existence of an entangled-CFT cosmology as evidence that the crunch is resolved"
      reason: "Would erase the difference between geometry, encoding, and observer access."
    - id: fp-observer-access
      subject: claim-phase01-lock
      proxy: "Using limited observer access or final-state determination as a synonym for direct reconstruction of the singular region"
      reason: "Would upgrade the strongest current closed-universe evidence into a claim the sources do not actually make."
  links:
    - id: link-phase01-summary
      source: claim-phase01-lock
      target: deliv-phase-summary
      relation: supports
      verified_by:
        - test-anchor-observables
        - test-no-overclaim
  uncertainty_markers:
    weakest_anchors:
      - "The anchor literature does not yet supply a shared observable criterion that makes an unresolved singularity impossible."
    disconfirming_observations:
      - "A source-backed comparison shows that the anchor papers only establish encoding or observer-limited access, with no stable cross-model observable worth carrying into later phases."
ASSERT_CONVENTION: metric_signature="(-,+,+,+) and mostly-plus AdS_5 extension when needed by the cited paper", natural_units="hbar=c=k_B=1", coordinate_system="boundary time t, FRW proper time tau, and explicit AdS radial coordinate only when fixed by the cited paper"
---

<objective>
Lock the Phase 01 anchor observables and resolution vocabulary into a canonical summary that later phases can inherit without smuggling in a stronger singularity claim than the sources support.

Purpose: turn the existing literature notes into one canonical phase artifact that records anchor evidence, vocabulary commitments, and open loopholes.
Output: `GPD/phases/01-core-holographic-constructions-and-anchor-papers/SUMMARY.md`
</objective>

<context>
@GPD/PROJECT.md
@GPD/ROADMAP.md
@GPD/STATE.md
@GPD/literature/PRIOR-WORK.md
@GPD/literature/SUMMARY.md
@GPD/literature/SINGULARITY-DIAGNOSTICS.md
@GPD/literature/PITFALLS.md
@GPD/phases/01-core-holographic-constructions-and-anchor-papers/CONTEXT.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Audit anchor observables and claim strength</name>
  <files>SUMMARY.md</files>
  <action>Re-read the tracked literature outputs and the five anchor references at the summary level, then draft a canonical Phase 01 summary that tags each anchor by observable or access basis and states what each one does and does not establish about the crunch.</action>
  <verify>Reject any sentence that names singularity resolution without the supporting observable or explicit source language. Preserve differences between microstate, wormhole, BCFT or braneworld, and closed-universe constructions.</verify>
  <done>The summary records the anchor set without flattening distinct models into a single entangled-cosmology slogan.</done>
</task>

<task type="auto">
  <name>Task 2: Lock loopholes and provisional status</name>
  <files>SUMMARY.md</files>
  <action>Add a final section to the summary that names the strongest loopholes, keeps `R-01-DIAGNOSTIC-SPLIT` provisional, and states why a later criterion phase is still needed.</action>
  <verify>Check that the summary leaves room for a later disconfirming observable and does not present the current synthesis as verified.</verify>
  <done>The phase output hands later phases a clear vocabulary and an honest blocker list instead of an inflated conclusion.</done>
</task>

</tasks>

<verification>
Confirm that the resulting summary covers all five anchors, preserves the resolution-versus-encoding distinction, and leaves the provisional diagnostic split explicitly unverified.
</verification>

<success_criteria>
- Every anchor paper appears with an observable or access tag.
- The summary keeps direct resolution, encoding, and observer-limited access as distinct categories.
- The strongest loopholes are explicit enough to guide later synthesis and verification work.
</success_criteria>

<output>
After completion, create `GPD/phases/01-core-holographic-constructions-and-anchor-papers/SUMMARY.md`.
</output>
