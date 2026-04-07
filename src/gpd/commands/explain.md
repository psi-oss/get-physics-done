---
name: gpd:explain
description: Explain a physics concept rigorously in the context of the active project or standalone question
argument-hint: "[concept, result, method, notation, or paper]"
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
Produce a rigorous, well-scoped explanation of a concept, method, notation, result, or paper in the context of the user's current research workflow.

**Orchestrator role:** Clarify scope when necessary, gather local project/process context, spawn a `gpd-explainer` agent, optionally run `gpd-bibliographer` to verify cited papers, and present the finished explanation plus reading path.

**Why subagent:** The explanation needs local state, notation, nearby derivations, and literature context. Fresh context keeps it rigorous.
When available, the explainer should also use the derived citation-source catalog so literature guides can prefer stable `reference_id` anchors and openable URLs instead of reconstructing papers from prose.
If the topic is already represented in `intermediate_results`, use `gpd result search` to recover the canonical result before explaining it so the explanation can anchor to the stored equation, description, phase, and verification state. If a canonical `result_id` is already known, use `gpd result show "{result_id}"` to inspect the stored result directly before explaining it. When the explanation also needs the upstream derivation path, run `gpd result deps "{result_id}"` after the search or show step so the explanation can reuse the recorded dependency chain instead of reconstructing it from prose. When the explanation needs the reverse impact tree, run `gpd result downstream "{result_id}"` to separate direct dependents from transitive dependents.
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

- If the request is materially ambiguous and the active project does not disambiguate it, ask one focused clarification question.
- Otherwise infer the intended scope from the current phase, manuscript work, notation, and nearby project files.
- If the concept looks like a derived equation or stored quantity, search the result registry first with `gpd result search` before falling back to prose-only context. If you find a canonical `result_id`, use `gpd result show "{result_id}"` for the direct stored-result view, `gpd result deps "{result_id}"` when the explanation needs upstream context, and `gpd result downstream "{result_id}"` when the explanation needs the reverse impact tree.

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
