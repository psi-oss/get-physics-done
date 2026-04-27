---
name: gpd:explain
description: Explain a physics concept rigorously in the context of the active project or a standalone question with an explicit topic
argument-hint: "[concept, result, method, notation, or paper]"
context_mode: project-aware
command-policy:
  schema_version: 1
  subject_policy:
    subject_kind: explanation_subject
    resolution_mode: explanation_input
    explicit_input_kinds:
      - concept, result, method, notation, or paper
    allow_interactive_without_subject: true
  supporting_context_policy:
    project_context_mode: project-aware
    project_reentry_mode: disallowed
    optional_file_patterns:
      - GPD/STATE.md
      - GPD/ROADMAP.md
      - GPD/explanations/*.md
  output_policy:
    output_mode: managed
    managed_root_kind: gpd_managed_durable
    default_output_subtree: GPD/explanations
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
Produce a rigorous, well-scoped explanation of a concept, method, notation, result, or paper in the context of the user's current research workflow.

Keep any GPD-authored explanation artifacts under `GPD/explanations/` rooted at the current workspace. In project-backed runs that means the resolved project root's `GPD/explanations/`; in standalone runs it means `./GPD/explanations/` in the invoking workspace.

**Orchestrator role:** Clarify scope when necessary, gather local project/process context, spawn a `gpd-explainer` agent, optionally run `gpd-bibliographer` to verify cited papers, and present the finished explanation plus reading path.

**Why subagent:** The explanation needs local state, notation, nearby derivations, and literature context. Fresh context keeps it rigorous.
When available, the explainer should also use the derived citation-source catalog so literature guides can prefer stable `reference_id` anchors and openable URLs instead of reconstructing papers from prose.
If the topic is already represented in `intermediate_results`, follow `{GPD_INSTALL_DIR}/references/results/result-lookup-policy.md` before explaining it so the explanation anchors to stored equation, phase, verification, dependency, and impact context instead of reconstructing that context from prose.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/explain.md
</execution_context>

<context>
Concept or topic: $ARGUMENTS

Check for prior explanation artifacts:

```bash
ls GPD/explanations/*.md 2>/dev/null | head -10
```

</context>

<process>

## 0. Validate Context

```bash
CONTEXT=$(gpd --raw validate command-context explain "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

## 1. Parse Request

Extract the target concept from `$ARGUMENTS`.

- If `$ARGUMENTS` is empty in project-context mode, ask one focused question to identify the concept, result, method, notation, or paper to explain.
- If `$ARGUMENTS` is empty in standalone mode, stop and ask the user to rerun with an explicit concept/topic; standalone preflight should already have rejected the empty launch.
- If the request is non-empty but materially ambiguous and the active project does not disambiguate it, ask one focused clarification question.
- Otherwise infer the intended scope from the current phase, manuscript work, notation, and nearby project files.
- If the concept looks like a derived equation or stored quantity, apply `{GPD_INSTALL_DIR}/references/results/result-lookup-policy.md` before falling back to prose-only context.

## 2. Gather Context

If a GPD project exists, load project state and current-process context before spawning the explainer.

## 3. Execute the Explain Workflow

Follow the explain workflow from `@{GPD_INSTALL_DIR}/workflows/explain.md` end-to-end.

## 4. Return Results

Show the explanation summary, report path, citation-audit status, and the best papers to open next. If derived citation-source context is available, prefer it when naming follow-up papers or links.
</process>

<success_criteria>

- [ ] Standalone or project context validated
- [ ] Relevant local files and active-process context gathered when available
- [ ] `gpd-explainer` spawned with a scoped objective
- [ ] Explanation written with clear structure, project grounding, and literature guide
- [ ] Citations verified by `gpd-bibliographer` or uncertainty explicitly flagged
- [ ] User receives report path plus recommended follow-up papers/questions
      </success_criteria>
