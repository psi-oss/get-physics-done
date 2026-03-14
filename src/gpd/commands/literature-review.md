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

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Conduct a systematic literature review for a physics research topic. Identifies key papers, maps citation networks, catalogs methods and results, finds open questions, and produces a structured LITERATURE-REVIEW.md.

**Orchestrator role:** Scope the review, spawn gpd-literature-reviewer agent, handle checkpoints, present results.

**Why subagent:** Literature searches burn context fast (reading abstracts, following citation chains, cross-referencing results, tracking conventions across papers). Fresh 200k context for the full survey. Main context stays lean for user interaction.

A physics literature review is not a bibliography. It is a map of the intellectual landscape: who computed what, using which methods, with what assumptions, getting what results, and where do they agree or disagree. The reviewer must think like a physicist surveying a field, not a librarian cataloging references.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/literature-review.md
</execution_context>

<context>
Topic: $ARGUMENTS

Check for existing reviews:

```bash
ls .gpd/literature/*.md 2>/dev/null | head -10
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

INIT=$(gpd init progress --include state,roadmap,config)
```

Extract `commit_docs`, `project_contract`, `active_reference_context`, and any existing `reference_artifact_files` from init JSON. Resolve reviewer model:

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
ls .gpd/literature/*.md 2>/dev/null
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
  </objective>

<review_strategy>
A physics literature review follows a structured protocol:

1. **Identify foundational works** -- The seminal papers that defined the field or subfield. These are non-negotiable: every physicist in the area knows them.

2. **Map the methodological landscape** -- What theoretical and computational methods have been applied?

   - Analytical: perturbation theory, exact solutions, variational methods, RG, etc.
   - Numerical: Monte Carlo, exact diagonalization, DMRG, DFT, molecular dynamics, etc.
   - Each method has a regime of validity, characteristic approximations, and known limitations.

3. **Catalog key results** -- For each significant paper:

   - What was computed (observable, quantity, prediction)
   - What method was used (and its limitations)
   - What was found (numerical value, scaling law, phase diagram feature)
   - What conventions were used (units, metric signature, Fourier conventions)
   - How it connects to other results (agrees, disagrees, extends, corrects)
   - Whether it should be treated as a must-surface benchmark or comparison target downstream

4. **Trace citation networks** -- Which papers cite which? Where are the intellectual lineages?

   - Method A lineage: paper1 -> paper2 -> paper3 (progressively refined)
   - Method B lineage: paperX -> paperY (competing approach)
   - Reconciliation papers: where different methods were compared

5. **Identify controversies and disagreements** -- Where do published results conflict?

   - Different numerical values for the same quantity
   - Different phase diagram topologies
   - Competing theoretical explanations
   - Unresolved sign or factor disagreements

6. **Find open questions** -- What has NOT been computed or resolved?

   - Quantities mentioned but never calculated
   - Regimes where no method works reliably
   - Long-standing conjectures without proof
   - Experimental predictions not yet tested

7. **Assess the current frontier** -- What is state-of-the-art right now?
   - Most recent results and their significance
   - Active groups and their focus areas
   - Emerging methods or approaches
     </review_strategy>

<source_hierarchy>

1. **Textbooks and monographs** -- For established results and standard methods
2. **Review articles** (Rev. Mod. Phys., Physics Reports, Annual Reviews) -- For field overview
3. **Seminal papers** -- Original derivations and key breakthroughs
4. **Recent arXiv preprints** -- For current state-of-the-art
5. **Conference proceedings** -- For very recent results and community direction
   </source_hierarchy>

<output>
Write to: .gpd/literature/{slug}-REVIEW.md

Structure:

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
  </output>
```

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

**If `## REVIEW COMPLETE`:**

- Display executive summary and key takeaways
- Report paper count and coverage assessment
- Offer options:
  - "Deep dive on subtopic" -- focus on one aspect found during review
  - "Start research" -- use review to plan a research phase
  - "Find gaps" -- identify what's missing for a specific calculation
  - "Export references" -- format for BibTeX / manuscript

**If `## CHECKPOINT REACHED`:**

- Present checkpoint details to user
- Common checkpoints in literature review:
  - "Found conflicting conventions between major references -- which do you want to adopt?"
  - "Two competing theoretical frameworks -- which is more relevant to your work?"
  - "Need access to a paywalled paper -- can you provide the key results?"
  - "Scope is broader than expected -- should I narrow focus?"
- Get user response
- Spawn continuation agent

**If `## REVIEW INCONCLUSIVE`:**

- Show what was found and what's missing
- Offer options:
  - "Broaden search" -- expand keywords and sources
  - "Narrow focus" -- restrict to specific subtopic
  - "Manual search" -- provide specific papers to include
  - "Accept partial" -- use what was found

## 5. Spawn Continuation agent (After Checkpoint)

```markdown
<objective>
Continue literature review: {topic}. Prior state in review file.
</objective>

<prior_state>
Review file path: .gpd/literature/{slug}-REVIEW.md
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
