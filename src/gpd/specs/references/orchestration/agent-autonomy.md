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
| **supervised** | New projects or high-stakes work | User approves every decision; agent waits at every checkpoint | Checkpoints after every task or physics choice |
| **balanced** | Standard research | Agent can make routine decisions but pausing for blockers | Standard physics checkpoints with automatic progress |
| **yolo** | Rapid exploratory or toy workloads | Agent can act autonomously but must still honor correctness gates | Checkpoints only for physics failures or blockers |

## Autonomy-Aware Plan Checking

Plan checking runs with the same contract, anchor, and verification rigor regardless of autonomy. Higher autonomy modes trigger extra scrutiny:

- **supervised:** Focus on blockers but still gate contracts, acceptance tests, and disconfirming paths.
- **balanced:** Validate all required dimensions, ensure non-interactive plans document explicit verification, and warn when estimated tasks exceed 60 minutes without checkpoints.
- **yolo:** Require independent testability for contract-critical outputs, limit scope creep, and flag plans that combine derivation and validation without clear failure isolation.

## Tangent Control Model

When a tangent arises (a legitimate alternative path), never silently branch. Resolve it with one of four outcomes:
1. `checkpoint:human-verify` when the tangent needs human input.
2. `checkpoint:decision` when a choice must be made about the tangent.
3. `checkpoint:defer` when the tangent is postponed but still relevant.
4. `checkpoint:complete` when tangents are resolved within the same handoff.

Report the chosen outcome before moving forward.

## Research Modes

Research mode (`GPD/config.json.research_mode`) governs how tangents are handled, not the correctness gates themselves. Use the metadata to frame how much tangent work to surface.

| Mode | Execution Style |
|---|---|
| **explore** | Surface alternatives as proposals; use the 4-way tangent model before branching.
| **balanced** | Stick to the plan unless a tangent reaches proposal status; document deviations.
| **exploit** | Suppress optional tangents unless explicitly requested; keep focus on contract progress.
| **adaptive** | Start in explore mode, then switch to exploit-style suppression once a decisive path is validated, and document the shift.

## Operator Reference

Read the config values during `load_project_state` so you always know which enforcement surfaces are active.

```bash
AUTONOMY=$(echo "$INIT" | gpd json get .autonomy --default balanced)
RESEARCH_MODE=$(echo "$INIT" | gpd json get .research_mode --default balanced)
```

If the fields are absent, default to `balanced`.
