---
name: gpd:show-phase
description: Inspect a single phase's artifacts, status, and results
argument-hint: "<phase-number>"
context_mode: project-required
requires:
  files: ["GPD/ROADMAP.md"]
allowed-tools:
  - file_read
  - shell
  - search_files
  - find_files
---


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

@GPD/STATE.md
@GPD/ROADMAP.md
</context>

<process>
Execute the included show-phase workflow end-to-end.
Preserve all report sections and formatting.

## Step 1: Init Context

```bash
INIT=$(gpd --raw init phase-op "$ARGUMENTS")
```

Extract from init JSON: `phase_dir`, `phase_number`, `phase_name`, `phase_found`, `phase_slug`, `padded_phase`.

**If `phase_found` is false:** Error with available phases and exit.

## Step 2: Load Phase Directory

List all files in the phase directory and categorize them (PLANs, SUMMARYs, CONTEXT, RESEARCH, VERIFICATION, VALIDATION, scripts, data).

## Step 3: Parse Roadmap

Read ROADMAP.md to extract this phase's description, goal, dependencies, and current status indicator.

## Step 4: Plan Completion

For standalone `PLAN.md` and numbered `*-PLAN.md`, check whether the matching `SUMMARY.md` / `*-SUMMARY.md` artifact exists. Present the results as a completion table.

## Step 5: Key Results

Extract key results from standalone `SUMMARY.md` and numbered `*-SUMMARY.md` files using `summary-extract`:

```bash
gpd --raw summary-extract <path> --field one_liner --field key_results --field equations
```

## Step 6: Verification Status

Check for `*-VERIFICATION.md` and `*-VALIDATION.md` files. Report their status (passed, issues found, pending).

## Step 7: Convention Changes

Check `SUMMARY.md` / `*-SUMMARY.md` frontmatter for `affects` fields that indicate convention changes introduced in this phase.

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
