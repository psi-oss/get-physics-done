# Hook wiring & advanced overrides

This document explains the runtime-side hook wiring and the advanced environment overrides that surface while you debug or script GPD.

## Hook wiring overview

Three hook surfaces power the runtime integrations:

- `src/gpd/hooks/runtime_detect.py` is the shared detector that reads `GPD_ACTIVE_RUNTIME`, per-runtime config directories, and the install manifest. Bridge commands (`gpd` inside a runtime) call it to anchor every hook to the right runtime and scope before any status or notify payload is parsed.
- `src/gpd/hooks/statusline.py` is loaded by every runtime to render the GPD statusline. It resolves the hook payload policy, reads the telemetry/update context from stdin, and writes the ANSI-colored `GPD` segment that shows the current model, research position, and context usage.
- `src/gpd/hooks/notify.py` runs inside the runtime when GPD reports observability events, emits update notices, and records lightweight telemetry. It also looks up runtime metadata with `runtime_detect` so notifications stay tied to the same runtime that produced the payload.

Together these scripts share helper modules such as `payload_policy.py`, `payload_roots.py`, and `install_metadata.py`, so each runtime can keep its statusline, notification, update check, and telemetry workstreams aligned with the detected runtime environment.

## Advanced runtime overrides & debug

### `GPD_ACTIVE_RUNTIME`

Set this to a canonical runtime name (for example `codex`, `claude-code`, `gemini`, or `opencode`) to bypass the auto-detection heuristics in `runtime_detect.py`. GPD normalizes the value before choosing a runtime, so case-insensitive aliases like `Codex` work too. This is handy when you run `uv run gpd` from a shell that needs to stay attached to one runtime, when tests want to force a specific adapter, or when you build tooling that must talk to the same runtime regardless of the current working directory.

### `GPD_DISABLE_CHECKOUT_REEXEC`

`gpd.runtime_cli` may re-exec through your checkout when the active package does not match the clocked install. Set this variable (for example, `export GPD_DISABLE_CHECKOUT_REEXEC=1`) to skip that re-exec flow and stay in your current interpreter. Keeping it set is useful while you develop GPD itself or when a runtime hook wants to capture the checkout output without bouncing into another process.

### `GPD_DEBUG`

Setting `GPD_DEBUG=1` enables hook-debug logging inside `gpd/hooks/debug.py`, which is imported by `statusline.py`, `notify.py`, and several other hook helpers. Each call to `hook_debug()` writes a `[gpd-debug]` line to stderr, so you can follow the hook execution path without changing production behavior.
