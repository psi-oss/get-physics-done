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
This pack standardizes manuscript-root resolution and publication gating. It does not decide whether a command may accept a standalone external manuscript/artifact; workflow-specific intake policy remains authoritative.
When a workflow does expose a bounded external-authoring lane, that lane must stay explicit-intake only and fail closed without the required manifest.

## Canonical Sources

- `@{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md`
- `@{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md`
- `@{GPD_INSTALL_DIR}/references/publication/publication-response-artifacts.md`

## Rules

- Load the manuscript-root preflight only when the workflow is about to resolve or package manuscript-owned artifacts.
- Use the round-artifact contract for latest-round suffixing and sibling artifact naming.
- Use the response-artifact contract for paired response completion and fail-closed child-return semantics.
- Keep the workflow explicit about on-disk verification. A completed child return is provisional until the required artifacts exist in the workspace.
- Keep GPD-authored auxiliary publication outputs under `GPD/`, but do not imply the manuscript draft or manuscript-root manifests have moved out of the resolved manuscript directory.
- When a workflow exposes the bounded external-authoring lane, accept one explicit intake manifest only. Do not mine arbitrary folders or infer claim/evidence bindings from loose notes.
- For that bounded lane, keep GPD-authored durable outputs under `GPD/publication/{subject_slug}/...`; treat `GPD/publication/{subject_slug}/manuscript/` as the only manuscript/build root and `GPD/publication/{subject_slug}/intake/` as intake/provenance state only.
- Do not infer widened `gpd:arxiv-submission` scope, full publication-root migration, or embedded external staged-review parity from this pack alone; route authored-manuscript review to standalone `gpd:peer-review` when the drafting workflow stops short of review parity.
- Do not infer standalone external-artifact support from this pack alone.
- Do not restate the publication pipeline in wrappers or downstream agent prompts when this reference is already loaded.
