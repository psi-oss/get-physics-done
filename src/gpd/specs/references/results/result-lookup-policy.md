# Result Lookup Policy

Use this policy whenever a workflow needs canonical result-registry context.

- Use `gpd result search` to locate stored results by identifier, equation, description, phase, or dependency. Use `gpd result search --depends-on "{upstream_result_id}"` only when you need a flat, filterable list of downstream results.
- Once a canonical `result_id` is known, run `gpd result show "{result_id}"` before reconstructing from state or files; it is the direct stored-result view.
- Use `gpd result deps "{result_id}"` for the recorded upstream dependency chain when provenance, assumptions, or propagated uncertainty matter.
- Use `gpd result downstream "{result_id}"` for impact analysis that must distinguish direct dependents from transitive dependents.
- Keep `gpd query search` for SUMMARY/frontmatter lookup; do not use it as the canonical result registry.
