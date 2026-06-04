"""Privacy and non-integration contracts for the Research Persona foundation."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import pytest

from gpd.core.profile import profile_path
from gpd.core.state import default_state_dict

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"

_RUNTIME_SURFACE_FILES = (
    REPO_ROOT / "pyproject.toml",
    REPO_ROOT / "src" / "gpd" / "registry.py",
    REPO_ROOT / "src" / "gpd" / "core" / "commands.py",
    REPO_ROOT / "src" / "gpd" / "core" / "registry_frontmatter.py",
    REPO_ROOT / "src" / "gpd" / "core" / "registry_types.py",
    REPO_ROOT / "src" / "gpd" / "core" / "public_surface_contract.json",
    REPO_ROOT / "src" / "gpd" / "core" / "public_surface_contract_schema.json",
)
_APPROVED_RESEARCH_PERSONA_RUNTIME_PATHS = {
    COMMANDS_DIR / "build-persona.md",
    COMMANDS_DIR / "help.md",
    AGENTS_DIR / "gpd-persona-builder.md",
    AGENTS_DIR / "gpd-researcher-doppelganger.md",
    AGENTS_DIR / "gpd-expertise-explainer.md",
    AGENTS_DIR / "gpd-scientific-taste.md",
    WORKFLOWS_DIR / "build-persona.md",
    WORKFLOWS_DIR / "build-persona-stage-manifest.json",
    WORKFLOWS_DIR / "build-persona" / "persona-intake.md",
    WORKFLOWS_DIR / "build-persona" / "source-ingestion.md",
    WORKFLOWS_DIR / "build-persona" / "persona-synthesis.md",
    WORKFLOWS_DIR / "build-persona" / "approval-and-apply.md",
    WORKFLOWS_DIR / "help.md",
    REPO_ROOT / "src" / "gpd" / "specs" / "references" / "research" / "research-persona-applications.md",
}

_PROJECT_GPD_FORBIDDEN_LOAD_PATHS = (
    "research-persona",
    "research_persona",
    "profile.json",
    "history/events.jsonl",
    "tombstones/events.jsonl",
)


def _research_persona_module() -> ModuleType:
    try:
        return importlib.import_module("gpd.core.research_persona")
    except ModuleNotFoundError as exc:
        if exc.name == "gpd.core.research_persona":
            pytest.fail("Phase 1 must provide gpd.core.research_persona before these contracts can run")
        raise


def _is_research_persona_term(text: str) -> bool:
    lowered = text.lower()
    dashed = lowered.replace("_", "-")
    compact = lowered.replace("_", "").replace("-", "").replace(" ", "")
    return "research-persona" in dashed or "research persona" in lowered or "researchpersona" in compact


def _runtime_integration_files() -> list[Path]:
    paths: list[Path] = []
    for root in (COMMANDS_DIR, AGENTS_DIR, WORKFLOWS_DIR):
        paths.extend(path for path in root.rglob("*") if path.is_file() and path.suffix in {".md", ".json"})
    paths.extend(path for path in _RUNTIME_SURFACE_FILES if path.exists())
    return sorted(set(paths))


def _tree_snapshot(root: Path) -> dict[str, tuple[int, str]]:
    if not root.exists():
        return {}
    snapshot: dict[str, tuple[int, str]] = {}
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        relative = path.relative_to(root).as_posix()
        stat = path.stat()
        snapshot[relative] = (stat.st_size, path.read_text(encoding="utf-8"))
    return snapshot


def _iter_text_atoms(value: object, *, path: str = "$") -> list[tuple[str, str]]:
    atoms: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            key_path = f"{path}.{key_text}"
            atoms.append((key_path, key_text))
            atoms.extend(_iter_text_atoms(child, path=key_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            atoms.extend(_iter_text_atoms(child, path=f"{path}[{index}]"))
    elif isinstance(value, str):
        atoms.append((path, value))
    return atoms


def test_research_persona_runtime_mentions_are_limited_to_approved_local_surfaces() -> None:
    hits: list[str] = []
    for path in _runtime_integration_files():
        if path in _APPROVED_RESEARCH_PERSONA_RUNTIME_PATHS:
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _is_research_persona_term(line):
                relative = path.relative_to(REPO_ROOT).as_posix()
                hits.append(f"{relative}:{line_number}: {line.strip()}")

    assert not hits, (
        "Research Persona runtime mentions must stay inside the approved local persona builder, "
        "capsule application, and help surfaces:\n" + "\n".join(hits)
    )


def test_default_project_state_has_no_research_persona_payload() -> None:
    state = default_state_dict()

    hits = [f"{path}: {text!r}" for path, text in _iter_text_atoms(state) if _is_research_persona_term(text)]

    assert not hits, "Research Persona data must stay out of the default project state dict:\n" + "\n".join(hits)


def test_research_persona_storage_is_namespaced_away_from_author_profile(tmp_path: Path) -> None:
    research_persona = _research_persona_module()

    root = research_persona.research_persona_root(tmp_path)
    path = research_persona.research_persona_path(tmp_path)

    assert root == tmp_path / "research-persona"
    assert path == tmp_path / "research-persona" / "profile.json"
    assert path != profile_path(tmp_path)
    assert profile_path(tmp_path) == tmp_path / "profile.json"


def test_missing_research_persona_load_is_read_only_and_never_writes_project_gpd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    research_persona = _research_persona_module()
    project_root = tmp_path / "project"
    gpd_dir = project_root / "GPD"
    data_root = tmp_path / "machine-data"
    gpd_dir.mkdir(parents=True)
    (gpd_dir / "state.json").write_text('{"existing": true}\n', encoding="utf-8")
    (gpd_dir / "STATE.md").write_text("# Existing State\n", encoding="utf-8")
    (gpd_dir / "config.json").write_text("{}\n", encoding="utf-8")
    before = _tree_snapshot(gpd_dir)

    monkeypatch.chdir(project_root)
    monkeypatch.setenv("GPD_DATA_DIR", str(data_root))

    persona = research_persona.load_research_persona()

    assert persona.schema_version == 1
    assert _tree_snapshot(gpd_dir) == before
    assert not (data_root / "research-persona").exists()
    for relative_path in _PROJECT_GPD_FORBIDDEN_LOAD_PATHS:
        assert not (gpd_dir / relative_path).exists(), relative_path
