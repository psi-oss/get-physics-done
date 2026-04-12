# Runtime Catalog Reference

Use this page when you need a quick reference for the runtime flags and command prefixes that the installer recognizes. The canonical runtime metadata lives in `src/gpd/adapters/runtime_catalog.json`, and this table is generated from that file by running `python scripts/render_runtime_catalog_table.py`.

```
npx -y get-physics-done --<flag> --local
```

Replace `<flag>` with the install flag for the runtime you want (for example `--claude` for Claude Code). When you change the runtime catalog, rerun the renderer above and copy the updated table into this page so the onboarding docs keep in sync with the adapters.

| Runtime | `npx` flag | Launch command | Command prefix | Selection aliases |
|---------|------------|----------------|----------------|--------------------|
| Claude Code | `--claude` | `claude` | `/gpd:` | `claude-code`, `claude code`, `claude`, `--claude-code` |
| Gemini CLI | `--gemini` | `gemini` | `/gpd:` | `gemini`, `gemini cli`, `--gemini-cli` |
| Codex | `--codex` | `codex` | `$gpd-` | `codex`, `--codex-cli` |
| OpenCode | `--opencode` | `opencode` | `/gpd-` | `opencode`, `open code`, `--open-code` |

Using this table (and the runtime quickstarts linked from the onboarding hub) keeps your install commands aligned with the runtime adapters. For more in-depth onboarding, read the OS guide for your machine and the runtime quickstart you are actually using.
