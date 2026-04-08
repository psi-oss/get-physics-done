---
load_when:
  - "proof redteam"
  - "proof audit"
  - "theorem-bearing review"
  - "proof critique"
  - "theorem-to-proof alignment"
type: proof-redteam-protocol
tier: 1
context_cost: medium
---

# Proof Redteam Protocol

Use this protocol when a workflow needs a fail-closed adversarial proof audit. The goal is to catch scope narrowing, dropped hypotheses, missing parameter coverage, hidden assumptions, and unsupported conclusion clauses before any target is treated as established.

## Operating Rules

1. Treat each proof audit as a one-shot run. If user input is needed, return a checkpoint and stop.
2. The orchestrator owns the continuation handoff. Do not ask the user to wait inside the spawned run.
3. Reconstruct the proof inventory before judging correctness.
4. Audit the proof against the inventory line by line.
5. Run at least one adversarial probe.
6. Fail closed when coverage is incomplete, the claim narrows, or the artifact is malformed.
7. Write only the canonical proof-redteam artifact requested by the orchestrator.

## Supported Audit Modes

The proof critic can be invoked in four shared modes:

- `plan`
- `phase`
- `manuscript`
- `derivation`

Mode selection changes only the surrounding workflow bindings. The proof critic itself stays the same skeptical specialist.

Rules:

- `plan` mode audits plan-scoped theorem obligations and sibling proof artifacts.
- `phase` mode audits phase-scoped proof artifacts and freshness gates.
- `manuscript` mode adds workflow-owned manuscript binding fields such as the active manuscript snapshot and review round.
- `derivation` mode audits derivation-scoped theorem claims and their sibling proof artifact.

## Fail-Closed Semantics

The proof critic must not certify a result unless all required proof obligations are visible and covered.

Required behaviors:

- If the artifact path is missing or unreadable, return failure.
- If the exact claim text is not available, return failure.
- If a named parameter, hypothesis, quantifier, or conclusion clause is uncovered, return `gaps_found` unless a human decision is genuinely required.
- If the proof establishes only a special case, do not treat the claim as established.
- If the workflow requires a manuscript-scoped audit, the workflow must bind the manuscript fields explicitly; the proof critic must not invent them.

## Artifact Discipline

The proof critic writes the canonical proof-redteam artifact and nothing else.

Rules:

- The frontmatter must match the proof-redteam schema exactly.
- The body must include the proof inventory, coverage ledger, adversarial probe, verdict, and required follow-up.
- The artifact must be re-read from disk by the orchestrator before success is accepted.
- Return text is never enough on its own.

## Workflow Boundaries

Workflow owners decide when to invoke the proof critic and which mode to use.

- `peer-review` owns manuscript binding and manuscript-level proof review overlays.
- `verify-work` owns phase-level proof freshness and repair gating.
- `execute-phase` owns proof-bearing phase execution gates.
- `derive-equation` owns derivation-scoped theorem audits.

The proof critic should not absorb those workflow-specific rules into its universal kernel. Keep the kernel narrow and let the workflow inject the right binding only when needed.

