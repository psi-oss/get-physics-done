---
phase: 01-benchmark
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: []
interactive: false
contract:
  schema_version: 1
  scope:
    question: What benchmark must this plan recover?
  context_intake:
    must_read_refs: [ref-benchmark]
    must_include_prior_outputs: [.gpd/phases/00-baseline/00-01-SUMMARY.md]
  claims:
    - id: claim-benchmark
      statement: Recover the benchmark value within tolerance
      deliverables: [deliv-figure]
      acceptance_tests: [test-benchmark]
      references: [ref-benchmark]
  deliverables:
    - id: deliv-figure
      kind: figure
      path: figures/benchmark.png
      description: Benchmark comparison figure
  references:
    - id: ref-benchmark
      kind: paper
      locator: Author et al., Journal, 2024
      role: benchmark
      why_it_matters: Published comparison target
      applies_to: [claim-benchmark]
      must_surface: true
      required_actions: [read, compare, cite]
  acceptance_tests:
    - id: test-benchmark
      subject: claim-benchmark
      kind: benchmark
      procedure: Compare against the benchmark reference
      pass_condition: Matches reference within tolerance
      evidence_required: [deliv-figure, ref-benchmark]
  forbidden_proxies:
    - id: fp-benchmark
      subject: claim-benchmark
      proxy: Qualitative trend match without numerical comparison
      reason: Would allow false progress without testing the decisive benchmark
  uncertainty_markers:
    weakest_anchors: [Reference tolerance interpretation]
    disconfirming_observations: [Benchmark agreement disappears once normalization is fixed]
---

Fixture plan body.
