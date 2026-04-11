# Schema and Registry Ownership

This note names the canonical sources of truth for runtime/schema ownership. Keep
it compact and update these files instead of copying schema details into runtime
prompts or generated surfaces.

## Canonical Sources

- **Runtime catalog:** `src/gpd/adapters/runtime_catalog.json`, with shape and enum ownership in `src/gpd/adapters/runtime_catalog_schema.json` and loader validation in `src/gpd/adapters/runtime_catalog.py`.
- **MCP registry and infra descriptors:** `src/gpd/mcp/builtin_servers.py` owns built-in MCP server definitions that install flows, launch flows, and release-tested `infra/gpd-*.json` descriptors consume; regenerate the JSON artifacts from `build_public_descriptors()` whenever you adjust these definitions.
- **Public surface contract:** `src/gpd/core/public_surface_contract.json`, with schema ownership in `src/gpd/core/public_surface_contract_schema.json` and loader validation in `src/gpd/core/public_surface_contract.py`.
- **Model-visible schemas:** `src/gpd/core/model_visible_sections.py` owns shared rendering rules for model-visible YAML sections; individual canonical contract schemas live under `src/gpd/specs/templates/` and are inlined by runtime compilation rather than duplicated in prompt prose.
- **Continuation state:** the runtime state schema owns `continuation.bounded_segment`, execution-lineage fields, and compatibility projections such as `.continue-here.md` and derived execution heads; prompts should name the handoff surface but not restate the full field list.
- **Proof red-team gates:** proof-bearing artifact requirements and verifier verdict vocabulary are owned by the verifier/proof schemas and templates under `src/gpd/specs/templates/`; workflow prompts should reference those gates instead of copying pass/fail prose.

## Maintenance Rule

When adding or changing runtime capabilities, MCP servers, public onboarding
fields, or model-visible schema vocabulary, update the owning file above first,
then adjust generated/runtime projections and focused contract tests. Keep the
`infra/gpd-*.json` artifacts synchronized by rerunning the generator that emits
`build_public_descriptors()` output instead of editing those JSON files by hand.
Do not make large prompt-file rewrites to establish ownership.
