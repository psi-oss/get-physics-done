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

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Switch the research profile used by GPD agents. Controls how each agent approaches physics tasks, balancing rigor and depth vs speed and breadth.

**Profiles:**

- **deep-theory**: Formal derivations with full mathematical rigor. Agents prioritize step-by-step proofs, explicit index manipulation, careful treatment of boundary terms, and complete justification of approximations. Best for: publishing-quality analytical work.
- **numerical**: Computational physics mode. Agents prioritize efficient implementations, numerical stability, convergence analysis, and performance. Best for: simulation development, data analysis, large-scale computations.
- **exploratory**: Creative exploration of new ideas. Agents prioritize breadth over depth, order-of-magnitude estimates, dimensional analysis, and rapid feasibility checks. Best for: brainstorming, literature surveys, scoping new directions.
- **review**: Validation and checking mode. Agents prioritize finding errors, verifying limits, cross-checking independent derivations, and testing edge cases. Best for: pre-submission review, debugging calculations, sanity checks.
- **paper-writing**: Publication-focused mode. Agents prioritize clear exposition, proper notation, complete derivation chains, and reader-friendly presentation. Best for: drafting manuscripts, preparing supplementary materials.

Routes to the set-profile workflow which handles:

- Argument validation (deep-theory/numerical/exploratory/review/paper-writing)
- Config file creation if missing
- Profile update in config.json
- Confirmation with profile description display
- Reminder that `/gpd:settings` handles concrete runtime model IDs per tier
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/set-profile.md
</execution_context>

<process>
**Follow the set-profile workflow** from `@{GPD_INSTALL_DIR}/workflows/set-profile.md`.

The workflow handles all logic including:

1. Profile argument validation
2. Config file ensuring
3. Config reading and updating
4. Profile description table generation from RESEARCH_PROFILES
5. Confirmation display showing active profile and its characteristics
   </process>
