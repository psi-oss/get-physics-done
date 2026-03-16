---
name: gtd:measure-lambda
description: Display current λ₂ across all active foundations
context_mode: project-required
allowed-tools:
  - shell
---

<objective>
Measure and display the global coherence λ₂ of the current project or foundation.
</objective>

<process>
1. Scan project artifacts for phase headers.
2. Calculate λ₂ using the `get-arkhe-done` coherence module.
3. Report the result and the current phase trajectory.
</process>
