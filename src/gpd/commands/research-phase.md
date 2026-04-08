---
name: gpd:research-phase
description: Research how to tackle a phase (standalone - usually use gpd:plan-phase instead)
argument-hint: "[phase]"
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - task
---
<objective>
Research how to tackle a phase. Use this command when you want phase-specific investigation before planning or when you need to re-research after planning is complete.

**Orchestrator role:** Parse phase, validate against roadmap, check existing research, gather context, spawn researcher agent, present results.

**Why subagent:** Research burns context fast. Fresh context keeps the main context lean.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/research-phase.md
@{GPD_INSTALL_DIR}/references/orchestration/model-profile-resolution.md
</execution_context>

<context>
Phase number: $ARGUMENTS (required)

Normalize phase input in step 1 before any directory lookups.
</context>

<process>

## 0. Initialize Context

```bash
INIT=$(gpd --raw init phase-op --include state,config "$ARGUMENTS")
```

Extract from init JSON: `phase_dir`, `phase_number`, `phase_name`, `phase_found`, `commit_docs`, `has_research`, `project_contract`, `project_contract_gate`, `project_contract_load_info`, `project_contract_validation`, `active_reference_context`, `reference_artifacts_content`. Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true.

Resolve researcher model:

```bash
RESEARCHER_MODEL=$(gpd resolve-model gpd-phase-researcher)
```

## 1. Validate Phase

```bash
PHASE_INFO=$(gpd --raw roadmap get-phase "${phase_number}")
```

**If `found` is false:** Error and exit. **If `found` is true:** Extract `phase_number`, `phase_name`, `goal` from JSON.

## 2. Check Existing Research

```bash
ls "${phase_dir}/"*-RESEARCH.md 2>/dev/null
```

**If exists:** Offer: 1) Update research, 2) View existing, 3) Skip. Wait for response.

**If doesn't exist:** Continue.

## 3. Gather Phase Context

```bash
# Phase section already loaded in PHASE_INFO
echo "$PHASE_INFO" | gpd json get .section --default ""
cat GPD/REQUIREMENTS.md 2>/dev/null
cat "${phase_dir}/"*-CONTEXT.md 2>/dev/null
gpd --raw state snapshot | gpd json get .decisions --default "[]"
```

Present summary with phase description, requirements, prior decisions.

## 4. Spawn gpd-phase-researcher Agent

Research depth follows the workflow-owned `research_mode`. Do not invent separate command-local mode labels here.

```markdown
<research_type>
Phase Research -- investigating HOW to approach a specific physics problem or computation.
</research_type>

<objective>
Research approach for Phase {phase_number}: {phase_name}
Research depth: use the active workflow `research_mode` from init/config
</objective>

<context>
**Phase description:** {phase_description}
**Requirements:** {requirements_list}
**Prior decisions:** {decisions_if_any}
**Phase context:** {context_md_content}
**Active references:** {active_reference_context}
**Reference artifacts:** {reference_artifacts_content}
</context>

<downstream_consumer>
Your RESEARCH.md will be loaded by `gpd:plan-phase` which uses specific sections:

- `## User Constraints` -- Plans must honor locked decisions and scope boundaries
- `## Active Anchor References` -- Plans must keep mandated references, benchmarks, and prior artifacts visible
- `## Mathematical Framework` -- Derivations and calculations follow this formalism
- `## Standard Approaches` -- Plans use these mathematical/computational methods
- `## Existing Results to Leverage` -- Tasks use established results instead of re-deriving them
- `## Don't Re-Derive` -- Tasks cite and reuse these anchors directly
- `## Common Pitfalls` -- Verification steps check for these (divergences, gauge artifacts, numerical instabilities)
- `## Validation Strategies` -- Validation compares against these known solutions, limits, and benchmarks

Be prescriptive, not exploratory. "Use X" not "Consider X or Y."
</downstream_consumer>

<output>
Write to: {phase_dir}/{phase_number}-RESEARCH.md
</output>
```

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-phase-researcher.md for your role and instructions.\n\n" + filled_prompt,
  subagent_type="gpd-phase-researcher",
  model="{researcher_model}",
  readonly=false,
  description="Research Phase {phase}"
)
```

## 5. Handle Agent Return

Handle the researcher return through the workflow-owned child-return contract. Do not branch on heading text here.

- `gpd_return.status: completed` -- Verify `{phase_dir}/{phase_number}-RESEARCH.md` exists and passes the artifact gate, show the summary, and offer: Plan phase, Dig deeper, Review full, Done.
- `gpd_return.status: checkpoint` -- Present the checkpoint to the user, collect the response, and spawn a fresh continuation run.
- `gpd_return.status: blocked` or `failed` -- Show what was attempted and offer: Add context, Try different mode, Manual.

## 6. Spawn Continuation Agent

```markdown
<objective>
Continue research for Phase {phase_number}: {phase_name}
</objective>

<prior_state>
Research file path: {phase_dir}/{phase_number}-RESEARCH.md
Read that file before continuing so you inherit the prior research state instead of relying on an inline `@...` attachment.
</prior_state>

<checkpoint_response>
**Type:** {checkpoint_type}
**Response:** {user_response}
</checkpoint_response>
```

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-phase-researcher.md for your role and instructions.\n\n" + continuation_prompt,
  subagent_type="gpd-phase-researcher",
  model="{researcher_model}",
  readonly=false,
  description="Continue research Phase {phase}"
)
```

</process>

<success_criteria>

- [ ] Phase validated against roadmap
- [ ] Existing research checked
- [ ] gpd-phase-researcher spawned with context
- [ ] Checkpoints handled correctly
- [ ] User knows next steps
      </success_criteria>
