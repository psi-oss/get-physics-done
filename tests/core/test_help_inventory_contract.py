"""Contract test for help inventory coverage."""

from __future__ import annotations

import re

from gpd import registry as content_registry


def _repo_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (_repo_root() / relative_path).read_text(encoding="utf-8")


def _section(content: str, start_marker: str, end_marker: str) -> str:
    start = content.index(start_marker) + len(start_marker)
    end = content.index(end_marker, start)
    return content[start:end]


def _help_command_inventory(*contents: str) -> set[str]:
    surfaces: set[str] = set()
    pattern = re.compile(r"(?m)(?<![A-Za-z0-9-])(?:gpd:|/gpd:|gpd\s+)([a-z0-9-]+)\b")
    for content in contents:
        surfaces.update(pattern.findall(content))
    return surfaces


def test_help_inventory_covers_registry_command_inventory() -> None:
    content_registry.invalidate_cache()

    registry_commands = set(content_registry.list_commands())
    help_inventory = _help_command_inventory(
        _read("src/gpd/commands/help.md"),
        _read("src/gpd/specs/workflows/help.md"),
    )

    missing = sorted(registry_commands - help_inventory)
    assert missing == []


def test_help_inventory_uses_runtime_neutral_framing_in_shared_source() -> None:
    help_sources = [
        _read("src/gpd/commands/help.md"),
        _read("src/gpd/specs/workflows/help.md"),
    ]

    assert all("canonical in-runtime slash-command names in `/gpd:*` form" not in content for content in help_sources)
    assert all("/gpd:*" not in content for content in help_sources)
    assert any("canonical in-runtime command names" in content for content in help_sources)
    assert all("slash-command" not in content for content in help_sources)


def test_help_workflow_paper_toolchain_doctor_row_is_single_sourced() -> None:
    help_workflow = _read("src/gpd/specs/workflows/help.md")

    assert len(re.findall(r"(?m)^\s*gpd doctor --runtime <runtime> --local\|--global\b.*$", help_workflow)) == 1
    assert len(re.findall(r"(?m)^\s*gpd doctor --runtime <runtime> --global\b.*$", help_workflow)) == 0


def test_help_command_uses_one_shared_extract_warning() -> None:
    help_command = _read("src/gpd/commands/help.md")

    assert help_command.count("Shared wrapper rule for every extract below") == 1
    assert help_command.count("output only the requested section and do not rewrite, summarize, or invent alternate wording") == 1


def test_help_command_keeps_one_shared_workflow_authority_note() -> None:
    help_command = _read("src/gpd/commands/help.md")

    assert help_command.count("the loaded workflow help file is the authority") == 1
    assert "Use the loaded workflow help file as the authority." not in help_command


def test_help_workflow_keeps_concise_local_cli_surface_note() -> None:
    help_workflow = _read("src/gpd/specs/workflows/help.md")

    assert "Use `gpd --help` to inspect the executable local install/readiness/permissions/diagnostics surface directly." in help_workflow
    assert "The bootstrap installer owns Node.js / Python / `venv` prerequisites; use `gpd --help`" not in help_workflow


def test_help_workflow_files_and_structure_and_knowledge_lifecycle_coverages() -> None:
    help_workflow = _read("src/gpd/specs/workflows/help.md")
    files_section = _section(help_workflow, "## Files & Structure", "## Workflow Modes")

    assert "literature/" in files_section
    assert "knowledge/" in files_section
    assert "reviews/" in files_section
    assert "research/" not in files_section

    assert "The literature survey lives under `GPD/literature/`, and reviewed knowledge docs live under `GPD/knowledge/` with review artifacts in `GPD/knowledge/reviews/`." in help_workflow
    assert "Drafts stay `draft` until reviewed, and they move into `in_review` while a review round is open" in help_workflow
    assert "If the target is `stable` or `superseded`, route the user to `gpd:review-knowledge`" in help_workflow
    assert "Stable knowledge is already visible through the shared runtime reference surfaces, but it remains reviewed background synthesis rather than a separate authority tier" in help_workflow
    assert "Migration/backfill for older or provisional docs remains deferred; use canonical `GPD/knowledge/{knowledge_id}.md` targets for now." in help_workflow
    assert "stable` docs can later become `superseded`; superseded docs remain addressable and traceable rather than disappearing" in help_workflow
    assert "Example topic: `gpd:digest-knowledge \"renormalization group fixed points\"`" in help_workflow
    assert "Example modern arXiv: `gpd:digest-knowledge 2401.12345v2`" in help_workflow
    assert "Example legacy arXiv: `gpd:digest-knowledge hep-th/9901001`" in help_workflow
    assert "Example source file: `gpd:digest-knowledge ./notes/rg-notes.md`" in help_workflow
    assert "Example explicit knowledge path: `gpd:digest-knowledge GPD/knowledge/K-renormalization-group-fixed-points.md`" in help_workflow
    assert "Stable knowledge is already visible through the shared runtime reference surfaces" in help_workflow
    assert "Stable knowledge is available through the shared runtime reference surfaces" in help_workflow
