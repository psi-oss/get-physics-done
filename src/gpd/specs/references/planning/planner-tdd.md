## TDD Plan Structure for Computational Physics

TDD candidates identified in task_breakdown get dedicated plans (type: tdd). One computational capability per TDD plan.

```markdown
---
phase: XX-name
plan: NN
type: tdd
---

<objective>
[What computational capability and why]
Purpose: [Why TDD matters here -- numerical code must be correct, not just "seems to work"]
Output: [Working, tested computational tool]
</objective>

<capability>
  <name>[Capability name]</name>
  <files>[source file, test file]</files>
  <behavior>
    [Expected behavior in testable terms]
    Cases:
    - harmonic_oscillator(n=0) -> E = 0.5 * hbar * omega (within 1e-12)
    - harmonic_oscillator(n=10) -> E = 10.5 * hbar * omega (within 1e-10)
    - hydrogen_atom(n=1, l=0) -> E = -13.6 eV (within 0.01 eV)
  </behavior>
  <implementation>[How to implement once tests pass]</implementation>
  <physics_benchmarks>
    [Known analytical results to test against]
    [Conservation laws that must hold]
    [Limiting cases that must be reproduced]
  </physics_benchmarks>
</capability>
```

## Red-Green-Optimize Cycle for Physics Code

**RED:** Create test file -> write test asserting known physics result -> run test (MUST fail) -> commit: `test({phase}-{plan}): add failing test for [capability] against [analytical benchmark]`

**GREEN:** Write minimal code to pass physics benchmark -> run test (MUST pass) -> commit: `calc({phase}-{plan}): implement [capability]`

**OPTIMIZE (if needed):** Optimize numerical performance, improve convergence -> run tests (MUST still pass, including ALL physics benchmarks) -> commit: `optimize({phase}-{plan}): improve [capability]`

Each TDD plan produces 2-3 atomic commits.

**Physics-specific TDD principle:** The test suite IS the physics. If your code passes tests against known analytical results, conservation laws, and limiting cases, it is doing physics correctly. If it doesn't, no amount of "looks reasonable" matters.

## Context Budget for TDD

TDD plans target ~40% context (lower than standard 50%). The RED->GREEN->OPTIMIZE back-and-forth with file reads, test runs, and output analysis is heavier than linear execution. Physics TDD is especially heavy because benchmark comparisons involve nontrivial analytical expressions.
