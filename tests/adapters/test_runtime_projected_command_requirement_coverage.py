"""Fast coverage for runtime-projected command requirement wrappers."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd.adapters.install_utils import project_markdown_for_runtime
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.core.model_visible_text import command_visibility_note
from gpd.registry import _frontmatter_parts, _load_frontmatter_mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
RUNTIMES = tuple(descriptor.runtime_name for descriptor in iter_runtime_descriptors())


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _command_names() -> tuple[str, ...]:
    return tuple(path.stem for path in sorted(COMMANDS_DIR.glob("*.md")))


def _command_frontmatter(command_name: str) -> dict[str, object]:
    frontmatter, _body = _frontmatter_parts(_read(COMMANDS_DIR / f"{command_name}.md"))
    assert frontmatter is not None, f"{command_name} is missing command frontmatter"
    return _load_frontmatter_mapping(frontmatter, error_prefix=f"Malformed frontmatter for {command_name}")


def _command_requirements(command_name: str) -> dict[str, object]:
    meta = _command_frontmatter(command_name)
    requirements = meta.get("requires")
    return dict(requirements) if isinstance(requirements, dict) else {}


COMMANDS_WITH_REQUIREMENTS = tuple(command_name for command_name in _command_names() if _command_requirements(command_name))
REVIEW_COMMANDS = {
    command_name for command_name in _command_names() if isinstance(_command_frontmatter(command_name).get("review-contract"), dict)
}


def _project_command(command_name: str, runtime: str) -> str:
    projected = project_markdown_for_runtime(
        _read(COMMANDS_DIR / f"{command_name}.md"),
        runtime=runtime,
        path_prefix="/runtime/",
        src_root=REPO_ROOT / "src/gpd",
        protect_agent_prompt_body=False,
        command_name=command_name,
    )

    assert isinstance(projected, str)
    return projected


def _runtime_command_visibility_note(runtime: str) -> str:
    note = command_visibility_note()
    if runtime == "codex":
        return note.replace("`gpd:suggest-next`", "`$gpd-suggest-next`")
    return note


@pytest.mark.parametrize("runtime", RUNTIMES)
@pytest.mark.parametrize("command_name", COMMANDS_WITH_REQUIREMENTS)
def test_runtime_projected_commands_keep_requirements_visible(command_name: str, runtime: str) -> None:
    command_requires = _command_requirements(command_name)
    projected = _project_command(command_name, runtime)

    assert _runtime_command_visibility_note(runtime) in projected
    assert projected.count("## Command Requirements") == 1

    for require_key, require_value in command_requires.items():
        assert str(require_key) in projected
        if isinstance(require_value, list):
            for item in require_value:
                assert str(item) in projected
        else:
            assert str(require_value) in projected


@pytest.mark.parametrize("runtime", RUNTIMES)
@pytest.mark.parametrize("command_name", tuple(name for name in COMMANDS_WITH_REQUIREMENTS if name in REVIEW_COMMANDS))
def test_runtime_projected_review_commands_keep_requirements_before_review_contract(
    command_name: str,
    runtime: str,
) -> None:
    projected = _project_command(command_name, runtime)

    assert "## Command Requirements" in projected
    assert "## Review Contract" in projected
    assert projected.index("## Command Requirements") < projected.index("## Review Contract")


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_runtime_projected_peer_review_keeps_canonical_manuscript_roots_and_explicit_artifact_boundary_visible(
    runtime: str,
) -> None:
    projected = _project_command("peer-review", runtime)

    for fragment in (
        "paper/*.tex",
        "paper/*.md",
        "manuscript/*.tex",
        "manuscript/*.md",
        "draft/*.tex",
        "draft/*.md",
        "The default in-project manuscript family is limited to `paper/`, `manuscript/`, and `draft/`.",
        "Explicit external artifact intake may also target `.tex`, `.md`, `.txt`, or `.pdf`.",
    ):
        assert fragment in projected
