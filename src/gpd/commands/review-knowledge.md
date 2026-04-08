---
name: gpd:review-knowledge
description: Review a knowledge document for approval, changes, or promotion gating
argument-hint: "[knowledge path or canonical knowledge_id]"
context_mode: project-aware
review-contract:
  review_mode: review
  schema_version: 1
  required_outputs:
    - "GPD/knowledge/reviews/{knowledge_id}-R{round_suffix}-REVIEW.md"
    - "GPD/knowledge/{knowledge_id}.md"
  required_evidence:
    - existing knowledge document
    - knowledge sources and coverage summary
    - current knowledge frontmatter/body snapshot
    - prior review artifact when revisiting a document
  blocking_conditions:
    - missing project state
    - missing knowledge document
    - ambiguous knowledge target
    - degraded review integrity
    - stale approved review evidence
  preflight_checks:
    - command_context
    - project_state
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
Review a knowledge document and decide whether it can be promoted to stable, needs changes, or should remain under review.

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

@GPD/STATE.md
@GPD/knowledge/
@GPD/knowledge/reviews/

Resolve the target deterministically from the explicit argument:

- an exact `GPD/knowledge/{knowledge_id}.md` path
- or a canonical `K-*` knowledge_id that resolves to that path

If the target is ambiguous, the workflow must stop and ask for clarification.
</context>

<process>
@{GPD_INSTALL_DIR}/references/shared/canonical-schema-discipline.md
@{GPD_INSTALL_DIR}/templates/knowledge-schema.md
@{GPD_INSTALL_DIR}/templates/knowledge.md

Follow `@{GPD_INSTALL_DIR}/workflows/review-knowledge.md` exactly.
</process>

<success_criteria>
- [ ] Review target resolved exactly from path or canonical knowledge_id
- [ ] Review artifact written under `GPD/knowledge/reviews/`
- [ ] Review metadata records round, reviewer identity, artifact path/hash, reviewed-content hash, and stale handling
- [ ] `approved` promotes the document to `stable` only when the review is fresh
- [ ] `needs_changes` and `rejected` keep or mark the document `in_review`
- [ ] Validation fails closed on ambiguous targets or stale approved evidence
- [ ] No automatic migration, beginner onboarding exposure, or full supersession orchestration is claimed
</success_criteria>
