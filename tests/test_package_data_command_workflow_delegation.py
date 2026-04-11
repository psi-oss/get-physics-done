"""Regression guard for package-data command <-> workflow delegation."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
_README_TEXT = (TESTS_DIR / "README.md").read_text(encoding="utf-8")
_LOCAL_CLI_BLOCK = "repo-graph-local-cli-only"
_INTERNAL_WORKFLOW_BLOCK = "repo-graph-internal-workflow-only"
_INTERNAL_WORKFLOW_MARKER = "<!-- internal-workflow-only -->"


def _delegated_stem_names() -> tuple[str, ...]:
    readme = (TESTS_DIR / "README.md").read_text(encoding="utf-8")
    pattern = re.compile(
        r"<!-- repo-graph-same-stem-command-workflow:start -->\n"
        r"- `src/gpd/commands/{(?P<names>[^}]*)}\.md -> src/gpd/specs/workflows/{same stems}\.md`\n"
        r"<!-- repo-graph-same-stem-command-workflow:end -->"
    )
    match = pattern.search(readme)
    if match is None:
        raise AssertionError("README lacks repo-graph same-stem command workflow block")

    stems = [stem.strip() for stem in match.group("names").split(",") if stem.strip()]
    if not stems:
        raise AssertionError("README command-workflow delegation list is empty")

    return tuple(stems)


def _parse_readme_block(block_name: str) -> tuple[str, ...]:
    pattern = re.compile(
        rf"<!-- {block_name}:start -->\n(?P<body>.*?)<!-- {block_name}:end -->",
        re.DOTALL,
    )
    match = pattern.search(_README_TEXT)
    if match is None:
        raise AssertionError(f"README lacks {block_name} block")
    stems: list[str] = []
    for line in match.group("body").splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        content = stripped.lstrip("-").strip()
        if content.startswith("`") and content.endswith("`"):
            content = content.strip("`")
        if "->" in content:
            content = content.split("->", 1)[0].strip()
        if content:
            stems.append(content)
    return tuple(stems)


def _local_cli_only_command_stems() -> tuple[str, ...]:
    return _parse_readme_block(_LOCAL_CLI_BLOCK)


def _internal_workflow_only_stems() -> tuple[str, ...]:
    return _parse_readme_block(_INTERNAL_WORKFLOW_BLOCK)


def _load_command_frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    if not text.lstrip().startswith("---"):
        return {}
    lines = text.lstrip().splitlines()
    try:
        end = lines[1:].index("---") + 1
    except ValueError:
        return {}
    block = "\n".join(lines[1:end])
    parsed = yaml.safe_load(block)
    return parsed or {}


def _command_stems_without_workflows() -> tuple[str, ...]:
    documented = set(_delegated_stem_names())
    all_commands = {path.stem for path in COMMANDS_DIR.glob("*.md")}
    extras = sorted(all_commands - documented)
    return tuple(extras)


def test_package_data_reuses_same_stem_command_workflows() -> None:
    """Ensure each documented same-stem command has matching workflow data."""

    for stem in _delegated_stem_names():
        command_path = COMMANDS_DIR / f"{stem}.md"
        workflow_path = WORKFLOWS_DIR / f"{stem}.md"

        assert command_path.is_file(), f"Missing command spec for {stem}"
        assert workflow_path.is_file(), f"Missing workflow spec for {stem}"


def test_command_wrappers_delegate_to_matching_workflow_names() -> None:
    """Keep wrapper metadata and workflow include targets in sync."""

    for stem in _delegated_stem_names():
        command_path = COMMANDS_DIR / f"{stem}.md"
        command_text = command_path.read_text(encoding="utf-8")
        frontmatter = _load_command_frontmatter(command_path)

        assert frontmatter.get("name") == f"gpd:{stem}"
        assert frontmatter.get("description"), f"Missing description for {stem}"
        assert frontmatter.get("local_cli_only") is not True

        workflow_include = f"@{{GPD_INSTALL_DIR}}/workflows/{stem}.md"
        assert workflow_include in command_text, f"{stem} wrapper must include {workflow_include}"


def test_local_cli_only_commands_marked_and_exempt() -> None:
    local_cli_only = set(_local_cli_only_command_stems())
    assert local_cli_only == {"health", "suggest-next"}
    assert set(_command_stems_without_workflows()) == local_cli_only

    for stem in local_cli_only:
        command_path = COMMANDS_DIR / f"{stem}.md"
        assert command_path.is_file(), f"Missing local CLI command spec for {stem}"
        frontmatter = _load_command_frontmatter(command_path)
        assert frontmatter.get("local_cli_only") is True


def test_internal_workflows_marked_and_documented() -> None:
    documented_internal = set(_internal_workflow_only_stems())
    assert documented_internal == {"execute-plan", "transition", "verify-phase"}
    all_workflows = {path.stem for path in WORKFLOWS_DIR.glob("*.md")}
    documented_delegated = set(_delegated_stem_names())
    orphaned_workflows = all_workflows - documented_delegated

    assert documented_internal == orphaned_workflows

    for stem in documented_internal:
        workflow_path = WORKFLOWS_DIR / f"{stem}.md"
        assert workflow_path.is_file(), f"Missing internal workflow spec for {stem}"
        content = workflow_path.read_text(encoding="utf-8")
        assert _INTERNAL_WORKFLOW_MARKER in content
