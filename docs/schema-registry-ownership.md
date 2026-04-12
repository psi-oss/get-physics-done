# Schema and Registry Ownership

This note names the canonical sources of truth for runtime/schema ownership. Keep
it compact and update these files instead of copying schema details into runtime
prompts or generated surfaces.

## Canonical Sources

The table below lists the canonical schema, runtime catalog, and registry sources. Regenerate this section by running `python scripts/schema_registry_sources.py` so it always reflects the `CANONICAL_SOURCES` list defined in that module.

| Source | Description |
|--------|-------------|
| `src/gpd/adapters/runtime_catalog.json` | Runtime catalog payload that drives install flags and runtime selection. |
| `src/gpd/adapters/runtime_catalog_schema.json` | Schema shape that validates every runtime catalog entry. |
| `src/gpd/adapters/runtime_catalog.py` | Catalog loader, validator, and adapter registry helpers. |
| `src/gpd/mcp/builtin_servers.py` | Builder for the MCP registry whose output lands under infra/gpd-*.json. |
| `infra/gpd-*.json` | Generated MCP descriptor payloads derived from builtin servers. |
| `src/gpd/core/public_surface_contract.json` | Public surface contract that documents CLI command contracts. |
| `src/gpd/core/public_surface_contract_schema.json` | Schema that constrains the public surface contract structure. |
| `src/gpd/core/public_surface_contract.py` | Validator and loader for the public surface contract schema. |
| `src/gpd/core/model_visible_sections.py` | Shared rendering rules that keep schema sections visible to models. |
| `src/gpd/specs/templates/` | Canonical contract and prompt templates referenced by runtime prompts. |

The remaining paragraphs below (continuation state, proof red-team gates, etc.) describe how the runtime prompts should reference these sources without restating the raw field list.

## Maintenance Rule

When adding or changing runtime capabilities, MCP servers, public onboarding
fields, or model-visible schema vocabulary, update the owning file above first,
then adjust generated/runtime projections and focused contract tests. Keep the
`infra/gpd-*.json` artifacts synchronized by rerunning the generator that emits
`build_public_descriptors()` output instead of editing those JSON files by hand.
Do not make large prompt-file rewrites to establish ownership.
