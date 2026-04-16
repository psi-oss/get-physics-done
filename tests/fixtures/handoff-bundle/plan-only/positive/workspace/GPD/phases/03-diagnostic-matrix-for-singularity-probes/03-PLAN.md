---
phase: "03"
plan: "03"
type: execute
wave: 1
depends_on: []
files_modified:
  - GPD/phases/03-diagnostic-matrix-for-singularity-probes/03-PLAN.md
  - GPD/phases/03-diagnostic-matrix-for-singularity-probes/03-SUMMARY.md
interactive: false
conventions:
  units: "c = hbar = 1 with AdS radius L explicit"
  metric: "mostly-plus"
  coordinates: "conformal time eta, comoving spatial slices, holographic radial coordinate z"
contract:
  schema_version: 1
  scope:
    question: "Do current entanglement, QES, and complexity benchmarks support singularity resolution or mainly probe avoidance?"
    in_scope:
      - "Assemble a cross-paper matrix of probes and near-singularity behavior."
      - "Separate robust avoidance signals from speculative resolution claims."
  context_intake:
    must_read_refs: [ref-antonini, ref-manu, ref-engelhardt, ref-narayan, ref-sahu]
    must_include_prior_outputs:
      - GPD/phases/01-literature-anchors-and-entangled-cft-setup/01-SUMMARY.md
    user_asserted_anchors: [arXiv:2307.14416, arXiv:2012.07351, arXiv:1404.2309, arXiv:2404.00761, arXiv:2411.14673]
    known_good_baselines:
      - GPD/phases/01-literature-anchors-and-entangled-cft-setup/01-SUMMARY.md
    context_gaps:
      - "No decisive boundary observable for microscopic singularity resolution is known yet."
    crucial_inputs:
      - "Benchmark the Antonini construction against QES and complexity behavior near Kasner-like singularities."
  claims:
    - id: claim-diagnostic-matrix
      statement: "Current benchmark probes cluster around singularity avoidance and diagnostic blindness more strongly than around microscopic singularity resolution."
      deliverables: [deliv-phase03-summary]
      acceptance_tests: [test-diagnostic-matrix]
      references: [ref-antonini, ref-manu, ref-engelhardt, ref-narayan, ref-sahu]
  deliverables:
    - id: deliv-phase03-summary
      kind: table
      path: GPD/phases/03-diagnostic-matrix-for-singularity-probes/03-SUMMARY.md
      description: "Phase 03 diagnostic matrix and interpretation."
  references:
    - id: ref-antonini
      kind: paper
      locator: "Antonini, Sasieta, Swingle, arXiv:2307.14416"
      role: benchmark
      why_it_matters: "Provides the cosmology-from-entanglement target that the benchmark matrix is assessing."
      applies_to: [claim-diagnostic-matrix]
      must_surface: true
      required_actions: [read, compare, cite]
    - id: ref-manu
      kind: paper
      locator: "Manu, Narayan, Paul, arXiv:2012.07351"
      role: benchmark
      why_it_matters: "Anchors the QES and extremal-surface avoidance behavior."
      applies_to: [claim-diagnostic-matrix]
      must_surface: true
      required_actions: [read, compare, cite]
    - id: ref-narayan
      kind: paper
      locator: "Narayan, Saini, Yadav, arXiv:2404.00761"
      role: benchmark
      why_it_matters: "Tests whether complexity adds information beyond entanglement near the singularity."
      applies_to: [claim-diagnostic-matrix]
      must_surface: true
      required_actions: [read, compare, cite]
    - id: ref-engelhardt
      kind: paper
      locator: "Engelhardt, Hertog, Horowitz, arXiv:1404.2309"
      role: benchmark
      why_it_matters: "Adds a direct boundary-correlator probe of cosmological singularities to the matrix."
      applies_to: [claim-diagnostic-matrix]
      must_surface: true
      required_actions: [read, compare, cite]
    - id: ref-sahu
      kind: paper
      locator: "Sahu, Van Raamsdonk, arXiv:2411.14673"
      role: benchmark
      why_it_matters: "Supplies a nearby 2025 entangled multi-CFT cosmology benchmark."
      applies_to: [claim-diagnostic-matrix]
      must_surface: true
      required_actions: [read, compare, cite]
  acceptance_tests:
    - id: test-diagnostic-matrix
      subject: claim-diagnostic-matrix
      kind: benchmark
      procedure: "Check that the matrix records each anchor, its probe family, and whether its near-singularity behavior supports avoidance, resolution, or only comparison geometry."
      pass_condition: "The summary shows that QES and complexity benchmarks mostly support avoidance or diagnostic blindness, that boundary correlators provide a real but as-yet untransplanted diagnostic benchmark, and that it leaves the search for a decisive resolution observable open."
      evidence_required: [deliv-phase03-summary, ref-manu, ref-engelhardt, ref-narayan, ref-sahu]
  forbidden_proxies:
    - id: fp-complexity-alone
      subject: claim-diagnostic-matrix
      proxy: "Treat complexity suppression near the singularity as by itself proving resolution."
      reason: "Complexity can mirror probe avoidance without identifying a microscopic boundary resolution mechanism."
  links:
    - id: link-diagnostic-matrix
      source: claim-diagnostic-matrix
      target: deliv-phase03-summary
      relation: supports
      verified_by: [test-diagnostic-matrix]
  uncertainty_markers:
    weakest_anchors:
      - "Whether complexity provides an independent diagnostic rather than echoing entanglement behavior."
    disconfirming_observations:
      - "A benchmark paper exhibits a boundary observable that directly penetrates the singular regime and distinguishes resolution from avoidance."
---

<objective>
Answer whether current benchmark probes support singularity resolution or primarily singularity avoidance.

Purpose: Build a diagnostic matrix that lets later verification distinguish robust signals from speculative narrative.
Output: A phase summary containing the benchmark matrix and a concise interpretation of what the probes actually show.
</objective>

<tasks>
<task type="auto">
  <name>Task 1: Build the benchmark matrix</name>
  <files>GPD/phases/03-diagnostic-matrix-for-singularity-probes/03-SUMMARY.md</files>
  <action>Organize the Antonini, Manu, Engelhardt, Narayan, and Sahu papers into a single matrix recording the probe family and its near-singularity behaviour.</action>
  <verify>Check that each row states whether the source supports avoidance, comparison geometry, or a candidate resolution signal.</verify>
  <done>The summary contains a complete cross-paper matrix with a readable interpretation column.</done>
</task>

<task type="auto">
  <name>Task 2: Separate robust and speculative claims</name>
  <files>GPD/phases/03-diagnostic-matrix-for-singularity-probes/03-SUMMARY.md</files>
  <action>Use the matrix to distinguish robust avoidance signals from claims that remain speculative or unsupported.</action>
  <verify>Check that the final interpretation leaves the decisive boundary observable question open when the cited benchmarks do not settle it.</verify>
  <done>The summary ends with a constrained interpretation that prioritizes avoidance over resolution unless stronger evidence is found.</done>
</task>
</tasks>

<verification>
Every benchmark paper in the matrix must be tied to an explicit probe family and a concrete near-singularity behavior. Reject any conclusion that treats complexity suppression or generic bulk encoding as decisive without a sharper boundary discriminator.
</verification>

<success_criteria>
The phase summary shows that current benchmark probes mostly support avoidance or diagnostic blindness, and it identifies the missing observable that would be needed to justify a stronger resolution claim.
</success_criteria>
