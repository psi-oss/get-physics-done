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

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Produce a rigorous, well-scoped explanation of a concept, method, notation, result, or paper in the context of the user's current research workflow.

**Orchestrator role:** Clarify scope when necessary, gather local project/process context, spawn a `gpd-explainer` agent, optionally run `gpd-bibliographer` to verify cited papers, and present the finished explanation plus reading path.

**Why subagent:** A good explanation has to hold together local project state, notation, nearby derivations, and literature context. Fresh context lets the explainer stay rigorous without dropping the active process.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/explain.md
</execution_context>

<context>
Concept or topic: $ARGUMENTS

Check for prior explanation artifacts:

```bash
ls .gpd/explanations/*.md 2>/dev/null | head -10
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

## 2. Gather Context

If a GPD project exists, load project state and current-process context before spawning the explainer.

## 3. Execute the Explain Workflow

Follow the explain workflow from `@{GPD_INSTALL_DIR}/workflows/explain.md` end-to-end.

## 4. Return Results

Show the explanation summary, report path, citation-audit status, and the best papers to open next.
</process>

<success_criteria>

- [ ] Standalone or project context validated
- [ ] Relevant local files and active-process context gathered when available
- [ ] `gpd-explainer` spawned with a scoped objective
- [ ] Explanation written with clear structure, project grounding, and literature guide
- [ ] Citations verified by `gpd-bibliographer` or uncertainty explicitly flagged
- [ ] User receives report path plus recommended follow-up papers/questions
      </success_criteria>
