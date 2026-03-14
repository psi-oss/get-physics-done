---
name: gpd:research-phase
description: Research how to tackle a phase (standalone - usually use /gpd:plan-phase instead)
argument-hint: "[phase]"
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - task
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Research how to tackle a phase. Spawns gpd-phase-researcher agent with phase context.

**Note:** This is a standalone research command. For most workflows, use `/gpd:plan-phase` which integrates research automatically.

**Use this command when:**

- You want to research without planning yet
- You want to re-research after planning is complete
- You need to investigate before deciding if a phase is feasible
- You need to survey the literature or mathematical landscape for a physics problem

**Orchestrator role:** Parse phase, validate against roadmap, check existing research, gather context, spawn researcher agent, present results.

**Why subagent:** Research burns context fast (literature searches, method surveys, source verification). Fresh 200k context for investigation. Main context stays lean for user interaction.
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
INIT=$(gpd init phase-op "$ARGUMENTS")
```

Extract from init JSON: `phase_dir`, `phase_number`, `phase_name`, `phase_found`, `commit_docs`, `has_research`, `project_contract`, `active_reference_context`, `reference_artifacts_content`.

Resolve researcher model:

```bash
RESEARCHER_MODEL=$(gpd resolve-model gpd-phase-researcher)
```

## 1. Validate Phase

```bash
PHASE_INFO=$(gpd roadmap get-phase "${phase_number}")
```

**If `found` is false:** Error and exit. **If `found` is true:** Extract `phase_number`, `phase_name`, `goal` from JSON.

## 2. Check Existing Research

```bash
ls .gpd/phases/${PHASE}-*/RESEARCH.md 2>/dev/null
```

**If exists:** Offer: 1) Update research, 2) View existing, 3) Skip. Wait for response.

**If doesn't exist:** Continue.

## 3. Gather Phase Context

```bash
# Phase section already loaded in PHASE_INFO
echo "$PHASE_INFO" | gpd json get .section --default ""
cat .gpd/REQUIREMENTS.md 2>/dev/null
cat .gpd/phases/${PHASE}-*/*-CONTEXT.md 2>/dev/null
grep -A30 "### Decisions" .gpd/STATE.md 2>/dev/null
```

Present summary with phase description, requirements, prior decisions.

## 4. Spawn gpd-phase-researcher Agent

Research modes: literature (default), feasibility, methodology, comparison.

```markdown
<research_type>
Phase Research -- investigating HOW to approach a specific physics problem or computation.
</research_type>

<key_insight>
The question is NOT "which method should I use?"

The question is: "What do I not know that I don't know?"

For this phase, discover:

- What is the established theoretical framework?
- What mathematical methods and computational tools form the standard approach?
- What approximations are standard and what are their regimes of validity?
- What problems do people commonly hit (divergences, instabilities, sign problems)?
- What is the current state-of-the-art vs what the model's training data says is SOTA?
- What should NOT be derived from scratch (use established results instead)?
- Are there known exact solutions, limiting cases, or benchmark results for validation?
- What are the key references (textbooks, review articles, seminal papers)?
  </key_insight>

<objective>
Research approach for Phase {phase_number}: {phase_name}
Mode: literature
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
Your RESEARCH.md will be loaded by `/gpd:plan-phase` which uses specific sections:

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

<quality_gate>
Before declaring complete, verify:

- [ ] All relevant subfields investigated (not just some)
- [ ] Negative claims verified with literature or established results
- [ ] Multiple sources for critical claims (cross-reference textbooks and papers)
- [ ] Confidence levels assigned honestly
- [ ] Approximation regimes clearly stated with validity conditions
- [ ] Section names match what plan-phase expects
      </quality_gate>

<output>
Write to: .gpd/phases/${PHASE}-{slug}/${PHASE}-RESEARCH.md
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

**`## RESEARCH COMPLETE`:** Display summary, offer: Plan phase, Dig deeper, Review full, Done.

**`## CHECKPOINT REACHED`:** Present to user, get response, spawn continuation.

**`## RESEARCH INCONCLUSIVE`:** Show what was attempted, offer: Add context, Try different mode, Manual.

## 6. Spawn Continuation Agent

```markdown
<objective>
Continue research for Phase {phase_number}: {phase_name}
</objective>

<prior_state>
Research file path: .gpd/phases/${PHASE}-{slug}/${PHASE}-RESEARCH.md
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
