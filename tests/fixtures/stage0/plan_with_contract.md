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
  claims:
    - id: claim-benchmark
      statement: Recover the benchmark value within tolerance
      deliverables: [deliv-figure]
  deliverables:
    - id: deliv-figure
      kind: figure
      path: figures/benchmark.png
      description: Benchmark comparison figure
  acceptance_tests:
    - id: test-benchmark
      subject: claim-benchmark
      kind: benchmark
      procedure: Compare against the benchmark reference
      pass_condition: Matches reference within tolerance
---

Fixture plan body.
