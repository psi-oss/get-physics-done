"""Guardrails for public release consistency."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_required_public_release_artifacts_exist() -> None:
    repo_root = _repo_root()
    required = (
        "README.md",
        "LICENSE",
        "CITATION.cff",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
    )

    missing = [path for path in required if not (repo_root / path).is_file()]
    assert missing == []


def test_public_docs_acknowledge_psi_and_gsd_inspiration() -> None:
    repo_root = _repo_root()

    for relative_path in ("README.md", "docs/USER-GUIDE.md"):
        content = (repo_root / relative_path).read_text(encoding="utf-8")
        assert "Physical Superintelligence (PSI)" in content
        assert "GSD" in content
        assert "get-shit-done-cc" in content


def test_infra_descriptors_reference_public_bootstrap_flow() -> None:
    repo_root = _repo_root()
    expected = "npx github:physicalsuperintelligence/get-physics-done"
    stale_markers = (
        "packages/gpd",
        "uv pip install -e",
        "pip install -e packages/gpd",
    )

    for path in sorted((repo_root / "infra").glob("gpd-*.json")):
        content = path.read_text(encoding="utf-8")
        assert expected in content, f"{path.name} should reference the public bootstrap flow"
        for marker in stale_markers:
            assert marker not in content, f"{path.name} should not mention {marker!r}"


def test_manual_test_plan_covers_public_readme_install() -> None:
    repo_root = _repo_root()
    content = (repo_root / "MANUAL-TEST-PLAN.md").read_text(encoding="utf-8")

    assert "Phase 0: Public Release Smoke Test" in content
    assert "npx github:physicalsuperintelligence/get-physics-done" in content
    assert "follow only the public README instructions" in content


def test_initial_release_date_matches_launch_plan() -> None:
    repo_root = _repo_root()
    changelog = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "## [0.1.0] - 2026-03-15" in changelog
