---
name: gpd:digest-knowledge
description: Create or update a project knowledge document from a topic, source file, arXiv ID, or existing knowledge path
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
Create or update a knowledge document from an explicit topic, source file, arXiv ID, or existing knowledge document path, while keeping the wrapper thin and the workflow authoritative.

**Orchestrator role:** Validate command context, gather the local project state needed to resolve a canonical target, classify the input, and then delegate the actual create/update decision-making to the workflow-owned `digest-knowledge` instructions.

**Why subagent:** The workflow will need fresh context for source intake, deterministic target resolution, and draft synthesis without contaminating the wrapper with policy details.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/digest-knowledge.md
</execution_context>

<context>
Input: $ARGUMENTS

Check for existing knowledge docs:

```bash
ls GPD/knowledge/*.md 2>/dev/null | head -10
```

Check for related source inputs when you already know the target family:

```bash
ls GPD/literature/*.md 2>/dev/null | head -10
ls GPD/research-map/*.md 2>/dev/null | head -10
```

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

Extract `commit_docs`, `project_contract`, `project_contract_gate`, `project_contract_load_info`, `project_contract_validation`, `active_reference_context`, and any existing `reference_artifact_files` from init JSON. Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true.

## 1. Classify The Request

Interpret `$ARGUMENTS` as one of:

1. explicit knowledge document path
2. explicit source file path
3. arXiv identifier
4. free-form topic or question

If the request is materially ambiguous, stop and ask one focused clarification question instead of guessing.

## 2. Resolve The Target

Prefer deterministic resolution over implicit repair:

1. reuse an explicit `GPD/knowledge/K-*.md` path if provided
2. update an existing knowledge doc only when the target is exact and unambiguous
3. otherwise create a new draft target from a normalized `knowledge_id`

If more than one existing knowledge doc is plausible, stop and ask for clarification.

## 3. Delegate The Workflow

Construct a concise handoff for the workflow-owned command logic:

```markdown
<objective>
Digest knowledge from {input_kind}: {input_summary}

**Scope:**

- Canonical target: {target_path_or_none}
- Resolution mode: create | update | clarify
- Contract-critical anchors: {active_reference_context}

Keep the knowledge-specific resolution, synthesis, and draft-writing rules in the workflow-owned `digest-knowledge` instructions. This wrapper should only classify, resolve, and route.
</objective>
```

If the workflow requires a spawned writer, delegate that work there and keep the wrapper focused on orchestration only.

## 4. Return Results

Report the resolved target, whether the action was create or update, and any clarification questions that blocked progress.

</process>

<success_criteria>

- [ ] Command context validated
- [ ] Input classified explicitly
- [ ] Canonical target resolved or ambiguity surfaced
- [ ] Workflow-owned behavior delegated cleanly
- [ ] Result reported without overclaiming review or runtime ingestion

</success_criteria>
