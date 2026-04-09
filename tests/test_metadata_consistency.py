"""Consistency checks for public repo metadata and inventory counts."""

from __future__ import annotations

import ast
import importlib
import json
import re
import sys
import tomllib
from pathlib import Path

import pytest

from gpd import registry as content_registry
from gpd.contracts import ConventionLock
from gpd.core.config import MODEL_PROFILES
from gpd.core.health import _ALL_CHECKS
from gpd.core.patterns import PatternDomain
from gpd.registry import VALID_CONTEXT_MODES


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read(relative_path: str) -> str:
    return (_repo_root() / relative_path).read_text(encoding="utf-8")


def _decorated_mcp_tools(relative_path: str) -> list[str]:
    """Return top-level ``@mcp.tool()`` function names from a server module."""
    tree = ast.parse(_read(relative_path), filename=relative_path)
    tool_names: list[str] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "tool"
                and isinstance(func.value, ast.Name)
                and func.value.id == "mcp"
            ):
                tool_names.append(node.name)
                break
    return tool_names


def test_decorated_mcp_tools_includes_async_function_defs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module_path = tmp_path / "async_mcp_module.py"
    module_path.write_text(
        "\n".join(
            [
                "mcp = object()",
                "",
                "@mcp.tool()",
                "async def async_tool():",
                "    return None",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys.modules[__name__],
        "_read",
        lambda relative_path: module_path.read_text(encoding="utf-8"),
    )

    assert _decorated_mcp_tools("async_mcp_module.py") == ["async_tool"]


def _descriptor_python_module(descriptor: dict[str, object]) -> str | None:
    args = descriptor.get("args")
    if isinstance(args, list) and len(args) == 2 and args[0] == "-m":
        return str(args[1])

    alternatives = descriptor.get("alternatives")
    if not isinstance(alternatives, dict):
        return None
    python_module = alternatives.get("python_module")
    if not isinstance(python_module, dict):
        return None
    alt_args = python_module.get("args")
    if isinstance(alt_args, list) and len(alt_args) == 2 and alt_args[0] == "-m":
        return str(alt_args[1])
    return None


def _module_advertised_mcp_tools(module_name: str) -> list[str]:
    module = importlib.import_module(module_name)
    advertised = getattr(module, "ADVERTISED_TOOL_NAMES", None)
    if isinstance(advertised, tuple):
        return list(advertised)
    if isinstance(advertised, list):
        return advertised
    module_path = Path("src") / Path(*module_name.split(".")).with_suffix(".py")
    return _decorated_mcp_tools(module_path.as_posix())


def _project_script_lines(repo_root: Path) -> list[str]:
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8").splitlines()
    collecting = False
    script_lines: list[str] = []
    for line in pyproject:
        stripped = line.strip()
        if stripped == "[project.scripts]":
            collecting = True
            continue
        if collecting and stripped.startswith("["):
            break
        if collecting and stripped:
            script_lines.append(stripped)
    return script_lines


def _project_script_targets(repo_root: Path) -> dict[str, str]:
    script_targets: dict[str, str] = {}
    for line in _project_script_lines(repo_root):
        name, target = line.split("=", 1)
        script_targets[name.strip().strip('"')] = target.strip().strip('"')
    return script_targets


def test_readme_ci_badge_points_to_existing_workflow() -> None:
    repo_root = _repo_root()
    workflow = repo_root / ".github" / "workflows" / "test.yml"
    readme = _read("README.md")

    assert workflow.is_file()
    assert "actions/workflows/test.yml" in readme


def test_python_floor_is_consistent_across_install_surfaces() -> None:
    project = tomllib.loads(_read("pyproject.toml"))["project"]
    assert project["requires-python"] == ">=3.11"

    readme = _read("README.md")
    installer = _read("bin/install.js")

    assert "Python 3.11+" in readme
    assert "MIN_SUPPORTED_PYTHON_MINOR = 11" in installer
    assert "PREFERRED_VERSIONED_PYTHON_MINORS = [13, 12, 11]" in installer
    assert "preferredPythonCommands" in installer
    assert "Python 3.11+ is required" in installer


def test_canonical_registry_skill_inventory_counts_match_repo_contents() -> None:
    repo_root = _repo_root()
    commands_count = len(list((repo_root / "src" / "gpd" / "commands").glob("*.md")))
    agents_count = len(list((repo_root / "src" / "gpd" / "agents").glob("*.md")))
    content_registry.invalidate_cache()
    canonical_skills_count = len(content_registry.list_skills())
    mcp_server_count = len([p for p in (repo_root / "src" / "gpd" / "mcp" / "servers").glob("*.py") if p.name != "__init__.py"])
    mcp_script_count = sum(1 for line in _project_script_lines(repo_root) if line.startswith('"gpd-mcp-'))
    managed_integration_script_count = sum(
        1 for name in _project_script_targets(repo_root) if name == "gpd-mcp-wolfram"
    )

    assert commands_count > 0
    assert agents_count > 0
    # The canonical registry/MCP skill index remains commands + agents even
    # when a runtime projects a narrower discoverable install surface.
    assert canonical_skills_count == commands_count + agents_count
    assert mcp_server_count == mcp_script_count - managed_integration_script_count


def test_agent_metadata_inventory_uses_valid_enums_without_changing_canonical_skill_surface() -> None:
    content_registry.invalidate_cache()

    valid_surfaces = set(content_registry.AGENT_SURFACES)
    valid_role_families = set(content_registry.AGENT_ROLE_FAMILIES)
    valid_artifact_authorities = set(content_registry.AGENT_ARTIFACT_WRITE_AUTHORITIES)
    valid_shared_state_authorities = set(content_registry.AGENT_SHARED_STATE_AUTHORITIES)

    assert not hasattr(content_registry, "VALID_AGENT_SURFACES")
    assert not hasattr(content_registry, "VALID_AGENT_ROLE_FAMILIES")
    assert not hasattr(content_registry, "VALID_AGENT_ARTIFACT_WRITE_AUTHORITIES")
    assert not hasattr(content_registry, "VALID_AGENT_SHARED_STATE_AUTHORITIES")

    for name in content_registry.list_agents():
        agent = content_registry.get_agent(name)
        assert agent.surface in valid_surfaces, name
        assert agent.role_family in valid_role_families, name
        assert agent.artifact_write_authority in valid_artifact_authorities, name
        assert agent.shared_state_authority in valid_shared_state_authorities, name


def test_convention_field_counts_match_source_of_truth() -> None:
    convention_count = len(ConventionLock.model_fields) - 1  # exclude custom_conventions
    assert convention_count > 0

    assert f"Convention lock ({convention_count} physics fields + custom)" in _read("src/gpd/core/__init__.py")
    assert f"locks conventions for up to {convention_count} physics fields" in _read("README.md")


def test_pattern_domain_counts_match_source_of_truth() -> None:
    domain_count = len(PatternDomain)
    assert domain_count > 0

    assert f"Error pattern library (8 categories, {domain_count} domains)" in _read("src/gpd/core/__init__.py")
    assert f'pattern_app = typer.Typer(help="Error pattern library (8 categories, {domain_count} domains)")' in _read(
        "src/gpd/cli.py"
    )


def test_mcp_server_count_matches_public_entrypoints() -> None:
    from gpd.mcp.managed_integrations import WOLFRAM_BRIDGE_COMMAND

    repo_root = _repo_root()
    mcp_server_count = len([p for p in (repo_root / "src" / "gpd" / "mcp" / "servers").glob("*.py") if p.name != "__init__.py"])
    builtin_mcp_script_count = sum(
        1
        for name in _project_script_targets(repo_root)
        if name.startswith("gpd-mcp-") and name != WOLFRAM_BRIDGE_COMMAND
    )
    assert mcp_server_count > 0
    assert mcp_server_count == builtin_mcp_script_count


def test_managed_mcp_server_keys_match_public_descriptors_and_infra_inventory() -> None:
    from gpd.mcp.builtin_servers import GPD_MCP_SERVER_KEYS, build_public_descriptors

    repo_root = _repo_root()
    descriptor_keys = set(build_public_descriptors())
    infra_keys = {path.stem for path in (repo_root / "infra").glob("gpd-*.json")}

    assert GPD_MCP_SERVER_KEYS == descriptor_keys
    assert GPD_MCP_SERVER_KEYS == infra_keys


def test_gpd_skills_infra_health_check_tracks_the_research_vertical() -> None:
    descriptor = json.loads(_read("infra/gpd-skills.json"))
    health_check = descriptor["health_check"]

    assert health_check["tool"] == "list_skills"
    assert health_check["input"] == {}
    assert "gpd-execute-phase" in health_check["expect"]
    assert "gpd-research-phase" in health_check["expect"]


def test_optional_wolfram_bridge_stays_outside_builtin_public_mcp_surface() -> None:
    from gpd.mcp.builtin_servers import GPD_MCP_SERVER_KEYS, build_public_descriptors
    from gpd.mcp.managed_integrations import WOLFRAM_BRIDGE_COMMAND, WOLFRAM_MANAGED_SERVER_KEY

    repo_root = _repo_root()
    descriptor_keys = set(build_public_descriptors())
    infra_keys = {path.stem for path in (repo_root / "infra").glob("gpd-*.json")}
    script_targets = _project_script_targets(repo_root)

    assert WOLFRAM_MANAGED_SERVER_KEY not in GPD_MCP_SERVER_KEYS
    assert WOLFRAM_MANAGED_SERVER_KEY not in descriptor_keys
    assert WOLFRAM_MANAGED_SERVER_KEY not in infra_keys

    if WOLFRAM_BRIDGE_COMMAND in script_targets:
        assert script_targets[WOLFRAM_BRIDGE_COMMAND] == "gpd.mcp.integrations.wolfram_bridge:main"


def test_public_mcp_descriptor_capabilities_match_server_tools() -> None:
    from gpd.mcp.builtin_servers import build_public_descriptors

    descriptors = build_public_descriptors()
    for name, descriptor in descriptors.items():
        module_name = _descriptor_python_module(descriptor)
        assert isinstance(module_name, str), name
        assert descriptor["capabilities"] == _module_advertised_mcp_tools(module_name), name


def test_public_mcp_descriptor_entry_point_alternatives_match_pyproject_scripts() -> None:
    from gpd.mcp.builtin_servers import build_public_descriptors

    repo_root = _repo_root()
    script_targets: dict[str, str] = {}
    for line in _project_script_lines(repo_root):
        name, target = line.split("=", 1)
        script_targets[name.strip().strip('"')] = target.strip().strip('"')

    descriptors = build_public_descriptors()
    for name, descriptor in descriptors.items():
        module_name = _descriptor_python_module(descriptor)
        assert isinstance(module_name, str), name
        script_name = descriptor.get("command")
        assert isinstance(script_name, str), name
        assert descriptor.get("args") == []
        assert script_name.startswith("gpd-mcp-")
        assert script_targets[script_name] == f"{module_name}:main"

        alternatives = descriptor.get("alternatives")
        assert isinstance(alternatives, dict), name
        python_module = alternatives.get("python_module")
        assert isinstance(python_module, dict), name
        assert python_module.get("command") == "${GPD_PYTHON}"
        assert python_module.get("args") == ["-m", module_name]
        assert (
            python_module.get("notes")
            == "Replace `${GPD_PYTHON}` with a Python >=3.11 interpreter that has GPD installed."
        )


def test_arxiv_descriptor_tracks_optional_dependency_surface() -> None:
    from gpd.mcp.builtin_servers import build_public_descriptors

    project = tomllib.loads(_read("pyproject.toml"))["project"]
    dependencies: list[str] = project["dependencies"]
    optional = project.get("optional-dependencies", {})
    assert not any(item.startswith("arxiv-mcp-server") for item in dependencies)
    assert optional == {"arxiv": ["arxiv-mcp-server>=0.4.11"]}

    descriptor = build_public_descriptors()["gpd-arxiv"]
    assert descriptor["prerequisites"] == ["Install GPD before enabling built-in MCP servers."]
    assert descriptor["capabilities"][-1] == "download_source"


def test_agent_count_matches_prompts_and_user_docs() -> None:
    agents_count = len(list((_repo_root() / "src" / "gpd" / "agents").glob("*.md")))
    assert agents_count == len(MODEL_PROFILES)
    assert "specialist agents" in _read("README.md")
    assert f"across all {agents_count} agents" in _read("src/gpd/specs/workflows/set-profile.md")


def test_settings_workflow_documents_runtime_native_model_override_guidance() -> None:
    workflow = _read("src/gpd/specs/workflows/settings.md")

    assert "model_overrides" in workflow
    assert "tier-1" in workflow
    assert "infer the active runtime identifier" in workflow
    assert "the exact model string the active runtime accepts" in workflow
    assert "Preserve any provider prefixes" in workflow
    assert "slash-delimited ids" in workflow
    assert "execution.review_cadence" in workflow
    assert "planning.commit_docs" in workflow
    assert "git.branching_strategy" in workflow


def test_branching_strategy_docs_use_canonical_config_literals() -> None:
    settings = _read("src/gpd/specs/workflows/settings.md")
    planning = _read("src/gpd/specs/references/planning/planning-config.md")
    execute_phase = _read("src/gpd/specs/workflows/execute-phase.md")
    complete_milestone = _read("src/gpd/specs/workflows/complete-milestone.md")

    assert '"branching_strategy": "none" | "per-phase" | "per-milestone"' in settings
    assert 'Git branching approach: `"none"`, `"per-phase"`, or `"per-milestone"`' in planning
    assert '| `per-phase`     | At `execute-phase` start' in planning
    assert '| `per-milestone` | At first `execute-phase` of milestone' in planning
    assert '**"per-phase" or "per-milestone":** Use pre-computed `branch_name` from init:' in execute_phase
    assert '**For "per-phase" strategy:**' in complete_milestone
    assert '**For "per-milestone" strategy:**' in complete_milestone
    assert 'if [ "$BRANCHING_STRATEGY" = "per-phase" ]; then' in complete_milestone
    assert 'if [ "$BRANCHING_STRATEGY" = "per-milestone" ]; then' in complete_milestone
    assert '"branching_strategy": "none" | "phase" | "milestone"' not in settings
    assert 'Git branching approach: `"none"`, `"phase"`, or `"milestone"`' not in planning
    assert '| `phase`     | At `execute-phase` start' not in planning
    assert '| `milestone` | At first `execute-phase` of milestone' not in planning


def test_help_and_settings_surface_current_commit_docs_and_review_cadence_shapes() -> None:
    settings = _read("src/gpd/specs/workflows/settings.md")
    help_workflow = _read("src/gpd/specs/workflows/help.md")

    for content in (settings, help_workflow):
        assert "execution.review_cadence" in content
        assert "planning.commit_docs" in content

    assert "needs-calculation" in help_workflow


def test_execute_phase_docs_use_review_cadence_not_removed_verify_between_waves_knob() -> None:
    execute_command = _read("src/gpd/commands/execute-phase.md")
    execute_workflow = _read("src/gpd/specs/workflows/execute-phase.md")

    assert "execution.review_cadence" in execute_command
    assert "dense" in execute_command
    assert "adaptive" in execute_command
    assert "sparse" in execute_command
    assert "workflow.verify_between_waves" not in execute_command
    assert "review_cadence" in execute_workflow
    assert "verify_between_waves" not in execute_workflow


def test_health_check_count_matches_skill_documentation() -> None:
    health_check_count = len(_ALL_CHECKS)
    assert health_check_count > 0

    command = _read("src/gpd/commands/health.md")
    assert "All {total} health checks passed." in command
    assert "All checks reported with status" in command


def test_every_command_declares_valid_context_mode() -> None:
    commands_dir = _repo_root() / "src" / "gpd" / "commands"
    pattern = re.compile(r"^context_mode:\s*(.+?)\s*$", re.MULTILINE)

    missing: list[str] = []
    invalid: list[str] = []

    for path in sorted(commands_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        match = pattern.search(content)
        if match is None:
            missing.append(path.name)
            continue
        mode = match.group(1).strip()
        if mode not in VALID_CONTEXT_MODES:
            invalid.append(f"{path.name}: {mode}")

    assert missing == []
    assert invalid == []


def test_update_workflow_uses_runtime_placeholders_for_cache_paths() -> None:
    workflow = _read("src/gpd/specs/workflows/update.md")

    assert "<GPD_CONFIG_DIR>" not in workflow
    assert '"{GPD_CONFIG_DIR}/cache/gpd-update-check.json"' in workflow


def test_referee_response_round_suffix_convention_is_consistent() -> None:
    write_paper = _read("src/gpd/specs/workflows/write-paper.md")
    peer_review = _read("src/gpd/specs/workflows/peer-review.md")
    respond = _read("src/gpd/specs/workflows/respond-to-referees.md")
    arxiv = _read("src/gpd/specs/workflows/arxiv-submission.md")
    author_response = _read("src/gpd/specs/templates/paper/author-response.md")
    template = _read("src/gpd/specs/templates/paper/referee-response.md")

    assert 'ROUND_SUFFIX="-R2"' in peer_review
    assert 'ROUND_SUFFIX="-R3"' in peer_review
    assert '`GPD/review/REFEREE_RESPONSE{round_suffix}.md`' in respond
    assert '`GPD/AUTHOR-RESPONSE{round_suffix}.md`' in respond
    assert "GPD/paper" not in respond
    assert "needs-calculation" in respond
    assert "issues_needing_calculation" in author_response
    assert "needs-calculation" in author_response
    assert "templates/paper/author-response.md" in template
    assert "REFEREE_RESPONSE-R2.md" in template
    assert "REFEREE_RESPONSE_R2.md" not in respond
    assert "REFEREE_RESPONSE_R2.md" not in template
    assert "paper/referee-reports" not in respond
    assert "publication-manuscript-root-preflight.md" in peer_review
    assert "${MANUSCRIPT_ROOT}/REFEREE_RESPONSE" not in peer_review
    assert "publication-bootstrap-preflight.md" in write_paper
    assert "publication-response-writer-handoff.md" in write_paper
    assert "publication-bootstrap-preflight.md" in respond
    assert "publication-response-writer-handoff.md" in respond
    assert "publication-bootstrap-preflight.md" in arxiv
    assert "publication-response-writer-handoff.md" not in arxiv


def test_bibliography_template_tracks_live_references_bib_path() -> None:
    template = _read("src/gpd/specs/templates/bibliography.md")

    assert "references/references.bib" in template
    assert "GPD/references.bib" not in template
