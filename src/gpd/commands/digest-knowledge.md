---
name: gpd:digest-knowledge
description: Create or update a draft project knowledge document from a topic, source file, arXiv ID, or existing knowledge path
argument-hint: "[topic | source file | arXiv ID | GPD/knowledge/K-*.md]"
context_mode: project-aware
allowed-tools:
  - file_read
  - file_write
  - shell
  - search_files
  - find_files
  - task
  - ask_user
---

<objective>
Create or update a draft knowledge document from a topic, source file, arXiv ID, or existing knowledge path. Validate context, classify the input, resolve the target, then delegate knowledge-specific decisions to the workflow.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/digest-knowledge.md
@{GPD_INSTALL_DIR}/templates/knowledge-schema.md
</execution_context>

<context>
Input: $ARGUMENTS

Quick reference:
- `ls GPD/knowledge/*.md 2>/dev/null | head -10`
- `ls GPD/literature/*.md 2>/dev/null | head -10`
- `ls GPD/research-map/*.md 2>/dev/null | head -10`

</context>

<process>

## 0. Initialize Context

```bash
CONTEXT=$(gpd --raw validate command-context digest-knowledge "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi

INIT=$(gpd --raw init progress --include state,roadmap,config)
```

Extract `commit_docs`, `project_contract`, `project_contract_gate`, `active_reference_context`, and any `reference_artifact_files` from `INIT`. Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true.

## 1. Classify The Request

Interpret `$ARGUMENTS` as:

1. explicit knowledge document path
2. explicit source file path
3. arXiv identifier
4. free-form topic or question

If the request is unclear, ask a focused clarification question before proceeding. Route review/promotion requests (stable mutation or approval) to `gpd:review-knowledge`.

## 2. Resolve The Target

Prefer deterministic resolution:

1. reuse an explicit `GPD/knowledge/K-*.md` path when provided
2. update an existing knowledge doc only when the target is exact, unambiguous, and still draft
3. otherwise create a new draft target from a normalized `knowledge_id`

If multiple candidates remain, ask for clarification. If the resolved target is `stable` or `superseded`, hand the request to `gpd:review-knowledge`.

## 3. Delegate Workflow

Construct a concise workflow handoff:

```markdown
<objective>
Digest knowledge from {input_kind}: {input_summary}

**Scope:**

- Canonical target: {target_path_or_none}
- Resolution mode: create | update | clarify
- Contract-critical anchors: {active_reference_context}

Use the workflow-owned `digest-knowledge` rules for synthesis and draft writing. If the request is review, approval, or stable-state mutation, route to `gpd:review-knowledge`.
</objective>
```

If a spawned writer is required, have the workflow-owned logic create it and keep this wrapper focused on orchestration.

## 4. Return Results

Report the resolved target, whether the action was create or update, and any clarification questions that blocked progress.

</process>

<success_criteria>

- [ ] Command context validated
- [ ] Input classified explicitly
- [ ] Canonical target resolved or ambiguity surfaced
- [ ] Workflow-owned behavior delegated cleanly
- [ ] Draft-only boundary preserved
- [ ] Result reported without overclaiming review or automatic promotion

</success_criteria>
