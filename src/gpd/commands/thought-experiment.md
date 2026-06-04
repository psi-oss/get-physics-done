---
name: gpd:thought-experiment
description: Run Gedanken experiments to generate theoretical postulates and conjectures as inspiration before a rigorous derivation or proof
argument-hint: "[phase number or topic]"
context_mode: project-aware
command-policy:
  schema_version: 1
  subject_policy:
    subject_kind: thought_experiment_subject
    resolution_mode: phase_or_topic
    explicit_input_kinds:
      - phase number or standalone topic
  supporting_context_policy:
    project_context_mode: project-aware
    project_reentry_mode: disallowed
    optional_file_patterns:
      - GPD/STATE.md
      - GPD/ROADMAP.md
      - GPD/research-map/*.md
      - GPD/analysis/*.md
  output_policy:
    output_mode: managed
    managed_root_kind: gpd_managed_durable
    default_output_subtree: GPD/analysis
    stage_artifact_policy: gpd_owned_outputs_only
allowed-tools:
  - file_read
  - file_write
  - shell
  - search_files
  - find_files
  - task
help:
  group: Planning and execution
  order: 215
  compact_description: Generate thought experiments and candidate postulates for a project phase or an explicit topic, before rigorous derivation
  display_signature: gpd:thought-experiment [phase or topic]
  examples:
    - gpd:thought-experiment "what limits the entanglement entropy of an evaporating black hole"
  notes:
    - Produces unproven conjectures filtered by cheap physics checks; it is inspiration, not proof, and routes survivors to gpd:derive-equation or gpd:plan-phase.
  root_detail_order: 135
---


<objective>
Route a thought-experiment request into the workflow-owned ideation flow.

Generate Gedanken (thought) experiments around a physical question and distill
them into candidate theoretical postulates and conjectures — the inspiration
that *precedes* a rigorous derivation or proof. Provide a phase number or an
explicit topic as the argument. This command is non-interactive: it never opens
a prompt. If no phase or topic is supplied, stop and print guidance asking the
caller to re-run with an explicit topic or phase number — do not ask a
clarification question and do not block waiting for input.

This command deliberately favors breadth and physical insight over rigor. Every
postulate it emits is an explicitly unproven conjecture, pre-filtered by cheap
sanity checks (dimensions, symmetry, conservation, known limits) so that
obviously-wrong ideas are discarded before expensive rigorous work begins. The
same-named workflow owns framing, idea generation, postulate extraction,
plausibility filtering, artifact writing, and routing to the rigorous lane.

Keep standalone/current-workspace durable artifacts under `GPD/analysis/` rooted
at the invoking workspace. Only runs with authoritative phase context may
additionally write a sibling phase artifact.
</objective>

<context>
Phase or topic: $ARGUMENTS

Validated command-context owns optional current-workspace project context. Use
the `CONTEXT` payload and the workflow-owned `init` step for optional
`GPD/STATE.md` / `GPD/ROADMAP.md` background when present; this wrapper must not
attach raw project-file includes.
</context>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/thought-experiment.md
</execution_context>

<process>

**Pre-flight check:**
```bash
CONTEXT=$(gpd --raw validate command-context thought-experiment "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Parse the returned JSON before continuing.

The workflow owns canonical target resolution plus `slug` and `OUTPUT_PATH`
selection. Do not promise phase-local artifacts, project state mutation, or
commits when authoritative phase context is absent.

Follow the included thought-experiment workflow end-to-end. Postulates are
inspiration only: never present them as established results, and always offer
the rigorous follow-up (`gpd:derive-equation`, `gpd:branch-hypothesis`, or
`gpd:plan-phase`).
</process>

<success_criteria>

- [ ] Command context validated
- [ ] Thought-experiment workflow executed as the authority for mechanics
- [ ] Postulates marked as unproven conjectures with a proposed rigorous next step
- [ ] Standalone/current-workspace outputs kept under `GPD/analysis/`
</success_criteria>
</output>
