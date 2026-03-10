---
name: gpd:plan-milestone-gaps
description: Create phases to close all gaps identified by research milestone audit
context_mode: project-required
requires:
  files: [".gpd/v*-MILESTONE-AUDIT.md"]
allowed-tools:
  - file_read
  - file_write
  - shell
  - find_files
  - search_files
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Create all phases necessary to close gaps identified by `/gpd:audit-milestone`.

Reads MILESTONE-AUDIT.md, groups gaps into logical phases, creates phase entries in ROADMAP.md, and offers to plan each phase.

One command creates all fix phases — no manual `/gpd:add-phase` per gap.

Physics research gaps fall into distinct categories that map naturally to phase types:

- **Missing derivations** — An intermediate step was assumed without proof, or a result was quoted without re-derivation in the current notation. Phase type: analytical calculation.
- **Unchecked limiting cases** — A formula should reduce to a known result in some limit (e.g., weak coupling, large N, zero temperature) but this was never verified. Phase type: analytical verification.
- **Unvalidated numerical results** — Code produces numbers but they were never checked against analytical predictions, known benchmarks, or convergence tests. Phase type: numerical validation.
- **Missing error analysis** — Numerical results lack error bars, convergence studies, or systematic error estimates. Approximation bounds were never computed. Phase type: error analysis.
- **Incomplete literature comparison** — Results were not compared with prior work, or discrepancies with published results were noted but not resolved. Phase type: literature review.
- **Unsupported claims** — A summary or conclusion makes a claim that is not backed by any derivation or data in the completed phases. Phase type: depends on the claim.
- **Internal inconsistencies** — Results from different phases disagree (e.g., analytical prediction does not match numerics, or two derivations give different answers). Phase type: debugging / reconciliation.
- **Dimensional or symmetry violations** — An expression has wrong dimensions, or breaks a symmetry that should be preserved. Phase type: analytical correction.
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/plan-milestone-gaps.md
</execution_context>

<context>
**Audit results:**
find_files: .gpd/v*-MILESTONE-AUDIT.md (use most recent)

**Original intent (for prioritization):**
@.gpd/PROJECT.md
@.gpd/REQUIREMENTS.md

**Current state:**
@.gpd/ROADMAP.md
@.gpd/STATE.md
</context>

<process>
Execute the plan-milestone-gaps workflow from @{GPD_INSTALL_DIR}/workflows/plan-milestone-gaps.md end-to-end.
Preserve all workflow gates (audit loading, prioritization, phase grouping, user confirmation, roadmap updates).

Prioritization should consider:

1. **Correctness blockers first** — Dimensional errors, sign errors, and internal inconsistencies must be resolved before anything else. A wrong result cannot be published or built upon.
2. **Foundations before extensions** — Missing derivations and unchecked limits come before literature comparisons or error analysis, because if the core result is wrong, everything downstream is wasted effort.
3. **Publishability gates** — Error analysis and literature comparison are required for publication but can be deferred if the milestone goal is "establish the result" rather than "write the paper."
4. **Scope control** — Some gaps may be intentionally deferred to the next milestone. The user decides; the system presents options with clear consequences.
   </process>
