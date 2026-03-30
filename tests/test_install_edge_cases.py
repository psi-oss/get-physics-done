"""Edge-case tests for GPD install system — 10 scenarios from team lead.

1. Install to read-only directory
2. Install with corrupted package data (missing commands/)
3. Install preserves non-GPD files in commands/
4. GPD_MODEL=invalid:model doesn't affect install
5. Uninstall with corrupted manifest JSON
6. Install with very long path names (>200 chars)
7. Install when HOME is not set (env var fallback)
8. Multi-runtime install to same target_dir
9. Registry with invalid YAML frontmatter
10. expand_at_includes with 3-way circular @includes
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from gpd import registry
from gpd.adapters import get_adapter, iter_runtime_descriptors
from gpd.adapters.install_utils import (
    MANIFEST_NAME,
    expand_at_includes,
    validate_package_integrity,
    write_settings,
)
from gpd.registry import _parse_agent_file, _parse_frontmatter

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


_RUNTIME_DESCRIPTORS = tuple(iter_runtime_descriptors())
_ALL_RUNTIMES = tuple(descriptor.runtime_name for descriptor in _RUNTIME_DESCRIPTORS)
_RUNTIMES_WITH_MANIFEST_FILE_PREFIXES = tuple(
    descriptor.runtime_name for descriptor in _RUNTIME_DESCRIPTORS if descriptor.manifest_file_prefixes
)


def _make_gpd_root(tmp_path: Path) -> Path:
    """Create a minimal valid GPD package data directory."""
    root = tmp_path / "gpd_pkg"
    for d in ("commands", "agents", "hooks"):
        (root / d).mkdir(parents=True)
    (root / "commands" / "help.md").write_text(
        "---\nname: gpd:help\ndescription: Help\n---\nBody.\n",
        encoding="utf-8",
    )
    (root / "agents" / "gpd-verifier.md").write_text(
        "---\nname: gpd-verifier\ndescription: Verify\ntools: file_read\ncolor: green\n---\nPrompt.\n",
        encoding="utf-8",
    )
    (root / "hooks" / "statusline.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "hooks" / "check_update.py").write_text("print('ok')\n", encoding="utf-8")
    for subdir in ("references", "templates", "workflows"):
        d = root / "specs" / subdir
        d.mkdir(parents=True)
        (d / f"{subdir[:3]}.md").write_text(f"# {subdir}\n", encoding="utf-8")
    return root


def _write_manifest(target: Path, *, runtime: str, install_scope: str = "local", explicit_target: bool = True) -> None:
    target.mkdir(parents=True, exist_ok=True)
    (target / MANIFEST_NAME).write_text(
        json.dumps(
            {
                "runtime": runtime,
                "install_scope": install_scope,
                "explicit_target": explicit_target,
            }
        ),
        encoding="utf-8",
    )


def _seed_ambiguous_install_target(target: Path, *, manifest_state: str) -> None:
    """Create a target that looks like an install but lacks trustworthy ownership data."""
    (target / "commands" / "gpd").mkdir(parents=True, exist_ok=True)
    (target / "commands" / "gpd" / "help.md").write_text("help\n", encoding="utf-8")
    (target / "get-physics-done").mkdir(parents=True, exist_ok=True)
    (target / "get-physics-done" / "VERSION").write_text("1.0\n", encoding="utf-8")

    manifest_path = target / MANIFEST_NAME
    if manifest_state == "corrupt":
        manifest_path.write_text("{not-json", encoding="utf-8")
    elif manifest_state == "unknown":
        manifest_path.write_text(
            json.dumps({"runtime": "not-a-runtime", "install_scope": "local"}),
            encoding="utf-8",
        )


def _install_gemini_for_tests(gpd_root: Path, target: Path) -> None:
    adapter = get_adapter("gemini")
    result = adapter.install(gpd_root, target, is_global=True)
    adapter.finalize_install(result)

_FOREIGN_RUNTIME_BY_RUNTIME = {
    descriptor.runtime_name: _ALL_RUNTIMES[(index + 1) % len(_ALL_RUNTIMES)]
    for index, descriptor in enumerate(_RUNTIME_DESCRIPTORS)
}


# =========================================================================
# 1. Install to a read-only directory
# =========================================================================


class TestInstallReadOnlyDirectory:
    """Install to a read-only target should fail with a clear error."""

    def test_install_to_readonly_target_raises(self, tmp_path: Path) -> None:
        gpd_root = _make_gpd_root(tmp_path)
        target = tmp_path / "readonly"
        target.mkdir()

        # Make target read-only
        target.chmod(stat.S_IRUSR | stat.S_IXUSR)
        try:
            adapter = get_adapter("claude-code")
            with pytest.raises((PermissionError, OSError)):
                adapter.install(gpd_root, target, is_global=True)
        finally:
            # Restore permissions for cleanup
            target.chmod(stat.S_IRWXU)

    def test_write_settings_to_readonly_dir_raises(self, tmp_path: Path) -> None:
        readonly = tmp_path / "readonly"
        readonly.mkdir()
        readonly.chmod(stat.S_IRUSR | stat.S_IXUSR)
        try:
            with pytest.raises(PermissionError, match="Cannot write to settings"):
                write_settings(readonly / "settings.json", {"key": "value"})
        finally:
            readonly.chmod(stat.S_IRWXU)


# =========================================================================
# 2. Install with corrupted package data (missing commands/)
# =========================================================================


class TestInstallCorruptedPackage:
    """Missing required subdirectories should fail with clear FileNotFoundError."""

    def test_missing_commands_dir(self, tmp_path: Path) -> None:
        root = tmp_path / "broken"
        (root / "agents").mkdir(parents=True)
        (root / "hooks").mkdir(parents=True)
        # commands/ is missing

        with pytest.raises(FileNotFoundError, match="commands"):
            validate_package_integrity(root)

    def test_missing_agents_dir(self, tmp_path: Path) -> None:
        root = tmp_path / "broken"
        (root / "commands").mkdir(parents=True)
        (root / "hooks").mkdir(parents=True)

        with pytest.raises(FileNotFoundError, match="agents"):
            validate_package_integrity(root)

    def test_missing_hooks_dir(self, tmp_path: Path) -> None:
        root = tmp_path / "broken"
        (root / "commands").mkdir(parents=True)
        (root / "agents").mkdir(parents=True)

        with pytest.raises(FileNotFoundError, match="hooks"):
            validate_package_integrity(root)

    def test_missing_specs_dir(self, tmp_path: Path) -> None:
        root = tmp_path / "broken"
        (root / "commands").mkdir(parents=True)
        (root / "agents").mkdir(parents=True)
        (root / "hooks").mkdir(parents=True)

        with pytest.raises(FileNotFoundError, match="specs"):
            validate_package_integrity(root)

    def test_all_dirs_present_passes(self, tmp_path: Path) -> None:
        root = tmp_path / "valid"
        for d in ("commands", "agents", "hooks", "specs"):
            (root / d).mkdir(parents=True)
        # Should not raise
        validate_package_integrity(root)

    def test_install_with_missing_commands_raises_runtime_error(self, tmp_path: Path) -> None:
        """Full install flow surfaces the integrity error."""
        root = tmp_path / "broken"
        (root / "agents").mkdir(parents=True)
        (root / "hooks").mkdir(parents=True)
        # commands/ missing

        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()

        with pytest.raises(FileNotFoundError, match="commands"):
            adapter.install(root, target, is_global=True)


# =========================================================================
# 3. Install preserves non-GPD files in commands/
# =========================================================================


class TestNonGpdFilesPreserved:
    """Non-GPD files in commands/ and agents/ should survive install/uninstall."""

    def test_install_preserves_non_gpd_commands(self, tmp_path: Path) -> None:
        gpd_root = _make_gpd_root(tmp_path)
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"

        # Pre-populate with non-GPD commands
        user_cmds = target / "commands"
        user_cmds.mkdir(parents=True)
        (user_cmds / "my-custom-cmd.md").write_text("# My custom command\n", encoding="utf-8")
        (user_cmds / "another-tool").mkdir()
        (user_cmds / "another-tool" / "cmd.md").write_text("# Another\n", encoding="utf-8")

        adapter.install(gpd_root, target, is_global=True)

        # GPD commands installed in commands/gpd/
        assert (target / "commands" / "gpd").is_dir()
        # User commands still present
        assert (target / "commands" / "my-custom-cmd.md").exists()
        assert (target / "commands" / "another-tool" / "cmd.md").exists()

    def test_uninstall_preserves_non_gpd_commands(self, tmp_path: Path) -> None:
        gpd_root = _make_gpd_root(tmp_path)
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"

        # Install first
        (target / "commands").mkdir(parents=True)
        (target / "commands" / "my-custom-cmd.md").write_text("custom\n", encoding="utf-8")
        adapter.install(gpd_root, target, is_global=True)

        # Uninstall
        adapter.uninstall(target)

        # GPD commands removed
        assert not (target / "commands" / "gpd").exists()
        # User commands preserved
        assert (target / "commands" / "my-custom-cmd.md").exists()

    def test_uninstall_preserves_non_gpd_agents(self, tmp_path: Path) -> None:
        gpd_root = _make_gpd_root(tmp_path)
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()

        adapter.install(gpd_root, target, is_global=True)

        # Add a non-GPD agent
        (target / "agents" / "my-custom-agent.md").write_text("custom agent\n", encoding="utf-8")

        adapter.uninstall(target)

        # GPD agents removed, custom preserved
        gpd_agents = [f for f in (target / "agents").iterdir() if f.name.startswith("gpd-") and f.suffix == ".md"]
        assert len(gpd_agents) == 0
        assert (target / "agents" / "my-custom-agent.md").exists()

    def test_install_preserves_unmanaged_hook_with_matching_gpd_basename(self, tmp_path: Path) -> None:
        gpd_root = _make_gpd_root(tmp_path)
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        unmanaged_hook = target / "hooks" / "statusline.py"
        unmanaged_hook.parent.mkdir(parents=True)
        unmanaged_hook.write_text("# third-party statusline hook\n", encoding="utf-8")

        adapter.install(gpd_root, target, is_global=True)

        assert unmanaged_hook.read_text(encoding="utf-8") == "# third-party statusline hook\n"
        assert (target / "hooks" / "check_update.py").exists()


# =========================================================================
# 4. Cross-runtime manifest ownership refusal
# =========================================================================


class TestCrossRuntimeManifestOwnershipRefusal:
    """Foreign manifests should block explicit installs and most uninstalls."""

    @pytest.mark.parametrize("runtime", _ALL_RUNTIMES)
    def test_install_refuses_foreign_manifest_on_explicit_target(self, tmp_path: Path, runtime: str) -> None:
        gpd_root = _make_gpd_root(tmp_path)
        adapter = get_adapter(runtime)
        target = tmp_path / f"{runtime}-target"
        target.mkdir()
        preserved = target / "get-physics-done" / "keep.md"
        preserved.parent.mkdir(parents=True, exist_ok=True)
        preserved.write_text("keep\n", encoding="utf-8")
        foreign_runtime = _FOREIGN_RUNTIME_BY_RUNTIME[runtime]
        _write_manifest(target, runtime=foreign_runtime)

        install_kwargs: dict[str, object] = {"is_global": False, "explicit_target": True}
        if runtime == "codex":
            skills_dir = tmp_path / "skills"
            skills_dir.mkdir()
            install_kwargs["skills_dir"] = skills_dir

        with pytest.raises(RuntimeError) as excinfo:
            adapter.install(gpd_root, target, **install_kwargs)

        message = str(excinfo.value)
        assert f"Refusing to install into `{target}`" in message
        assert f"{get_adapter(foreign_runtime).display_name} (`{foreign_runtime}`)" in message
        assert f"{adapter.display_name} (`{runtime}`)" in message
        assert preserved.read_text(encoding="utf-8") == "keep\n"
        assert json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))["runtime"] == foreign_runtime

    @pytest.mark.parametrize("runtime", _ALL_RUNTIMES)
    def test_install_refuses_corrupt_manifest_on_explicit_target_named_like_runtime_default(
        self, tmp_path: Path, runtime: str
    ) -> None:
        gpd_root = _make_gpd_root(tmp_path)
        adapter = get_adapter(runtime)
        target = tmp_path / adapter.config_dir_name
        target.mkdir()
        preserved = target / "get-physics-done" / "keep.md"
        preserved.parent.mkdir(parents=True, exist_ok=True)
        preserved.write_text("keep\n", encoding="utf-8")
        (target / MANIFEST_NAME).write_text("{not valid json", encoding="utf-8")

        install_kwargs: dict[str, object] = {"is_global": True, "explicit_target": True}
        if runtime == "codex":
            skills_dir = tmp_path / "skills"
            skills_dir.mkdir()
            install_kwargs["skills_dir"] = skills_dir

        with pytest.raises(RuntimeError) as excinfo:
            adapter.install(gpd_root, target, **install_kwargs)

        message = str(excinfo.value)
        assert f"Refusing to install into `{target}`" in message
        assert "manifest cannot be trusted" in message
        assert preserved.read_text(encoding="utf-8") == "keep\n"

    @pytest.mark.parametrize("manifest_state", ["missing", "corrupt", "unknown"])
    def test_install_refuses_ambiguous_target_when_manifest_cannot_prove_ownership(
        self, tmp_path: Path, manifest_state: str
    ) -> None:
        gpd_root = _make_gpd_root(tmp_path)
        adapter = get_adapter("claude-code")
        target = tmp_path / "ambiguous-target"
        target.mkdir()
        _seed_ambiguous_install_target(target, manifest_state=manifest_state)

        with pytest.raises(RuntimeError) as excinfo:
            adapter.install(gpd_root, target, is_global=False, explicit_target=True)

        message = str(excinfo.value)
        assert f"Refusing to install into `{target}`" in message
        if manifest_state == "unknown":
            assert "manifest cannot be trusted" in message
        assert (target / "commands" / "gpd" / "help.md").exists()
        assert (target / "get-physics-done" / "VERSION").exists()

    @pytest.mark.parametrize("runtime", _RUNTIMES_WITH_MANIFEST_FILE_PREFIXES)
    def test_install_refuses_manifest_with_runtime_file_prefixes_but_no_runtime(
        self, tmp_path: Path, runtime: str
    ) -> None:
        gpd_root = _make_gpd_root(tmp_path)
        adapter = get_adapter(runtime)
        target = tmp_path / f"{runtime}-prefixed-target"
        target.mkdir()
        manifest_prefix = adapter.runtime_descriptor.manifest_file_prefixes[0]
        (target / MANIFEST_NAME).write_text(
            json.dumps(
                {
                    "install_scope": "local",
                    "files": {f"{manifest_prefix}artifact.txt": "hash"},
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(RuntimeError) as excinfo:
            adapter.install(gpd_root, target, is_global=False, explicit_target=True)

        message = str(excinfo.value)
        assert f"Refusing to install into `{target}`" in message
        assert "manifest cannot be trusted" in message

    @pytest.mark.parametrize("manifest_state", ["missing", "corrupt", "unknown"])
    def test_uninstall_refuses_ambiguous_target_when_manifest_cannot_prove_ownership(
        self, tmp_path: Path, manifest_state: str
    ) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / "ambiguous-target"
        target.mkdir()
        _seed_ambiguous_install_target(target, manifest_state=manifest_state)

        with pytest.raises(RuntimeError) as excinfo:
            adapter.uninstall(target)

        message = str(excinfo.value)
        assert f"Refusing to uninstall from `{target}`" in message
        if manifest_state == "unknown":
            assert "manifest cannot be trusted" in message
        assert (target / "commands" / "gpd" / "help.md").exists()
        assert (target / "get-physics-done" / "VERSION").exists()

    @pytest.mark.parametrize("runtime", _RUNTIMES_WITH_MANIFEST_FILE_PREFIXES)
    def test_uninstall_refuses_manifest_with_runtime_file_prefixes_but_no_runtime(
        self, tmp_path: Path, runtime: str
    ) -> None:
        adapter = get_adapter(runtime)
        target = tmp_path / f"{runtime}-prefixed-target"
        target.mkdir()
        manifest_prefix = adapter.runtime_descriptor.manifest_file_prefixes[0]
        (target / MANIFEST_NAME).write_text(
            json.dumps(
                {
                    "install_scope": "local",
                    "files": {f"{manifest_prefix}artifact.txt": "hash"},
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(RuntimeError) as excinfo:
            adapter.uninstall(target)

        message = str(excinfo.value)
        assert f"Refusing to uninstall from `{target}`" in message
        assert "manifest cannot be trusted" in message

    @pytest.mark.parametrize("runtime", _ALL_RUNTIMES)
    def test_uninstall_refuses_foreign_manifest(self, tmp_path: Path, runtime: str) -> None:
        adapter = get_adapter(runtime)
        target = tmp_path / f"{runtime}-target"
        target.mkdir()
        foreign_runtime = _FOREIGN_RUNTIME_BY_RUNTIME[runtime]
        _write_manifest(target, runtime=foreign_runtime)
        preserved = target / "get-physics-done" / "keep.md"
        preserved.parent.mkdir(parents=True, exist_ok=True)
        preserved.write_text("keep\n", encoding="utf-8")

        if runtime == "codex":
            skills_dir = tmp_path / "skills"
            skills_dir.mkdir()
            with pytest.raises(RuntimeError) as excinfo:
                adapter.uninstall(target, skills_dir=skills_dir)
        else:
            with pytest.raises(RuntimeError) as excinfo:
                adapter.uninstall(target)

        message = str(excinfo.value)
        assert f"Refusing to uninstall from `{target}`" in message
        assert f"{get_adapter(foreign_runtime).display_name} (`{foreign_runtime}`)" in message
        assert f"{adapter.display_name} (`{runtime}`)" in message
        assert preserved.read_text(encoding="utf-8") == "keep\n"


# =========================================================================
# 5. GPD_MODEL=invalid:model doesn't affect install
# =========================================================================


class TestGpdModelEnvVar:
    """GPD_MODEL is a runtime setting — install should succeed regardless."""

    def test_install_with_invalid_model_succeeds(self, tmp_path: Path) -> None:
        gpd_root = _make_gpd_root(tmp_path)
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()

        with patch.dict(os.environ, {"GPD_MODEL": "invalid:totally-fake-model"}):
            result = adapter.install(gpd_root, target, is_global=True)

        assert result["runtime"] == "claude-code"
        assert (target / "commands" / "gpd").is_dir()

    def test_install_with_empty_model_succeeds(self, tmp_path: Path) -> None:
        gpd_root = _make_gpd_root(tmp_path)
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()

        with patch.dict(os.environ, {"GPD_MODEL": ""}):
            result = adapter.install(gpd_root, target, is_global=True)

        assert result["runtime"] == "claude-code"


# =========================================================================
# 6. Uninstall with corrupted manifest JSON
# =========================================================================


class TestUninstallCorruptedManifest:
    """Corrupted or missing manifests should block managed uninstall."""

    def test_uninstall_with_corrupted_manifest(self, tmp_path: Path) -> None:
        gpd_root = _make_gpd_root(tmp_path)
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()

        # Install normally
        adapter.install(gpd_root, target, is_global=True)

        # Corrupt the manifest
        (target / MANIFEST_NAME).write_text("{{{invalid json!!!", encoding="utf-8")

        with pytest.raises(RuntimeError, match="manifest cannot be trusted"):
            adapter.uninstall(target)

    def test_uninstall_with_missing_manifest(self, tmp_path: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"

        # Create GPD structure manually (no manifest)
        (target / "commands" / "gpd").mkdir(parents=True)
        (target / "commands" / "gpd" / "help.md").write_text("help\n", encoding="utf-8")
        (target / "get-physics-done").mkdir(parents=True)
        (target / "get-physics-done" / "VERSION").write_text("1.0\n", encoding="utf-8")

        with pytest.raises(RuntimeError, match="contains GPD artifacts but no manifest"):
            adapter.uninstall(target)

    def test_reinstall_after_corrupted_manifest(self, tmp_path: Path) -> None:
        """Re-install over a corrupted manifest should refuse unsafe ownership guesses."""
        gpd_root = _make_gpd_root(tmp_path)
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()

        adapter.install(gpd_root, target, is_global=True)
        (target / MANIFEST_NAME).write_text("NOT JSON", encoding="utf-8")

        with pytest.raises(RuntimeError, match="manifest cannot be trusted"):
            adapter.install(gpd_root, target, is_global=True)


# =========================================================================
# 6. Install with very long path names
# =========================================================================


class TestLongPathNames:
    """Install with very long path names should work or fail gracefully."""

    def test_long_target_dir_name(self, tmp_path: Path) -> None:
        gpd_root = _make_gpd_root(tmp_path)
        adapter = get_adapter("claude-code")

        # Create a path with ~200 char total (within OS limits on most systems)
        long_name = "a" * 100
        target = tmp_path / long_name / ".claude"
        target.mkdir(parents=True)

        result = adapter.install(gpd_root, target, is_global=True)
        assert result["commands"] > 0
        assert (target / "commands" / "gpd").is_dir()

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows has stricter path limits")
    def test_deeply_nested_target(self, tmp_path: Path) -> None:
        """Deeply nested but valid directory still works."""
        gpd_root = _make_gpd_root(tmp_path)
        adapter = get_adapter("claude-code")

        nested = tmp_path
        for i in range(10):
            nested = nested / f"level{i}"
        target = nested / ".claude"
        target.mkdir(parents=True)

        result = adapter.install(gpd_root, target, is_global=True)
        assert result["commands"] > 0


# =========================================================================
# 7. Install when HOME is not set (env var fallback)
# =========================================================================


class TestHomeUnset:
    """When HOME is unset, adapters with env var overrides should still work."""

    def test_claude_config_dir_env_overrides_home(self, tmp_path: Path) -> None:
        """CLAUDE_CONFIG_DIR should be used instead of Path.home()."""
        adapter = get_adapter("claude-code")
        custom_dir = tmp_path / "custom-claude"
        custom_dir.mkdir()

        with patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(custom_dir)}):
            assert adapter.global_config_dir == custom_dir

    def test_codex_config_dir_env_overrides_home(self, tmp_path: Path) -> None:
        adapter = get_adapter("codex")
        custom_dir = tmp_path / "custom-codex"
        custom_dir.mkdir()

        with patch.dict(os.environ, {"CODEX_CONFIG_DIR": str(custom_dir)}):
            assert adapter.global_config_dir == custom_dir

    def test_global_dir_fallback_uses_home(self) -> None:
        """Without env vars, global_config_dir should use Path.home()."""
        adapter = get_adapter("claude-code")
        env_clean = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}

        with patch.dict(os.environ, env_clean, clear=True):
            result = adapter.global_config_dir
            assert result == Path.home() / ".claude"

    def test_install_with_explicit_target_dir_ignores_home(self, tmp_path: Path) -> None:
        """Using --target-dir bypasses HOME entirely."""
        gpd_root = _make_gpd_root(tmp_path)
        adapter = get_adapter("claude-code")
        target = tmp_path / "explicit-target"
        target.mkdir()

        # install() takes target_dir directly — doesn't need HOME
        result = adapter.install(gpd_root, target, is_global=False)
        assert result["commands"] > 0


# =========================================================================
# 8. Multi-runtime install to same target_dir
# =========================================================================


class TestMultiRuntimeSameTarget:
    """Multiple runtimes installing to the same directory."""

    def test_second_install_overwrites_get_physics_done(self, tmp_path: Path) -> None:
        """Reinstalling the same runtime keeps the target structure valid."""
        gpd_root = _make_gpd_root(tmp_path)
        target = tmp_path / "shared"
        target.mkdir()

        adapter1 = get_adapter("claude-code")
        adapter1.install(gpd_root, target, is_global=True)

        # get-physics-done should exist
        version_file = target / "get-physics-done" / "VERSION"
        assert version_file.exists()
        first_content = version_file.read_text(encoding="utf-8")

        # Second install of the same runtime should keep the install valid.
        adapter2 = get_adapter("claude-code")
        adapter2.install(gpd_root, target, is_global=True)

        assert version_file.exists()
        second_content = version_file.read_text(encoding="utf-8")
        # Same version, just confirming it survived
        assert second_content == first_content

    def test_both_runtimes_leave_valid_structure(self, tmp_path: Path) -> None:
        """Both runtimes can create valid installs in separate directories."""
        gpd_root = _make_gpd_root(tmp_path)
        target_cc = tmp_path / "claude"
        target_cc.mkdir()
        target_gem = tmp_path / "gemini"
        target_gem.mkdir()

        adapter_cc = get_adapter("claude-code")
        adapter_cc.install(gpd_root, target_cc, is_global=True)

        _install_gemini_for_tests(gpd_root, target_gem)

        # Both should have written commands
        assert (target_cc / "commands" / "gpd").is_dir()
        assert (target_gem / "commands" / "gpd").is_dir()
        # Manifests should be valid independently
        manifest_cc = json.loads((target_cc / MANIFEST_NAME).read_text(encoding="utf-8"))
        manifest_gem = json.loads((target_gem / MANIFEST_NAME).read_text(encoding="utf-8"))
        assert "version" in manifest_cc
        assert "version" in manifest_gem
        assert len(manifest_cc["files"]) > 0
        assert len(manifest_gem["files"]) > 0


# =========================================================================
# 9. Registry with invalid YAML frontmatter
# =========================================================================


class TestRegistryInvalidYaml:
    """Registry parsing a .md file with invalid YAML frontmatter."""

    def test_invalid_yaml_in_frontmatter_raises(self, tmp_path: Path) -> None:
        """Invalid YAML in frontmatter should fail fast with path context."""
        f = tmp_path / "bad-yaml.md"
        f.write_text(
            "---\nname: [unclosed bracket\n  bad: :\n---\nBody.\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="Invalid frontmatter in .*bad-yaml\\.md"):
            _parse_agent_file(f, source="agents")

    def test_registry_frontmatter_with_invalid_yaml_raises(self) -> None:
        """Malformed registry frontmatter should raise instead of being swallowed."""
        text = "---\n: : : invalid\n---\nBody."
        with pytest.raises(ValueError, match="Malformed YAML frontmatter"):
            _parse_frontmatter(text)

    def test_valid_yaml_non_dict_raises(self) -> None:
        """Non-mapping registry frontmatter should also fail fast."""
        text = "---\n- list\n- items\n---\nBody."
        with pytest.raises(ValueError, match="Frontmatter must parse to a mapping"):
            _parse_frontmatter(text)

    def test_discovery_skips_non_md_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Discovery only processes .md files — other files are safe."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "valid.md").write_text("---\nname: valid\n---\nPrompt.", encoding="utf-8")
        # Non-.md file with invalid YAML — should be ignored
        (agents_dir / "broken.yaml").write_text("---\n: : : invalid\n---\n", encoding="utf-8")

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        registry.invalidate_cache()

        try:
            result = registry._discover_agents()
            assert "valid" in result
            assert len(result) == 1  # broken.yaml not loaded
        finally:
            registry.invalidate_cache()

    def test_agent_with_empty_yaml_block(self, tmp_path: Path) -> None:
        """Agent .md with empty YAML block (--- followed by ---) uses stem as name."""
        f = tmp_path / "empty-yaml.md"
        f.write_text("---\n \n---\nBody text.", encoding="utf-8")
        agent = _parse_agent_file(f, source="agents")
        assert agent.name == "empty-yaml"  # Falls back to stem
        assert agent.system_prompt == "Body text."


# =========================================================================
# 10. expand_at_includes with 3-way circular @includes
# =========================================================================


class TestExpandAtIncludesCircular:
    """Test circular include detection with 3-file cycle: A→B→C→A."""

    def _make_src(self, tmp_path: Path, files: dict[str, str]) -> Path:
        gpd_dir = tmp_path / "get-physics-done"
        gpd_dir.mkdir(parents=True, exist_ok=True)
        for rel, content in files.items():
            p = gpd_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return gpd_dir

    def test_three_way_cycle(self, tmp_path: Path) -> None:
        """A includes B, B includes C, C includes A — should detect cycle."""
        gpd_dir = self._make_src(
            tmp_path,
            {
                "a.md": f"alpha\n@{tmp_path}/get-physics-done/b.md",
                "b.md": f"beta\n@{tmp_path}/get-physics-done/c.md",
                "c.md": f"gamma\n@{tmp_path}/get-physics-done/a.md",
            },
        )
        content = f"@{tmp_path}/get-physics-done/a.md"
        result = expand_at_includes(content, str(gpd_dir), "~/.test/")

        assert "alpha" in result
        assert "beta" in result
        assert "gamma" in result
        assert "cycle detected" in result

    def test_diamond_dependency(self, tmp_path: Path) -> None:
        """Diamond: A→B, A→C, B→D, C→D — D should be included twice (no cycle)."""
        gpd_dir = self._make_src(
            tmp_path,
            {
                "d.md": "diamond-leaf",
                "b.md": f"branch-b\n@{tmp_path}/get-physics-done/d.md",
                "c.md": f"branch-c\n@{tmp_path}/get-physics-done/d.md",
            },
        )
        content = f"@{tmp_path}/get-physics-done/b.md\n@{tmp_path}/get-physics-done/c.md"
        result = expand_at_includes(content, str(gpd_dir), "~/.test/")

        assert "branch-b" in result
        assert "branch-c" in result
        # D should appear (included from both B and C — include_stack is per-expansion)
        # Actually, include_stack tracks already-included files to prevent cycles.
        # After B includes D and returns, D is removed from include_stack (discard).
        # So C can also include D. Both should work.
        assert "diamond-leaf" in result
        assert "cycle detected" not in result

    def test_include_read_error(self, tmp_path: Path) -> None:
        """Include of a file with encoding errors produces an error comment."""
        gpd_dir = self._make_src(tmp_path, {})
        # Write a binary file that's not valid UTF-8
        bad_file = tmp_path / "get-physics-done" / "binary.md"
        bad_file.write_bytes(b"\xff\xfe\x00\x01 invalid utf8")

        content = f"@{tmp_path}/get-physics-done/binary.md"
        result = expand_at_includes(content, str(gpd_dir), "~/.test/")
        assert "include read error" in result

    def test_max_depth_produces_comment(self, tmp_path: Path) -> None:
        """At depth = MAX_INCLUDE_EXPANSION_DEPTH - 1, next level produces comment."""
        gpd_dir = self._make_src(
            tmp_path,
            {
                "deep.md": f"deep-content\n@{tmp_path}/get-physics-done/deeper.md",
                "deeper.md": "should-not-expand",
            },
        )
        content = f"@{tmp_path}/get-physics-done/deep.md"
        # depth=9 means deep.md expands at depth=10, but deeper.md at depth=10
        # hits the "depth == MAX" check inside expand_at_includes
        result = expand_at_includes(content, str(gpd_dir), "~/.test/", depth=9)
        assert "deep-content" in result
        assert "depth limit reached" in result
