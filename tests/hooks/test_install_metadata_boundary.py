"""Targeted assertions for install-metadata runtime boundary hardening."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from gpd.hooks.install_context import detect_self_owned_install
from gpd.hooks.install_metadata import (
    assess_install_target,
    config_dir_has_complete_install,
    config_dir_has_managed_install_markers,
    installed_update_command,
    load_install_manifest_runtime_status,
    load_install_manifest_scope_status,
    load_install_manifest_state,
)
from gpd.hooks.runtime_detect import _manifest_runtime_status as runtime_detect_manifest_runtime_status


def _seed_anonymous_install_tree(config_dir: Path, *, hook_filename: str) -> Path:
    """Create an install tree that only carries anonymous legacy ownership hints."""
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "get-physics-done").mkdir(parents=True, exist_ok=True)
    (config_dir / "gpd-file-manifest.json").write_text(
        json.dumps(
            {
                "install_scope": "local",
                "files": {
                    "skills/gpd-help/SKILL.md": "legacy-hint",
                },
            }
        ),
        encoding="utf-8",
    )

    hook_path = config_dir / "hooks" / hook_filename
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text("# hook\n", encoding="utf-8")
    return hook_path


@pytest.mark.parametrize(
    ("manifest_content", "expected_state", "expected_payload"),
    [
        (None, "missing", {}),
        (b"\xff", "corrupt", {}),
        ("[]", "invalid", {}),
        (json.dumps({"install_scope": "local", "runtime": "codex"}), "ok", {"install_scope": "local", "runtime": "codex"}),
    ],
)
def test_load_install_manifest_state_classifies_manifest_payloads(
    tmp_path: Path,
    manifest_content: bytes | str | None,
    expected_state: str,
    expected_payload: dict[str, object],
) -> None:
    config_dir = tmp_path / ".codex"
    config_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = config_dir / "gpd-file-manifest.json"
    if manifest_content is not None:
        if isinstance(manifest_content, bytes):
            manifest_path.write_bytes(manifest_content)
        else:
            manifest_path.write_text(manifest_content, encoding="utf-8")

    assert load_install_manifest_state(config_dir) == (expected_state, expected_payload)


@pytest.mark.parametrize(
    ("manifest_content", "expected_state", "expected_scope"),
    [
        (None, "missing", None),
        (b"\xff", "corrupt", None),
        ("[]", "invalid", None),
        (json.dumps({"runtime": "codex"}), "missing_install_scope", None),
        (json.dumps({"runtime": "codex", "install_scope": ""}), "malformed_install_scope", None),
        (json.dumps({"runtime": "codex", "install_scope": "workspace"}), "malformed_install_scope", None),
        (json.dumps({"runtime": "codex", "install_scope": "local"}), "ok", "local"),
        (json.dumps({"runtime": "codex", "install_scope": "global"}), "ok", "global"),
    ],
)
def test_load_install_manifest_scope_status_classifies_manifest_payloads(
    tmp_path: Path,
    manifest_content: bytes | str | None,
    expected_state: str,
    expected_scope: str | None,
) -> None:
    config_dir = tmp_path / ".codex"
    config_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = config_dir / "gpd-file-manifest.json"
    if manifest_content is not None:
        if isinstance(manifest_content, bytes):
            manifest_path.write_bytes(manifest_content)
        else:
            manifest_path.write_text(manifest_content, encoding="utf-8")

    state, payload, scope = load_install_manifest_scope_status(config_dir)
    assert state == expected_state
    assert scope == expected_scope
    if expected_state in {"ok", "missing_install_scope", "malformed_install_scope"}:
        assert payload == json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        assert payload == {}


def test_config_dir_has_managed_install_markers_detects_install_surfaces(tmp_path: Path) -> None:
    config_dir = tmp_path / ".codex"
    config_dir.mkdir(parents=True, exist_ok=True)
    version_path = config_dir / "get-physics-done" / "VERSION"
    version_path.parent.mkdir(parents=True, exist_ok=True)
    version_path.write_text("1.0.0\n", encoding="utf-8")

    assert config_dir_has_managed_install_markers(config_dir) is True


def test_config_dir_has_managed_install_markers_ignores_empty_managed_dirs(tmp_path: Path) -> None:
    config_dir = tmp_path / ".codex"
    (config_dir / "get-physics-done").mkdir(parents=True, exist_ok=True)
    (config_dir / "commands" / "gpd").mkdir(parents=True, exist_ok=True)
    (config_dir / "command").mkdir(parents=True, exist_ok=True)

    assert config_dir_has_managed_install_markers(config_dir) is False


def test_config_dir_has_managed_install_markers_fails_closed_on_scan_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / ".codex"
    managed_dir = config_dir / "get-physics-done"
    (managed_dir / "commands").mkdir(parents=True, exist_ok=True)
    original_rglob = Path.rglob

    def _rglob(path: Path, pattern: str):
        if path == managed_dir / "commands":
            raise OSError("permission denied")
        return original_rglob(path, pattern)

    monkeypatch.setattr(Path, "rglob", _rglob)

    assert config_dir_has_managed_install_markers(config_dir) is True


def test_config_dir_has_managed_install_markers_ignores_user_agents_and_hooks(tmp_path: Path) -> None:
    config_dir = tmp_path / ".codex"
    hooks_dir = config_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "statusline.py").write_text("# third-party hook\n", encoding="utf-8")
    agents_dir = config_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "my-custom-agent.md").write_text("custom\n", encoding="utf-8")

    assert config_dir_has_managed_install_markers(config_dir) is False


def test_assess_install_target_distinguishes_absent_and_clean_targets(tmp_path: Path) -> None:
    absent = tmp_path / ".codex"
    clean = tmp_path / ".codex-clean"
    clean.mkdir(parents=True, exist_ok=True)

    absent_assessment = assess_install_target(absent)
    clean_assessment = assess_install_target(clean)

    assert absent_assessment.state == "absent"
    assert absent_assessment.has_managed_markers is False
    assert clean_assessment.state == "clean"
    assert clean_assessment.has_managed_markers is False


def test_assess_install_target_classifies_owned_complete_and_incomplete_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / ".codex"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"install_scope": "local", "runtime": "codex"}),
        encoding="utf-8",
    )

    class _FakeAdapter:
        def __init__(self, missing_install_artifacts: tuple[str, ...]) -> None:
            self._missing_install_artifacts = missing_install_artifacts
            self.local_config_dir_name = ".codex"

        def missing_install_artifacts(self, target_dir: Path) -> tuple[str, ...]:
            return self._missing_install_artifacts

    monkeypatch.setattr("gpd.hooks.install_metadata.get_adapter", lambda runtime: _FakeAdapter(()))
    complete = assess_install_target(config_dir)

    monkeypatch.setattr(
        "gpd.hooks.install_metadata.get_adapter",
        lambda runtime: _FakeAdapter(("agents/gpd-help/SKILL.md",)),
    )
    incomplete = assess_install_target(config_dir)

    assert complete.state == "owned_complete"
    assert complete.has_managed_markers is True
    assert incomplete.state == "owned_incomplete"
    assert incomplete.missing_install_artifacts == ("agents/gpd-help/SKILL.md",)


@pytest.mark.parametrize(
    ("hook_filename",),
    [
        ("check_update.py",),
        ("statusline.py",),
        ("notify.py",),
    ],
)
def test_hook_self_detection_accepts_manifest_backed_owned_incomplete_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    hook_filename: str,
) -> None:
    config_dir = tmp_path / ".codex"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"install_scope": "local", "runtime": "codex"}),
        encoding="utf-8",
    )

    class _FakeAdapter:
        def __init__(self, missing_install_artifacts: tuple[str, ...]) -> None:
            self._missing_install_artifacts = missing_install_artifacts
            self.local_config_dir_name = ".codex"

        def missing_install_artifacts(self, target_dir: Path) -> tuple[str, ...]:
            return self._missing_install_artifacts

    monkeypatch.setattr(
        "gpd.hooks.install_metadata.get_adapter",
        lambda runtime: _FakeAdapter(("agents/gpd-help/SKILL.md",)),
    )
    hook_path = config_dir / "hooks" / hook_filename
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text("# hook\n", encoding="utf-8")

    incomplete = assess_install_target(config_dir)
    detected = detect_self_owned_install(hook_path)

    assert incomplete.state == "owned_incomplete"
    assert detected is not None
    assert detected.runtime == "codex"
    assert detected.install_scope == "local"
    assert installed_update_command(config_dir) is None


def test_hook_self_detection_requires_explicit_target_metadata_for_update_command(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / ".codex"
    hook_path = _seed_anonymous_install_tree(config_dir, hook_filename="notify.py")
    manifest_path = config_dir / "gpd-file-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "runtime": "codex",
            "install_target_dir": str(config_dir),
        }
    )
    manifest.pop("explicit_target", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert detect_self_owned_install(hook_path) is not None
    assert installed_update_command(config_dir) is None


def test_assess_install_target_classifies_foreign_and_untrusted_manifests(
    tmp_path: Path,
) -> None:
    foreign_dir = tmp_path / ".codex-foreign"
    foreign_dir.mkdir(parents=True, exist_ok=True)
    (foreign_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"install_scope": "local", "runtime": "codex"}),
        encoding="utf-8",
    )

    untrusted_dir = tmp_path / ".codex-untrusted"
    untrusted_dir.mkdir(parents=True, exist_ok=True)
    (untrusted_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"install_scope": "local"}),
        encoding="utf-8",
    )

    foreign = assess_install_target(foreign_dir, expected_runtime="claude-code")
    untrusted = assess_install_target(untrusted_dir)

    assert foreign.state == "foreign_runtime"
    assert foreign.manifest_runtime == "codex"
    assert untrusted.state == "untrusted_manifest"
    assert untrusted.manifest_state == "missing_runtime"


def test_assess_install_target_preserves_unsupported_manifest_runtime(
    tmp_path: Path,
) -> None:
    retired_dir = tmp_path / ".retired-runtime"
    retired_dir.mkdir(parents=True, exist_ok=True)
    (retired_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"install_scope": "local", "runtime": "retired-runtime"}),
        encoding="utf-8",
    )

    unsupported = assess_install_target(retired_dir)
    foreign = assess_install_target(retired_dir, expected_runtime="codex")

    assert unsupported.state == "unsupported_runtime"
    assert unsupported.manifest_state == "unsupported_runtime"
    assert unsupported.manifest_runtime == "retired-runtime"
    assert unsupported.readiness_state == "blocked"
    assert "not supported by this GPD version" in unsupported.readiness_message()
    assert foreign.state == "foreign_runtime"
    assert foreign.manifest_runtime == "retired-runtime"


@pytest.mark.parametrize(
    ("manifest_content", "expected_state", "expected_runtime"),
    [
        (None, "missing", None),
        (b"\xff", "corrupt", None),
        ("[]", "invalid", None),
        (json.dumps({"install_scope": "local"}), "missing_runtime", None),
        (json.dumps({"install_scope": "local", "runtime": 123}), "malformed_runtime", None),
        (json.dumps({"install_scope": "local", "runtime": "Codex"}), "malformed_runtime", None),
        (json.dumps({"install_scope": "local", "runtime": "retired-runtime"}), "unsupported_runtime", "retired-runtime"),
        (json.dumps({"install_scope": "local", "runtime": "codex"}), "ok", "codex"),
    ],
)
def test_install_manifest_runtime_status_is_shared_across_surfaces(
    tmp_path: Path,
    manifest_content: bytes | str | None,
    expected_state: str,
    expected_runtime: str | None,
) -> None:
    config_dir = tmp_path / ".codex"
    config_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = config_dir / "gpd-file-manifest.json"
    if manifest_content is not None:
        if isinstance(manifest_content, bytes):
            manifest_path.write_bytes(manifest_content)
        else:
            manifest_path.write_text(manifest_content, encoding="utf-8")

    metadata_state, metadata_payload, metadata_runtime = load_install_manifest_runtime_status(config_dir)
    detect_state, detect_runtime = runtime_detect_manifest_runtime_status(config_dir)

    assert metadata_state == expected_state
    assert metadata_runtime == expected_runtime
    assert detect_state == expected_state
    assert detect_runtime == expected_runtime
    if expected_state in {"ok", "unsupported_runtime", "missing_runtime", "malformed_runtime"}:
        assert metadata_payload == json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        assert metadata_payload == {}


def test_runtime_less_manifest_tree_is_rejected_by_install_metadata(tmp_path: Path) -> None:
    config_dir = tmp_path / ".codex"
    _seed_anonymous_install_tree(config_dir, hook_filename="install_metadata.py")

    assert config_dir_has_complete_install(config_dir) is False
    assert installed_update_command(config_dir) is None


def test_non_utf8_manifest_tree_is_rejected_by_install_metadata(tmp_path: Path) -> None:
    config_dir = tmp_path / ".codex"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "get-physics-done").mkdir(parents=True, exist_ok=True)
    (config_dir / "gpd-file-manifest.json").write_bytes(b"\xff")

    assert config_dir_has_complete_install(config_dir) is False
    assert installed_update_command(config_dir) is None


@pytest.mark.parametrize(
    ("hook_filename",),
    [
        ("check_update.py",),
        ("statusline.py",),
        ("notify.py",),
    ],
)
def test_hook_self_detection_rejects_runtime_less_manifest_tree(tmp_path: Path, hook_filename: str) -> None:
    config_dir = tmp_path / ".codex"
    hook_path = _seed_anonymous_install_tree(config_dir, hook_filename=hook_filename)

    assert detect_self_owned_install(hook_path) is None


@pytest.mark.parametrize(
    ("hook_filename",),
    [
        ("check_update.py",),
        ("statusline.py",),
        ("notify.py",),
    ],
)
def test_hook_self_detection_rejects_non_utf8_manifest_tree(tmp_path: Path, hook_filename: str) -> None:
    config_dir = tmp_path / ".codex"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "get-physics-done").mkdir(parents=True, exist_ok=True)
    (config_dir / "gpd-file-manifest.json").write_bytes(b"\xff")
    hook_path = config_dir / "hooks" / hook_filename
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text("# hook\n", encoding="utf-8")

    assert detect_self_owned_install(hook_path) is None


def test_runtime_detect_uses_shared_manifest_scope_helper() -> None:
    import gpd.hooks.runtime_detect as runtime_detect

    source = inspect.getsource(runtime_detect)

    assert "install_scope_from_manifest" in source
    assert "_manifest_install_scope" not in source


def test_runtime_detect_manifest_helper_signature_drops_unused_cwd_and_home() -> None:
    from gpd.hooks.runtime_detect import _runtime_from_manifest_or_path

    params = inspect.signature(_runtime_from_manifest_or_path).parameters

    assert "cwd" not in params
    assert "home" not in params


def test_runtime_detect_install_helper_signature_drops_unused_cwd_and_home() -> None:
    from gpd.hooks.runtime_detect import _has_gpd_install

    params = inspect.signature(_has_gpd_install).parameters

    assert "cwd" not in params
    assert "home" not in params


def test_runtime_cli_uses_shared_manifest_runtime_helper() -> None:
    import gpd.runtime_cli as runtime_cli

    source = inspect.getsource(runtime_cli)

    assert "load_install_manifest_runtime_status" in source
    assert "config_dir_has_managed_install_markers" in source
    assert "def _manifest_runtime_status" not in source
    assert "def _has_managed_install_markers" not in source


def test_install_metadata_keeps_manifest_boundary_free_of_install_utils_imports() -> None:
    import gpd.hooks.install_metadata as install_metadata

    source = inspect.getsource(install_metadata)

    assert "from gpd.adapters.install_utils import" not in source
    assert "import gpd.adapters.install_utils as" not in source
    assert "get_managed_install_surface_policy" in source
    assert "get_shared_install_metadata" in source
