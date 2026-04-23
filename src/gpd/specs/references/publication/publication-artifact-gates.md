---
type: publication-artifact-gates
tier: 2
context_cost: low
---

# Publication Artifact Gates

Pointer file for manuscript-root and latest-round publication gating. This file is not a live authority and prompt wiring should not load it.

Canonical sources:

- `@{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md`
- `@{GPD_INSTALL_DIR}/references/publication/publication-pipeline-modes.md`
- `@{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md`
- `@{GPD_INSTALL_DIR}/references/publication/publication-response-artifacts.md`

The manuscript-root contract owns root resolution, manuscript-local artifact rooting, and `gpd paper-build` authority. The round and response contracts own latest-round gating, paired response completion, and fail-closed child-return semantics. For the publication-lane boundary itself, rely on `publication-pipeline-modes.md`; this pointer file does not expand intake policy or manuscript-local artifact scope.
