"""Install lifecycle tests for the supported runtime adapters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.adapters import get_adapter
from gpd.adapters.install_utils import MANIFEST_NAME, build_runtime_cli_bridge_command
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.hooks.install_metadata import assess_install_target


def _install_and_finalize(adapter, gpd_root: Path, target: Path, **install_kwargs: object) -> dict[str, object]:
    result = adapter.install(gpd_root, target, **install_kwargs)
    adapter.finalize_install(result)
    return result


def _assert_manifest_present(target: Path) -> dict[str, object]:
    manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["version"]
    assert manifest["files"]
    return manifest


@pytest.fixture()
def gpd_root() -> Path:
    """Return the GPD package data root."""
    root = Path(__file__).resolve().parent.parent / "src" / "gpd"
    assert (root / "commands").is_dir()
    assert (root / "agents").is_dir()
    assert (root / "specs").is_dir()
    assert (root / "hooks").is_dir()
    return root


_INSTALL_LIFECYCLE_DESCRIPTORS = iter_runtime_descriptors()
_MARKDOWN_COMMAND_RUNTIME = next(
    descriptor for descriptor in _INSTALL_LIFECYCLE_DESCRIPTORS if descriptor.native_include_support
)
_EXTERNAL_SKILLS_RUNTIME = next(
    descriptor for descriptor in _INSTALL_LIFECYCLE_DESCRIPTORS if "skills/" in descriptor.manifest_file_prefixes
)


def test_markdown_command_runtime_lifecycle_round_trip(tmp_path: Path, gpd_root: Path) -> None:
    adapter = get_adapter(_MARKDOWN_COMMAND_RUNTIME.runtime_name)
    target = tmp_path / _MARKDOWN_COMMAND_RUNTIME.config_dir_name
    target.mkdir()

    _install_and_finalize(adapter, gpd_root, target, is_global=True)

    commands_dir = target / "commands" / "gpd"
    assert commands_dir.is_dir()
    assert (commands_dir / "start.md").exists()
    assert (commands_dir / "tour.md").exists()

    slides_md = commands_dir / "slides.md"
    slides_content = slides_md.read_text(encoding="utf-8")
    assert "context_mode: projectless" in slides_content
    assert "/get-physics-done/workflows/slides.md" in slides_content

    bridge_command = build_runtime_cli_bridge_command(
        adapter.runtime_name,
        target_dir=target,
        config_dir_name=adapter.config_dir_name,
        is_global=True,
        explicit_target=False,
    )
    suggest_next = (commands_dir / "suggest-next.md").read_text(encoding="utf-8")
    assert bridge_command in suggest_next
    assert "Uses `gpd --raw suggest`" in suggest_next

    manifest = _assert_manifest_present(target)
    assert manifest["runtime"] == adapter.runtime_name
    assert (target / "hooks" / "statusline.py").exists()
    assert (target / "get-physics-done" / "VERSION").exists()

    uninstall_result = adapter.uninstall(target)
    assert uninstall_result["removed"]
    assert not (target / "commands" / "gpd").exists()
    assert not (target / "get-physics-done").exists()
    assert not (target / MANIFEST_NAME).exists()


def test_external_skills_runtime_lifecycle_round_trip(tmp_path: Path, gpd_root: Path) -> None:
    adapter = get_adapter(_EXTERNAL_SKILLS_RUNTIME.runtime_name)
    target = tmp_path / _EXTERNAL_SKILLS_RUNTIME.config_dir_name
    target.mkdir()
    skills_dir = tmp_path / ".agents" / "skills"
    skills_dir.mkdir(parents=True)

    _install_and_finalize(adapter, gpd_root, target, is_global=True, skills_dir=skills_dir)

    gpd_skills = [d for d in skills_dir.iterdir() if d.is_dir() and d.name.startswith("gpd-")]
    assert gpd_skills
    assert (skills_dir / "gpd-help" / "SKILL.md").exists()
    assert (skills_dir / "gpd-start" / "SKILL.md").exists()
    assert (skills_dir / "gpd-tour" / "SKILL.md").exists()
    assert (skills_dir / "gpd-slides" / "SKILL.md").exists()

    help_skill = (skills_dir / "gpd-help" / "SKILL.md").read_text(encoding="utf-8")
    assert "context_mode:" in help_skill
    assert not (skills_dir / "gpd-planner").exists()

    assert (target / "agents" / "gpd-planner.toml").exists()
    config_toml = (target / "config.toml").read_text(encoding="utf-8")
    assert "notify" in config_toml
    assert "multi_agent = true" in config_toml
    manifest = _assert_manifest_present(target)
    assert manifest["codex_generated_skill_dirs"]
    assert all(name.startswith("gpd-") for name in manifest["codex_generated_skill_dirs"])

    suggest_next = (skills_dir / "gpd-suggest-next" / "SKILL.md").read_text(encoding="utf-8")
    bridge_command = build_runtime_cli_bridge_command(
        adapter.runtime_name,
        target_dir=target,
        config_dir_name=adapter.config_dir_name,
        is_global=True,
        explicit_target=False,
    )
    assert bridge_command in suggest_next

    preserved_skill = skills_dir / "gpd-user-keep"
    preserved_skill.mkdir()
    (preserved_skill / "SKILL.md").write_text("keep", encoding="utf-8")

    uninstall_result = adapter.uninstall(target, skills_dir=skills_dir)
    assert uninstall_result["skills"] > 0
    assert (preserved_skill / "SKILL.md").exists()
    assert not any((skills_dir / name).exists() for name in manifest["codex_generated_skill_dirs"])
    assert not (target / "get-physics-done").exists()
    assert not (target / MANIFEST_NAME).exists()


def test_install_readiness_treats_same_runtime_incomplete_install_as_repairable(tmp_path: Path) -> None:
    descriptor = _INSTALL_LIFECYCLE_DESCRIPTORS[0]
    other_descriptor = _INSTALL_LIFECYCLE_DESCRIPTORS[1]
    target = tmp_path / descriptor.config_dir_name
    target.mkdir()
    (target / MANIFEST_NAME).write_text(
        json.dumps({"runtime": descriptor.runtime_name, "install_scope": "local"}),
        encoding="utf-8",
    )

    assessment = assess_install_target(target, expected_runtime=descriptor.runtime_name)
    foreign = assess_install_target(target, expected_runtime=other_descriptor.runtime_name)

    assert assessment.state == "owned_incomplete"
    assert assessment.readiness_state == "blocked"
    assert foreign.state == "foreign_runtime"
    assert foreign.readiness_state == "blocked"


@pytest.mark.parametrize(
    "manifest_update",
    [
        {"files": {"/tmp/escape": "hash"}},
        {"files": {"../escape": "hash"}},
        {"files": {"hooks//statusline.py": "hash"}},
        {"files": {"hooks\\..\\escape.py": "hash"}},
        {"codex_generated_skill_dirs": ["../escape"]},
        {"codex_generated_skill_dirs": ["user-skill"]},
        {"opencode_generated_command_files": ["gpd-../../escape.md"]},
        {"managed_runtime_files": ["policies/../escape.toml"]},
    ],
)
def test_install_readiness_treats_unsafe_manifest_path_metadata_as_untrusted(
    tmp_path: Path,
    manifest_update: dict[str, object],
) -> None:
    descriptor = _INSTALL_LIFECYCLE_DESCRIPTORS[0]
    target = tmp_path / descriptor.config_dir_name
    target.mkdir()
    manifest = {
        "runtime": descriptor.runtime_name,
        "install_scope": "local",
        **manifest_update,
    }
    (target / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")

    assessment = assess_install_target(target, expected_runtime=descriptor.runtime_name)

    assert assessment.state == "untrusted_manifest"
    assert assessment.readiness_state == "blocked"
    assert assessment.manifest_state in {"malformed_files", "malformed_path_metadata"}


def test_install_preflight_allows_same_runtime_incomplete_repair(monkeypatch: pytest.MonkeyPatch) -> None:
    from gpd.cli import _run_install_readiness_preflight
    from gpd.core.health import CheckStatus, DoctorReport, HealthCheck, HealthSummary

    descriptor = _INSTALL_LIFECYCLE_DESCRIPTORS[0]
    issue = "Incomplete GPD install for this runtime; repair it with gpd install."
    report = DoctorReport(
        overall=CheckStatus.FAIL,
        summary=HealthSummary(ok=0, warn=0, fail=1, total=1),
        checks=[
            HealthCheck(
                status=CheckStatus.FAIL,
                label="Runtime Config Target",
                details={
                    "install_state": "owned_incomplete",
                    "target_assessment": {
                        "manifest_runtime": descriptor.runtime_name,
                        "expected_runtime": descriptor.runtime_name,
                    },
                },
                issues=[issue],
            )
        ],
    )

    monkeypatch.setattr("gpd.core.health.run_doctor", lambda **_kwargs: report)

    failures, advisories = _run_install_readiness_preflight(
        [descriptor.runtime_name],
        install_scope="local",
        target_dir=None,
    )

    assert failures == []
    assert advisories == {descriptor.runtime_name: [issue]}


def test_install_readiness_still_blocks_non_directory_target(tmp_path: Path) -> None:
    from gpd.core.health import CheckStatus, _doctor_check_runtime_target

    descriptor = _INSTALL_LIFECYCLE_DESCRIPTORS[0]
    target = tmp_path / descriptor.config_dir_name
    target.write_text("not a directory\n", encoding="utf-8")

    check = _doctor_check_runtime_target(target, runtime=descriptor.runtime_name)

    assert check.status == CheckStatus.FAIL
    assert any("exists but is not a directory" in issue for issue in check.issues)
