---
name: gpd:set-profile
description: Switch research profile for GPD agents (deep-theory/numerical/exploratory/review/paper-writing)
argument-hint: <profile>
context_mode: projectless
allowed-tools:
  - file_read
  - file_write
  - shell
---


<objective>
Switch the research profile used by GPD agents. Controls how each agent approaches physics tasks, balancing rigor and depth vs speed and breadth.

**Profiles:**

- **deep-theory**: Formal derivations with full mathematical rigor. Agents prioritize step-by-step proofs, explicit index manipulation, careful treatment of boundary terms, and complete justification of approximations. Best for: publishing-quality analytical work.
- **numerical**: Computational physics mode. Agents prioritize efficient implementations, numerical stability, convergence analysis, and performance. Best for: simulation development, data analysis, large-scale computations.
- **exploratory**: Creative exploration of new ideas. Agents prioritize breadth over depth, order-of-magnitude estimates, dimensional analysis, and rapid feasibility checks. Best for: brainstorming, literature surveys, scoping new directions.
- **review**: Validation and checking mode. Agents prioritize finding errors, verifying limits, cross-checking independent derivations, and testing edge cases. Best for: pre-submission review, debugging calculations, sanity checks.
- **paper-writing**: Publication-focused mode. Agents prioritize clear exposition, proper notation, complete derivation chains, and reader-friendly presentation. Best for: drafting manuscripts, preparing supplementary materials.

This command only changes `model_profile`. If you want to pin concrete runtime model IDs, use `gpd:set-tier-models`. If you want a workflow preset bundle or broader unattended/configuration changes, use `gpd:settings` so the existing knobs are resolved together instead of inventing a separate preset block.
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/set-profile.md
</execution_context>

<process>
Follow `@{GPD_INSTALL_DIR}/workflows/set-profile.md` exactly.
   </process>
