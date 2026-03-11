# References

This directory holds shared reference material used by specs and agent instructions.

## Top-level structure

- root `*.md` files: cross-cutting index/reference files (`README.md`, `physics-subfields.md`).
- `architecture/`: review and artifact-system design notes.
- `conventions/`: compact convention references and defaults.
- `examples/`: worked examples and contradiction-resolution demos.
- `execution/`: executor-specific playbooks, checkpoints, and worked examples.
- `methods/`: cross-domain method-selection guidance.
- `orchestration/`: runtime-agnostic orchestration, delegation, profile, and checkpoint references.
- `planning/`: planner and plan-checker reference material.
- `protocols/`: reusable execution or verification procedures by method.
- `publication/`: paper-writing, bibliography, figures, and peer-review references.
- `research/`: research-mode, questioning, and researcher shared guidance.
- `shared/`: shared protocols used by multiple agents.
- `subfields/`: physics-domain guidance organized by subfield.
- `templates/`: reusable document skeletons grouped by the workflow or agent that consumes them.
- `tooling/`: computational-library and tool integration guidance.
- `ui/`: interface-brand references shared by install surfaces.
- `verification/`: verification core, domains, audits, error catalogs, and worked examples.

## Placement rules

- Put new templates under `templates/<workflow-or-agent>/`.
- Put physics-domain primers or defaults under `subfields/`.
- Put stepwise methods and computation-specific procedures under `protocols/`.
- Put orchestration/runtime/model behavior references under `orchestration/`.
- Put verifier-specific material under `verification/`.
- Keep a reference at the root only when it is an index or a broadly shared cross-cutting entry point.
