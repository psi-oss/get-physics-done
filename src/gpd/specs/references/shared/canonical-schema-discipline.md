# Canonical Schema Discipline

Use the explicitly loaded schema, template, and contract/reference files that define an output shape or validation gate as the authority. Do not invent hidden fields, extra keys, fallback variants, flattened shapes, or stale payloads from prior runs.

If a field is hard-enforced, surface it in model-visible schema text before asking the model to satisfy it. Keep required IDs exact, non-empty, and cross-reference-safe. For project-scoping work, keep `project_contract` literal and preserve gate state, approval blockers, and linked IDs exactly. If required evidence or artifacts are missing, leave them missing, blocked, failed, or inconclusive instead of inventing a stand-in.
