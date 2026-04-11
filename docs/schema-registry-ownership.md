# Schema and Registry Ownership

This note names the canonical sources of truth for runtime/schema ownership. Keep
it compact and update these files instead of copying schema details into runtime
prompts or generated surfaces.

## Canonical Sources

- **Runtime catalog:** `src/gpd/adapters/runtime_catalog.json`, with shape and enum ownership in `src/gpd/adapters/runtime_catalog_schema.json` and loader validation in `src/gpd/adapters/runtime_catalog.py`.
- **MCP registry:** `src/gpd/mcp/builtin_servers.py` owns built-in MCP server definitions that install flows, launch flows, and public infra descriptors consume.
- **Public surface contract:** `src/gpd/core/public_surface_contract.json`, with schema ownership in `src/gpd/core/public_surface_contract_schema.json` and loader validation in `src/gpd/core/public_surface_contract.py`.
- **Model-visible schemas:** `src/gpd/core/model_visible_sections.py` owns shared rendering rules for model-visible YAML sections; individual canonical contract schemas live under `src/gpd/specs/templates/` and are inlined by runtime compilation rather than duplicated in prompt prose.

## Maintenance Rule

When adding or changing runtime capabilities, MCP servers, public onboarding
fields, or model-visible schema vocabulary, update the owning file above first,
then adjust generated/runtime projections and focused contract tests. Do not
make large prompt-file rewrites to establish ownership.
