---
name: gpd:discover
description: Run discovery phase to investigate methods, literature, and approaches before planning
argument-hint: "[phase or topic] [--depth quick|medium|deep]"
context_mode: project-aware
command-policy:
  schema_version: 1
  subject_policy:
    subject_kind: discovery_subject
    resolution_mode: phase_or_topic
    explicit_input_kinds:
      - phase number or standalone topic
    allow_interactive_without_subject: true
  supporting_context_policy:
    project_context_mode: project-aware
    project_reentry_mode: disallowed
    optional_file_patterns:
      - GPD/STATE.md
      - GPD/ROADMAP.md
  output_policy:
    output_mode: managed
    managed_root_kind: gpd_managed_durable
    default_output_subtree: GPD/analysis
allowed-tools:
  - file_read
  - shell
  - search_files
  - find_files
  - web_search
  - web_fetch
---


<objective>
Run a discovery investigation for an explicit research phase or standalone topic. Surveys the physics landscape: what is known, what methods exist, what approximations are valid, what data is available.

`--depth quick` (`depth: quick`) is verification-only and returns without writing `RESEARCH.md` or any other discovery file. Produces RESEARCH.md for `--depth medium` or `--depth deep`, which informs subsequent planning via gpd:plan-phase.
Standalone Level 2-3 artifacts live under `GPD/analysis/` in the invoking workspace; phase-scoped discovery stays in the resolved phase directory.

**Use this when:**

- You want to investigate before planning (survey methods, check literature)
- You need to assess feasibility of a phase approach
- You want deeper discovery than plan-phase provides automatically
- You need to resolve ambiguous or contradictory information in the literature

**Depth levels:**

- `quick` (Level 1): Verify a formula, check a convention, confirm a known result (2-5 min)
- `medium` (Level 2): Choose between methods, explore a regime, compare approaches (15-30 min)
- `deep` (Level 3): Novel problems, contradictory literature, foundational choices (1+ hour)
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/discover.md
</execution_context>

<context>
Phase or topic: $ARGUMENTS

@GPD/STATE.md
@GPD/ROADMAP.md
</context>

<process>
Execute the discover workflow from @{GPD_INSTALL_DIR}/workflows/discover.md end-to-end.

## Step 0: Validate Context

```bash
CONTEXT=$(gpd --raw validate command-context discover "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

If a phase number is supplied, use project phase context.
If no phase number is supplied, require an explicit topic.
Do not treat the mere presence of a project as enough to choose a discovery target.
If a project-backed invocation arrives without either a phase number or a topic, ask one focused question before continuing.

## Step 1: Parse Arguments

Extract a phase number or explicit topic, plus the optional depth flag, from `$ARGUMENTS` or from the focused clarification response when the project-backed invocation arrived without either.
Default depth: `medium` (Level 2).

## Step 2: Execute Discovery

Follow the discover workflow for the determined depth level.

## Step 3: Persistence Policy (if Level 2-3 produced RESEARCH.md)

Do not commit `RESEARCH.md` separately.
If discovery ran phase-scoped, leave the phase `RESEARCH.md` in the working tree for the later phase-completion commit.
If discovery ran in standalone mode, report the findings directly and, for Level 2-3, point to `GPD/analysis/discovery-{slug}.md` under the invoking workspace. Do not emit phase-only commit messages or file paths.

## Step 4: Present Results and Next Steps

Show discovery summary, confidence level, and offer next actions.
</process>

<success_criteria>

- [ ] Phase validated against roadmap
- [ ] Depth level determined (default medium)
- [ ] Discovery executed at appropriate depth
- [ ] Standard references consulted before general search
- [ ] RESEARCH.md created (Level 2-3) with recommendation, or Level 1 returned verification-only confirmation without writing a file
- [ ] Confidence gate applied
- [ ] No separate RESEARCH.md commit
- [ ] Next steps offered (plan-phase, dig deeper, review)
      </success_criteria>
