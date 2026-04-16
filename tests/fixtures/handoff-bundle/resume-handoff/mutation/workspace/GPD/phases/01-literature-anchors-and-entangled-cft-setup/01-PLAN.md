---
phase: "01"
plan: "01"
type: execute
wave: 1
depends_on: []
files_modified:
  - GPD/phases/01-literature-anchors-and-entangled-cft-setup/01-PLAN.md
  - GPD/phases/01-literature-anchors-and-entangled-cft-setup/01-SUMMARY.md
interactive: false
conventions:
  units: "c = hbar = 1 with AdS radius L explicit"
  metric: "mostly-plus"
  coordinates: "conformal time eta, comoving spatial slices, holographic radial coordinate z"
contract:
  schema_version: 1
  scope:
    question: "Which literature anchors constrain the entangled-CFT cosmology claim without overclaiming microscopic singularity resolution?"
    in_scope:
      - "Establish the primary Antonini-Sasieta-Swingle paper as the direct project anchor."
      - "Benchmark the project claim against explicit Kasner and extremal-surface singularity papers."
  context_intake:
    must_read_refs: [ref-antonini, ref-manu, ref-frenkel, ref-engelhardt]
    must_include_prior_outputs: []
    user_asserted_anchors: [arXiv:2307.14416, arXiv:2012.07351, arXiv:2004.01192, arXiv:1404.2309]
    known_good_baselines: [arXiv:2307.14416, arXiv:2012.07351, arXiv:1404.2309]
    context_gaps:
      - "The microscopic preparation of the entangled boundary state is still unclear."
    crucial_inputs:
      - "Separate singularity resolution from singularity avoidance before promoting any strong claim."
  claims:
    - id: claim-anchor-map
      statement: "The Antonini construction is the immediate anchor, but the strongest literature-grounded interpretation at this stage is benchmarked singularity diagnostics rather than demonstrated microscopic resolution."
      deliverables: [deliv-phase01-summary]
      acceptance_tests: [test-anchor-map]
      references: [ref-antonini, ref-manu, ref-frenkel, ref-engelhardt]
  deliverables:
    - id: deliv-phase01-summary
      kind: note
      path: GPD/phases/01-literature-anchors-and-entangled-cft-setup/01-SUMMARY.md
      description: "Phase 01 literature anchor summary."
  references:
    - id: ref-antonini
      kind: paper
      locator: "Antonini, Sasieta, Swingle, arXiv:2307.14416"
      role: benchmark
      why_it_matters: "Defines the cosmology-from-entanglement construction under study."
      applies_to: [claim-anchor-map]
      must_surface: true
      required_actions: [read, compare, cite]
    - id: ref-manu
      kind: paper
      locator: "Manu, Narayan, Paul, arXiv:2012.07351"
      role: benchmark
      why_it_matters: "Provides the clearest QES/extremal-surface singularity benchmark."
      applies_to: [claim-anchor-map]
      must_surface: true
      required_actions: [read, compare, cite]
    - id: ref-frenkel
      kind: paper
      locator: "Frenkel, Hartnoll, Kruthoff, Shi, arXiv:2004.01192"
      role: benchmark
      why_it_matters: "Supplies an explicit CFT-to-Kasner geometry benchmark for comparison."
      applies_to: [claim-anchor-map]
      must_surface: true
      required_actions: [read, compare, cite]
    - id: ref-engelhardt
      kind: paper
      locator: "Engelhardt, Hertog, Horowitz, arXiv:1404.2309"
      role: benchmark
      why_it_matters: "Provides an early boundary-correlator benchmark for how cosmological singularities can appear in field-theory observables."
      applies_to: [claim-anchor-map]
      must_surface: true
      required_actions: [read, compare, cite]
  acceptance_tests:
    - id: test-anchor-map
      subject: claim-anchor-map
      kind: benchmark
      procedure: "Check that the summary identifies the primary Antonini anchor and explicitly limits the claim to a benchmarked diagnostic interpretation in light of the Kasner/QES/two-point-function literature."
      pass_condition: "The summary cites the Antonini, Manu, Frenkel, and Engelhardt papers and leaves microscopic singularity resolution explicitly open."
      evidence_required: [deliv-phase01-summary, ref-antonini, ref-manu, ref-frenkel, ref-engelhardt]
  forbidden_proxies:
    - id: fp-entropy-only
      subject: claim-anchor-map
      proxy: "Treat generic entanglement-wedge encoding alone as proof of singularity resolution."
      reason: "Bulk encoding alone does not by itself distinguish resolution from generic semiclassical access to the cosmology."
  links:
    - id: link-anchor-map
      source: claim-anchor-map
      target: deliv-phase01-summary
      relation: supports
      verified_by: [test-anchor-map]
  uncertainty_markers:
    weakest_anchors:
      - "Microscopic preparation of the entangled state beyond random-state language."
    disconfirming_observations:
      - "A literature anchor shows direct microscopic singularity resolution already established in the boundary theory."
---

<objective>
Answer which literature anchors most sharply constrain the entangled-CFT cosmology question.

Purpose: Establish a benchmarked reading of the Antonini construction before any stronger singularity claim is made.
Output: A phase summary that records the primary anchors and the strongest non-overclaiming interpretation.
</objective>

<tasks>
<task type="auto">
  <name>Task 1: Map the primary literature anchors</name>
  <files>GPD/phases/01-literature-anchors-and-entangled-cft-setup/01-SUMMARY.md</files>
  <action>Compare the Antonini construction to the Manu, Frenkel, and Engelhardt benchmark papers and record which claims each paper can actually support.</action>
  <verify>Check that the summary explicitly surfaces the Antonini, Manu, Frenkel, and Engelhardt anchors and distinguishes cosmology-from-entanglement from singularity-resolution claims.</verify>
  <done>The summary identifies the direct project anchor and names the benchmark papers that constrain overclaiming.</done>
</task>

<task type="auto">
  <name>Task 2: State the strongest surviving interpretation</name>
  <files>GPD/phases/01-literature-anchors-and-entangled-cft-setup/01-SUMMARY.md</files>
  <action>Write the non-overclaiming interpretation that survives the comparison, keeping microscopic singularity resolution explicitly open.</action>
  <verify>Check that the resulting interpretation is benchmarked against the cited papers rather than inferred from entropy matching alone.</verify>
  <done>The summary concludes with a constrained working interpretation and explicit pressure points.</done>
</task>
</tasks>

<verification>
Require explicit citation of the primary anchor and at least three singularity benchmark papers, including a boundary-correlator benchmark. Reject any interpretation that upgrades generic bulk encoding into a demonstrated resolution mechanism.
</verification>

<success_criteria>
The phase summary identifies the Antonini paper as the direct anchor, names the decisive benchmark papers, and leaves microscopic singularity resolution open pending a sharper boundary observable.
</success_criteria>
