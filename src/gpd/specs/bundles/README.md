---
template_version: 1
---

# Protocol Bundles

Protocol bundles are the metadata layer that lets GPD stay generic while
loading specialized guidance when project metadata warrants it.

Each bundle lives in its own markdown file with YAML frontmatter. The
frontmatter is authoritative; the body is explanatory only.

## Required Frontmatter Fields

- `bundle_id`
- `bundle_version`
- `title`
- `summary`
- `trigger`
- `assets`

## Trigger Model

Trigger rules are generic and metadata-driven:

- `all_tags` and `any_tags` match normalized project / contract tags
- `all_terms` and `any_terms` match normalized project / contract text
- `min_score` prevents weak accidental matches

Core code stays domain-agnostic. Domain or method specificity belongs in bundle
metadata, not in planner / executor / verifier prompt logic.

## Asset Roles

Bundle assets are organized by role, not topic:

- `project_types`
- `subfield_guides`
- `verification_domains`
- `protocols_core`
- `protocols_optional`
- `execution_guides`

## Contribution Fields

Bundles can contribute:

- `anchor_prompts`
- `reference_prompts`
- `estimator_policies`
- `decisive_artifact_guidance`
- `verifier_extensions`

These are advisory surfaces layered on top of the phase contract. They do not
replace contract IDs, acceptance tests, or forbidden-proxy rules.
