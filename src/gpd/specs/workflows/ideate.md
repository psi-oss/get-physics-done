<purpose>
Run a source-grounded ideation session that turns papers or existing GPD knowledge into a durable blackboard, preserves the generator-critic exchange, and produces a ranked report of research questions plus the next best experiment, calculation, derivation, simulation, or literature check for each surviving idea.
</purpose>

<core_principle>
Final ranked ideas require source support. A topic can frame the session, but it is not evidence. Do not produce ranked source-grounded ideas until at least one non-topic source has a `source_manifest` row with `status: completed` or `status: reused`.
</core_principle>

<process>

<step name="validate_and_load_context" priority="first">
Run centralized command-context preflight before creating artifacts; stop and surface the validator output on failure.

Load current-workspace state, roadmap, config, and reference context without recent-project reentry; stop and surface initialization errors.

Parse `workspace_root`, `project_exists`, `state_exists`, `roadmap_exists`, `autonomy`, `research_mode`, and available reference/knowledge fields. The workflow may run before a GPD project exists; in that case all durable files stay under `./GPD/blackboards/` in the invoking workspace.
</step>

<step name="select_depth">
Parse `--depth fast|balanced|deep` from `$ARGUMENTS`.

If depth was not supplied, ask the user for one choice before source digestion:

- `fast`: one generator pass, one critic pass, one ideator revision, one report.
- `balanced`: two generator/critic rounds with a user steering checkpoint after round 1.
- `deep`: three rounds, broader search or more source digestion when needed, and user steering between rounds.

If `ask_user` is unavailable, present those three options in plain text and wait for the user's freeform response. Default to `fast` only when the user explicitly asks for the fastest path or the runtime cannot collect a depth choice.
</step>

<step name="initialize_artifacts">
Ensure the durable root `GPD/blackboards/` exists before writing session files.

Derive a stable ASCII topic slug from the explicit topic, the first source title/stem, or `ideation-session` when no better stem exists. Allocate collision-safe sibling paths:

```text
GPD/blackboards/ideate-YYYY-MM-DD-<topic-slug>.md
GPD/blackboards/ideate-YYYY-MM-DD-<topic-slug>-transcript.md
GPD/blackboards/ideate-YYYY-MM-DD-<topic-slug>-report.md
```

If a path already exists, append a numeric suffix before the transcript/report suffix, for example `ideate-YYYY-MM-DD-<topic-slug>-2.md`, `ideate-YYYY-MM-DD-<topic-slug>-2-transcript.md`, and `ideate-YYYY-MM-DD-<topic-slug>-2-report.md`.

Initialize exactly these three session files. The report file may stay in a blocked pre-report state until the source gate passes; do not create additional sibling digest, scratch, or round files.

Blackboard sections:

```text
# Ideation Blackboard

## Session
## User Preferences
## Source Manifest
## Source Digests
## Cross-Paper Model
## Tensions And Confusions
## Candidate Ideas
## Critic Notes
## Vetoed Ideas
## Ranked Questions
## Next Experiments Or Calculations
## Open Steering Questions
```

Transcript sections:

```text
# Ideation Transcript

## Turn 1

### User Or Workflow Prompt
### gpd-ideator Candidate Set
### gpd-ideation-critic Review
### gpd-ideator Revision
### Parent Synthesis
### Durable Effects
```

Report sections:

```text
# Ideation Report

## Executive Summary
## Source Corpus
## Ranked Research Questions
## Next Best Experiments Or Calculations
## Possible Issues
## Vetoed Ideas
## Recommended Next Actions
```
</step>

<step name="build_source_manifest">
Classify `$ARGUMENTS` into accepted inputs:

- arXiv IDs and URLs, including old-style IDs such as `hep-th/9901001`
- explicit `.pdf` files
- explicit `.tex` files
- directories containing paper-like `.tex` and `.pdf` files
- existing current-workspace `GPD/knowledge/K-*.md` documents
- free-form topic or question text

Use the current repo shared arXiv normalizer (`gpd.core.arxiv_source_download.normalize_arxiv_id`) when normalizing arXiv IDs. Keep directory scans shallow, accept only `.tex` and `.pdf`, prefer same-stem `.tex` over `.pdf`, and record duplicate/skipped files as warnings.

Create one source ledger in the blackboard init block:

```yaml
source_manifest:
  sources:
    - source_id: SRC-001
      kind: arxiv | pdf | tex | knowledge_doc | directory_item | topic | blocked
      input: ""
      normalized_ref: ""
      status: pending | completed | reused | blocked
      digest_path: ""
      warnings: []
```

Source IDs must be stable within the session and use `SRC-NNN`. Topic rows are useful context but are never evidence.
</step>

<step name="source_gate">
Before spawning ideation agents, enforce the source gate:

1. A final ranked idea must cite at least one `SRC-NNN` row whose `kind` is not `topic` or `blocked` and whose `status` is `completed` or `reused`.
2. If the invocation is only a topic and no usable project/knowledge sources are selected, ask exactly:

```text
Do you want to supply paper/arXiv/PDF/folder sources, or should GPD search for candidate papers?
```

3. If the user chooses to supply sources, stop after writing the blocked blackboard, transcript, and blocked report note. Tell the user to rerun with the sources or provide them in the continuation.
4. If the user chooses search, run a bounded literature search, show 3 to 5 candidate papers with short reasons, ask which papers to ingest, and only then continue to source digestion.
5. If no completed or reused non-topic sources are available after that step, leave the session blocked and do not produce ranked source-grounded ideas.

The blocked report state must not contain a `## Ranked Research Questions` list with invented entries. It should record that source grounding is pending.
</step>

<step name="digest_sources">
For each pending non-topic source, spawn `gpd-paper-digester` with the session paths and the `SRC-NNN` row. Existing current-workspace `GPD/knowledge/K-*.md` documents may be marked `reused` when they already provide a usable source-grounded surface; otherwise digest them like other source surfaces.

Resolve the digester model through the standard model-profile path; omit the model argument when no runtime-specific override is configured.

@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

```
task(
  subagent_type="gpd-paper-digester",
  model="{resolved_digester_model_if_any}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-paper-digester.md for your role and instructions.

Digest source {source_id} for the active ideation session.
Read the source manifest row, the selected source surface, and the current blackboard.
For `.tex`, read directly. For `.pdf`, use the current artifact-text extraction/validation path and preserve extraction warnings. For arXiv, use the normalized ID and prefer TeX/source when available.

Update only the session blackboard and transcript paths below, or return the digest content for the parent to append when direct writes are unavailable:
- ${SESSION_BLACKBOARD}
- ${SESSION_TRANSCRIPT}

Return a typed gpd_return envelope with status, source_id, digest_path or blackboard section anchor, grounding_warnings, and files_written.

<spawn_contract>
activation: "digest source {source_id}"
write_scope:
  mode: scoped_write
  allowed_paths:
    - ${SESSION_BLACKBOARD}
    - ${SESSION_TRANSCRIPT}
expected_artifacts:
  - ${SESSION_BLACKBOARD}
  - ${SESSION_TRANSCRIPT}
shared_state_policy: return_only
</spawn_contract>

Do not promote any knowledge document to stable. Do not write outside `GPD/blackboards/` unless the parent workflow explicitly selected a current-workspace draft `GPD/knowledge/` target.",
  description="Digest ideation source {source_id}"
)
```

After each return, verify that the matching `source_manifest` row is `completed`, `reused`, or `blocked`, and that warnings are visible in the blackboard. The source gate remains closed until at least one row is `completed` or `reused`.
</step>

<step name="run_ideation_rounds">
Run the selected number of rounds:

| Depth | Rounds | User steering |
| --- | --- | --- |
| `fast` | 1 | before final report only if the critic finds a hard blocker |
| `balanced` | 2 | after round 1 |
| `deep` | 3 | after rounds 1 and 2, with optional added source search/digestion |

For each round:

1. Parent updates the blackboard with source digests, depth, and user preferences.
2. Spawn `gpd-ideator` to propose candidate research questions and next experiments/calculations/checks.
3. Spawn `gpd-ideation-critic` to review candidates for source support, novelty, physics importance, feasibility, assumption risk, and experiment quality.
4. Critic marks each candidate as keep, revise, or veto.
5. Move vetoed ideas into `## Vetoed Ideas`; never delete them.
6. Spawn or continue `gpd-ideator` for revisions of kept/revise candidates.
7. Parent appends the readable turn to the transcript and updates blackboard sections.
8. If the depth requires steering, ask whether to continue, narrow, broaden, add sources, or stop early.

Resolve ideator and critic models through the standard model-profile path; omit model arguments when no runtime-specific override is configured.

```
task(
  subagent_type="gpd-ideator",
  model="{resolved_ideator_model_if_any}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-ideator.md for your role and instructions.

Use the active ideation blackboard and source manifest to generate or revise candidate research questions for round {round_number}.
Every candidate must include source_ids using `SRC-NNN`, a source-specific support note, ranking rationale, possible issues, and a next best experiment/calculation/check.
Do not use topic rows as evidence. Do not invent missing source support.

Write or return updates for:
- ${SESSION_BLACKBOARD}
- ${SESSION_TRANSCRIPT}

Return a typed gpd_return envelope with status, round_number, candidate_ids, veto_candidates_if_any, files_written, issues, and next_actions.

<spawn_contract>
activation: "ideator round {round_number}"
write_scope:
  mode: scoped_write
  allowed_paths:
    - ${SESSION_BLACKBOARD}
    - ${SESSION_TRANSCRIPT}
expected_artifacts:
  - ${SESSION_BLACKBOARD}
  - ${SESSION_TRANSCRIPT}
shared_state_policy: return_only
</spawn_contract>

Respect the source gate and return instead of inventing unsupported source links.",
  description="Ideate round {round_number}"
)
```

```
task(
  subagent_type="gpd-ideation-critic",
  model="{resolved_critic_model_if_any}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-ideation-critic.md for your role and instructions.

Review round {round_number} candidate ideas against the source manifest, digests, blackboard, and transcript.
Assess source support, novelty, physics importance, feasibility, hidden assumptions, whether the proposed experiment/calculation tests the idea, and whether the idea is actionable in the user's timeframe.
For each candidate return `keep`, `revise`, or `veto`. Veto when source support is insufficient, novelty is low, physics importance is low, feasibility is poor, assumptions are confused, the proposed check does not test the idea, the idea is outside the source corpus, or the result would be non-actionable.

Write or return updates for:
- ${SESSION_BLACKBOARD}
- ${SESSION_TRANSCRIPT}

Return a typed gpd_return envelope with status, round_number, decisions, vetoed_ideas, files_written, issues, and next_actions.

<spawn_contract>
activation: "critic round {round_number}"
write_scope:
  mode: scoped_write
  allowed_paths:
    - ${SESSION_BLACKBOARD}
    - ${SESSION_TRANSCRIPT}
expected_artifacts:
  - ${SESSION_BLACKBOARD}
  - ${SESSION_TRANSCRIPT}
shared_state_policy: return_only
</spawn_contract>

Return decisions in structured form so the parent can preserve vetoed ideas and update the transcript.",
  description="Critique ideation round {round_number}"
)
```
</step>

<step name="steering_checkpoints">
At each required steering checkpoint, show:

- completed/reused source count and any grounding warnings
- top kept or revised candidate questions
- veto count and short veto reasons
- open steering questions from the blackboard

Ask for one of:

1. continue
2. narrow to selected candidates
3. broaden with more sources/search
4. revise constraints or ranking priorities
5. stop and write the best supported report now

If the user interrupts, persist the blackboard and transcript, leave the report in a checkpoint state, and return a continuation note pointing to the three session files.
</step>

<step name="write_final_report">
Write the final report only after the source gate passes. Every non-vetoed ranked idea must include at least one `source_ids` entry that resolves to a completed or reused non-topic source row.

Visible ranked idea shape:

```yaml
question_id: RQ-001
research_question: ""
source_ids:
  - SRC-001
score:
  novelty: 1-5
  physics_importance: 1-5
  feasibility: 1-5
  overall: 1-5
why_it_matters: ""
next_best_experiment:
  type: calculation | derivation | simulation | real_world_experiment | literature_check
  objective: ""
  protocol: ""
  success_criterion: ""
  required_inputs: []
possible_issues:
  - ""
```

Vetoed idea shape:

```yaml
idea_id: VI-001
idea: ""
veto_reason: ""
vetoed_by: gpd-ideation-critic
source_ids: []
possible_revisit_condition: ""
```

Ranking criteria are novelty, physics importance, and feasibility. Every surviving idea needs a next best experiment, calculation, derivation, simulation, or literature check. The report must include possible issues with each idea and a separate `## Vetoed Ideas` section.

Do not expose the words `grounded`, `mixed`, or `speculative` as classification labels in the final report. Enforce grounding through `source_ids`, source-specific support, and the source gate instead.
</step>

<step name="return_results">
Return a concise completion summary with:

- blackboard path
- transcript path
- report path
- depth used
- number of completed/reused sources
- number of ranked research questions
- number of vetoed ideas
- recommended next action

If the source gate is blocked, return `status: blocked`, point to the blackboard/transcript/report paths, and ask for sources or permission to search. Do not summarize invented ranked ideas.
</step>

</process>

<success_criteria>
- [ ] Command context validated before artifact creation
- [ ] Durable root is `GPD/blackboards`
- [ ] Exactly three session files initialized: blackboard, transcript, and report
- [ ] Source manifest contains stable `SRC-NNN` rows
- [ ] Topic-only runs ask the required supply-sources-or-search question
- [ ] Final ranked ideas cite completed/reused non-topic `SRC-NNN` rows
- [ ] Depth mode is `fast`, `balanced`, or `deep`
- [ ] Transcript preserves `gpd-ideator` and `gpd-ideation-critic` turns
- [ ] Vetoed ideas appear in a separate report section
- [ ] User steering checkpoints are offered for balanced/deep rounds
</success_criteria>
