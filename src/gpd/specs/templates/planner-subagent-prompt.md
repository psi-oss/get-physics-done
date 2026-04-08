---
template_version: 1
---

# Planner Subagent Prompt Template

Template for spawning `gpd-planner`. Keep wrappers thin: pass phase-specific inputs, mode flags, and return conventions; do not restate planner policy.

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

**Project State:** {state_content}
**Project Contract:** {project_contract}
**Project Contract Gate:** {project_contract_gate}
**Project Contract Load Info:** {project_contract_load_info}
**Project Contract Validation:** {project_contract_validation}
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
Keep dimensions, limits, and cross-method consistency explicit. For proof-bearing work, keep hypotheses, parameters, and conclusions auditable in the body.
</physics_planning_requirements>

<contract_visibility_requirements>
Planning requires an approved `project_contract`. If `project_contract_gate.authoritative` is false, `project_contract_load_info.status` starts with `blocked`, or `project_contract_validation.valid` is false, return `## CHECKPOINT REACHED` instead of guessing.
Keep `project_contract` as the grounding ledger. Use `effective_reference_intake` and `active_reference_context` only as readable projections of the same anchors.
Treat stable knowledge docs surfaced through `active_reference_context` and `reference_artifacts_content` as reviewed background syntheses. They may clarify assumptions, caveats, and method choice when they agree with stronger sources, but they do not override `convention_lock`, `project_contract`, the PLAN `contract`, `contract_results`, `comparison_verdicts`, proof-review artifacts, or direct benchmark/result evidence.
If stable knowledge materially shapes the plan, surface it explicitly in existing plan structures or prose; do not invent a separate knowledge authority or ledger.
Use explicit `knowledge_deps` when a plan materially depends on a reviewed knowledge doc and downstream gating should be enforced; keep implicit stable background advisory only.
Treat `approach_policy` as execution policy only. Keep `scope.in_scope` populated and `contract.context_intake` concrete enough to audit.
For proof-bearing work, use an explicit non-`other` `claim_kind` with auditable hypotheses, quantified variables, and named parameters.
</contract_visibility_requirements>

<tangent_control>
Do not silently branch or widen scope. If multiple viable main-line paths remain and the user has not chosen among them, return `## CHECKPOINT REACHED` instead of emitting parallel plans.
</tangent_control>

<light_mode_instructions>
**If plan depth is `light`:** Keep the full canonical frontmatter and contract block. Light mode changes body verbosity only.
</light_mode_instructions>

<context_budget_guidance>
Keep plan prompts concise. Prefer fresh reads over copied history, and split oversized phases instead of overloading one plan.
</context_budget_guidance>

<downstream_consumer>
Output is consumed by gpd:execute-phase. Plans need frontmatter, XML tasks, rigorous verification criteria, complete contract coverage, explicit dependency wiring, and surfaced anchors or benchmarks. Reflect selected protocol bundle guidance in tasks, verification paths, and decisive artifact choices.
</downstream_consumer>

<quality_gate>
- [ ] PLAN.md files created in phase directory
- [ ] Frontmatter is valid
- [ ] The contract block is complete per `plan-contract-schema.md`
- [ ] `tool_requirements` are declared whenever specialized machine-checkable prerequisites exist
- [ ] `tool_requirements` pass `gpd validate plan-preflight <PLAN.md>` before the plan is treated as execution-ready
- [ ] Tasks are specific, actionable, and testable
- [ ] Dependencies and waves are correct
- [ ] Required refs, prior outputs, baselines, and protocol bundle guidance are surfaced where needed
- [ ] Forbidden proxies are rejected explicitly
- [ ] Dimensional analysis and validation checkpoints cover each quantitative result
- [ ] Proof-bearing plans keep proof artifacts and sibling `*-PROOF-REDTEAM.md` audits explicit
</quality_gate>
```

## Revision Template

```markdown
<revision_context>
**Phase:** {phase_number}
**Mode:** revision

**Existing plans:** {plans_content}
**Checker issues:** {structured_issues_from_checker}
**Project State:** {state_content}
**Project Contract:** {project_contract}
**Project Contract Gate:** {project_contract_gate}
**Project Contract Load Info:** {project_contract_load_info}
**Project Contract Validation:** {project_contract_validation}
**Contract Intake:** {contract_intake}
**Effective Reference Intake:** {effective_reference_intake}
**Protocol Bundles:** {protocol_bundle_context}
**Active References:** {active_reference_context}
**Reference Artifacts:** {reference_artifacts_content}
Stable knowledge docs may appear in the shared reference surfaces above. Treat them as reviewed background synthesis only: they can shape assumptions and method choice when consistent with stronger sources, but they do not override `convention_lock`, `project_contract`, the PLAN `contract`, or direct evidence.
If a plan materially depends on a reviewed knowledge doc and the reliance must be gateable downstream, express that dependency with explicit `knowledge_deps`; otherwise keep the knowledge implicit and advisory.

**Phase Context:**
Revisions MUST still honor user decisions.
{context_content}
</revision_context>

<instructions>
Make targeted updates to address checker issues.
Do NOT replan from scratch unless issues are fundamental.
If `project_contract_gate.authoritative` is false, `project_contract_load_info.status` starts with `blocked`, or `project_contract_validation.valid` is false, return `## CHECKPOINT REACHED` instead of patching around guessed scope.
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
| `{project_contract_gate}` | `project_contract_gate` from init JSON |
| `{project_contract_load_info}` | `project_contract_load_info` from init JSON |
| `{project_contract_validation}` | `project_contract_validation` from init JSON |
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
