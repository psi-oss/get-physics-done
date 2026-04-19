from __future__ import annotations

from pathlib import Path

import pytest

from gpd.adapters.install_utils import project_markdown_for_runtime
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.registry import _frontmatter_parts, _load_frontmatter_mapping
from tests.adapters.review_contract_test_utils import extract_review_contract_section

RUNTIMES = tuple(descriptor.runtime_name for descriptor in iter_runtime_descriptors())
COMMANDS_DIR = Path(__file__).resolve().parents[2] / "src/gpd/commands"


def _read_command(command_name: str) -> str:
    return (COMMANDS_DIR / f"{command_name}.md").read_text(encoding="utf-8")


def _review_command_names() -> tuple[str, ...]:
    names: list[str] = []
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        frontmatter, _body = _frontmatter_parts(path.read_text(encoding="utf-8"))
        assert frontmatter is not None, f"{path.name} is missing command frontmatter"
        meta = _load_frontmatter_mapping(frontmatter, error_prefix=f"Malformed frontmatter for {path.stem}")
        if isinstance(meta.get("review-contract"), dict):
            names.append(path.stem)
    return tuple(names)


REVIEW_COMMANDS = _review_command_names()


def _transform_source_command_content(command_name: str, runtime: str) -> str:
    return project_markdown_for_runtime(
        _read_command(command_name),
        runtime=runtime,
        path_prefix="/runtime/",
        src_root=Path(__file__).resolve().parents[2] / "src/gpd",
        command_name=command_name,
    )


@pytest.mark.parametrize(
    "command_name",
    REVIEW_COMMANDS,
)
@pytest.mark.parametrize("runtime", RUNTIMES)
def test_review_contract_section_matches_registry_across_runtime_wrappers(
    command_name: str,
    runtime: str,
) -> None:
    expected_section = extract_review_contract_section(_transform_source_command_content(command_name, RUNTIMES[0]))
    transformed_content = _transform_source_command_content(command_name, runtime)

    assert extract_review_contract_section(transformed_content) == expected_section
    assert transformed_content.count("## Review Contract") == 1


@pytest.mark.parametrize(
    ("command_name", "expected_fragments"),
    (
        (
            "peer-review",
            (
                "explicit external-artifact review:",
                "manuscript-local publication artifacts",
                "project-backed review missing required manuscript-root publication artifacts",
            ),
        ),
        (
            "arxiv-submission",
            (
                "latest peer-review review ledger",
                "latest peer-review referee decision",
                "missing latest staged peer-review decision evidence",
            ),
        ),
    ),
)
@pytest.mark.parametrize("runtime", RUNTIMES)
def test_review_contract_runtime_surfaces_keep_publication_specific_gate_fragments(
    command_name: str,
    expected_fragments: tuple[str, ...],
    runtime: str,
) -> None:
    transformed_content = _transform_source_command_content(command_name, runtime)

    for fragment in expected_fragments:
        assert fragment in transformed_content
