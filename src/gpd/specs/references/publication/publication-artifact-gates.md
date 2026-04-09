---
type: publication-artifact-gates
tier: 2
context_cost: low
---

# Publication Artifact Gates

Legacy bridge for manuscript-root and latest-round publication gating.

This file is retained only for transitional compatibility. It is not a live authority and should not be loaded by new prompt wiring.

Canonical sources:

- `@{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md`
- `@{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md`
- `@{GPD_INSTALL_DIR}/references/publication/publication-response-artifacts.md`

The manuscript-root contract owns root resolution, manuscript-local artifact rooting, and `gpd paper-build` authority. The round and response contracts own latest-round gating, paired response completion, and fail-closed child-return semantics.
