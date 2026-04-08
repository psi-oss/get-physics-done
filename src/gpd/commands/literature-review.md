---
name: gpd:literature-review
description: Structured literature review for a physics research topic with citation network analysis and open question identification
argument-hint: "[topic or research question]"
context_mode: project-aware
allowed-tools:
  - file_read
  - file_write
  - shell
  - search_files
  - find_files
  - task
  - web_search
  - web_fetch
  - ask_user
---
<objective>
Conduct a systematic literature review for a physics research topic and produce a structured `LITERATURE-REVIEW.md` plus a machine-readable, strict `CITATION-SOURCES.json` sidecar for manuscript reuse.

**Orchestrator role:** Scope the review, spawn the gpd-literature-reviewer agent, handle checkpoints, and present results.

**Why subagent:** Literature searches burn context fast. Fresh context keeps the survey lean.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/literature-review.md
</execution_context>

<context>
Topic: $ARGUMENTS

Check for existing reviews:

```bash
ls GPD/literature/*.md 2>/dev/null | head -10
```

</context>

<process>

## 0. Initialize Context

```bash
CONTEXT=$(gpd --raw validate command-context literature-review "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi

INIT=$(gpd --raw init progress --include state,roadmap,config)
```

Extract `commit_docs`, `project_contract`, `project_contract_gate`, `project_contract_load_info`, `project_contract_validation`, `active_reference_context`, and any existing `reference_artifact_files` from init JSON. Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true. Resolve reviewer model:

```bash
REVIEWER_MODEL=$(gpd resolve-model gpd-literature-reviewer)
```

## 1. Scope the Review

Use ask_user to establish scope:

1. **Topic and focus** -- What specific physics question or subfield? (e.g., "topological insulators in 2D", not just "condensed matter")
2. **Depth** -- Quick survey (key papers only, ~10 refs) | Standard review (~30 refs) | Comprehensive survey (~50+ refs)
3. **Time range** -- All time | Last N years | Since specific paper/result
4. **Purpose** -- Background for new project | Finding methods for specific calculation | Identifying open problems | Preparing manuscript introduction

After all gathered, confirm scope and proceed.

## 2. Check Existing Reviews

```bash
ls GPD/literature/*.md 2>/dev/null
```

**If exists for same topic:** Offer: 1) Update with recent papers, 2) View existing, 3) Start fresh.

**If doesn't exist:** Continue.

## 3. Spawn gpd-literature-reviewer Agent

```markdown
<objective>
Conduct systematic literature review: {topic}

**Scope:**

- Depth: {depth}
- Time range: {time_range}
- Purpose: {purpose}
- Contract-critical anchors: {active_reference_context}

Keep the field-specific search protocol in the workflow-owned `gpd-literature-reviewer` instructions. This wrapper should only scope, checkpoint, and route.
</objective>
```

<output>
Write to: GPD/literature/{slug}-REVIEW.md

- Frontmatter (topic, date, depth, paper count)
- Executive Summary (3-5 key takeaways)
- Foundational Works (seminal papers with brief descriptions)
- Methodological Landscape (methods used, regimes, limitations)
- Key Results Catalog (tabulated: paper, method, result, conventions)
- Citation Network (intellectual lineages)
- Controversies and Disagreements (conflicting results)
- Open Questions (what remains unsolved)
- Current Frontier (state-of-the-art)
- Active Anchor Registry (must-read papers, decisive benchmarks, and prior artifacts to carry forward)
- Recommended Reading Path (ordered list for someone entering the field)
- Full Reference List (formatted citations)
- Citation Source Sidecar (`GPD/literature/{slug}-CITATION-SOURCES.json`, strict `CitationSource` records keyed by stable `reference_id`)
</output>

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-literature-reviewer.md for your role and instructions.\n\n" + filled_prompt,
  subagent_type="gpd-literature-reviewer",
  model="{reviewer_model}",
  readonly=false,
  description="Literature review {slug}"
)
```

## 4. Handle Agent Return

Handle the reviewer return through the workflow-owned child-return contract. Do not branch on heading text here.

- `gpd_return.status: completed` -- Verify `GPD/literature/{slug}-REVIEW.md` and `GPD/literature/{slug}-CITATION-SOURCES.json` exist and pass the artifact gate, display the executive summary and key takeaways, and offer: Deep dive on subtopic, Start research, Find gaps, Export references.
- `gpd_return.status: checkpoint` -- Present the checkpoint details to the user, collect the response, and spawn a fresh continuation run.
- `gpd_return.status: blocked` or `failed` -- Show what was found and what is missing, then offer: Broaden search, Narrow focus, Manual search, Accept partial.

## 5. Spawn Continuation agent (After Checkpoint)

```markdown
<objective>
Continue literature review: {topic}. Prior state in review file.
</objective>

<prior_state>
Review file path: GPD/literature/{slug}-REVIEW.md
Read that file before continuing so you inherit the prior search state instead of relying on an inline `@...` attachment.
</prior_state>

<checkpoint_response>
**Type:** {checkpoint_type}
**Response:** {user_response}
</checkpoint_response>
```

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-literature-reviewer.md for your role and instructions.\n\n" + continuation_prompt,
  subagent_type="gpd-literature-reviewer",
  model="{reviewer_model}",
  readonly=false,
  description="Continue review {slug}"
)
```

</process>

<success_criteria>

- [ ] Review scope established (topic, depth, time range, purpose)
- [ ] Existing reviews checked
- [ ] gpd-literature-reviewer spawned with structured search protocol
- [ ] Checkpoints handled correctly (convention conflicts, scope decisions)
- [ ] LITERATURE-REVIEW.md created with all sections
- [ ] Key results tabulated with methods and conventions
- [ ] Open questions identified
- [ ] Citation network mapped
- [ ] User knows next steps (research planning, gap analysis, manuscript prep)
      </success_criteria>
