---
name: gpd:review-knowledge
description: Review a current-workspace knowledge document for approval, changes, or promotion gating
argument-hint: "[current-workspace GPD/knowledge/{knowledge_id}.md | canonical K-* knowledge_id]"
context_mode: project-aware
command-policy:
  schema_version: 1
  subject_policy:
    subject_kind: knowledge_document
    resolution_mode: explicit_current_workspace_canonical_target
    explicit_input_kinds:
      - knowledge_document_path
      - knowledge_id
    allow_external_subjects: false
    supported_roots:
      - GPD/knowledge
    allowed_suffixes:
      - .md
  supporting_context_policy:
    project_context_mode: project-aware
    project_reentry_mode: disallowed
    optional_file_patterns:
      - GPD/knowledge/*.md
      - GPD/knowledge/reviews/*.md
      - GPD/STATE.md
  output_policy:
    output_mode: managed
    managed_root_kind: gpd_managed_durable
    default_output_subtree: GPD/knowledge
    stage_artifact_policy: gpd_owned_outputs_only
review-contract:
  review_mode: review
  schema_version: 1
  required_outputs:
    - "GPD/knowledge/reviews/{knowledge_id}-R{review_round}-REVIEW.md"
    - "GPD/knowledge/{knowledge_id}.md"
  required_evidence:
    - current-workspace canonical knowledge document
    - knowledge sources and coverage summary
    - current knowledge frontmatter/body snapshot
    - prior review artifact when revisiting a document
  blocking_conditions:
    - missing knowledge document
    - ambiguous knowledge target
    - non-canonical knowledge target
    - degraded review integrity
    - stale approved review evidence
  preflight_checks:
    - command_context
    - knowledge_target
    - knowledge_document
    - knowledge_review_freshness
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
Review a current-workspace knowledge document and decide whether it can be promoted to stable, needs changes, or should remain under review.

The review target must resolve to the current workspace's canonical `GPD/knowledge/{knowledge_id}.md` path. Review artifacts and lifecycle updates stay under the same current-workspace `GPD/knowledge/` tree.

Keep the wrapper thin and let the workflow own target resolution, review artifact writing, freshness checks, and lifecycle updates.

**Why subagent:** Review and promotion decisions burn context fast. Fresh context keeps the orchestrator lean.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/review-knowledge.md
@{GPD_INSTALL_DIR}/templates/knowledge-schema.md
@{GPD_INSTALL_DIR}/templates/knowledge.md
@{GPD_INSTALL_DIR}/references/shared/canonical-schema-discipline.md
</execution_context>

<context>
Review target: $ARGUMENTS

@GPD/knowledge/
@GPD/knowledge/reviews/

Use `GPD/STATE.md` only as optional background context when it exists. Strict knowledge review preflight is anchored to the explicit current-workspace knowledge target, not to project-state recovery.

Resolve the target deterministically from the explicit argument:

- an exact current-workspace `GPD/knowledge/{knowledge_id}.md` path
- or a canonical `K-*` knowledge_id that resolves to that path

Reject lookalikes such as `notes/K-*.md` or any other non-canonical `K-*.md` path outside the current workspace `GPD/knowledge/` tree.
If the target is ambiguous, the workflow must stop and ask for clarification.
</context>

<process>
@{GPD_INSTALL_DIR}/references/shared/canonical-schema-discipline.md
@{GPD_INSTALL_DIR}/templates/knowledge-schema.md
@{GPD_INSTALL_DIR}/templates/knowledge.md

Follow `@{GPD_INSTALL_DIR}/workflows/review-knowledge.md` exactly.
</process>

<success_criteria>
- [ ] Review target resolved exactly from a current-workspace canonical path or canonical knowledge_id
- [ ] Review artifact written under `GPD/knowledge/reviews/`
- [ ] Review metadata records round, reviewer identity, artifact path/hash, reviewed-content hash, and stale handling
- [ ] `approved` promotes the document to `stable` only when the review is fresh
- [ ] `needs_changes` and `rejected` keep or mark the document `in_review`
- [ ] Validation fails closed on non-canonical lookalikes, ambiguous targets, or stale approved evidence
- [ ] No automatic import, beginner onboarding exposure, or full supersession orchestration is claimed
</success_criteria>
