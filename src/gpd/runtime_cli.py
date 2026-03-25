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
import os
import sys
from pathlib import Path

from gpd.adapters import get_adapter
from gpd.adapters.install_utils import (
    COMMANDS_DIR_NAME,
    FLAT_COMMANDS_DIR_NAME,
    GPD_INSTALL_DIR_NAME,
    build_runtime_install_repair_command,
)
from gpd.adapters.runtime_catalog import resolve_global_config_dir
from gpd.core.constants import ENV_GPD_ACTIVE_RUNTIME, ENV_GPD_DISABLE_CHECKOUT_REEXEC
from gpd.hooks.install_metadata import load_install_manifest_state
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
    """Return install metadata for *config_dir* when the manifest is valid JSON."""
    manifest_state, payload = load_install_manifest_state(config_dir)
    if manifest_state != "ok":
        return {}
    return payload


def _manifest_runtime_status(config_dir: Path) -> tuple[str | None, str]:
    """Return the persisted runtime plus the manifest contract status."""
    manifest_state, manifest = load_install_manifest_state(config_dir)
    if manifest_state != "ok":
        return None, manifest_state
    if "runtime" not in manifest:
        return None, "missing_runtime"

    runtime = manifest.get("runtime")
    if not isinstance(runtime, str):
        return None, "malformed_runtime"

    normalized = runtime.strip()
    if not normalized:
        return None, "malformed_runtime"
    canonical_runtime = normalize_runtime_name(normalized)
    if canonical_runtime is None:
        return None, "malformed_runtime"
    return canonical_runtime, "ok"


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


def _is_matching_local_install_candidate(candidate: Path, *, runtime: str, cli_cwd: Path) -> bool:
    """Return whether *candidate* should satisfy a local bridge config-dir lookup."""
    if not candidate.is_dir():
        return False

    manifest_runtime, manifest_status = _manifest_runtime_status(candidate)
    adapter = get_adapter(runtime)
    canonical_global_dir = resolve_global_config_dir(adapter.runtime_descriptor, home=Path.home(), environ={})
    if manifest_status == "ok":
        if manifest_runtime != runtime:
            return False

        manifest = _load_install_manifest(candidate)
        manifest_scope = manifest.get("install_scope")
        if manifest_scope == "global":
            return False
        if _paths_equal(candidate, canonical_global_dir) and manifest_scope != "local":
            return False
        return True

    has_install_markers = any(
        (
            (candidate / GPD_INSTALL_DIR_NAME).is_dir(),
            (candidate / COMMANDS_DIR_NAME / "gpd").is_dir(),
            (candidate / FLAT_COMMANDS_DIR_NAME).is_dir(),
        )
    )
    if not has_install_markers:
        return False
    if _paths_equal(candidate, canonical_global_dir):
        return False
    return True


def _resolve_local_config_dir(raw_value: str, *, runtime: str, cli_cwd: Path) -> Path:
    """Resolve a local config dir reference against the nearest matching ancestor."""
    relative = Path(raw_value).expanduser()
    resolved_cwd = cli_cwd.resolve(strict=False)
    fallback: Path | None = None
    adapter = get_adapter(runtime)
    for base in (resolved_cwd, *resolved_cwd.parents):
        candidate = (base / relative).resolve(strict=False)
        if not _is_matching_local_install_candidate(candidate, runtime=runtime, cli_cwd=resolved_cwd):
            continue
        manifest_runtime, manifest_status = _manifest_runtime_status(candidate)
        if manifest_status == "ok" and adapter.has_complete_install(candidate):
            return candidate
        if fallback is None:
            fallback = candidate
    if fallback is not None:
        return fallback
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
    if explicit_target:
        return True

    adapter = get_adapter(runtime)
    if install_scope == "global":
        canonical_global_dir = resolve_global_config_dir(adapter.runtime_descriptor, home=Path.home(), environ={})
        return not _paths_equal(config_dir, canonical_global_dir)

    default_local_config_dir = adapter.resolve_local_config_dir(cli_cwd).resolve(strict=False)
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
    manifest_install_scope: str | None,
    raw_config_dir: str,
    config_dir: Path,
    install_scope: str,
    explicit_target: bool,
    cli_cwd: Path,
) -> str:
    """Return repair guidance when the resolved config dir belongs to another runtime."""
    owning_install_scope = manifest_install_scope if manifest_install_scope in {"local", "global"} else install_scope
    repair_command = build_runtime_install_repair_command(
        manifest_runtime,
        install_scope=owning_install_scope,
        target_dir=config_dir,
        explicit_target=_uses_effective_explicit_target(
            runtime=manifest_runtime,
            raw_config_dir=raw_config_dir,
            config_dir=config_dir,
            install_scope=owning_install_scope,
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
        "The manifest `runtime` field must be a recognized non-empty runtime string.\n"
        f"Repair or reinstall with: `{repair_command}`\n"
    )


def _missing_manifest_runtime_error_message(
    *,
    runtime: str,
    raw_config_dir: str,
    config_dir: Path,
    install_scope: str,
    explicit_target: bool,
    cli_cwd: Path,
) -> str:
    """Return repair guidance when the install manifest omits ``runtime``."""
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
        f"GPD runtime bridge rejected incomplete install manifest at `{config_dir}`.\n"
        "The manifest must declare a non-empty `runtime` field.\n"
        f"Repair or reinstall with: `{repair_command}`\n"
    )


def _untrusted_manifest_error_message(
    *,
    runtime: str,
    raw_config_dir: str,
    config_dir: Path,
    install_scope: str,
    explicit_target: bool,
    cli_cwd: Path,
) -> str:
    """Return repair guidance when the install manifest cannot be trusted."""
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
        f"GPD runtime bridge rejected unreadable install manifest at `{config_dir}`.\n"
        "The manifest must be a JSON object with a non-empty `runtime` field.\n"
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
    manifest_runtime, manifest_status = _manifest_runtime_status(config_dir)
    manifest_payload = _load_install_manifest(config_dir) if manifest_status == "ok" else {}
    manifest_install_scope = manifest_payload.get("install_scope")
    if not isinstance(manifest_install_scope, str):
        manifest_install_scope = None
    if manifest_status in {"corrupt", "invalid"}:
        sys.stderr.write(
            _untrusted_manifest_error_message(
                runtime=runtime,
                raw_config_dir=options.config_dir,
                config_dir=config_dir,
                install_scope=options.install_scope,
                explicit_target=bool(options.explicit_target),
                cli_cwd=cli_cwd,
            )
        )
        return 127
    if manifest_status == "missing_runtime":
        sys.stderr.write(
            _missing_manifest_runtime_error_message(
                runtime=runtime,
                raw_config_dir=options.config_dir,
                config_dir=config_dir,
                install_scope=options.install_scope,
                explicit_target=bool(options.explicit_target),
                cli_cwd=cli_cwd,
            )
        )
        return 127
    if manifest_status == "malformed_runtime":
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
                manifest_install_scope=manifest_install_scope,
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
