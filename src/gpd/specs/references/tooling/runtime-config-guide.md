# Runtime Configuration Guide

Guidance for configuring host runtime environments when running GPD. This reference covers recommended settings, extension compatibility, portable configuration patterns, and common environment pitfalls across all supported runtimes.

## Recommended Minimal Configuration

After installation (`{GPD_BOOTSTRAP_COMMAND}`), GPD writes managed entries into the host runtime's configuration directory. These managed entries include:

- **Status line or notification hooks** -- GPD status display in the runtime UI
- **Update check hooks** -- check for GPD updates on session start
- **MCP servers** -- GPD MCP servers for state and paper tooling (where supported)

GPD does not touch entries it did not create. Existing user hooks, MCP servers, and settings are preserved.

## Permission Mode Alignment

GPD's `runtime_permissions` integration (via `gpd permissions sync --runtime <runtime> --autonomy <mode>`) aligns the runtime's tool-permission mode with GPD's autonomy setting:

| GPD Autonomy | Recommended Runtime Mode | Effect |
|-------------|-------------------------|--------|
| `supervised` | Default (prompts for each tool) | Maximum human oversight |
| `balanced` | Plan mode where supported | Opt-in lighter checkpoint cadence, prompts for destructive actions |
| `yolo` | Most permissive available | `gpd permissions sync --runtime <runtime> --autonomy yolo` applies the runtime-native setting |

When `autonomy=yolo`, `gpd permissions sync --runtime <runtime> --autonomy yolo` writes the appropriate permissive-mode configuration for the active runtime. This takes effect on the next session launch where a restart is required, or immediately where the runtime supports hot reload.

## Extension and Skill Compatibility

GPD installs its commands and agents into the runtime's command/agent directories. Other extensions and skills can coexist as long as they do not:

1. **Override GPD command names** -- GPD uses the `gpd:` prefix (or runtime-equivalent). Any other extension using the same prefix will conflict.
2. **Modify GPD-managed hooks** -- Status line and update hooks are GPD-managed. Other hooks with different names are fine.
3. **Remove the `{GPD_INSTALL_ROOT_DIR_NAME}/` directory** -- GPD stores all installed content under the runtime's config directory in `{GPD_INSTALL_ROOT_DIR_NAME}/`. Do not remove this directory while a project is active.

### Known-Safe Combinations

- Built-in runtime tools (file read/write, shell, search, etc.) -- fully compatible
- User-defined custom slash commands -- compatible if they do not use the `gpd:` prefix
- Third-party MCP servers -- compatible; GPD's MCP servers use reserved `gpd-*` names such as `gpd-state`, `gpd-skills`, and `gpd-verification`
- Multiple project configuration files -- compatible; GPD does not modify project-level config files it did not create

### Potentially Problematic Combinations

- Extensions that modify runtime settings files without preserving existing entries -- may remove GPD hooks
- Extensions that clear the command directory -- will remove GPD commands
- Custom agents named `gpd-*` -- will conflict with GPD agent names

## Portable Configuration Patterns

### Avoid Machine-Specific Paths

GPD generates paths relative to the runtime config directory during install. If you manually reference paths in project configuration:

- Use `~/` prefix instead of `/Users/username/` or `/home/username/`
- Use `$HOME` in shell hook commands
- Avoid hardcoding Python interpreter paths; use `python3` or the managed GPD Python environment created by the installer

### Multi-Machine Setup

When syncing a GPD project across machines (via git, cloud storage, etc.):

1. The `GPD/` project directory is portable -- it uses relative paths internally
2. Runtime-specific configuration is machine-local -- re-run `{GPD_BOOTSTRAP_COMMAND}` on each machine
3. The managed GPD Python environment is machine-local -- the installer recreates it automatically
4. MCP server config is machine-local -- re-install regenerates it

### Low-Resource Environments

- GPD requires Python 3.11+ and Node.js for installation
- The managed venv uses approximately 200MB of disk for dependencies
- The host runtime requires network access to its provider's API
- If disk space is limited, free space before installing so the managed environment and generated runtime config can be recreated cleanly
- On ARM devices, ensure the Python interpreter matches the architecture

## Troubleshooting

### GPD Commands Not Appearing

1. Verify the install completed: check for `{GPD_INSTALL_ROOT_DIR_NAME}/` in the runtime config directory
2. Check the managed manifest file inside `<config-dir>`
3. Re-install if needed: `{GPD_BOOTSTRAP_COMMAND}`

### Permission Prompts Interrupting Workflow

1. Check the unattended verdict: `gpd validate unattended-readiness --runtime <runtime> --autonomy <mode>` (use `supervised` unless you intentionally selected another autonomy mode)
2. Inspect current runtime alignment: `gpd permissions status --runtime <runtime> --autonomy <mode>`
3. For fully unattended execution, align the selected runtime explicitly, for example `gpd permissions sync --runtime <runtime> --autonomy yolo` after choosing `yolo`
4. For plan-mode (approve plans, auto-execute): check your runtime's `--permission-mode` or equivalent launch flag

### Hooks Not Running

1. Check the runtime settings file for GPD-managed hook entries
2. Verify hook scripts exist in the `{GPD_INSTALL_ROOT_DIR_NAME}/hooks/` subdirectory
3. Re-install to regenerate: `{GPD_BOOTSTRAP_COMMAND}`

### MCP Servers Not Connecting

1. Check the runtime's MCP configuration file
2. Verify the managed Python environment has dependencies with the environment created by the installer
3. Re-install to regenerate MCP config: `{GPD_BOOTSTRAP_COMMAND}`
