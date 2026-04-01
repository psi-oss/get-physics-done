from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from gpd.adapters import get_adapter, iter_runtime_descriptors
from gpd.core import public_surface_contract as public_surface_contract_module
from gpd.core.onboarding_surfaces import (
    beginner_onboarding_hub_url,
    beginner_runtime_surface,
    beginner_runtime_surfaces,
    beginner_startup_ladder_text,
)
from gpd.core.public_surface_contract import (
    beginner_onboarding_caveats,
    beginner_preflight_requirements,
    load_public_surface_contract,
    resume_authority_contract,
)


def test_beginner_onboarding_surface_contract_exposes_hub_and_ladder() -> None:
    assert beginner_onboarding_hub_url().endswith("/docs/README.md")
    assert beginner_startup_ladder_text() == "`help -> start -> tour -> new-project / map-research -> resume-work`"
    assert beginner_preflight_requirements() == (
        "One supported runtime is already installed and can open from your normal terminal.",
        "Node.js 20+ is available in that same terminal.",
        "Python 3.11+ with the standard `venv` module is available there too.",
    )
    assert beginner_onboarding_caveats() == (
        "GPD is not a standalone app.",
        "GPD does not install your runtime for you.",
        "GPD does not include model access, billing, or API credits.",
        "This hub is the beginner path, not the full reference.",
    )


def test_beginner_startup_ladder_stays_separate_from_deeper_recovery_follow_ups() -> None:
    startup_ladder = beginner_startup_ladder_text()

    assert startup_ladder.endswith("resume-work`")
    assert "suggest-next" not in startup_ladder
    assert "pause-work" not in startup_ladder
    assert "Node" not in startup_ladder
    assert "Python" not in startup_ladder
    assert "--local" not in startup_ladder
    assert "standalone" not in startup_ladder
    assert "billing" not in startup_ladder


def test_beginner_runtime_surfaces_follow_runtime_catalog() -> None:
    surfaces = beginner_runtime_surfaces()
    descriptors = iter_runtime_descriptors()

    assert tuple(surface.runtime_name for surface in surfaces) == tuple(
        descriptor.runtime_name for descriptor in descriptors
    )

    for surface in surfaces:
        adapter = get_adapter(surface.runtime_name)
        assert surface.display_name == adapter.display_name
        assert surface.launch_command == adapter.launch_command
        assert surface.help_command == adapter.help_command
        assert surface.start_command == adapter.format_command("start")
        assert surface.tour_command == adapter.format_command("tour")
        assert surface.new_project_command == adapter.new_project_command
        assert surface.new_project_minimal_command == f"{adapter.new_project_command} --minimal"
        assert surface.map_research_command == adapter.map_research_command
        assert surface.resume_work_command == adapter.format_command("resume-work")
        assert surface.settings_command == adapter.format_command("settings")


def test_beginner_runtime_surface_single_lookup_matches_bulk_surface() -> None:
    for surface in beginner_runtime_surfaces():
        assert beginner_runtime_surface(surface.runtime_name) == surface


def test_resume_authority_contract_exposes_full_validated_surface() -> None:
    contract = resume_authority_contract()

    assert contract.compat_surface == "compat_resume_surface"
    assert contract.session_mirror == "legacy session mirror nested under compat_resume_surface"


def test_public_surface_contract_loader_rejects_shape_drift(monkeypatch, tmp_path: Path) -> None:
    canonical_path = Path(__file__).resolve().parents[2] / "src" / "gpd" / "core" / "public_surface_contract.json"
    canonical_payload = json.loads(canonical_path.read_text(encoding="utf-8"))

    class _FakeFiles:
        def __init__(self, contract_path: Path) -> None:
            self._contract_path = contract_path

        def joinpath(self, name: str) -> Path:
            assert name == "public_surface_contract.json"
            return self._contract_path

    def _load_with_payload(payload: dict[str, object]) -> None:
        contract_path = tmp_path / "public_surface_contract.json"
        contract_path.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(public_surface_contract_module, "files", lambda package: _FakeFiles(contract_path))
        load_public_surface_contract.cache_clear()

    drifted_payload = copy.deepcopy(canonical_payload)
    drifted_payload["resume_authority"]["session_mirror"] = ""
    _load_with_payload(drifted_payload)
    with pytest.raises(ValueError, match=r"resume_authority\.session_mirror must be a non-empty string"):
        load_public_surface_contract()

    unknown_key_payload = copy.deepcopy(canonical_payload)
    unknown_key_payload["resume_authority"]["legacy_note"] = "unexpected"
    _load_with_payload(unknown_key_payload)
    with pytest.raises(ValueError, match=r"resume_authority must contain exactly"):
        load_public_surface_contract()

    load_public_surface_contract.cache_clear()


def test_public_surface_contract_loader_rejects_boolean_schema_version(monkeypatch, tmp_path: Path) -> None:
    canonical_path = Path(__file__).resolve().parents[2] / "src" / "gpd" / "core" / "public_surface_contract.json"
    canonical_payload = json.loads(canonical_path.read_text(encoding="utf-8"))

    class _FakeFiles:
        def __init__(self, contract_path: Path) -> None:
            self._contract_path = contract_path

        def joinpath(self, name: str) -> Path:
            assert name == "public_surface_contract.json"
            return self._contract_path

    contract_path = tmp_path / "public_surface_contract.json"
    canonical_payload["schema_version"] = True
    contract_path.write_text(json.dumps(canonical_payload), encoding="utf-8")
    monkeypatch.setattr(public_surface_contract_module, "files", lambda package: _FakeFiles(contract_path))
    load_public_surface_contract.cache_clear()

    with pytest.raises(ValueError, match=r"Unsupported public surface contract schema_version: True"):
        load_public_surface_contract()

    load_public_surface_contract.cache_clear()
