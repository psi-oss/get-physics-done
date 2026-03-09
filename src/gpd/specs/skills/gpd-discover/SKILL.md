---
name: gpd-discover
description: Run discovery phase to investigate methods, literature, and approaches before planning
argument-hint: "<phase> [--depth verify|standard|deep]"
requires:
  files: [".planning/ROADMAP.md"]
allowed-tools:
  - read_file
  - shell
  - grep
  - glob
  - web_search
  - web_fetch
---

<!-- Tool names in allowed-tools use canonical GPD names. Adapters translate per runtime. -->
<!-- @ includes are expanded at install time for runtimes that do not resolve them natively. -->

<objective>
Run a standalone discovery investigation for a research phase. Surveys the physics landscape: what is known, what methods exist, what approximations are valid, what data is available.

Produces RESEARCH.md (with `depth: quick`) that informs subsequent planning via $gpd-plan-phase.

**Use this when:**

- You want to investigate before planning (survey methods, check literature)
- You need to assess feasibility of a phase approach
- You want deeper discovery than plan-phase provides automatically
- You need to resolve ambiguous or contradictory information in the literature

**Depth levels:**

- `quick` (Level 1): Verify a formula, check a convention, confirm a known result (2-5 min)
- `medium` (Level 2): Choose between methods, explore a regime, compare approaches (15-30 min)
- `deep` (Level 3): Novel problems, contradictory literature, foundational choices (1+ hour)

**Related commands:**

- `$gpd-research-phase` — Spawns a dedicated researcher agent for deeper phase-specific investigation. Use when you need exhaustive domain knowledge for planning.
- `$gpd-literature-review` — Standalone literature survey for a topic (not tied to a specific phase). Use for broad field surveys or manuscript preparation.
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/discover.md
</execution_context>

<context>
Phase: $ARGUMENTS (required - phase number, optionally with --depth flag)

@.planning/STATE.md
@.planning/ROADMAP.md
</context>

<process>
Execute the discover workflow from @{GPD_INSTALL_DIR}/workflows/discover.md end-to-end.

## Step 0: Initialize

```bash
INIT=$(gpd init phase-op "$PHASE")
```

Extract: `phase_dir`, `phase_number`, `phase_name`, `phase_found`, `phase_slug`, `padded_phase`, `commit_docs`.

**If `phase_found` is false:** Error with available phases and exit.

## Step 1: Parse Arguments

Extract phase number and depth flag from $ARGUMENTS.
Default depth: `medium` (Level 2).

## Step 2: Execute Discovery

Follow the discover workflow for the determined depth level.

## Step 3: Commit (if Level 2-3 produced RESEARCH.md)

```bash
gpd commit "discover(${phase_number}): ${depth} discovery for ${phase_name}" --files ".planning/phases/${padded_phase}-${phase_slug}/RESEARCH.md"
```

## Step 4: Present Results and Next Steps

Show discovery summary, confidence level, and offer next actions.
</process>

<success_criteria>

- [ ] Phase validated against roadmap
- [ ] Depth level determined (default medium)
- [ ] Discovery executed at appropriate depth
- [ ] Standard references consulted before general search
- [ ] RESEARCH.md created (Level 2-3) with recommendation
- [ ] Confidence gate applied
- [ ] Committed to git (Level 2-3)
- [ ] Next steps offered (plan-phase, dig deeper, review)
      </success_criteria>
