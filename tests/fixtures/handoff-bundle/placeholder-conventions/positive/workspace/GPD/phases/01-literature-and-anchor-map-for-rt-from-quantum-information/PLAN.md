---
phase: 01
plan: anchor-audit-and-dependency-baseline
title: "Anchor audit and dependency baseline"
objective: "Convert the current anchor set into a canonical Phase 01 summary that separates the leading RT benchmark from JLMS, operator-algebra QEC, entanglement wedge reconstruction, tensor-network heuristics, and the current frontier gap."
type: execute
wave: 1
depends_on: []
files_modified:
  - SUMMARY.md
interactive: false
conventions:
  metric_signature: "mostly-plus (-,+,+,+) for Lorentzian bulk conventions"
  natural_units: "hbar = c = k_B = 1"
  coordinate_system: "boundary time t with spatial region A; bulk AdS uses Poincare coordinates (z,t,vec{x}) unless a cited anchor specifies otherwise"
approximations:
  - name: "Semiclassical large-N bulk limit"
    parameter: "1/N and G_N"
    validity: "Adequate for comparing RT, JLMS, and operator-algebra QEC claims in the standard code-subspace regime"
    breaks_when: "The summary treats the semiclassical area term as derived from quantum-information structure alone"
    check: "Keep every leading-area claim tied either to RT06 as benchmark input or explicitly label it unresolved"
  - name: "Random tensor networks as heuristic stand-ins for geometry"
    parameter: "fidelity of the network-to-geometry mapping"
    validity: "Useful only as controlled heuristic support for RT-like structure and bulk-entropy corrections"
    breaks_when: "Minimal-cut analogies are promoted to a derivation of the leading geometric area term"
    check: "Reject any summary sentence that cites tensor networks without listing the imported geometric assumptions"
contract:
  schema_version: 1
  scope:
    question: "What anchor commitments and dependency distinctions must be fixed in Phase 01 before later phases can assess whether quantum-information arguments recover the leading Ryu-Takayanagi formula?"
    in_scope:
      - "Audit the benchmark role of RT06 for the leading area formula"
      - "Separate JLMS, operator-algebra QEC, and entanglement wedge reconstruction from the origin of the leading area term"
      - "Place random tensor networks and Gao24-style frontier results into the dependency map without upgrading them into a derivation claim"
    out_of_scope:
      - "Claiming a QI-only derivation of the leading RT area term"
      - "Resolving the 2025-2026 frontier literature beyond the current verified anchor set"
      - "Executing later-phase reconstruction, tensor-network, or frontier-comparison work"
  context_intake:
    must_read_refs:
      - Ref-RT06
      - Ref-ADH14
      - Ref-JLMS15
      - Ref-DHW16
      - Ref-HNQTWY16
      - Ref-Gao24
    must_include_prior_outputs:
      - GPD/PROJECT.md
      - GPD/ROADMAP.md
      - GPD/STATE.md
      - report.md
    user_asserted_anchors:
      - Ref-RT06
      - Ref-Gao24
    known_good_baselines:
      - Ref-RT06
      - Ref-DHW16
    context_gaps:
      - "No verified generic 2025-2026 QI-only derivation of the leading area term had been identified when Phase 01 was planned; Bao25 later supplied a restricted-scope update"
      - "The current command surface has already shown contradictions between derived state, durable state, and diagnostics"
    crucial_inputs:
      - "Anchor-by-anchor dependency tracing rather than consensus summaries"
      - "Explicit separation between benchmark input, derived consequence, heuristic support, and unresolved gap"
  claims:
    - id: claim-phase01-baseline
      statement: "Phase 01 can produce a grounded canonical summary only if each anchor is assigned an explicit role in the RT dependency chain and the leading-area derivation gap remains visible."
      claim_kind: result
      deliverables:
        - deliv-phase-summary
      acceptance_tests:
        - test-anchor-roles
        - test-gap-separation
        - test-false-progress
      references:
        - Ref-RT06
        - Ref-ADH14
        - Ref-JLMS15
        - Ref-DHW16
        - Ref-HNQTWY16
        - Ref-Gao24
  deliverables:
    - id: deliv-phase-summary
      kind: note
      path: GPD/phases/01-literature-and-anchor-map-for-rt-from-quantum-information/SUMMARY.md
      description: "Canonical Phase 01 summary that locks anchor roles, dependency ordering, and the live gap in the leading-area derivation story"
      must_contain:
        - "per-anchor role in the dependency chain"
        - "explicit distinction between leading RT, corrections, reconstruction, and heuristics"
        - "statement that the leading-area derivation gap remains open"
  references:
    - id: Ref-RT06
      kind: paper
      locator: "Shinsei Ryu and Tadashi Takayanagi, Holographic Derivation of Entanglement Entropy from AdS/CFT, arXiv:hep-th/0603001"
      role: benchmark
      why_it_matters: "Defines the leading RT area formula that later quantum-information arguments must explain rather than assume."
      applies_to:
        - claim-phase01-baseline
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
    - id: Ref-ADH14
      kind: paper
      locator: "Ahmed Almheiri, Xi Dong, and Daniel Harlow, Bulk Locality and Quantum Error Correction in AdS/CFT, arXiv:1411.7041"
      role: method
      why_it_matters: "Introduces the quantum-error-correction language that later sharpens subregion duality and reconstruction claims."
      applies_to:
        - claim-phase01-baseline
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
    - id: Ref-JLMS15
      kind: paper
      locator: "Daniel L. Jafferis, Aitor Lewkowycz, Juan Maldacena, and S. Josephine Suh, Relative entropy equals bulk relative entropy, arXiv:1512.06431"
      role: method
      why_it_matters: "Represents the relative-entropy backbone for entanglement wedge reasoning in the semiclassical code subspace."
      applies_to:
        - claim-phase01-baseline
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
    - id: Ref-DHW16
      kind: paper
      locator: "Xi Dong, Daniel Harlow, and Aron C. Wall, Reconstruction of Bulk Operators within the Entanglement Wedge in Gauge-Gravity Duality, arXiv:1601.05416"
      role: method
      why_it_matters: "Pins entanglement wedge reconstruction to explicit assumptions so it is not confused with a derivation of RT itself."
      applies_to:
        - claim-phase01-baseline
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
    - id: Ref-HNQTWY16
      kind: paper
      locator: "Patrick Hayden, Sepehr Nezami, Xiao-Liang Qi, Nathaniel Thomas, Michael Walter, and Zhao Yang, Holographic duality from random tensor networks, arXiv:1601.01694"
      role: method
      why_it_matters: "Provides the cleanest RT-like toy-model support while still importing nontrivial geometric structure."
      applies_to:
        - claim-phase01-baseline
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
    - id: Ref-Gao24
      kind: paper
      locator: "Ping Gao, Modular flow in JT gravity and entanglement wedge reconstruction, arXiv:2402.18655"
      role: must_consider
      why_it_matters: "Tests whether recent modular-flow advances sharpen the reconstruction story without closing the leading-area gap."
      applies_to:
        - claim-phase01-baseline
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
    - id: test-anchor-roles
      subject: claim-phase01-baseline
      kind: benchmark
      procedure: "Check that the Phase 01 summary assigns each anchor an explicit role: benchmark, method, reconstruction, heuristic support, or frontier constraint."
      pass_condition: "All six anchors appear with concrete roles and none is reduced to a generic holography citation."
      evidence_required:
        - deliv-phase-summary
        - Ref-RT06
        - Ref-ADH14
        - Ref-JLMS15
        - Ref-DHW16
        - Ref-HNQTWY16
        - Ref-Gao24
      automation: human
    - id: test-gap-separation
      subject: claim-phase01-baseline
      kind: consistency
      procedure: "Review the summary and ensure it separately classifies the leading RT term, bulk-entropy corrections, entanglement wedge reconstruction, and random-tensor-network support."
      pass_condition: "The summary explicitly marks the leading-area derivation as unresolved while allowing stronger status for later-chain reconstruction claims."
      evidence_required:
        - deliv-phase-summary
        - Ref-RT06
        - Ref-JLMS15
        - Ref-DHW16
        - Ref-HNQTWY16
        - Ref-Gao24
      automation: human
    - id: test-false-progress
      subject: claim-phase01-baseline
      kind: proxy
      procedure: "Reject any language that upgrades reconstruction or tensor-network minimal cuts into a derivation of the leading area term without naming the imported semiclassical assumptions."
      pass_condition: "False-progress modes are explicit and excluded from the success claim."
      evidence_required:
        - deliv-phase-summary
        - Ref-ADH14
        - Ref-HNQTWY16
      automation: human
  forbidden_proxies:
    - id: fp-reconstruction-is-derivation
      subject: claim-phase01-baseline
      proxy: "Treating entanglement wedge reconstruction or JLMS as equivalent to deriving the leading RT area term"
      reason: "Would collapse a downstream consequence into the very benchmark it presupposes."
    - id: fp-tensor-network-proof
      subject: claim-phase01-baseline
      proxy: "Treating random tensor-network minimal cuts as a proof of the geometric area term"
      reason: "Would hide imported geometric structure behind a successful toy-model analogy."
  links:
    - id: link-phase01-summary
      source: claim-phase01-baseline
      target: deliv-phase-summary
      relation: supports
      verified_by:
        - test-anchor-roles
        - test-gap-separation
        - test-false-progress
  uncertainty_markers:
    weakest_anchors:
      - "No verified 2025-2026 paper in the current workspace closes the generic leading-area derivation gap; Bao25 later supplied a restricted-scope derivation claim."
    disconfirming_observations:
      - "A supposedly QI-only derivation still assumes the semiclassical area term or background geometry as an input."
ASSERT_CONVENTION: metric_signature="mostly-plus (-,+,+,+) for Lorentzian bulk conventions", natural_units="hbar = c = k_B = 1", coordinate_system="boundary time t with spatial region A; bulk AdS uses Poincare coordinates (z,t,vec{x}) unless a cited anchor specifies otherwise"
---

<objective>
Lock a canonical Phase 01 summary that turns the existing anchor set into an explicit dependency baseline for the RT-from-quantum-information question.

Purpose: give later phases a stable Phase 01 artifact that names what each anchor does and does not establish, instead of relying on free-form memory or provisional narrative.
Output: `GPD/phases/01-literature-and-anchor-map-for-rt-from-quantum-information/SUMMARY.md`
</objective>

<context>
@GPD/PROJECT.md
@GPD/ROADMAP.md
@GPD/STATE.md
@report.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Audit anchor roles and dependency ordering</name>
  <files>SUMMARY.md</files>
  <action>Re-read the tracked project artifacts and summarize the six anchor references so the Phase 01 output records which paper fixes the leading benchmark, which sharpen reconstruction, which provide heuristic RT-like support, and which only constrain the current frontier.</action>
  <verify>Reject any sentence that cites a paper without assigning it a specific role in the dependency chain. Keep the leading RT benchmark distinct from reconstruction and heuristic support.</verify>
  <done>The summary contains a per-anchor map that later phases can inherit without collapsing the logic of the program.</done>
</task>

<task type="auto">
  <name>Task 2: Lock the false-progress guardrails</name>
  <files>SUMMARY.md</files>
  <action>Write the Phase 01 summary so it explicitly states why JLMS, entanglement wedge reconstruction, and random tensor networks do not by themselves close the leading-area derivation gap.</action>
  <verify>Keep the conclusion provisional and fail-closed: if a step presupposes semiclassical geometry or the RT formula, say so directly rather than smoothing it over.</verify>
  <done>The summary names the open gap and the main overclaim modes that later phases must not inherit.</done>
</task>

</tasks>

<verification>
Confirm that the resulting summary names all six anchors, preserves the leading-area derivation gap as open, and excludes the two main false-progress modes: reconstruction-as-derivation and tensor-network-analogy-as-proof.
</verification>

<success_criteria>
- A Phase 01 summary exists and can serve as the dependency baseline for later phases.
- Every anchor in the current contract has an explicit role in the summary.
- The summary does not claim that quantum-information structure alone has already derived the leading RT area term.
</success_criteria>

<output>
After completion, create `GPD/phases/01-literature-and-anchor-map-for-rt-from-quantum-information/SUMMARY.md`.
</output>
