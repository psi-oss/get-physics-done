---
name: gpd:audit-milestone
description: Audit research milestone completion against original research goals
argument-hint: "[version]"
context_mode: project-required
requires:
  files: [".gpd/ROADMAP.md", ".gpd/STATE.md"]
allowed-tools:
  - file_read
  - find_files
  - search_files
  - shell
  - task
  - file_write
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Verify a research milestone achieved its definition of done. Check whether the original research question has been answered, whether all claims are supported by derivations or data, whether results are internally consistent, and whether cross-phase integration is sound.

**This command IS the orchestrator.** Reads existing VERIFICATION.md files (phases already verified during execute-phase), aggregates open questions and deferred gaps, then spawns an integration checker for cross-phase consistency (e.g., do numerical results match analytical predictions? do approximations used in phase 3 remain valid given the parameter regime explored in phase 5?).
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/audit-milestone.md
</execution_context>

<context>
Version: $ARGUMENTS (optional — defaults to current milestone)

**Original Research Goals:**
@.gpd/PROJECT.md
@.gpd/REQUIREMENTS.md

**Planned Work:**
@.gpd/ROADMAP.md
@.gpd/config.json (if exists)

**Completed Work:**
find_files: .gpd/phases/*/*-SUMMARY.md
find_files: .gpd/phases/*/*-VERIFICATION.md
</context>

<inline_guidance>

## What Constitutes a Complete Milestone

- **All phases verified:** Every phase has a VERIFICATION.md with pass/conditional-pass status. No phase should be left unverified.
- **Cross-phase consistency checked:** Results from different phases must agree where they overlap. Analytical predictions from phase N match numerical results from phase M. Parameters used consistently across all phases.
- **Notation stable:** The same symbol means the same thing in every phase. No silent redefinitions of variables, conventions, or normalizations between phases.
- **Requirements 100% covered:** Every REQ-ID from REQUIREMENTS.md is mapped to a completed phase with supporting evidence (derivation, numerical result, or explicit deferral with justification).
- **Open questions catalogued:** Any unresolved issues or surprising results are explicitly listed for the next milestone, not left implicit.

## Common Audit Findings

- **Notation drift between phases:** Phase 1 uses omega for angular frequency, phase 4 uses omega for a solid angle. This silently corrupts any expression that combines results from both phases.
- **Approximation regime mismatch:** Phase 2 derives a result valid for T >> T_c, but phase 5 evaluates it at T = 1.1 T_c where corrections are large.
- **Missing limiting cases:** Results were obtained but never checked against known limits. The audit should flag any result that lacks at least one limiting-case verification.
- **Disconnected phases:** Two phases solve related problems but never compare answers. The integration checker should verify that results are compatible.
- **Deferred items forgotten:** Requirements marked "deferred" during planning that were never revisited or explicitly carried to the next milestone.
- **Inconsistent error bars:** Numerical results from different phases quote uncertainties estimated with different methods or at different confidence levels.

</inline_guidance>

<process>
Execute the audit-milestone workflow from @{GPD_INSTALL_DIR}/workflows/audit-milestone.md end-to-end.
Preserve all workflow gates (scope determination, verification reading, integration check, requirements coverage, routing).

The audit evaluates research completeness across these dimensions:

1. **Research question coverage** — Has each stated research question been answered or explicitly deferred with justification?
2. **Derivation completeness** — Are all analytical results derived from stated assumptions with no gaps in the logical chain?
3. **Claim support** — Is every claim in summaries backed by either a derivation, a numerical result, or a literature reference?
4. **Internal consistency** — Do results from different phases agree? Do analytical and numerical results match where they should?
5. **Limiting cases** — Have all expected limiting behaviors been checked (e.g., weak coupling, high temperature, non-relativistic limit)?
6. **Dimensional consistency** — Do all expressions have correct dimensions throughout?
7. **Error analysis** — Are uncertainties quantified for numerical results? Are approximation errors bounded?
8. **Literature comparison** — Have results been compared with existing literature where applicable?
9. **Open questions** — Are remaining open questions explicitly catalogued for the next milestone?
   </process>
