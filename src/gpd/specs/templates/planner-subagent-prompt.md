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
**Project Contract:** {project_contract}
**Roadmap:** {roadmap_content}
**Requirements:** {requirements_content}
**Active References:** {active_reference_context}
**Reference Artifacts:** {reference_artifacts_content}

**Phase Context:**
IMPORTANT: If context exists below, it contains USER DECISIONS from /gpd:discuss-phase.

- **Decisions** = LOCKED -- honor exactly, do not revisit
- **Agent's Discretion** = Freedom -- make methodological choices
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
- **Contract completeness:** Every plan must carry decisive claims, deliverables, references, acceptance tests, forbidden proxies, and uncertainty markers in frontmatter
- **Anchor discipline:** If a benchmark, paper, dataset, baseline, or prior artifact is contract-critical, surface it in the plan instead of treating it as optional background
</physics_planning_requirements>

<contract_completion_requirements>
If `project_contract` is non-empty:

- Every PLAN.md must include a `contract` frontmatter block with exact IDs for claims, deliverables, references, acceptance tests, and forbidden proxies.
- Every PLAN.md must carry forward required context from the contract: must-read refs, prior outputs, baselines, and user anchors when execution depends on them.
- Every PLAN.md must include uncertainty markers from the contract when they constrain interpretation or verification.
- `must_haves` must be the compatibility projection of this `contract` block, not a separate free-form invention.
- Autonomy mode and model profile may change cadence or detail, but they do NOT relax contract completeness.
- If the planner cannot determine the right contract slice for the phase, return `## CHECKPOINT REACHED` instead of writing a weak plan.
</contract_completion_requirements>

<light_mode_instructions>
**If plan depth is `light`:** Keep the full canonical frontmatter, including `wave`, `depends_on`, `files_modified`, `interactive`, `conventions`, `contract`, and derived `must_haves`.

Simplify only the body:

- keep one high-level task block per plan
- keep verification and success criteria concise
- omit code snippets and unnecessary implementation detail

Light mode changes verbosity, not contract completeness.
</light_mode_instructions>

<context_budget_guidance>
Context windows are finite (~200k tokens, ~80% usable). Plans must be sized accordingly:

- **Target per plan:** ~50% context budget (40% for hypothesis-driven plans)
- **Segment large phases** into multiple plans rather than one overloaded plan
- **Flag context-heavy plans** in frontmatter: `context_note: "Heavy - consider splitting if >6 tasks"`
- **Group related tasks** that share intermediate results in the same plan
- **Use waves** for independent work -- each subagent gets a fresh context window

See `{GPD_INSTALL_DIR}/references/orchestration/context-budget.md` for detailed budget allocation by workflow type.
</context_budget_guidance>

<downstream_consumer>
Output consumed by /gpd:execute-phase. Plans need:

- Frontmatter (`wave`, `depends_on`, `files_modified`, `interactive`, `conventions`, `contract`, `must_haves`)
- Tasks in XML format
- Verification criteria with mathematical rigor requirements
- Contract-complete claim, deliverable, reference, acceptance-test, forbidden-proxy, and uncertainty-marker coverage
- must_haves derived from the selected contract slice and phase goal
- Contract-critical anchors and benchmarks surfaced wherever the plan depends on them
</downstream_consumer>

<quality_gate>

- [ ] PLAN.md files created in phase directory
- [ ] Each plan has valid frontmatter
- [ ] Each plan includes a contract block with claims, deliverables, references, acceptance tests, forbidden proxies, and uncertainty markers
- [ ] Tasks are specific and actionable with clear mathematical deliverables
- [ ] Dependencies correctly identified
- [ ] Waves assigned for parallel execution
- [ ] must_haves derived from the contract and phase goal including limiting case recovery
- [ ] Required refs, prior outputs, and baselines are surfaced in `<context>` or verification paths
- [ ] Forbidden proxies are rejected explicitly in `<done>` or `<success_criteria>`
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
**Project Contract:** {project_contract}
**Active References:** {active_reference_context}
**Reference Artifacts:** {reference_artifacts_content}

**Phase Context:**
Revisions MUST still honor user decisions.
{context_content}
</revision_context>

<instructions>
Make targeted updates to address checker issues.
Do NOT replan from scratch unless issues are fundamental.
Fix contract-gate blockers first: missing decisive outputs, missing acceptance tests, missing anchor refs, forbidden-proxy misses, and missing disconfirming paths.
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
| `{project_contract}` | `project_contract` from init JSON |
| `{roadmap_content}` | `roadmap_content` from init JSON |
| `{requirements_content}` | `requirements_content` from init JSON |
| `{active_reference_context}` | `active_reference_context` from init JSON |
| `{reference_artifacts_content}` | `reference_artifacts_content` from init JSON |
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
