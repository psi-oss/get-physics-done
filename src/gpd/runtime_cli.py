"""Shared bridge for installed runtime shell invocations.

Installed prompt sources author plain ``gpd`` commands. During install, runtime
adapters rewrite those shell invocations to this bridge so one runtime-agnostic
entrypoint can:

1. validate the install contract for the target runtime config dir
2. pin the active runtime deterministically
3. dispatch into the real GPD CLI without depending on runtime-private
   launcher files
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from gpd.adapters import get_adapter
from gpd.adapters.install_utils import MANIFEST_NAME, build_runtime_install_repair_command
from gpd.core.constants import ENV_GPD_ACTIVE_RUNTIME, ENV_GPD_DISABLE_CHECKOUT_REEXEC
from gpd.hooks.install_metadata import installed_runtime
from gpd.hooks.runtime_detect import normalize_runtime_name


def _parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    """Parse bridge arguments and return the remaining GPD CLI args."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--config-dir", required=True)
    parser.add_argument("--install-scope", choices=("local", "global"), required=True)
    parser.add_argument("--explicit-target", action="store_true")
    bridge_args: list[str] = []
    index = 0
    while index < len(argv):
        arg = str(argv[index])
        if arg == "--explicit-target":
            bridge_args.append(arg)
            index += 1
            continue
        if any(arg.startswith(prefix) for prefix in ("--runtime=", "--config-dir=", "--install-scope=")):
            bridge_args.append(arg)
            index += 1
            continue
        if arg in {"--runtime", "--config-dir", "--install-scope"}:
            bridge_args.append(arg)
            if index + 1 < len(argv):
                bridge_args.append(str(argv[index + 1]))
            index += 2
            continue
        break

    options = parser.parse_args(bridge_args)
    gpd_args = argv[index:]
    if gpd_args[:1] == ["--"]:
        gpd_args = gpd_args[1:]
    return options, gpd_args


def _split_global_cli_options(argv: list[str]) -> tuple[list[str], list[str]]:
    """Partition root-global CLI options from the rest of the argv stream."""
    global_args: list[str] = []
    remaining_args: list[str] = []
    passthrough = False
    index = 0

    while index < len(argv):
        arg = str(argv[index])
        if passthrough:
            remaining_args.append(arg)
            index += 1
            continue

        if arg == "--":
            passthrough = True
            remaining_args.append(arg)
            index += 1
            continue

        if arg == "--raw":
            global_args.append(arg)
            index += 1
            continue

        if arg == "--cwd":
            global_args.append(arg)
            if index + 1 < len(argv):
                global_args.append(str(argv[index + 1]))
                index += 2
            else:
                index += 1
            continue

        if arg.startswith("--cwd="):
            global_args.append(arg)
            index += 1
            continue

        remaining_args.append(arg)
        index += 1

    return global_args, remaining_args


def _resolve_cli_cwd_from_argv(argv: list[str]) -> Path:
    """Resolve the effective CLI cwd from raw argv before Typer parses it."""
    raw_cwd = "."
    global_args, _ = _split_global_cli_options(argv)
    for index, arg in enumerate(global_args):
        if arg == "--cwd" and index + 1 < len(global_args):
            raw_cwd = global_args[index + 1]
            continue
        if arg.startswith("--cwd="):
            raw_cwd = arg.split("=", 1)[1]

    candidate = Path(raw_cwd).expanduser()
    if candidate.is_absolute():
        return candidate.resolve(strict=False)
    return (Path.cwd() / candidate).resolve(strict=False)


def _load_install_manifest(config_dir: Path) -> dict[str, object]:
    """Return install metadata for *config_dir* when present."""
    manifest_path = config_dir / MANIFEST_NAME
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _manifest_runtime_status(config_dir: Path) -> tuple[str | None, bool]:
    """Return the persisted runtime and whether the manifest declares one."""
    manifest = _load_install_manifest(config_dir)
    if "runtime" not in manifest:
        return None, False

    runtime = manifest.get("runtime")
    if not isinstance(runtime, str):
        return None, True

    normalized = runtime.strip()
    if not normalized:
        return None, True
    return normalize_runtime_name(normalized) or normalized, True


def _runtime_display_name(runtime: str) -> str:
    """Return a human-readable runtime label when the runtime is known."""
    try:
        return get_adapter(runtime).display_name
    except KeyError:
        return runtime


def _format_unknown_runtime_error(exc: KeyError) -> str:
    """Return the stable user-facing message for an unknown runtime."""
    if len(exc.args) == 1 and isinstance(exc.args[0], str):
        return exc.args[0]
    return str(exc)


def _canonical_runtime_name(runtime: str) -> str:
    """Return the canonical runtime id for aliases and display names."""
    normalized = normalize_runtime_name(runtime)
    if normalized is not None:
        return normalized
    return runtime.strip()


def _paths_equal(left: Path, right: Path) -> bool:
    """Return whether two paths resolve to the same location when comparable."""
    try:
        return left.expanduser().resolve() == right.expanduser().resolve()
    except OSError:
        return left.expanduser() == right.expanduser()


def _is_matching_local_install_candidate(candidate: Path, *, runtime: str) -> bool:
    """Return whether *candidate* should satisfy a local bridge config-dir lookup."""
    if not candidate.is_dir():
        return False

    manifest = _load_install_manifest(candidate)
    manifest_scope = manifest.get("install_scope")
    if manifest_scope == "global":
        return False

    manifest_runtime = manifest.get("runtime")
    if isinstance(manifest_runtime, str):
        normalized_runtime = normalize_runtime_name(manifest_runtime.strip()) if manifest_runtime.strip() else None
        manifest_runtime_value = normalized_runtime or manifest_runtime.strip()
        if manifest_runtime_value and manifest_runtime_value != runtime:
            return False

    if manifest_scope == "local":
        return True

    adapter = get_adapter(runtime)
    if _paths_equal(candidate, adapter.global_config_dir):
        return False

    return installed_runtime(candidate) == runtime


def _resolve_local_config_dir(raw_value: str, *, runtime: str, cli_cwd: Path) -> Path:
    """Resolve a local config dir reference against the nearest matching ancestor."""
    relative = Path(raw_value).expanduser()
    resolved_cwd = cli_cwd.resolve(strict=False)
    for base in (resolved_cwd, *resolved_cwd.parents):
        candidate = (base / relative).resolve(strict=False)
        if _is_matching_local_install_candidate(candidate, runtime=runtime):
            return candidate
    return (resolved_cwd / relative).resolve(strict=False)


def _resolve_config_dir(
    raw_value: str,
    *,
    runtime: str,
    install_scope: str,
    explicit_target: bool,
    cli_cwd: Path,
) -> Path:
    """Resolve the configured runtime dir from an absolute or local-workspace reference."""
    candidate = Path(raw_value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve(strict=False)
    if install_scope == "local" and not explicit_target:
        return _resolve_local_config_dir(raw_value, runtime=runtime, cli_cwd=cli_cwd)
    return (cli_cwd / candidate).resolve(strict=False)


def _uses_effective_explicit_target(
    *,
    runtime: str,
    raw_config_dir: str,
    config_dir: Path,
    install_scope: str,
    explicit_target: bool,
    cli_cwd: Path,
) -> bool:
    """Return whether repair guidance must emit ``--target-dir``."""
    if explicit_target or install_scope != "local":
        return explicit_target

    default_local_config_dir = (cli_cwd / Path(raw_config_dir).expanduser()).resolve(strict=False)
    return not _paths_equal(config_dir, default_local_config_dir)


def _maybe_reexec_from_checkout(raw_argv: list[str], *, cli_cwd: Path) -> None:
    """Re-exec through a checkout when the active package does not match it."""
    from gpd.version import checkout_root

    if os.environ.get(ENV_GPD_DISABLE_CHECKOUT_REEXEC) == "1":
        return

    root = checkout_root(cli_cwd)
    if root is None:
        return

    checkout_gpd = (root / "src" / "gpd").resolve(strict=False)
    active_gpd = Path(__file__).resolve().parent
    if active_gpd == checkout_gpd:
        return

    env = os.environ.copy()
    checkout_src = str((root / "src").resolve(strict=False))
    existing_pythonpath = [entry for entry in env.get("PYTHONPATH", "").split(os.pathsep) if entry]
    if checkout_src not in existing_pythonpath:
        env["PYTHONPATH"] = os.pathsep.join([checkout_src, *existing_pythonpath]) if existing_pythonpath else checkout_src
    env[ENV_GPD_DISABLE_CHECKOUT_REEXEC] = "1"
    os.execve(sys.executable, [sys.executable, "-m", "gpd.runtime_cli", *raw_argv], env)


def _install_error_message(
    *,
    runtime: str,
    raw_config_dir: str,
    config_dir: Path,
    install_scope: str,
    explicit_target: bool,
    cli_cwd: Path,
    missing: tuple[str, ...],
) -> str:
    """Return a deterministic repair message for an incomplete runtime install."""
    adapter = get_adapter(runtime)
    missing_list = ", ".join(f"`{relpath}`" for relpath in missing)
    repair_command = build_runtime_install_repair_command(
        runtime,
        install_scope=install_scope,
        target_dir=config_dir,
        explicit_target=_uses_effective_explicit_target(
            runtime=runtime,
            raw_config_dir=raw_config_dir,
            config_dir=config_dir,
            install_scope=install_scope,
            explicit_target=explicit_target,
            cli_cwd=cli_cwd,
        ),
    )
    return (
        f"GPD runtime install incomplete for {adapter.display_name} at `{config_dir}`.\n"
        f"Missing required install artifacts: {missing_list}\n"
        f"Repair the install with: `{repair_command}`\n"
    )


def _runtime_mismatch_error_message(
    *,
    runtime: str,
    manifest_runtime: str,
    raw_config_dir: str,
    config_dir: Path,
    install_scope: str,
    explicit_target: bool,
    cli_cwd: Path,
) -> str:
    """Return repair guidance when the resolved config dir belongs to another runtime."""
    repair_command = build_runtime_install_repair_command(
        manifest_runtime,
        install_scope=install_scope,
        target_dir=config_dir,
        explicit_target=_uses_effective_explicit_target(
            runtime=runtime,
            raw_config_dir=raw_config_dir,
            config_dir=config_dir,
            install_scope=install_scope,
            explicit_target=explicit_target,
            cli_cwd=cli_cwd,
        ),
    )
    return (
        f"GPD runtime bridge mismatch for {_runtime_display_name(runtime)} at `{config_dir}`.\n"
        f"Resolved install manifest pins {_runtime_display_name(manifest_runtime)} (`{manifest_runtime}`), "
        "so this bridge cannot safely continue.\n"
        f"Repair or reinstall with the owning runtime: `{repair_command}`\n"
    )


def _malformed_manifest_runtime_error_message(
    *,
    runtime: str,
    raw_config_dir: str,
    config_dir: Path,
    install_scope: str,
    explicit_target: bool,
    cli_cwd: Path,
) -> str:
    """Return repair guidance when the install manifest runtime field is malformed."""
    repair_command = build_runtime_install_repair_command(
        runtime,
        install_scope=install_scope,
        target_dir=config_dir,
        explicit_target=_uses_effective_explicit_target(
            runtime=runtime,
            raw_config_dir=raw_config_dir,
            config_dir=config_dir,
            install_scope=install_scope,
            explicit_target=explicit_target,
            cli_cwd=cli_cwd,
        ),
    )
    return (
        f"GPD runtime bridge rejected malformed install manifest at `{config_dir}`.\n"
        "The manifest `runtime` field must be a non-empty string.\n"
        f"Repair or reinstall with: `{repair_command}`\n"
    )


def main(argv: list[str] | None = None) -> int:
    """Validate the install contract, then dispatch into ``gpd.cli``."""
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    options, gpd_args = _parse_args(raw_argv)
    runtime = _canonical_runtime_name(options.runtime)
    cli_cwd = _resolve_cli_cwd_from_argv(gpd_args)
    _maybe_reexec_from_checkout(raw_argv, cli_cwd=cli_cwd)
    try:
        adapter = get_adapter(runtime)
    except KeyError as exc:
        sys.stderr.write(_format_unknown_runtime_error(exc) + "\n")
        return 127
    config_dir = _resolve_config_dir(
        options.config_dir,
        runtime=runtime,
        install_scope=options.install_scope,
        explicit_target=bool(options.explicit_target),
        cli_cwd=cli_cwd,
    )
    manifest_runtime, manifest_has_runtime = _manifest_runtime_status(config_dir)
    if manifest_has_runtime and manifest_runtime is None:
        sys.stderr.write(
            _malformed_manifest_runtime_error_message(
                runtime=runtime,
                raw_config_dir=options.config_dir,
                config_dir=config_dir,
                install_scope=options.install_scope,
                explicit_target=bool(options.explicit_target),
                cli_cwd=cli_cwd,
            )
        )
        return 127
    if manifest_runtime is not None and manifest_runtime != runtime:
        sys.stderr.write(
            _runtime_mismatch_error_message(
                runtime=runtime,
                manifest_runtime=manifest_runtime,
                raw_config_dir=options.config_dir,
                config_dir=config_dir,
                install_scope=options.install_scope,
                explicit_target=bool(options.explicit_target),
                cli_cwd=cli_cwd,
            )
        )
        return 127

    missing = adapter.missing_install_artifacts(config_dir)
    if missing:
        sys.stderr.write(
            _install_error_message(
                runtime=adapter.runtime_name,
                raw_config_dir=options.config_dir,
                config_dir=config_dir,
                install_scope=options.install_scope,
                explicit_target=bool(options.explicit_target),
                cli_cwd=cli_cwd,
                missing=missing,
            )
        )
        return 127

    os.environ[ENV_GPD_ACTIVE_RUNTIME] = adapter.runtime_name
    os.environ[ENV_GPD_DISABLE_CHECKOUT_REEXEC] = "1"

    from gpd.cli import entrypoint

    original_argv = list(sys.argv)
    try:
        sys.argv = ["gpd", *gpd_args]
        result = entrypoint()
    finally:
        sys.argv = original_argv

    if result is None:
        return 0
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
