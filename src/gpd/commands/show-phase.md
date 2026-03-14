---
name: gpd:show-phase
description: Inspect a single phase's artifacts, status, and results
argument-hint: "<phase-number>"
context_mode: project-required
requires:
  files: [".gpd/ROADMAP.md"]
allowed-tools:
  - file_read
  - shell
  - search_files
  - find_files
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Inspect a single research phase in detail: its artifacts, completion status, key results, convention changes, and verification state. Produces a structured report for quick situational awareness.

Use this when you want a deep look at one specific phase rather than overall project progress.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/show-phase.md
</execution_context>

<context>
Phase: $ARGUMENTS (required)
- Phase number to inspect (e.g., "3", "2.1")

@.gpd/STATE.md
@.gpd/ROADMAP.md
</context>

<process>
Execute the show-phase workflow from @{GPD_INSTALL_DIR}/workflows/show-phase.md end-to-end.
Preserve all report sections and formatting.

## Step 1: Init Context

```bash
INIT=$(gpd init phase-op "$ARGUMENTS")
```

Extract from init JSON: `phase_dir`, `phase_number`, `phase_name`, `phase_found`, `phase_slug`, `padded_phase`.

**If `phase_found` is false:** Error with available phases and exit.

## Step 2: Load Phase Directory

List all files in the phase directory and categorize them (PLANs, SUMMARYs, CONTEXT, RESEARCH, DISCOVERY, VERIFICATION, VALIDATION, scripts, data).

## Step 3: Parse Roadmap

Read ROADMAP.md to extract this phase's description, goal, dependencies, and current status indicator.

## Step 4: Plan Completion

For each PLAN.md, check if a matching SUMMARY.md exists. Present as completion table.

## Step 5: Key Results

Extract key results from SUMMARY.md files using `summary-extract`:

```bash
gpd summary-extract <path> --field one_liner --field key_results --field equations
```

## Step 6: Verification Status

Check for VERIFICATION.md and VALIDATION.md files. Report their status (passed, issues found, pending).

## Step 7: Convention Changes

Check SUMMARY.md frontmatter for `affects` fields that indicate convention changes introduced in this phase.

## Step 8: File Listing

List all files produced with sizes and modification dates.

Present everything as a structured ASCII report.
</process>

<success_criteria>

- [ ] Phase validated against roadmap
- [ ] All artifacts listed with completion status
- [ ] Key results extracted from summaries
- [ ] Verification/validation status shown
- [ ] Convention changes highlighted
- [ ] File listing with sizes
- [ ] Clear ASCII-formatted report
      </success_criteria>
