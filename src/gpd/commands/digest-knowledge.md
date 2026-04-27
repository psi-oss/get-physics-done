---
name: gpd:digest-knowledge
description: Create or update a draft knowledge document in the current workspace from a topic, source file, arXiv ID, or canonical knowledge path
argument-hint: "[topic | source file | arXiv ID | current-workspace GPD/knowledge/K-*.md]"
context_mode: project-aware
command-policy:
  schema_version: 1
  subject_policy:
    subject_kind: knowledge_document
    resolution_mode: explicit_input_to_canonical_current_workspace_target
    explicit_input_kinds:
      - knowledge_document_path
      - source_path
      - arxiv_id
      - topic
    allow_external_subjects: true
  supporting_context_policy:
    project_context_mode: project-aware
    project_reentry_mode: disallowed
    optional_file_patterns:
      - GPD/knowledge/*.md
      - GPD/literature/*.md
      - GPD/research-map/*.md
  output_policy:
    output_mode: managed
    managed_root_kind: gpd_managed_durable
    default_output_subtree: GPD/knowledge
    stage_artifact_policy: gpd_owned_outputs_only
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
Route a knowledge-digest request into the workflow-owned authoring/update implementation.

This wrapper owns command-context validation, current-workspace target boundaries, and out-of-lifecycle routing only. The same-named workflow owns classification, deterministic target resolution, source intake, draft synthesis, schema validation, and create/update decisions.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/digest-knowledge.md
</execution_context>

<context>
Input: $ARGUMENTS

External source material may live anywhere. The canonical knowledge target itself must stay under the current workspace's `GPD/knowledge/` tree.

Treat explicit source-file intake as including `.md`, `.txt`, `.pdf`, `.docx`, `.csv`, `.tsv`, and `.xlsx` when those paths are supplied directly. For `.pdf`, `.docx`, and `.xlsx`, keep any text extraction inside the workflow via `gpd validate artifact-text <path> --output <txt-path>`.

Do not treat lookalike `K-*.md` files outside the current workspace `GPD/knowledge/` tree as canonical knowledge targets. If the requested action is review, approval, promotion to `stable`, supersession, or mutation of an existing stable target, route to `gpd:review-knowledge`.
</context>

<process>
## 1. Validate Context

```bash
CONTEXT=$(gpd --raw validate command-context digest-knowledge "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

## 2. Delegate To Workflow

Execute the included digest-knowledge workflow end-to-end.
Preserve its current-workspace bootstrap, canonical `GPD/knowledge/` output root, draft-only lifecycle boundary, and review-knowledge routing.
</process>

<success_criteria>

- [ ] Command context validated
- [ ] Digest-knowledge workflow executed as the authority for mechanics
- [ ] Canonical target kept under current-workspace `GPD/knowledge/`
- [ ] External sources used only as sources, not durable target roots
- [ ] Review, approval, promotion, and stable-target mutation routed to `gpd:review-knowledge`
</success_criteria>
