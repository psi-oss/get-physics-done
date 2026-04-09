---
load_when:
  - "publication bootstrap"
  - "publication preflight"
  - "manuscript-root preflight"
  - "submission preflight"
type: publication-bootstrap-preflight
tier: 2
context_cost: low
---

# Publication Bootstrap Preflight

Canonical workflow-facing bootstrap and preflight reference for publication tasks.

Use this pack when a workflow needs to establish the manuscript-root gate, the latest review-round context, or the submission preflight path before any packaging or response drafting begins.

## Canonical Sources

- `@{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md`
- `@{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md`
- `@{GPD_INSTALL_DIR}/references/publication/publication-response-artifacts.md`

## Rules

- Load the manuscript-root preflight only when the workflow is about to resolve or package manuscript-owned artifacts.
- Use the round-artifact contract for latest-round suffixing and sibling artifact naming.
- Use the response-artifact contract for paired response completion and fail-closed child-return semantics.
- Keep the workflow explicit about on-disk verification. A completed child return is provisional until the required artifacts exist in the workspace.
- Do not restate the publication pipeline in wrappers or downstream agent prompts when this reference is already loaded.
