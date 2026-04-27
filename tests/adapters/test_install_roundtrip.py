"""Integration tests: install → read back → verify for all catalog runtimes.

Tests that installed content matches source expectations for each adapter.
Exercises both the write path (install) and the read path (loading/parsing
installed content) to catch serialization/deserialization mismatches.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tomllib
from functools import cache
from pathlib import Path

import pytest

from gpd.adapters import get_adapter, iter_adapters
from gpd.adapters.claude_code import ClaudeCodeAdapter
from gpd.adapters.codex import CodexAdapter
from gpd.adapters.gemini import GeminiAdapter
from gpd.adapters.install_utils import (
    build_runtime_cli_bridge_command,
    convert_tool_references_in_body,
    expand_at_includes,
    translate_frontmatter_tool_names,
)
from gpd.adapters.opencode import OpenCodeAdapter
from gpd.adapters.runtime_catalog import (
    get_runtime_descriptor,
    get_shared_install_metadata,
    iter_runtime_descriptors,
    list_runtime_names,
    resolve_global_config_dir,
)
from gpd.adapters.tool_names import build_canonical_alias_map
from gpd.core.public_surface_contract import local_cli_bridge_commands
from gpd.registry import load_agents_from_dir
from tests.doc_surface_contracts import assert_publication_lane_boundary_contract

REPO_GPD_ROOT = Path(__file__).resolve().parents[2] / "src" / "gpd"
RUNTIME_ALIAS_MAP = build_canonical_alias_map(adapter.tool_name_map for adapter in iter_adapters())
FULL_RUNTIME_MATRIX = tuple(descriptor.runtime_name for descriptor in iter_runtime_descriptors())
_SHARED_INSTALL = get_shared_install_metadata()
_INSTALL_CACHE: dict[tuple[str, tuple[str, ...]], Path] = {}


def expected_opencode_bridge(target: Path, *, is_global: bool = False, explicit_target: bool = False) -> str:
    return build_runtime_cli_bridge_command(
        "opencode",
        target_dir=target,
        config_dir_name=".opencode",
        is_global=is_global,
        explicit_target=explicit_target,
    )


def _make_checkout_stub(tmp_path: Path) -> tuple[Path, Path]:
    """Create a minimal checkout root with a local virtualenv interpreter."""
    checkout_root = tmp_path / "checkout"
    src_root = checkout_root / "src" / "gpd"
    for subdir in ("commands", "agents", "hooks", "specs"):
        (src_root / subdir).mkdir(parents=True, exist_ok=True)
    (checkout_root / "package.json").write_text(
        json.dumps({"name": "get-physics-done", "version": "9.9.9", "gpdPythonVersion": "9.9.9"}),
        encoding="utf-8",
    )
    (checkout_root / "pyproject.toml").write_text(
        '[project]\nname = "get-physics-done"\nversion = "9.9.9"\n',
        encoding="utf-8",
    )
    venv_python_rel = Path("Scripts") / "python.exe" if os.name == "nt" else Path("bin") / "python"
    checkout_python = checkout_root / ".venv" / venv_python_rel
    checkout_python.parent.mkdir(parents=True, exist_ok=True)
    checkout_python.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    return checkout_root, checkout_python


def _collect_textual_artifacts(root: Path) -> str:
    """Return concatenated text from readable installed artifacts under *root*."""
    chunks: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            chunks.append(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
    return "\n".join(chunks)


def _install_real_repo_for_runtime(tmp_path: Path, runtime: str, source_root: Path = REPO_GPD_ROOT) -> Path:
    if runtime == "claude-code":
        target = tmp_path / ".claude"
        target.mkdir()
        ClaudeCodeAdapter().install(source_root, target)
        return target

    if runtime == "codex":
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        CodexAdapter().install(source_root, target, is_global=False, skills_dir=skills)
        return target

    if runtime == "gemini":
        target = tmp_path / ".gemini"
        target.mkdir()
        _install_gemini_for_tests(source_root, target)
        return target

    if runtime == "opencode":
        target = tmp_path / ".opencode"
        target.mkdir()
        OpenCodeAdapter().install(source_root, target)
        return target

    raise AssertionError(f"Unsupported runtime {runtime}")


def _install_gemini_for_tests(gpd_root: Path, target: Path) -> GeminiAdapter:
    """Install Gemini artifacts and persist the deferred Gemini settings."""
    adapter = GeminiAdapter()
    result = adapter.install(gpd_root, target)
    adapter.finalize_install(result)
    return adapter


def test_install_roundtrip_full_runtime_matrix_matches_catalog_runtimes() -> None:
    assert FULL_RUNTIME_MATRIX == tuple(list_runtime_names())
    assert FULL_RUNTIME_MATRIX == tuple(adapter.runtime_name for adapter in iter_adapters())


@cache
def _source_signature(root: Path) -> tuple[str, ...]:
    signature_entries: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        signature_entries.append(f"{path.relative_to(root).as_posix()}:{digest}")
    return tuple(signature_entries)


def _cached_real_install(runtime: str, source_root: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    cache_key = (runtime, _source_signature(source_root))
    if cache_key not in _INSTALL_CACHE:
        _INSTALL_CACHE[cache_key] = _install_real_repo_for_runtime(
            tmp_path_factory.mktemp(f"{runtime}-real-install"),
            runtime,
            source_root=source_root,
        )
    return _INSTALL_CACHE[cache_key]


@pytest.fixture(scope="module")
def real_installed_repo_factory(tmp_path_factory: pytest.TempPathFactory):
    def factory(runtime: str) -> Path:
        return _cached_real_install(runtime, REPO_GPD_ROOT, tmp_path_factory)

    return factory


def _expected_local_bridge_for_runtime(runtime: str, target: Path) -> str:
    adapter = get_adapter(runtime)
    return build_runtime_cli_bridge_command(
        runtime,
        target_dir=target,
        config_dir_name=adapter.config_dir_name,
        is_global=False,
        explicit_target=False,
    )


def _canonicalize_runtime_markdown(content: str, *, runtime: str) -> str:
    content = re.sub(
        r"@(?:\./)?[^\s`>)]*get-physics-done/([^\s`>)]+)",
        r"@{GPD_INSTALL_DIR}/\1",
        content,
    )
    content = re.sub(
        r"@(?:\./)?[^\s`>)]*agents/([^\s`>)]+)",
        r"@{GPD_AGENTS_DIR}/\1",
        content,
    )
    content = re.sub(
        (
            r"(?:'[^']+'|\"[^\"]+\"|[^ \n`]+)\s+-m gpd\.runtime_cli\s+--runtime\s+[a-z-]+\s+"
            r"--config-dir\s+(?:'[^']+'|\"[^\"]+\"|[^ \n`]+)\s+--install-scope\s+(?:local|global)"
            r"(?:\s+--explicit-target)?"
        ),
        "gpd",
        content,
    )
    content = expand_at_includes(
        content,
        REPO_GPD_ROOT / "specs",
        "/normalized/",
        runtime=runtime,
    )
    content = translate_frontmatter_tool_names(content, lambda name: RUNTIME_ALIAS_MAP.get(name, name))
    content = convert_tool_references_in_body(content, RUNTIME_ALIAS_MAP)
    content = content.replace("$gpd-", "gpd:")
    content = content.replace("/gpd:", "gpd:")
    content = content.replace("/gpd-", "gpd:")
    if runtime == "opencode":
        # The opencode adapter rewrites bare `gpd:X` command references in
        # markdown body text to `gpd-X` during install (see
        # `_GPD_BARE_COMMAND_RE` in gpd.adapters.opencode). Reverse that here
        # for contract-assertion purposes so tests can use the canonical
        # `gpd:X` form regardless of runtime. This list enumerates the
        # command stems we know to rewrite, to avoid accidentally touching
        # CLI tool or agent names like `gpd-check-proof` that legitimately
        # use the hyphenated form.
        _OPENCODE_REWRITTEN_STEMS = (
            "add-phase", "add-todo", "arxiv-submission", "audit-milestone",
            "autonomous", "branch-hypothesis", "check-todos", "compact-state",
            "compare-branches", "compare-experiment", "compare-results",
            "complete-milestone", "debug", "decisions", "derive-equation",
            "digest-knowledge", "dimensional-analysis", "discover",
            "discuss-phase", "error-patterns", "error-propagation",
            "execute-phase", "explain", "export-logs", "export", "graph",
            "health", "help", "insert-phase", "limiting-cases",
            "list-phase-assumptions", "literature-review", "map-research",
            "merge-phases", "new-milestone", "new-project",
            "numerical-convergence", "parameter-sweep", "pause-work",
            "peer-review", "plan-milestone-gaps", "plan-phase", "progress",
            "quick", "reapply-patches", "record-insight", "regression-check",
            "remove-phase", "research-phase", "respond-to-referees",
            "resume-work", "review-knowledge", "revise-phase",
            "sensitivity-analysis", "set-profile", "set-tier-models",
            "settings", "show-phase", "slides", "start", "suggest-next",
            "sync-state", "tangent", "tour", "undo", "update",
            "validate-conventions", "verify-work", "write-paper",
        )
        for stem in _OPENCODE_REWRITTEN_STEMS:
            content = re.sub(
                rf"(?<![A-Za-z0-9_./:$-])gpd-{re.escape(stem)}\b",
                f"gpd:{stem}",
                content,
            )
    return content


def _read_compare_experiment_command(tmp_path: Path, target: Path, runtime: str) -> str:
    if runtime == "claude-code":
        return (target / "commands" / "gpd" / "compare-experiment.md").read_text(encoding="utf-8")

    if runtime == "codex":
        return (tmp_path / "skills" / "gpd-compare-experiment" / "SKILL.md").read_text(encoding="utf-8")

    if runtime == "gemini":
        parsed = tomllib.loads((target / "commands" / "gpd" / "compare-experiment.toml").read_text(encoding="utf-8"))
        prompt = parsed.get("prompt")
        assert isinstance(prompt, str)
        return prompt

    if runtime == "opencode":
        return (target / "command" / "gpd-compare-experiment.md").read_text(encoding="utf-8")

    raise AssertionError(f"Unsupported runtime {runtime}")


def _read_runtime_command_prompt(tmp_path: Path, target: Path, runtime: str, command_name: str) -> str:
    if runtime == "claude-code":
        return (target / "commands" / "gpd" / f"{command_name}.md").read_text(encoding="utf-8")

    if runtime == "codex":
        return (tmp_path / "skills" / f"gpd-{command_name}" / "SKILL.md").read_text(encoding="utf-8")

    if runtime == "gemini":
        parsed = tomllib.loads((target / "commands" / "gpd" / f"{command_name}.toml").read_text(encoding="utf-8"))
        prompt = parsed.get("prompt")
        assert isinstance(prompt, str)
        return prompt

    if runtime == "opencode":
        return (target / "command" / f"gpd-{command_name}.md").read_text(encoding="utf-8")

    raise AssertionError(f"Unsupported runtime {runtime}")


def _read_runtime_update_surface(tmp_path: Path, target: Path, runtime: str) -> str:
    if runtime == "claude-code":
        return (target / "commands" / "gpd" / "update.md").read_text(encoding="utf-8")

    if runtime == "codex":
        return (tmp_path / "skills" / "gpd-update" / "SKILL.md").read_text(encoding="utf-8")

    if runtime == "gemini":
        parsed = tomllib.loads((target / "commands" / "gpd" / "update.toml").read_text(encoding="utf-8"))
        prompt = parsed.get("prompt")
        assert isinstance(prompt, str)
        return prompt

    if runtime == "opencode":
        return (target / "command" / "gpd-update.md").read_text(encoding="utf-8")

    raise AssertionError(f"Unsupported runtime {runtime}")


def _read_runtime_agent_prompt(target: Path, runtime: str, agent_name: str) -> str:
    if runtime in {"claude-code", "codex", "gemini", "opencode"}:
        return (target / "agents" / f"{agent_name}.md").read_text(encoding="utf-8")
    raise AssertionError(f"Unsupported runtime {runtime}")


def _assert_installed_contract_visibility(
    verifier: str,
    executor: str,
    new_project: str,
    plan_phase: str,
    write_paper: str,
    plan_schema: str,
    execute_phase: str,
    verify_work: str,
    *,
    runtime: str,
) -> None:
    verifier = _canonicalize_runtime_markdown(verifier, runtime=runtime)
    executor = _canonicalize_runtime_markdown(executor, runtime=runtime)
    new_project = _canonicalize_runtime_markdown(new_project, runtime=runtime)
    plan_phase = _canonicalize_runtime_markdown(plan_phase, runtime=runtime)
    write_paper = _canonicalize_runtime_markdown(write_paper, runtime=runtime)
    plan_schema = _canonicalize_runtime_markdown(plan_schema, runtime=runtime)
    execute_phase = _canonicalize_runtime_markdown(execute_phase, runtime=runtime)
    verify_work = _canonicalize_runtime_markdown(verify_work, runtime=runtime)

    assert "Execute phase plans through the workflow-owned wave executor" in execute_phase
    assert "references/orchestration/context-budget.md" in execute_phase
    assert "<inline_guidance>" not in execute_phase

    assert "templates/contract-results-schema.md" in verifier
    assert "plan_contract_ref" in verifier
    assert "contract_results" in verifier
    assert "comparison_verdicts" in verifier
    assert "suggested_contract_checks" in verifier
    assert "contract_results.uncertainty_markers" in verifier

    assert "templates/contract-results-schema.md" in executor
    assert "plan_contract_ref" in executor
    assert "contract_results" in executor
    assert "comparison_verdicts" in executor
    assert "These ledgers are user-visible evidence." in executor

    assert "templates/project-contract-schema.md" in new_project
    assert "project_contract_load_info" in new_project
    assert "project_contract_validation" in new_project
    assert "`schema_version` must be the integer `1`" in new_project
    assert "`references[].must_surface` must stay a boolean `true` or `false`" in new_project
    assert "`context_intake`" in new_project
    assert "`approach_policy`" in new_project
    assert "`uncertainty_markers`" in new_project
    assert "`context_intake`, `approach_policy`, and `uncertainty_markers` must each stay as objects, not strings or lists." in new_project
    assert "review_mode: publication" in write_paper
    assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in write_paper
    assert "GPD/review/REFEREE_RESPONSE{round_suffix}.md" in write_paper
    assert "GPD/review/REVIEW-LEDGER{round_suffix}.json" in write_paper
    assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in write_paper
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in write_paper
    assert "GPD/REFEREE-REPORT{round_suffix}.tex" in write_paper

    assert "Canonical contract schema and hard validation rules" in plan_phase
    assert (
        "every proof-bearing plan must surface the theorem statement, named parameters, hypotheses, "
        "quantifier/domain obligations, and intended conclusion clauses visibly enough that a later audit can "
        "detect missing coverage"
    ) in plan_phase

    assert "`contract.context_intake` is required and must be a non-empty object" in plan_schema
    assert "`must_surface` is a boolean scalar. Use the YAML literals `true` and `false`" in plan_schema
    assert "If `must_surface: true`, `required_actions` must not be empty." in plan_schema
    assert "If `must_surface: true`, `applies_to[]` must not be empty." in plan_schema
    assert "`carry_forward_to[]` is optional free-text workflow scope" in plan_schema
    assert "`uncertainty_markers` must be a YAML object, not a string or list." in plan_schema

    assert "workflow.verifier=false" in execute_phase
    assert "skip verification" in execute_phase
    assert "proof red-teaming" in execute_phase
    assert "{plan_id}-PROOF-REDTEAM.md" in execute_phase
    assert "Targeted flags narrow the optional check mix only." in verify_work
    assert "Every spawned agent is a one-shot delegation" in verify_work
    assert "If a required proof-redteam audit is missing, stale, malformed, or not `passed`, spawn `gpd-check-proof` once" in verify_work


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_installed_peer_review_prompt_keeps_publication_lane_boundary(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    peer_review = _read_runtime_command_prompt(target.parent, target, runtime, "peer-review")
    peer_review = _canonicalize_runtime_markdown(peer_review, runtime=runtime)

    assert "Keep GPD-authored auxiliary review artifacts under `GPD/` in the invoking workspace." in peer_review
    assert (
        "The manuscript itself and any manuscript-local publication manifests stay rooted at the resolved manuscript directory."
        in peer_review
    )


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_installed_verifier_prompt_surface_keeps_one_wrapper_and_stays_within_budget(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    verifier = _read_runtime_agent_prompt(target, runtime, "gpd-verifier")
    descriptor = get_runtime_descriptor(runtime)
    line_budget, char_budget = (900, 60_000) if descriptor.native_include_support else (6_500, 430_000)

    assert verifier.count("## Agent Requirements") == 1
    assert verifier.index("## Agent Requirements") < verifier.index("## Bootstrap Discipline")
    if descriptor.native_include_support:
        assert verifier.count("verification-report.md") == 1
        assert verifier.count("contract-results-schema.md") == 1
        assert verifier.count("canonical-schema-discipline.md") == 1
    else:
        assert verifier.count("# Verification Report Template") == 1
        assert verifier.count("# Contract Results Schema") == 1
        assert verifier.count("# Canonical Schema Discipline") == 1
    assert len(verifier.splitlines()) <= line_budget
    assert len(verifier) <= char_budget


@pytest.mark.no_stable_hook_python
@pytest.mark.parametrize("runtime", ["claude-code"])
def test_install_artifacts_pin_checkout_python_when_running_from_checkout(
    tmp_path: Path,
    runtime: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the real checkout-python resolution path, not the stable fallback."""
    checkout_root, checkout_python = _make_checkout_stub(tmp_path)
    stale_managed_python = "/managed/gpd/venv/bin/python"

    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: checkout_root)
    monkeypatch.setattr("gpd.adapters.install_utils.sys.executable", stale_managed_python)

    target = _install_real_repo_for_runtime(tmp_path, runtime)
    artifact_roots = [target]
    if runtime == "codex":
        artifact_roots.append(tmp_path / "skills")

    installed_text = "\n".join(_collect_textual_artifacts(root) for root in artifact_roots)

    assert str(checkout_python) in installed_text
    assert stale_managed_python not in installed_text


@pytest.mark.parametrize("runtime", ["codex"])
def test_update_surface_materializes_workflow_paths_in_compiled_artifacts(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    adapter = next(adapter for adapter in iter_adapters() if adapter.runtime_name == runtime)
    canonical_global_dir = resolve_global_config_dir(adapter.runtime_descriptor)
    content = _read_runtime_update_surface(target.parent, target, runtime)

    if runtime == "claude-code":
        assert f"@{target.as_posix()}/get-physics-done/workflows/update.md" in content
        assert "{GPD_CONFIG_DIR}" not in content
    else:
        assert f'GPD_CONFIG_DIR="{target.as_posix()}"' in content
        assert f'GPD_GLOBAL_CONFIG_DIR="{canonical_global_dir.as_posix()}"' in content
        update_command = f"{adapter.update_command} --local"
        assert f'UPDATE_COMMAND="{update_command}"' in content
        assert (
            f'PATCH_META="{target.as_posix()}/{_SHARED_INSTALL.patches_dir_name}/backup-meta.json"' in content
        )
        assert "TARGET_DIR_ARG=$(" not in content


@pytest.mark.parametrize("runtime", ["claude-code"])
def test_shared_installed_markdown_preserves_round_aware_review_placeholders(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)

    shared_markdown = sorted((target / "get-physics-done").rglob("*.md"))
    assert shared_markdown

    saw_round_placeholder = False
    for markdown_path in shared_markdown:
        content = markdown_path.read_text(encoding="utf-8")
        if "{round_suffix}" in content or "{-RN}" in content:
            saw_round_placeholder = True

    assert saw_round_placeholder is True


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_installed_referee_latex_template_exists_and_matches_source(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    source_template = REPO_GPD_ROOT / "specs" / "templates" / "paper" / "referee-report.tex"
    installed_template = (
        real_installed_repo_factory(runtime) / "get-physics-done" / "templates" / "paper" / "referee-report.tex"
    )

    assert source_template.exists()
    assert installed_template.exists()
    assert installed_template.read_bytes() == source_template.read_bytes()

# ---------------------------------------------------------------------------
# Claude Code: install → read back → compare
# ---------------------------------------------------------------------------


class TestClaudeCodeRoundtrip:
    """Install into .claude/, then verify installed files match source semantics."""

    @pytest.fixture()
    def installed(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        return _cached_real_install("claude-code", REPO_GPD_ROOT, tmp_path_factory)

    def test_commands_roundtrip(self, installed: Path) -> None:
        """Installed commands/gpd/ files correspond 1:1 with source commands/."""
        src_mds = sorted(f.name for f in (REPO_GPD_ROOT / "commands").rglob("*.md"))
        dest_mds = sorted(f.name for f in (installed / "commands" / "gpd").rglob("*.md"))
        assert dest_mds == src_mds

    def test_command_placeholders_resolved(self, installed: Path) -> None:
        """All {GPD_INSTALL_DIR} and ~/.claude/ placeholders are replaced."""
        for md in (installed / "commands" / "gpd").rglob("*.md"):
            content = md.read_text(encoding="utf-8")
            assert "{GPD_INSTALL_DIR}" not in content

    def test_agent_frontmatter_preserved(self, installed: Path) -> None:
        """Claude Code agents keep frontmatter intact (tools, description)."""
        for md in (installed / "agents").glob("gpd-*.md"):
            content = md.read_text(encoding="utf-8")
            assert content.startswith("---"), f"{md.name} missing frontmatter"
            # Frontmatter should have description and either tools: or allowed-tools:
            end = content.find("---", 3)
            frontmatter = content[3:end]
            assert "description:" in frontmatter, f"{md.name} missing description"

    def test_gpd_content_placeholders_resolved(self, installed: Path) -> None:
        """get-physics-done/ .md files have placeholders replaced."""
        for md in (installed / "get-physics-done").rglob("*.md"):
            content = md.read_text(encoding="utf-8")
            assert "{GPD_INSTALL_DIR}" not in content

    def test_shared_content_tool_references_are_translated(self, installed: Path) -> None:
        """Shared markdown content should use Claude-native tool names."""
        workflow = _collect_textual_artifacts(installed / "get-physics-done" / "workflows")
        reference = _collect_textual_artifacts(installed / "get-physics-done" / "references")

        assert "AskUserQuestion([" in workflow
        assert "ask_user(" not in workflow
        assert "Task(" in workflow
        assert "task(" not in workflow
        assert "WebSearch" in reference
        assert "web_search" not in reference

    def test_version_file(self, installed: Path) -> None:
        """VERSION file exists and is non-empty."""
        version = installed / "get-physics-done" / "VERSION"
        assert version.exists()
        assert len(version.read_text(encoding="utf-8").strip()) > 0

    def test_manifest_tracks_all_files(self, installed: Path) -> None:
        """File manifest lists entries for commands, agents, and content."""
        manifest = json.loads((installed / "gpd-file-manifest.json").read_text(encoding="utf-8"))
        files = manifest["files"]
        assert any(k.startswith("commands/gpd/") for k in files)
        assert any(k.startswith("agents/") for k in files)
        assert any(k.startswith("get-physics-done/") for k in files)
        assert "version" in manifest


# ---------------------------------------------------------------------------
# Codex: install → read back → compare
# ---------------------------------------------------------------------------


class TestCodexRoundtrip:
    """Install into .codex/ + skills/, verify command skills plus agent roles."""

    @pytest.fixture()
    def installed(self, tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
        target = _cached_real_install("codex", REPO_GPD_ROOT, tmp_path_factory)
        return target, target.parent / "skills"

    def test_commands_become_skill_dirs(self, installed: tuple[Path, Path]) -> None:
        """Each command becomes a gpd-<name>/SKILL.md directory."""
        _, skills = installed
        skill_dirs = [d for d in skills.iterdir() if d.is_dir() and d.name.startswith("gpd-")]
        assert len(skill_dirs) > 0
        for skill_dir in skill_dirs:
            skill_md = skill_dir / "SKILL.md"
            assert skill_md.exists(), f"{skill_dir.name}/ missing SKILL.md"

    def test_skill_md_has_frontmatter(self, installed: tuple[Path, Path]) -> None:
        """SKILL.md files have YAML frontmatter with name and description."""
        _, skills = installed
        for skill_dir in skills.iterdir():
            if not skill_dir.is_dir() or not skill_dir.name.startswith("gpd-"):
                continue
            skill_md = skill_dir / "SKILL.md"
            content = skill_md.read_text(encoding="utf-8")
            assert content.startswith("---"), f"{skill_dir.name}/SKILL.md missing frontmatter"
            end = content.find("---", 3)
            fm = content[3:end]
            assert "name:" in fm, f"{skill_dir.name} missing name field"
            assert "description:" in fm, f"{skill_dir.name} missing description field"

    def test_command_count_matches_source(self, installed: tuple[Path, Path]) -> None:
        """Number of skills matches source command count."""
        _, skills = installed
        src_count = sum(1 for _ in (REPO_GPD_ROOT / "commands").rglob("*.md"))
        skill_count = sum(1 for d in skills.iterdir() if d.is_dir() and d.name.startswith("gpd-"))
        assert skill_count == src_count

    def test_agents_not_installed_as_skills(self, installed: tuple[Path, Path]) -> None:
        """Codex agents are registered as roles, not duplicated as discoverable skills."""
        _, skills = installed
        agents = load_agents_from_dir(REPO_GPD_ROOT / "agents")
        for agent_name in sorted(agents):
            assert not (skills / agent_name).exists(), f"Agent should not be a Codex skill: {agent_name}"

    def test_agents_installed_as_md_files(self, installed: tuple[Path, Path]) -> None:
        """Agents are also installed as .md files under .codex/agents/."""
        target, _ = installed
        agents_dir = target / "agents"
        assert agents_dir.is_dir()
        src_agents = sorted(f.name for f in (REPO_GPD_ROOT / "agents").glob("*.md"))
        dest_agents = sorted(f.name for f in agents_dir.glob("*.md"))
        assert dest_agents == src_agents

    def test_agent_role_configs_installed(self, installed: tuple[Path, Path]) -> None:
        """Each installed Codex agent also gets a role config TOML."""
        target, _ = installed
        agents_dir = target / "agents"
        src_agent_names = sorted(f.stem for f in (REPO_GPD_ROOT / "agents").glob("*.md"))
        dest_role_names = sorted(f.stem for f in agents_dir.glob("gpd-*.toml"))
        assert dest_role_names == src_agent_names

    def test_shared_content_tool_references_are_translated(self, installed: tuple[Path, Path]) -> None:
        """Shared markdown content should use Codex runtime tool names."""
        target, _ = installed
        workflow = _collect_textual_artifacts(target / "get-physics-done" / "workflows")
        reference = _collect_textual_artifacts(target / "get-physics-done" / "references")

        assert "<codex_questioning>" in workflow
        assert "ask_user([" in workflow
        assert "AskUserQuestion" not in workflow
        assert "task(" in workflow
        assert "Task(" not in workflow
        assert "web_search" in reference
        assert "WebSearch" not in reference

    def test_slash_commands_converted(self, installed: tuple[Path, Path]) -> None:
        """Content replaces /gpd: with $gpd- for Codex invocation syntax."""
        target, _ = installed
        for md in (target / "get-physics-done").rglob("*.md"):
            content = md.read_text(encoding="utf-8")
            assert "/gpd:" not in content, f"{md.name} still has /gpd:"

    def test_config_toml_has_notify(self, installed: tuple[Path, Path]) -> None:
        """config.toml has a notify hook entry."""
        target, _ = installed
        toml_path = target / "config.toml"
        assert toml_path.exists()
        content = toml_path.read_text(encoding="utf-8")
        assert "notify" in content
        assert "multi_agent = true" in content
        assert "[agents.gpd-executor]" in content

    def test_manifest_tracks_skills(self, installed: tuple[Path, Path]) -> None:
        """File manifest includes skill entries."""
        target, _ = installed
        manifest_path = target / "gpd-file-manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "version" in manifest
        assert "files" in manifest


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_real_installed_set_tier_models_prompt_keeps_direct_tier_override_contract(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    content = _canonicalize_runtime_markdown(
        _read_runtime_command_prompt(target.parent, target, runtime, "set-tier-models"),
        runtime=runtime,
    )

    assert "gpd:set-tier-models" in content
    assert "tier-1" in content
    assert "tier-2" in content
    assert "tier-3" in content
    assert "gpd:set-profile" in content
    assert "gpd:settings" in content
    assert "model_overrides.<runtime>" in content
    assert "strongest reasoning" in content
    assert "balanced default" in content
    assert "fastest / most economical" in content


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_real_installed_compare_prompts_keep_gpd_output_contract_and_interactive_intake(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    compare_results = _canonicalize_runtime_markdown(
        _read_runtime_command_prompt(target.parent, target, runtime, "compare-results"),
        runtime=runtime,
    )
    compare_experiment = _canonicalize_runtime_markdown(
        _read_runtime_command_prompt(target.parent, target, runtime, "compare-experiment"),
        runtime=runtime,
    )

    assert "command_policy:" in compare_results
    assert "allow_interactive_without_subject: true" in compare_results
    assert "default_output_subtree: GPD/comparisons" in compare_results
    assert "comparison target, phase, artifact path, or source-a vs source-b" in compare_results
    assert "default_output_subtree: GPD/comparisons" in compare_experiment
    assert "GPD/comparisons/{slug}/" in compare_experiment
    assert "Do not run an unconditional standalone docs commit for this workflow." in compare_experiment
    assert "artifacts/comparisons/{slug}/" not in compare_experiment


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_real_installed_public_local_cli_commands_stay_canonical(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    bridge_command = _expected_local_bridge_for_runtime(runtime, target)
    installed_text = _collect_textual_artifacts(target.parent)

    for public_command in local_cli_bridge_commands():
        assert public_command in installed_text
        assert f"{bridge_command}{public_command[3:]}" not in installed_text


def test_help_like_skills_keep_canonical_local_cli_language(tmp_path: Path) -> None:
    """Codex skills keep canonical local CLI names in prose even when shell steps bridge."""
    _install_real_repo_for_runtime(tmp_path, "codex")
    skills = tmp_path / "skills"
    help_skill = (skills / "gpd-help" / "SKILL.md").read_text(encoding="utf-8")
    tour_skill = (skills / "gpd-tour" / "SKILL.md").read_text(encoding="utf-8")
    settings_skill = (skills / "gpd-settings" / "SKILL.md").read_text(encoding="utf-8")

    assert "Use `gpd --help` to inspect the executable local install/readiness/permissions/diagnostics surface directly." in help_skill
    assert "For a normal-terminal, current-workspace read-only recovery snapshot without launching the runtime, use `gpd resume`." in help_skill
    assert "For a normal-terminal, read-only machine-local usage / cost summary, use `gpd cost`." in help_skill
    assert "The normal terminal is where you install GPD, run `gpd --help`, and run" in tour_skill
    assert "`gpd resume` is the normal-terminal recovery step for reopening the right" in tour_skill
    assert "use `gpd --help` when you need the broader local CLI entrypoint" in settings_skill
    assert "use `gpd cost` after runs for advisory local usage / cost, optional USD budget guardrails, and the current profile tier mix" in settings_skill
    assert re.search(r"`[^`\n]*gpd\.runtime_cli[^`\n]*(?:--help|resume|cost)[^`\n]*`", help_skill) is None
    assert re.search(r"`[^`\n]*gpd\.runtime_cli[^`\n]*(?:--help|resume|cost)[^`\n]*`", tour_skill) is None
    assert re.search(r"`[^`\n]*gpd\.runtime_cli[^`\n]*(?:--help|resume|cost)[^`\n]*`", settings_skill) is None


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_real_installed_help_prompt_keeps_relaxed_technical_analysis_contract(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    help_prompt = _canonicalize_runtime_markdown(
        _read_runtime_command_prompt(target.parent, target, runtime, "help"),
        runtime=runtime,
    )

    assert "Project-aware technical-analysis lane:" in help_prompt
    assert "GPD/analysis/" in help_prompt
    assert "`gpd:graph` and `gpd:error-propagation` are separate commands and are not part of this relaxed current-workspace lane." in help_prompt
    assert "Usage: `gpd:dimensional-analysis results/01-SUMMARY.md`" in help_prompt
    assert "Usage: `gpd:limiting-cases results/01-SUMMARY.md`" in help_prompt
    assert "Usage: `gpd:numerical-convergence results/mesh-study.csv`" in help_prompt


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_real_installed_help_prompt_surfaces_bounded_write_paper_external_authoring_lane(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    help_prompt = _canonicalize_runtime_markdown(
        _read_runtime_command_prompt(target.parent, target, runtime, "help"),
        runtime=runtime,
    )

    assert_publication_lane_boundary_contract(help_prompt)
    assert "Usage: `gpd:write-paper --intake intake/write-paper-authoring-input.json`" in help_prompt


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_installed_prompt_contract_visibility_survives_adapter_projection(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    verifier = _read_runtime_agent_prompt(target, runtime, "gpd-verifier")
    executor = _read_runtime_agent_prompt(target, runtime, "gpd-executor")
    new_project = _read_runtime_command_prompt(target.parent, target, runtime, "new-project")
    plan_phase = _read_runtime_command_prompt(target.parent, target, runtime, "plan-phase")
    write_paper = _read_runtime_command_prompt(target.parent, target, runtime, "write-paper")
    plan_schema = (target / "get-physics-done" / "templates" / "plan-contract-schema.md").read_text(encoding="utf-8")
    execute_phase = _read_runtime_command_prompt(target.parent, target, runtime, "execute-phase")
    verify_work = _read_runtime_command_prompt(target.parent, target, runtime, "verify-work")

    _assert_installed_contract_visibility(
        verifier,
        executor,
        new_project,
        plan_phase,
        write_paper,
        plan_schema,
        execute_phase,
        verify_work,
        runtime=runtime,
    )
    assert "## Physics Stub Detection Patterns" not in verifier
    assert "Load on demand from `references/verification/examples/verifier-worked-examples.md`." in verifier


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_installed_executor_bootstrap_surface_defers_completion_only_materials(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    executor = _read_runtime_agent_prompt(target, runtime, "gpd-executor")
    bootstrap, _, _ = executor.partition("<summary_creation>")

    assert "templates/summary.md" not in bootstrap
    assert "templates/calculation-log.md" not in bootstrap
    assert "Order-of-Limits Awareness" not in bootstrap


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_installed_planner_bootstrap_surface_defers_execution_and_completion_materials(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    planner = _read_runtime_agent_prompt(target, runtime, "gpd-planner")
    bootstrap, separator, _ = planner.partition("On-demand references:")

    assert separator == "On-demand references:"
    assert "phase-prompt.md" in bootstrap
    assert "plan-contract-schema.md" in bootstrap
    assert "Read config.json for planning behavior settings." not in bootstrap
    assert "## Summary Template" not in bootstrap
    assert "Order-of-Limits Awareness" not in bootstrap
