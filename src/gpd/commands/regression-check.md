---
name: gpd:regression-check
description: Scan completed phase summaries and verifications for convention conflicts and verification-state regressions
argument-hint: "[phase number to limit scope, or empty for all]"
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - find_files
  - search_files
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Run the lightweight regression audit implemented by `gpd regression-check`.

This command does **not** re-run physics, numerical, dimensional, or contract verification. It scans already-recorded phase artifacts for regressions in verification state:

1. Convention conflicts across completed `*-SUMMARY.md` frontmatter
2. Missing, invalid, or non-canonical `*-VERIFICATION.md` statuses
3. Completed phases whose `*-VERIFICATION.md` still reports unresolved gaps

Use `/gpd:verify-work <phase>` when a flagged phase needs actual re-verification.

Output: structured CLI/JSON result with `passed`, `phases_checked`, and `issues`.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/regression-check.md
</execution_context>

<context>
Scope: $ARGUMENTS (optional)
- If a number (e.g., "3"): scan only that completed phase
- If empty: scan all completed phases
- Local `gpd regression-check --quick` additionally limits the scan to the two most recent completed phases

@GPD/STATE.md
@GPD/ROADMAP.md
</context>

<process>
Execute the regression-check workflow from @{GPD_INSTALL_DIR}/workflows/regression-check.md end-to-end.
Preserve the workflow gates that mirror the shipped implementation:

1. Validate command context and determine phase scope
2. Discover completed phases from plan + summary artifacts
3. Scan `*-SUMMARY.md` frontmatter for conflicting convention definitions
4. Scan `*-VERIFICATION.md` frontmatter for parse failures, invalid statuses, or unresolved gaps
5. Return the structured issue list without inventing a synthetic report file or claiming physics was re-verified
</process>
