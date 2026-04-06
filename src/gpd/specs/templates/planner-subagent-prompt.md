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

Use `@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md` as the canonical contract source. Keep this prompt for scope selection, mode flags, and return conventions only.
If `{project_contract}` is empty, stale, or too underspecified to identify the phase contract slice, return `## CHECKPOINT REACHED` rather than guessing.
Treat `approach_policy` as execution policy only.

**Project State:** {state_content}
**Project Contract:** {project_contract}
**Contract Intake:** {contract_intake}
**Effective Reference Intake:** {effective_reference_intake}
**Roadmap:** {roadmap_content}
**Requirements:** {requirements_content}
**Protocol Bundles:** {protocol_bundle_context}
**Active References:** {active_reference_context}
**Reference Artifacts:** {reference_artifacts_content}

**Phase Context:**
IMPORTANT: If context exists below, it contains USER DECISIONS from gpd:discuss-phase.

- **Decisions** = LOCKED -- honor exactly, do not revisit
- **Agent's Discretion** = Freedom -- make methodological choices
- **Deferred Ideas** = Out of scope -- do NOT include

{context_content}

**Research:** {research_content}
**Experiment Design (if exists):** {experiment_design_content}
**Gap Closure (if --gaps):** {verification_content} {validation_content}
</planning_context>

<physics_planning_requirements>
Keep dimensions, limits, proof coverage, and cross-method consistency explicit. Keep `contract.context_intake` specific, and make proof-bearing hypotheses, parameters, and conclusions auditable in the body.
</physics_planning_requirements>

<contract_completion_requirements>
Planning requires `project_contract`. Keep the contract block complete per the schema include. Use `effective_reference_intake` and `active_reference_context` for grounding, not as substitutes. Autonomy and model profile may change cadence, not contract completeness.
</contract_completion_requirements>

<contract_visibility_shortcuts>
The contract still exposes defaultable semantic fields: `observables[].kind`, `deliverables[].kind`, `acceptance_tests[].kind`, `references[].kind`, `references[].role`, and `links[].relation`. They default to `other` and may be omitted only when that generic category is actually intended.
Treat `approach_policy` as execution policy only; it does not substitute for grounding.
Include `references[]` only when the contract does not already carry explicit grounding through `context_intake` or preserved scoping inputs.
**Proof claim audit:** For theorem/proof work, enumerate hypotheses, quantified variables, and named parameters explicitly enough to catch silently narrowed subcases or dropped assumptions.
**Stale proof review gate:** If a proof-backed deliverable or theorem statement changes after review, rerun the proof audit before accepting the repaired target.
</contract_visibility_shortcuts>

<light_mode_instructions>
**If plan depth is `light`:** Keep the full canonical frontmatter, including `wave`, `depends_on`, `files_modified`, `interactive`, `conventions`, `contract`, and `contract.context_intake`. Simplify only the body: one high-level task block per plan, concise verification, no extra code snippets. Light mode changes verbosity, not contract completeness.
</light_mode_instructions>

<context_budget_guidance>
Context windows are finite (~200k tokens, ~80% usable). Target ~50% budget per plan, ~40% for hypothesis-driven plans, and split large phases into multiple plans instead of overloading one. Flag context-heavy plans in frontmatter and use waves so independent work gets fresh context. See `{GPD_INSTALL_DIR}/references/orchestration/context-budget.md` for budget details.
</context_budget_guidance>

<downstream_consumer>
Output consumed by gpd:execute-phase. Plans need frontmatter, XML tasks, rigorous verification criteria, complete contract coverage, explicit dependency wiring, and surfaced anchors/benchmarks. Reflect selected protocol bundle guidance in tasks, verification paths, and decisive artifact choices.
</downstream_consumer>

<quality_gate>
- [ ] PLAN.md files created in phase directory
- [ ] Frontmatter is valid
- [ ] The contract block is complete per `plan-contract-schema.md`
- [ ] Tasks are specific, actionable, and testable
- [ ] Dependencies and waves are correct
- [ ] Required refs, prior outputs, baselines, and protocol bundle guidance are surfaced where needed
- [ ] Forbidden proxies are rejected explicitly
- [ ] Dimensional analysis and validation checkpoints cover each quantitative result
</quality_gate>
```

## Canonical PLAN Contract Schema

Load the validator-enforced PLAN contract schema before writing or revising any `contract:` block:

@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md

---

## Revision Template

```markdown
<revision_context>
**Phase:** {phase_number}
**Mode:** revision

**Existing plans:** {plans_content}
**Checker issues:** {structured_issues_from_checker}
**Project State:** {state_content}
**Project Contract:** {project_contract}
**Contract Intake:** {contract_intake}
**Effective Reference Intake:** {effective_reference_intake}
**Protocol Bundles:** {protocol_bundle_context}
**Active References:** {active_reference_context}
**Reference Artifacts:** {reference_artifacts_content}

## Canonical PLAN Contract Schema

@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md

**Phase Context:**
Revisions MUST still honor user decisions.
{context_content}
</revision_context>

<instructions>
Make targeted updates to address checker issues.
Do NOT replan from scratch unless issues are fundamental.
If the approved project contract is missing or no longer sufficient to identify the right phase slice, return `## CHECKPOINT REACHED` instead of patching around guessed scope.
Fix contract-gate blockers first: missing decisive outputs, missing acceptance tests, missing anchor refs, forbidden-proxy misses, and missing disconfirming paths.
Return what changed.
</instructions>
```

---

## Placeholders

| Placeholder | Source |
| --- | --- |
| `{phase_number}` | `gpd --raw init plan-phase` |
| `{research_mode}` | `GPD/config.json` or init JSON |
| `{autonomy}` | `GPD/config.json` or init JSON |
| `{state_content}` | `state_content` from init JSON |
| `{project_contract}` | `project_contract` from init JSON |
| `{roadmap_content}` | `roadmap_content` from init JSON |
| `{requirements_content}` | `requirements_content` from init JSON |
| `{protocol_bundle_context}` | `protocol_bundle_context` from init JSON |
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
