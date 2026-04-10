---
phase: "03"
plan: "03"
depth: standard
provides: [diagnostic matrix, observable shortlist]
completed: 2026-04-09
one-liner: "Built a first-pass matrix showing that current benchmark probes mostly support singularity avoidance rather than resolution."
plan_contract_ref: "GPD/phases/03-diagnostic-matrix-for-singularity-probes/03-PLAN.md#/contract"
contract_results:
  claims:
    claim-diagnostic-matrix:
      status: passed
      summary: "The benchmark matrix supports a reading in which known probes cluster around avoidance or diagnostic blindness more strongly than microscopic resolution."
      linked_ids: [deliv-phase03-summary, test-diagnostic-matrix, ref-antonini, ref-manu, ref-engelhardt, ref-narayan, ref-sahu]
  deliverables:
    deliv-phase03-summary:
      status: passed
      path: "GPD/phases/03-diagnostic-matrix-for-singularity-probes/03-SUMMARY.md"
      summary: "Summary artifact records the cross-paper probe matrix and the unresolved diagnostic ambiguity."
      linked_ids: [claim-diagnostic-matrix, test-diagnostic-matrix]
  acceptance_tests:
    test-diagnostic-matrix:
      status: passed
      summary: "The matrix covers the probe families, classifies their near-singularity behavior, and leaves the decisive boundary observable question open."
      linked_ids: [claim-diagnostic-matrix, deliv-phase03-summary, ref-manu, ref-engelhardt, ref-narayan, ref-sahu]
  references:
    ref-antonini:
      status: completed
      completed_actions: [read, compare, cite]
      missing_actions: []
      summary: "Primary target construction retained as the cosmology-from-entanglement anchor being benchmarked."
    ref-manu:
      status: completed
      completed_actions: [read, compare, cite]
      missing_actions: []
      summary: "QES benchmark used as the cleanest avoidance reference point in the matrix."
    ref-narayan:
      status: completed
      completed_actions: [read, compare, cite]
      missing_actions: []
      summary: "Complexity benchmark compared against the entanglement/QES avoidance pattern."
    ref-engelhardt:
      status: completed
      completed_actions: [read, compare, cite]
      missing_actions: []
      summary: "Boundary-correlator benchmark used to keep a concrete field-theory diagnostic in the matrix."
    ref-sahu:
      status: completed
      completed_actions: [read, compare, cite]
      missing_actions: []
      summary: "Nearby 2025 multi-CFT cosmology benchmark used to compare structural similarities without overstating diagnostics."
  forbidden_proxies:
    fp-complexity-alone:
      status: rejected
      notes: "Complexity suppression near the singularity was not treated as a stand-alone proof of microscopic resolution."
  uncertainty_markers:
    weakest_anchors:
      - "Whether complexity provides an independent diagnostic rather than echoing entanglement behavior."
    unvalidated_assumptions:
      - "The current benchmark set is broad enough to classify the observable matrix without a dedicated phase-02 execution artifact."
    competing_explanations:
      - "The same probe pattern may reflect diagnostic blindness rather than genuine singularity resolution or avoidance."
    disconfirming_observations:
      - "A benchmark paper could still expose a boundary observable that penetrates the singular regime and distinguishes resolution from avoidance."
comparison_verdicts:
  - subject_id: claim-diagnostic-matrix
    subject_kind: claim
    subject_role: decisive
    reference_id: ref-antonini
    comparison_kind: prior_work
    metric: "alignment of the target construction with the benchmark matrix"
    threshold: "Antonini remains the construction being tested rather than the resolution proof itself"
    verdict: pass
    recommended_action: "Preserve the Antonini construction as the target of comparison rather than evidence of resolution."
    notes: "The matrix keeps the Antonini paper as the direct cosmology-from-entanglement anchor under test."
  - subject_id: claim-diagnostic-matrix
    subject_kind: claim
    subject_role: decisive
    reference_id: ref-manu
    comparison_kind: benchmark
    metric: "QES/extremal-surface behavior near the singularity"
    threshold: "avoidance-dominant behavior"
    verdict: pass
    recommended_action: "Keep later synthesis anchored to the explicit avoidance benchmark before making stronger claims."
    notes: "The Manu benchmark directly supports the avoidance pattern captured in the matrix."
  - subject_id: claim-diagnostic-matrix
    subject_kind: claim
    subject_role: decisive
    reference_id: ref-narayan
    comparison_kind: benchmark
    metric: "complexity behavior relative to entanglement probes"
    threshold: "complexity does not overturn the avoidance pattern"
    verdict: pass
    recommended_action: "Treat complexity as corroborating context until an independent boundary discriminator is found."
    notes: "The Narayan benchmark echoes the same near-singularity thinning pattern rather than providing a distinct resolution signal."
  - subject_id: claim-diagnostic-matrix
    subject_kind: claim
    subject_role: decisive
    reference_id: ref-engelhardt
    comparison_kind: benchmark
    metric: "boundary two-point-function sensitivity to the singular region"
    threshold: "diagnostic signature present without any resolution claim"
    verdict: pass
    recommended_action: "Treat boundary correlators as the most concrete missing observable to transplant into the entangled-CFT setting."
    notes: "Engelhardt-Hertog-Horowitz provide a genuine boundary diagnostic benchmark that complements the avoidance-heavy extremal-surface literature."
  - subject_id: claim-diagnostic-matrix
    subject_kind: claim
    subject_role: decisive
    reference_id: ref-sahu
    comparison_kind: prior_work
    metric: "nearby entangled-multi-CFT cosmology continuity into 2025 work"
    threshold: "structural benchmark present"
    verdict: pass
    recommended_action: "Use the 2025 benchmark as nearby context rather than as decisive evidence for the Antonini construction."
    notes: "Sahu supplies a nearby multi-CFT cosmology construction without settling the singularity-resolution question for the Antonini setup."
---

# Summary

## Diagnostic matrix

| Anchor | Boundary or bulk input | Probe family | Near-singularity behaviour | Current reading |
| --- | --- | --- | --- | --- |
| Antonini-Sasieta-Swingle 2023 | entangled microstates of a pair of holographic CFTs with big-bang/big-crunch AdS duals | entanglement-wedge encoding and state-dependent bulk reconstruction | semiclassical cosmology appears in one CFT's entanglement wedge, but no direct singularity-resolving observable is supplied | strong anchor for cosmology-from-entanglement, weak anchor for microscopic singularity resolution |
| Manu-Narayan-Paul 2021 | Kasner-like and reduced 2d cosmologies | classical extremal surfaces and QES | surfaces bend away from the singularity into the semiclassical region | strong anchor for singularity avoidance by known extremal probes |
| Frenkel-Hartnoll-Kruthoff-Shi 2020 | explicit CFT deformation flowing to Kasner universe | holographic RG-flow geometry | provides benchmark singular spacetime from boundary data | strong anchor for comparison geometry, not by itself a resolution mechanism |
| Engelhardt-Hertog-Horowitz 2014 | anisotropic Kasner solutions in gauge/gravity duality | boundary two-point correlators of heavy operators | correlators show strong horizon-scale signatures of the singularity | strongest direct boundary-diagnostic benchmark, but not a resolution mechanism |
| Narayan-Saini-Yadav 2024 | Kasner-like holographic cosmologies | complexity plus entanglement probes | complexity becomes effectively lightlike and vanishing near the singularity, echoing avoidance behaviour | suggests complexity adds support but may not add an independent decisive diagnostic |
| Sahu-Van Raamsdonk 2025 | entangled black-hole sectors dual to big-bang/big-crunch cosmologies | Euclidean-path-integral construction of a nearby multi-CFT cosmology | supplies a structurally nearby entangled cosmology rather than a singularity-diagnostic observable | useful nearby benchmark, but not yet decisive for the Antonini cosmology |

## Working interpretation

- The benchmark papers cluster around one robust pattern: known semiclassical probes avoid the singular region rather than resolving it, while boundary correlators can still register singularity-sensitive structure.
- The Antonini construction is therefore best treated as a candidate cosmology-from-entanglement framework whose singularity claims must be benchmarked against both the avoidance pattern and the Engelhardt boundary-diagnostic benchmark.
- The unresolved question is whether any boundary observable can separate genuine resolution from generic probe avoidance inside the Antonini state family itself.

```yaml
gpd_return:
  status: completed
  files_written:
    - GPD/phases/03-diagnostic-matrix-for-singularity-probes/03-PLAN.md
    - GPD/phases/03-diagnostic-matrix-for-singularity-probes/03-SUMMARY.md
  issues:
    - "No benchmark paper yet supplies a decisive boundary observable for microscopic singularity resolution."
  next_actions:
    - /gpd:verify-work 04
```
