<purpose>
Own the phase-research child handoff, artifact gate, typed return routing, and
fresh continuation handoff after `phase_bootstrap` validates the selected phase.
</purpose>

<stage_boundary>
This authority starts only after `phase_bootstrap` has validated the phase, handled existing research, gathered phase context, and loaded the `research_handoff` staged payload. Do not read `workflows/research-phase.md`; it is only a staged-file index.
</stage_boundary>

<stage_prerequisites>
If this authority is entered fresh, reuse the `load_research_phase_stage` helper
from `phase_bootstrap` before loading `research_handoff`.
</stage_prerequisites>

<process>
## Step 4: Spawn Researcher

Load the heavier handoff slice only after phase validation, existing-research routing, and context gathering are complete:

Apply `references/orchestration/continuation-boundary.md`; local checkpoint trigger=researcher needs user input.

```bash
HANDOFF_INIT=$(load_research_phase_stage research_handoff "${phase_number}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $HANDOFF_INIT"
  exit 1
fi
```

Use the staged refresh for `contract_intake`, `effective_reference_intake`, `reference_artifact_files`, `active_references`, `selected_protocol_bundle_ids`, `protocol_bundle_load_manifest`, and `protocol_bundle_verifier_extensions` before assembling the child handoff. Read planning files by path only when needed; this stage does not receive embedded reference, protocol, state, config, or roadmap bodies.

@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-phase-researcher.md for your role and instructions.

<objective>
Research mathematical methods, physical principles, and computational approaches for Phase {phase}: {name}
</objective>

Research depth: use the active workflow research_mode from init/config ({RESEARCH_MODE}).

<context>
Phase description: {description}
Requirements: {requirements}
Prior decisions: {decisions}
Phase context: {context_md}
</context>

<files_to_read>
Use file_read for any listed path before relying on its body:
- GPD/REQUIREMENTS.md when phase objectives or acceptance criteria matter
- GPD/ROADMAP.md when the phase sequence or milestone context matters
- GPD/STATE.md / GPD/state.json when current project position or decisions matter
- Files named in `effective_reference_intake.must_include_prior_outputs`
- Files named in `reference_artifact_files` when relevant to the phase question
</files_to_read>

<reference_handoff>
<contract_intake>{contract_intake}</contract_intake>
<effective_reference_intake>{effective_reference_intake}</effective_reference_intake>
<active_references>{active_references}</active_references>
<reference_artifact_files>{reference_artifact_files}</reference_artifact_files>
</reference_handoff>

<protocol_bundle_handoff>
<selected_protocol_bundle_ids>{selected_protocol_bundle_ids}</selected_protocol_bundle_ids>
<protocol_bundle_load_manifest>{protocol_bundle_load_manifest}</protocol_bundle_load_manifest>
<protocol_bundle_verifier_extensions>{protocol_bundle_verifier_extensions}</protocol_bundle_verifier_extensions>
</protocol_bundle_handoff>

When `selected_protocol_bundle_ids` is non-empty, use `protocol_bundle_load_manifest` to read the listed bundle assets and use `protocol_bundle_verifier_extensions` as the primary specialized research checklist surface. Use the broad physics research directives below only for uncovered areas or when no bundle is selected.

<physics_research_directives>
Cover only what is needed for this phase:
framework, standard results, limiting cases, computational methods,
dimensional scales, and pitfalls relevant to this phase.
</physics_research_directives>

<output>
Write to: {phase_dir}/{phase_number}-RESEARCH.md
</output>",
  subagent_type="gpd-phase-researcher",
  model="{researcher_model}",
  readonly=false
)
```

Add this contract inside the spawned prompt when adapting it:

```markdown
<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - "{phase_dir}/{phase_number}-RESEARCH.md"
expected_artifacts:
  - "{phase_dir}/{phase_number}-RESEARCH.md"
shared_state_policy: return_only
</spawn_contract>
```

Child artifact gate: apply `references/orchestration/child-artifact-gate.md`; tuple: role=`gpd-phase-researcher`; expected=`{phase_dir}/{phase_number}-RESEARCH.md`; allowed_root=`{phase_dir}`; validators=readable research artifact; applicator=none; failure=`retry research | skip to plan-phase | abort/discuss`.

## Step 5: Handle Return

**If the researcher agent fails to spawn or returns an error:** Report the failure. End with `## > Next Up`: primary `gpd:research-phase {phase_number}` to retry, plus `gpd:plan-phase {phase_number}` to skip research and plan directly, and `gpd:suggest-next`. Do not silently continue without research output.

- **Artifact gate:** Accept completed only after the gate tuple passes for `RESEARCH.md`. If the artifact is missing, unreadable, or absent from `gpd_return.files_written`, end with `## > Next Up`: primary `gpd:research-phase {phase_number}` to retry, plus `gpd:plan-phase {phase_number}` and `gpd:suggest-next`.
- `gpd_return.status: completed` -- Display summary and end with `## > Next Up`: primary `gpd:plan-phase {phase_number}`, plus `gpd:research-phase {phase_number}` to dig deeper, `gpd:show-phase {phase_number}` to review, and `gpd:suggest-next`.
- `gpd_return.status: checkpoint` -- Present the checkpoint and continue only through a fresh continuation handoff under `references/orchestration/continuation-boundary.md`. End with `## > Next Up`: primary `gpd:resume-work`, plus `gpd:research-phase {phase_number}` and `gpd:suggest-next`.
- `gpd_return.status: blocked` or `failed` -- Show attempts and end with `## > Next Up`: primary `gpd:discuss-phase {phase_number}` to add context, plus `gpd:research-phase {phase_number}` and `gpd:suggest-next`.

## Step 6: Spawn Continuation Researcher

```markdown
<objective>
Continue research as a fresh continuation handoff for Phase {phase_number}: {phase_name}
</objective>

<prior_state>
Research file path: {phase_dir}/{phase_number}-RESEARCH.md
Read that file before continuing so you inherit the prior research state instead of relying on inline prompt state.
</prior_state>

<files_to_read>
Use file_read for GPD/REQUIREMENTS.md, GPD/ROADMAP.md, GPD/STATE.md / GPD/state.json, files named in `effective_reference_intake.must_include_prior_outputs`, and files named in `reference_artifact_files` when they are relevant to the continuation.
</files_to_read>

<checkpoint_response>
**Type:** {checkpoint_type}
**Response:** {user_response}
</checkpoint_response>

<reference_handoff>
<contract_intake>{contract_intake}</contract_intake>
<effective_reference_intake>{effective_reference_intake}</effective_reference_intake>
<active_references>{active_references}</active_references>
<reference_artifact_files>{reference_artifact_files}</reference_artifact_files>
</reference_handoff>

<protocol_bundle_handoff>
<selected_protocol_bundle_ids>{selected_protocol_bundle_ids}</selected_protocol_bundle_ids>
<protocol_bundle_load_manifest>{protocol_bundle_load_manifest}</protocol_bundle_load_manifest>
<protocol_bundle_verifier_extensions>{protocol_bundle_verifier_extensions}</protocol_bundle_verifier_extensions>
</protocol_bundle_handoff>

<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - "{phase_dir}/{phase_number}-RESEARCH.md"
expected_artifacts:
  - "{phase_dir}/{phase_number}-RESEARCH.md"
shared_state_policy: return_only
</spawn_contract>
```

```bash
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-phase-researcher.md for your role and instructions.\n\n" + continuation_prompt,
  subagent_type="gpd-phase-researcher",
  model="{researcher_model}",
  readonly=false,
  description="Continue research Phase {phase}"
)
```

<step name="mayfly_notebook_maintenance">
After the research handoff completes, update the Mayfly research notebook so the
next session starts informed (project_dir=$CWD). Skip silently if the gpd-mayfly
tools are unavailable.

1. `gpd_mayfly:read_session_log` — check for unprocessed sessions.
2. For each significant finding: `gpd_mayfly:upsert_knowledge(topic, content)`.
   Preserve prior evidence bullets; add `→ session NNN` links to new findings.
3. `gpd_mayfly:update_frontier` — current best approach, directions, dead ends.
4. `gpd_mayfly:append_journal_row` — outcome + summary + knowledge_updated slugs.
5. `gpd_mayfly:write_session_notes` — approach, what you found, what to try next.
6. If new topics or status changes: `gpd_mayfly:update_map`.
</step>

</process>

<success_criteria>
- [ ] Phase argument validated and phase info loaded
- [ ] Existing research checked (update/skip offered if present)
- [ ] Phase context gathered (roadmap section, requirements, prior decisions)
- [ ] gpd-phase-researcher spawned with physics research directives
- [ ] RESEARCH.md written to phase directory and named in `gpd_return.files_written`
- [ ] Next action offered (plan phase, dig deeper, review)
</success_criteria>
