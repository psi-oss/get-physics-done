---
name: gpd:goal
description: Run toward a stated goal under binding caps (USD budget and/or phase count) until achieved, budget-stopped, or blocked
argument-hint: "\"<goal statement>\" [--budget-usd <amount>] [--max-phases <n>] | --resume [--budget-usd <amount>] [--max-phases <n>]"
context_mode: project-required
requires:
  files: ["GPD/ROADMAP.md", "GPD/STATE.md"]
allowed-tools:
  - file_read
  - shell
  - find_files
  - search_files
  - ask_user
  - task
help:
  group: Planning and execution
  order: 205
  compact_description: Goal-directed autonomous run with binding caps and verifier-gated completion
  display_signature: gpd:goal "<goal>" [--budget-usd <amount>] [--max-phases <n>]
---

<objective>
Run the project toward an explicit goal contract under binding caps. The run
continues itself through a goal loop modeled on the autonomous workflow and
terminates in exactly one state: achieved (every success criterion's
plan-contract claim verified passed), budget_stopped (a cap bound; clean
checkpoint with receipt), or blocked.
</objective>

<execution_context>
Canonical workflow index: `{GPD_INSTALL_DIR}/workflows/goal.md` (compatibility
index only; never load it as a stage authority). The sole executable authority
is the bootstrap included below.

@{GPD_INSTALL_DIR}/workflows/goal/goal-bootstrap.md
</execution_context>

<context>
`--budget-usd <amount>` sets a binding USD cap (enforced when the runtime
records cost telemetry). `--max-phases <n>` sets a binding phase-count cap
(enforced everywhere). At least one cap is required. `--resume` re-enters a
stopped goal run on the existing contract, optionally replacing the caps.
</context>

<process>
Follow the included goal-bootstrap authority. The goal may only be marked
achieved by the verification-gated criteria check (`gpd --raw goal gate`) —
never by self-assessment.
</process>
