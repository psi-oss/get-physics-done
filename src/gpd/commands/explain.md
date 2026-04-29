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
Route a request for a rigorous explanation into the workflow-owned implementation.

This wrapper owns command-context validation and the public output-root boundary only. The same-named workflow owns scope clarification, context gathering, explainer delegation, citation audit, result lookup, and reporting.

**Why subagent:** Fresh context lets `gpd-explainer` handle the explanation and `gpd-bibliographer` audit citations without bloating the orchestrator.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/explain.md
</execution_context>

<context>
Concept, result, method, notation, or paper: $ARGUMENTS

GPD-authored explanation artifacts stay under `GPD/explanations/` rooted at the current workspace.
Use `{GPD_INSTALL_DIR}/references/results/result-lookup-policy.md` for upstream result dependencies.
If `$ARGUMENTS` is empty in standalone mode, stop and ask the user to rerun with an explicit concept/topic.

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

Let the included workflow handle target clarification, project/standalone mode, result-registry lookup, explainer delegation, citation auditing, and final reporting.

Follow the included explain workflow end-to-end.
</process>

<success_criteria>

- [ ] Standalone or project context validated
- [ ] Explain workflow executed as the authority for mechanics
- [ ] Explanation artifacts kept under the current workspace's `GPD/explanations/`
</success_criteria>
