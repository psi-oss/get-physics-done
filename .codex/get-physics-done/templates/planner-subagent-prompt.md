---
template_version: 1
---

# Planner Subagent Prompt Template

Template for spawning `gpd-planner`. The planner agent owns the planning logic; this template carries phase-specific context, mode flags, and return conventions.

---

## Standard Planning Template

```markdown
<planning_context>
**Phase:** {phase_number}
**Mode:** {standard | gap_closure}
**Plan depth:** {full | light}
**Research mode:** {research_mode}
**Autonomy:** {autonomy}

**Project State:** {state_content}
**Roadmap:** {roadmap_content}
**Requirements:** {requirements_content}

**Phase Context:**
IMPORTANT: If context exists below, it contains USER DECISIONS from $gpd-discuss-phase.

- **Decisions** = LOCKED -- honor exactly, do not revisit
- **AI's Discretion** = Freedom -- make methodological choices
- **Deferred Ideas** = Out of scope -- do NOT include

{context_content}

**Research:** {research_content}
**Experiment Design (if exists):** {experiment_design_content}
**Gap Closure (if --gaps):** {verification_content} {validation_content}
</planning_context>

<physics_planning_requirements>
Each plan MUST include:

- **Mathematical rigor checkpoints:** Points where derivations must be verified for dimensional consistency, symmetry preservation, and correct tensor structure
- **Limiting case validation:** Explicit checks that results reduce correctly in all known limits (classical, non-relativistic, weak-coupling, thermodynamic, etc.)
- **Order-of-magnitude estimates:** Before any detailed calculation, estimate the expected scale of the answer
- **Error budget:** For numerical work, specify target precision and identify dominant error sources
- **Consistency checks:** Cross-checks between independent methods or approaches where possible
</physics_planning_requirements>

<light_mode_instructions>
**If plan depth is `light`:** Produce simplified plans containing ONLY:

- **must_haves** -- goal-backward success criteria
- **constraints** -- approximation regime, notation conventions, symmetry requirements
- **high-level approach** -- one paragraph describing the strategy (formalism, method, key steps)

Omit: code snippets, detailed task-by-task implementation steps, file paths, and wave assignments.
</light_mode_instructions>

<context_budget_guidance>
Context windows are finite (~200k tokens, ~80% usable). Plans must be sized accordingly:

- **Target per plan:** ~50% context budget (40% for hypothesis-driven plans)
- **Segment large phases** into multiple plans rather than one overloaded plan
- **Flag context-heavy plans** in frontmatter: `context_note: "Heavy - consider splitting if >6 tasks"`
- **Group related tasks** that share intermediate results in the same plan
- **Use waves** for independent work -- each subagent gets a fresh context window

See `./.codex/get-physics-done/references/orchestration/context-budget.md` for detailed budget allocation by workflow type.
</context_budget_guidance>

<downstream_consumer>
Output consumed by $gpd-execute-phase. Plans need:

- Frontmatter (`wave`, `depends_on`, `files_modified`, `autonomous`, `conventions`, `must_haves`)
- Tasks in XML format
- Verification criteria with mathematical rigor requirements
- must_haves derived from the phase goal
</downstream_consumer>

<quality_gate>

- [ ] PLAN.md files created in phase directory
- [ ] Each plan has valid frontmatter
- [ ] Tasks are specific and actionable with clear mathematical deliverables
- [ ] Dependencies correctly identified
- [ ] Waves assigned for parallel execution
- [ ] must_haves derived from phase goal including limiting case recovery
- [ ] Dimensional analysis check specified for each quantitative result
- [ ] Validation checkpoints placed after each major derivation step
</quality_gate>
```

---

## Revision Template

```markdown
<revision_context>
**Phase:** {phase_number}
**Mode:** revision

**Existing plans:** {plans_content}
**Checker issues:** {structured_issues_from_checker}

**Phase Context:**
Revisions MUST still honor user decisions.
{context_content}
</revision_context>

<instructions>
Make targeted updates to address checker issues.
Do NOT replan from scratch unless issues are fundamental.
Return what changed.
</instructions>
```

---

## Placeholders

| Placeholder | Source |
| --- | --- |
| `{phase_number}` | `gpd init plan-phase` |
| `{research_mode}` | `.gpd/config.json` or init JSON |
| `{autonomy}` | `.gpd/config.json` or init JSON |
| `{state_content}` | `state_content` from init JSON |
| `{roadmap_content}` | `roadmap_content` from init JSON |
| `{requirements_content}` | `requirements_content` from init JSON |
| `{context_content}` | phase `*-CONTEXT.md`, if present |
| `{research_content}` | fresh `*-RESEARCH.md` read after researcher completes |
| `{experiment_design_content}` | `*-EXPERIMENT-DESIGN.md`, if present |
| `{verification_content}` | phase `VERIFICATION.md` or init JSON |
| `{validation_content}` | phase validation/UAT notes, if present |
| `{plans_content}` | current PLAN.md files under revision |
| `{structured_issues_from_checker}` | checker return payload |

---

## Return Contract

Planner runs must return one of these markers:

- `## PLANNING COMPLETE`
- `## CHECKPOINT REACHED`
- `## PLANNING INCONCLUSIVE`

When returning `CHECKPOINT`, include the checkpoint type, the blocking decision, and the exact user input needed to continue.

---

## Failure Protocol

If planning cannot finish:

1. State the blocker concretely.
2. Report whether any PLAN.md files were written.
3. Return `## PLANNING INCONCLUSIVE`.
4. Provide the smallest next action: more context, retry, or manual intervention.
