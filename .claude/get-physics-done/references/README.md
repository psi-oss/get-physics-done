# References

This directory holds shared reference material used by specs and agent instructions.

## Top-level structure

- `protocols/`: reusable execution or verification procedures that apply across multiple agents or workflows.
- `subfields/`: domain-specific guidance organized by physics area.
- `templates/`: reusable document skeletons grouped by the workflow or agent that consumes them.
- root `*.md` files: cross-cutting references that are broadly useful and do not fit a single protocol, subfield, or template set.

## Placement rules

- Put new templates under `templates/<workflow-or-agent>/`.
- Put physics-domain primers or defaults under `subfields/`.
- Put stepwise methods, checklists, or operational rules under `protocols/`.
- Keep a reference at the root only when it is broadly shared and would be awkward to treat as a protocol, subfield note, or template.
