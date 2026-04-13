# Agent Autonomy & Profiles Reference

## Profile Calibration

Load the shared `GPD/config.json` profile when moderating execution rigor. The profile controls how much detail, documentation, and verification an agent adds beyond the universal correctness gates, but it does not alter the requirement to honor contracts, acceptance tests, anchors, disconfirming paths, and forbidden proxy checks.

| Profile | Execution Style | Checkpoint Cadence | Documentation Level |
|---|---|---|---|
| **deep-theory** | Maximum rigor, derivations from first principles, and explicit symmetry checks | After every derivation step | Full equations and justifications |
| **numerical** | Focus on convergence, error budgets, and reproducibility | After each numerical result | Detailed numerical logs, seeds, and tolerances |
| **exploratory** | Fast iteration, optional elaboration minimized | Per task start/end | Concise highlights and blockers |
| **review** | Cross-check every result against literature and benchmarks | With each comparison point | Full literature citations |
| **paper-writing** | Publication-ready presentation, notation, and citations | After each section | Structured, publication-quality prose |

## Autonomy Mode Behavior

Autonomy (`GPD/config.json.autonomy`) changes decision boundaries, not correctness. Always execute the same sanity gates: sign, dimension, convention, cancellation, self-critique, and contract validation.

| Mode | When to Use | Decision Behavior | Checkpoint Handling |
|---|---|---|---|
| **supervised** | New projects or high-stakes work | User approves scope-changing decisions and explicit review-stop outcomes; correctness gates still run exactly as usual | Stop at required review gates and user-visible decisions |
| **balanced** | Standard research | Agent can make routine decisions and auto-continue on clean passes, but must pause for blockers, unresolved review stops, or scope-changing choices | Standard physics checkpoints remain active; clean gates may continue automatically |
| **yolo** | Rapid exploratory or toy workloads | Agent may auto-continue on clean passes, but it must never skip correctness, first-result, skeptical, or pre-fanout gates | Stop only on blockers, failed required gates, or unresolved review stops; a gate may auto-continue only after it is explicitly cleared |

Autonomy never changes delegation semantics. Spawned agents remain one-shot handoffs: if a child run needs user input, it returns a checkpoint and the wrapper starts a fresh continuation instead of keeping the same child alive.

## Autonomy-Aware Plan Checking

Plan checking runs with the same contract, anchor, and verification rigor regardless of autonomy. Higher autonomy modes trigger extra scrutiny:

- **supervised:** Focus on blockers but still gate contracts, acceptance tests, and disconfirming paths.
- **balanced:** Validate all required dimensions, ensure non-interactive plans document explicit verification, and warn when estimated tasks exceed 60 minutes without checkpoints.
- **yolo:** Require independent testability for contract-critical outputs, limit scope creep, and flag plans that combine derivation and validation without clear failure isolation.

## Tangent Control Model

When a tangent arises (a legitimate alternative path), do not silently pursue it. Treat it as a proposal and classify it with exactly one of these four decisions:
1. `ignore` — not a real tangent; continue the approved mainline plan.
2. `defer` — record it briefly for later follow-up, then continue the mainline plan.
3. `branch_later` — recommend `gpd:tangent ...` or `gpd:branch-hypothesis ...` as explicit follow-up, but do not create new side work during the current pass.
4. `pursue_now` — only when the user explicitly requested tangent exploration or the approved contract already includes that alternative path.

This is proposal-first, not a new execution state machine. Tangent proposals ride on existing bounded review stops such as first-result, skeptical, or pre-fanout review.

## Research Modes

Research mode (`GPD/config.json.research_mode`) governs how tangents are handled, not the correctness gates themselves. Use the metadata to frame how much tangent work to surface.

| Mode | Execution Style |
|---|---|
| **explore** | Surface alternatives as tangent proposals and classify each one as `ignore | defer | branch_later | pursue_now` before branching. |
| **balanced** | Stick to the plan unless a tangent survives proposal review; document deviations instead of silently widening scope. |
| **exploit** | Suppress optional tangents by default; prefer `ignore` or `defer` unless the user or approved contract explicitly asks for tangent exploration. |
| **adaptive** | Start in explore mode, then switch to exploit-style suppression once a decisive path is validated, and document when the shift happens. |

## Operator Reference

Read the config values during `load_project_state` so you always know which enforcement surfaces are active.

```bash
AUTONOMY=$(echo "$INIT" | gpd json get .autonomy --default balanced)
RESEARCH_MODE=$(echo "$INIT" | gpd json get .research_mode --default balanced)
```

If the fields are absent, default to `balanced`.
