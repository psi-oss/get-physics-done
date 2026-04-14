# Runtime Catalog Reference

This file is the canonical table for runtime install flags, command prefixes, documented runtime aliases, and extra public selector flags. The data is generated directly from `src/gpd/adapters/runtime_catalog.json` by running `python scripts/render_runtime_catalog_table.py`. Re-run that script whenever the JSON changes so the onboarding docs keep referring to a single source of truth, and avoid copying the table elsewhere.

```
npx -y get-physics-done --<flag> --local
```

Replace `<flag>` with the canonical install flag for the runtime you want (for example `--claude` for Claude Code). When another public GPD surface asks for a runtime selector, use the documented runtime aliases or extra selector flags below; internal adapter/module spellings are intentionally not part of that public surface. When you change the runtime catalog, rerun the renderer above and copy the updated table into this page so the onboarding docs keep in sync with the adapters.

This page covers install flags and command prefixes, not the normal self-update path. For released updates, use your runtime update command (`/gpd:update`, `$gpd-update`, or `/gpd-update`) or rerun the same `npx -y get-physics-done --<flag> --local|--global` install command you used originally. Reserve bootstrap `--upgrade` for the developer-only `main`-branch path.

| Runtime | `npx` flag | Launch command | Command prefix | Runtime aliases | Extra selector flags |
|---------|------------|----------------|----------------|-----------------|----------------------|
| Claude Code | `--claude` | `claude` | `/gpd:` | `claude-code`, `claude code`, `claude` | `--claude-code` |
| Gemini CLI | `--gemini` | `gemini` | `/gpd:` | `gemini`, `gemini cli` | `--gemini-cli` |
| Codex | `--codex` | `codex` | `$gpd-` | `codex` | `--codex-cli` |
| OpenCode | `--opencode` | `opencode` | `/gpd-` | `opencode`, `open code` | `--open-code` |

Using this table (and the runtime quickstarts linked from the onboarding hub) keeps your install commands and documented public runtime selectors aligned with the runtime adapters. For more in-depth onboarding, read the OS guide for your machine and the runtime quickstart you are actually using.
