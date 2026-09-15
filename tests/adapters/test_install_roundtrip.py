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
from gpd.adapters.copilot_cli import CopilotCliAdapter
from gpd.adapters.gemini import GeminiAdapter
from gpd.adapters.hermes import HermesAdapter
from gpd.adapters.install_utils import (
    convert_tool_references_in_body,
    expand_at_includes,
    rewrite_gpd_shell_line_to_runtime_bridge,
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
from gpd.registry import list_commands, load_agents_from_dir
from tests.adapters.projection_test_utils import (
    RUNTIME_NOTE_TAGS,
    StagedCommandProjectionCase,
    assert_compact_staged_command_shim,
    assert_no_unresolved_include_markers,
    assert_protocol_bundle_jit_shape,
    assert_runtime_bridge_targets_active_runtime,
    first_runnable_shell_command,
    has_compact_non_native_shim,
    has_help_bridge_shim_sentinel,
    has_staged_shim_sentinel,
    has_workflow_reference_shim_sentinel,
    iter_staged_command_projection_cases,
    raw_include_count,
    runnable_shell_lines,
    runtime_bridge_command,
    shell_fences,
    single_runtime_note_block,
    staged_command_protocol_bundle_fields,
    tag_count,
)
from tests.assertion_taxonomy_support import assert_prompt_contracts, semantic_anchor
from tests.doc_surface_contracts import assert_publication_lane_boundary_contract
from tests.prompt_metrics_support import MarkdownFence

REPO_GPD_ROOT = Path(__file__).resolve().parents[2] / "src" / "gpd"
COMMANDS_DIR = REPO_GPD_ROOT / "commands"
WORKFLOWS_DIR = REPO_GPD_ROOT / "specs" / "workflows"
RUNTIME_ALIAS_MAP = build_canonical_alias_map(adapter.tool_name_map for adapter in iter_adapters())
FULL_RUNTIME_MATRIX = tuple(descriptor.runtime_name for descriptor in iter_runtime_descriptors())
FLAT_COMMAND_RUNTIME_MATRIX = tuple(
    descriptor.runtime_name
    for descriptor in iter_runtime_descriptors()
    if descriptor.managed_install_surface.flat_command_globs
)
_SHARED_INSTALL = get_shared_install_metadata()
_INSTALL_CACHE: dict[tuple[str, tuple[str, ...]], Path] = {}
STAGED_COMMAND_PROJECTION_CASES = iter_staged_command_projection_cases(
    commands_dir=COMMANDS_DIR,
    workflows_dir=WORKFLOWS_DIR,
)
STAGED_CASE_BY_COMMAND = {case.command_name: case for case in STAGED_COMMAND_PROJECTION_CASES}
INSTALLED_PROJECTION_SMOKE_COMMANDS = (
    "help",
    "execute-phase",
    "new-project",
    "write-paper",
    "peer-review",
    "verify-work",
)
INSTALLED_STAGED_SMOKE_COMMANDS = ("execute-phase", "new-project", "write-paper", "verify-work")
INSTALLED_SHELL_SMOKE_COMMANDS = ("health",)
INSTALLED_PROTOCOL_BUNDLE_SMOKE_COMMANDS = ("execute-phase",)
VERIFIER_SCHEMA_INCLUDE_SUFFIXES = (
    "templates/verification-report.md",
    "templates/contract-results-schema.md",
    "references/shared/canonical-schema-discipline.md",
)
STAGED_HELPER_TARGET_WORKFLOWS = ("plan-phase", "execute-phase", "new-project", "write-paper")
INTERNAL_HELPER_LABEL_STEMS = (
    "stage",
    "phase",
    "validate",
    "return",
    "child-handoff",
    "apply-return-updates",
)
LOCAL_HELPER_TERM_RE = re.compile(
    r"\b(?:stage\s+field-access|phase\s+(?:checkpoint|closeout-readiness)|"
    r"validate\s+child-handoff|return\s+skeleton|apply-return-updates)\b"
)
GEMINI_RUNTIME_NOTE_BLOCK_RE = re.compile(
    r"<gemini_runtime_notes>\n.*?</gemini_runtime_notes>\n*",
    re.DOTALL,
)
GEMINI_SHELL_RUNTIME_NOTE_BLOCK_RE = re.compile(
    r"<gemini_shell_runtime_notes>\n.*?</gemini_shell_runtime_notes>\n*",
    re.DOTALL,
)
UNRESOLVED_INSTALL_SHAPE_MARKERS = (
    "{GPD_INSTALL_DIR}",
    "{GPD_CONFIG_DIR}",
    "{GPD_RUNTIME_FLAG}",
)
GEMINI_FORBIDDEN_INSTALLED_SHELL_FRAGMENTS = (
    "PROJECT_CONTRACT_JSON",
    "printf '%s\\n'",
    "mktemp",
    "<<",
    "if [ $? -ne 0 ]",
)
LEADING_SHELL_ASSIGNMENT_RE = re.compile(r"^[A-Z][A-Z0-9_]*=")
RAW_GPD_COMMAND_SUBSTITUTION_RE = re.compile(r"\$\([^)]*\bgpd(?:\s|$)")


@cache
def _opencode_rewritten_command_stems() -> tuple[str, ...]:
    return tuple(sorted(list_commands(), key=lambda stem: (-len(stem), stem)))


@cache
def _opencode_hyphenated_public_command_re() -> re.Pattern[str]:
    stems = "|".join(re.escape(stem) for stem in _opencode_rewritten_command_stems())
    return re.compile(rf"(?<![A-Za-z0-9_./:$-])gpd-(?P<stem>{stems})(?![A-Za-z0-9_-])")


@cache
def _opencode_canonical_public_command_re() -> re.Pattern[str]:
    stems = "|".join(re.escape(stem) for stem in _opencode_rewritten_command_stems())
    return re.compile(rf"(?<![A-Za-z0-9_./$-])/?gpd:(?P<stem>{stems})(?![A-Za-z0-9_-])")


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


def _staged_projection_case(command_name: str) -> StagedCommandProjectionCase:
    case = STAGED_CASE_BY_COMMAND.get(command_name)
    assert case is not None, f"{command_name} has no staged projection case"
    return case


def _first_stage_authority_suffix(command_name: str) -> str:
    native_include_paths = _staged_projection_case(command_name).native_include_paths
    assert native_include_paths, f"{command_name} staged projection case has no native include paths"
    return native_include_paths[0]


def _has_native_staged_command_include(text: str, command_name: str) -> bool:
    return raw_include_count(text, _first_stage_authority_suffix(command_name)) == 1


def _assert_native_staged_command_include(text: str, *, command_name: str) -> None:
    assert _has_native_staged_command_include(text, command_name)
    root_suffix = f"workflows/{command_name}.md"
    if _first_stage_authority_suffix(command_name) != root_suffix:
        assert raw_include_count(text, root_suffix) == 0


def _assert_runtime_command_label_visible(text: str, *, runtime: str, command_name: str) -> None:
    expected_label = get_adapter(runtime).format_command(command_name)
    assert expected_label in text, f"{runtime} {command_name} surface is missing {expected_label!r}"


def _runtime_public_helper_labels(runtime: str) -> tuple[str, ...]:
    return tuple(get_adapter(runtime).format_command(stem) for stem in INTERNAL_HELPER_LABEL_STEMS)


def _strip_gemini_runtime_note_blocks(prompt: str) -> str:
    prompt = GEMINI_RUNTIME_NOTE_BLOCK_RE.sub("", prompt)
    return GEMINI_SHELL_RUNTIME_NOTE_BLOCK_RE.sub("", prompt)


def _gemini_prompt_needs_generic_runtime_note(prompt: str, *, bridge_command: str) -> bool:
    note_free_prompt = _strip_gemini_runtime_note_blocks(prompt)
    return bridge_command in note_free_prompt or LOCAL_HELPER_TERM_RE.search(note_free_prompt) is not None


def _installed_workflow_text(target: Path, workflow_name: str) -> str:
    workflow_root = target / "get-physics-done" / "workflows"
    path = workflow_root / f"{workflow_name}.md"
    assert path.exists(), f"missing installed workflow authority: {path}"
    texts = [path.read_text(encoding="utf-8")]

    manifest_path = workflow_root / f"{workflow_name}-stage-manifest.json"
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        seen: set[Path] = set()
        for stage in payload.get("stages", []):
            if not isinstance(stage, dict):
                continue
            for key in ("mode_paths", "loaded_authorities"):
                values = stage.get(key, [])
                if not isinstance(values, list):
                    continue
                for value in values:
                    if not isinstance(value, str):
                        continue
                    prefix = f"workflows/{workflow_name}/"
                    if not value.startswith(prefix) or not value.endswith(".md"):
                        continue
                    stage_path = target / "get-physics-done" / value
                    if stage_path.exists() and stage_path not in seen:
                        seen.add(stage_path)
                        texts.append(stage_path.read_text(encoding="utf-8"))

    return "\n\n".join(texts)


def _command_or_workflow_authority_text(target: Path, command_prompt: str, runtime: str, workflow_name: str) -> str:
    if has_compact_non_native_shim(command_prompt) or (
        workflow_name == "help" and "renderer-backed local CLI help bridge" in command_prompt
    ):
        command_text = _canonicalize_runtime_markdown(command_prompt, runtime=runtime)
        workflow_text = _canonicalize_runtime_markdown(_installed_workflow_text(target, workflow_name), runtime=runtime)
        return command_text + "\n" + workflow_text
    return _canonicalize_runtime_markdown(command_prompt, runtime=runtime)


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

    if runtime == "copilot-cli":
        target = tmp_path / ".copilot"
        target.mkdir()
        CopilotCliAdapter().install(source_root, target)
        return target

    if runtime == "hermes":
        target = tmp_path / ".hermes"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir(exist_ok=True)
        HermesAdapter().install(source_root, target, is_global=False, skills_dir=skills)
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
    return runtime_bridge_command(runtime, target)


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
    if runtime in {"copilot-cli", "opencode"}:
        # Flat command runtimes rewrite public command references to hyphenated
        # names during install. Reverse that here for contract-assertion
        # purposes so tests can use the canonical `gpd:X` form regardless of
        # runtime. Stems come from the live command registry so new commands are
        # covered automatically while CLI tools or agent names like
        # `gpd-check-proof` stay hyphenated.
        content = _opencode_hyphenated_public_command_re().sub(
            lambda match: f"gpd:{match.group('stem')}",
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

    if runtime in {"copilot-cli", "opencode"}:
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

    if runtime in {"copilot-cli", "opencode"}:
        return (target / "command" / f"gpd-{command_name}.md").read_text(encoding="utf-8")

    if runtime == "hermes":
        return (tmp_path / "skills" / f"gpd-{command_name}" / "SKILL.md").read_text(encoding="utf-8")

    raise AssertionError(f"Unsupported runtime {runtime}")


def _flat_generated_command_manifest_policy(runtime: str):
    descriptor = get_runtime_descriptor(runtime)
    policies = tuple(
        policy
        for policy in descriptor.manifest_metadata_list_policies
        if policy.item_prefix == "gpd-" and policy.item_suffix == ".md"
    )

    assert len(policies) == 1, f"{runtime} should catalog exactly one flat generated-command manifest policy"
    return policies[0]


@cache
def _installed_command_names() -> tuple[str, ...]:
    return tuple(sorted(path.stem for path in (REPO_GPD_ROOT / "commands").glob("*.md")))


def _installed_command_kind(runtime: str) -> str:
    if runtime == "claude-code":
        return "native_md"
    if runtime == "codex":
        return "codex_skill"
    if runtime == "gemini":
        return "gemini_toml_prompt"
    if runtime == "copilot-cli":
        return "copilot_flat_md"
    if runtime == "opencode":
        return "opencode_flat_md"
    if runtime == "hermes":
        return "hermes_skill"
    raise AssertionError(f"Unsupported runtime {runtime}")


def _iter_installed_command_prompts(
    target: Path,
    runtime: str,
) -> tuple[tuple[str, str, str], ...]:
    kind = _installed_command_kind(runtime)
    return tuple(
        (
            command_name,
            _read_runtime_command_prompt(target.parent, target, runtime, command_name),
            kind,
        )
        for command_name in _installed_command_names()
    )


def _classify_installed_gemini_shell_fence(
    fence: MarkdownFence,
    *,
    bridge_command: str,
    policy_prefixes: tuple[str, ...],
) -> str:
    command = first_runnable_shell_command(fence)
    if command is None:
        return "non-runnable"
    if command.startswith(bridge_command):
        return "runnable-bridge"
    if command.startswith(tuple(prefix for prefix in policy_prefixes if prefix != bridge_command)):
        return "policy-static"
    return "unsupported"


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

    if runtime in {"copilot-cli", "opencode"}:
        return (target / "command" / "gpd-update.md").read_text(encoding="utf-8")

    if runtime == "hermes":
        return (tmp_path / "skills" / "gpd-update" / "SKILL.md").read_text(encoding="utf-8")

    raise AssertionError(f"Unsupported runtime {runtime}")


def _read_runtime_agent_prompt(target: Path, runtime: str, agent_name: str) -> str:
    if runtime in {"claude-code", "codex", "copilot-cli", "gemini", "opencode"}:
        return (target / "agents" / f"{agent_name}.md").read_text(encoding="utf-8")
    if runtime == "hermes":
        return (target.parent / "skills" / f"gpd-agent-{agent_name}" / "SKILL.md").read_text(encoding="utf-8")
    raise AssertionError(f"Unsupported runtime {runtime}")


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_installed_peer_review_prompt_keeps_publication_lane_boundary(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    peer_review = _read_runtime_command_prompt(target.parent, target, runtime, "peer-review")
    peer_review = _command_or_workflow_authority_text(target, peer_review, runtime, "peer-review")

    if has_staged_shim_sentinel(peer_review):
        case = _staged_projection_case("peer-review")
        assert_compact_staged_command_shim(
            peer_review,
            command_name=case.command_name,
            first_stage=case.first_stage_id,
            staged_loading_keys=case.staged_loading_keys,
        )
        return

    assert_prompt_contracts(
        peer_review,
        semantic_anchor(
            "installed peer-review keeps centralized publication and review roots visible",
            ("selected publication/review roots", "GPD-authored review artifacts"),
        ),
        semantic_anchor(
            "installed peer-review keeps manuscript-local artifact boundary visible",
            ("manuscript-local publication manifests", "resolved manuscript directory"),
        ),
    )


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_installed_verifier_prompt_surface_keeps_one_wrapper_and_stays_within_budget(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    verifier = _read_runtime_agent_prompt(target, runtime, "gpd-verifier")
    line_budget, char_budget = (500, 35_000)

    assert verifier.count("## Agent Requirements") == 1
    assert verifier.index("## Agent Requirements") < verifier.index("## Bootstrap Discipline")
    for include_suffix in VERIFIER_SCHEMA_INCLUDE_SUFFIXES:
        assert include_suffix in verifier
        assert raw_include_count(verifier, include_suffix) == 0
    assert "# Verification Report Template" not in verifier
    assert "# Contract Results Schema" not in verifier
    assert "# Canonical Schema Discipline" not in verifier
    assert "`gpd verification-report skeleton ... --write --body-file ... --validate contract`" in verifier
    assert "`gpd verification-report finalize ... --patch ... --body-file ... --validate contract`" in verifier
    assert "## Physics Stub Detection Patterns" not in verifier
    assert "Load on demand from `references/verification/examples/verifier-worked-examples.md`." in verifier
    assert len(verifier.splitlines()) <= line_budget
    assert len(verifier) <= char_budget


@pytest.mark.no_stable_hook_python
@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
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
        assert f'PATCH_META="{target.as_posix()}/{_SHARED_INSTALL.patches_dir_name}/backup-meta.json"' in content
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


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
@pytest.mark.parametrize("command_name", INSTALLED_STAGED_SMOKE_COMMANDS)
def test_installed_smoke_staged_command_surface_uses_native_include_or_compact_stage_shim(
    real_installed_repo_factory,
    runtime: str,
    command_name: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    prompt = _read_runtime_command_prompt(target.parent, target, runtime, command_name)
    descriptor = get_runtime_descriptor(runtime)
    case = _staged_projection_case(command_name)

    assert (_installed_workflow_text(target, command_name)).strip()
    assert_no_unresolved_include_markers(prompt, label=f"{runtime} {command_name}")
    _assert_runtime_command_label_visible(prompt, runtime=runtime, command_name=command_name)

    if descriptor.native_include_support:
        _assert_native_staged_command_include(prompt, command_name=command_name)
        assert f"<!-- [included: {command_name}.md] -->" not in prompt
        assert not has_staged_shim_sentinel(prompt)
        return

    assert raw_include_count(prompt, f"workflows/{command_name}.md") == 0
    assert f"<!-- [included: {command_name}.md] -->" not in prompt
    assert_compact_staged_command_shim(
        prompt,
        command_name=case.command_name,
        first_stage=case.first_stage_id,
        staged_loading_keys=case.staged_loading_keys,
        command_label=get_adapter(runtime).format_command(case.command_name),
    )
    assert not has_help_bridge_shim_sentinel(prompt)
    assert len(prompt) < 20_000


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
@pytest.mark.parametrize("command_name", INSTALLED_PROTOCOL_BUNDLE_SMOKE_COMMANDS)
def test_installed_smoke_staged_command_surfaces_protocol_bundle_jit_without_catalog_inline(
    real_installed_repo_factory,
    runtime: str,
    command_name: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    prompt = _read_runtime_command_prompt(target.parent, target, runtime, command_name)
    case = _staged_projection_case(command_name)

    assert_protocol_bundle_jit_shape(
        prompt,
        case=case,
        runtime=runtime,
        expected_bundle_fields=staged_command_protocol_bundle_fields(WORKFLOWS_DIR, command_name),
    )


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_installed_help_surface_uses_native_include_or_compact_help_bridge_shim(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    prompt = _read_runtime_command_prompt(target.parent, target, runtime, "help")
    descriptor = get_runtime_descriptor(runtime)

    assert (_installed_workflow_text(target, "help")).strip()
    assert_no_unresolved_include_markers(prompt, label=f"{runtime} help")
    _assert_runtime_command_label_visible(prompt, runtime=runtime, command_name="help")

    assert raw_include_count(prompt, "workflows/help.md") == 0
    assert "<!-- [included: help.md] -->" not in prompt
    assert not has_staged_shim_sentinel(prompt)
    assert "<current-help-command>" not in prompt
    assert "--raw help" in prompt
    assert "--raw help --all" in prompt
    assert "--raw help --command <name>" in prompt
    assert len(prompt) < 10_000

    if not descriptor.native_include_support:
        assert has_help_bridge_shim_sentinel(prompt)


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_installed_smoke_command_runtime_note_tags_match_runtime_container(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    kind = _installed_command_kind(runtime)

    for command_name in INSTALLED_PROJECTION_SMOKE_COMMANDS:
        prompt = _read_runtime_command_prompt(target.parent, target, runtime, command_name)
        label = f"{runtime}:{command_name}:{kind}"

        if runtime == "codex":
            assert tag_count(prompt, "codex_runtime_notes") == (1, 1), label
            assert tag_count(prompt, "gemini_runtime_notes") == (0, 0), label
            assert tag_count(prompt, "gemini_shell_runtime_notes") == (0, 0), label
            continue

        if runtime == "gemini":
            assert tag_count(prompt, "codex_runtime_notes") == (0, 0), label
            bridge_command = _expected_local_bridge_for_runtime(runtime, target)
            expected_runtime_note_count = (
                (1, 1) if _gemini_prompt_needs_generic_runtime_note(prompt, bridge_command=bridge_command) else (0, 0)
            )
            assert tag_count(prompt, "gemini_runtime_notes") == expected_runtime_note_count, label
            expected_shell_note_count = (1, 1) if shell_fences(prompt) else (0, 0)
            assert tag_count(prompt, "gemini_shell_runtime_notes") == expected_shell_note_count, label
            continue

        for tag in RUNTIME_NOTE_TAGS:
            assert tag_count(prompt, tag) == (0, 0), label
        if runtime == "opencode":
            assert prompt.count("<!-- Managed by Get Physics Done (GPD). -->") == 1, label


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_installed_command_surfaces_have_no_unresolved_install_shape(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)

    for command_name, prompt, kind in _iter_installed_command_prompts(target, runtime):
        label = f"{runtime}:{command_name}:{kind}"
        assert_no_unresolved_include_markers(prompt, label=label)
        offenders = [marker for marker in UNRESOLVED_INSTALL_SHAPE_MARKERS if marker in prompt]
        assert offenders == [], f"{label} contains unresolved install shape markers: {offenders}"


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_installed_command_surfaces_only_embed_active_runtime_bridge(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    smoke_commands = tuple(dict.fromkeys((*INSTALLED_PROJECTION_SMOKE_COMMANDS, *INSTALLED_SHELL_SMOKE_COMMANDS)))

    for command_name in smoke_commands:
        prompt = _read_runtime_command_prompt(target.parent, target, runtime, command_name)
        assert_runtime_bridge_targets_active_runtime(
            prompt,
            runtime=runtime,
            label=f"{runtime}:{command_name}:{_installed_command_kind(runtime)}",
        )


@pytest.mark.parametrize("runtime", FLAT_COMMAND_RUNTIME_MATRIX)
def test_installed_flat_command_manifest_metadata_is_catalog_driven_and_matches_command_files(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    policy = _flat_generated_command_manifest_policy(runtime)
    manifest = json.loads((target / "gpd-file-manifest.json").read_text(encoding="utf-8"))
    generated = manifest.get(policy.key)
    expected_generated = tuple(sorted(f"gpd-{command_name}.md" for command_name in _installed_command_names()))

    assert isinstance(generated, list), f"{runtime} manifest should include list metadata {policy.key!r}"
    assert all(isinstance(item, str) for item in generated)
    assert tuple(generated) == expected_generated
    assert {f"command/{file_name}" for file_name in generated} <= set(manifest["files"])
    assert all((target / "command" / file_name).is_file() for file_name in generated)

    foreign_flat_metadata_keys = {
        other_policy.key
        for descriptor in iter_runtime_descriptors()
        if descriptor.runtime_name != runtime and descriptor.managed_install_surface.flat_command_globs
        for other_policy in descriptor.manifest_metadata_list_policies
        if other_policy.item_prefix == "gpd-" and other_policy.item_suffix == ".md"
    }
    assert foreign_flat_metadata_keys.isdisjoint(manifest)


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_installed_smoke_command_shell_fences_use_runtime_bridge_or_public_cli(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    bridge_command = _expected_local_bridge_for_runtime(runtime, target)
    kind = _installed_command_kind(runtime)
    offenders: list[str] = []

    for command_name in INSTALLED_SHELL_SMOKE_COMMANDS:
        prompt = _read_runtime_command_prompt(target.parent, target, runtime, command_name)
        fences = shell_fences(prompt)
        if not fences:
            continue
        for fence in fences:
            for line in runnable_shell_lines(fence):
                rewritten = rewrite_gpd_shell_line_to_runtime_bridge(line, bridge_command)
                if rewritten != line:
                    offenders.append(
                        f"{runtime}:{command_name}:{kind}: lines {fence.start_line}-{fence.end_line}: {line!r}"
                    )
                if RAW_GPD_COMMAND_SUBSTITUTION_RE.search(line):
                    offenders.append(
                        f"{runtime}:{command_name}:{kind}: lines {fence.start_line}-{fence.end_line}: "
                        f"raw gpd command substitution {line!r}"
                    )

    assert offenders == []


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_installed_target_workflow_helper_calls_stay_local_cli_not_runtime_labels(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    bridge_command = _expected_local_bridge_for_runtime(runtime, target)
    public_helper_labels = _runtime_public_helper_labels(runtime)
    offenders: list[str] = []
    helper_reference_count = 0

    for workflow_name in STAGED_HELPER_TARGET_WORKFLOWS:
        workflow_text = _installed_workflow_text(target, workflow_name)
        helper_reference_count += len(LOCAL_HELPER_TERM_RE.findall(workflow_text))

        for line_number, line in enumerate(workflow_text.splitlines(), start=1):
            if not LOCAL_HELPER_TERM_RE.search(line):
                continue
            for public_label in public_helper_labels:
                if public_label in line:
                    offenders.append(
                        f"{runtime}:{workflow_name}: line {line_number}: internal helper surfaced as {public_label!r}"
                    )

        for fence in shell_fences(workflow_text):
            for line in runnable_shell_lines(fence):
                if not LOCAL_HELPER_TERM_RE.search(line):
                    continue
                rewritten = rewrite_gpd_shell_line_to_runtime_bridge(line, bridge_command)
                if rewritten != line:
                    offenders.append(
                        f"{runtime}:{workflow_name}: lines {fence.start_line}-{fence.end_line}: "
                        f"helper shell line was not bridged: {line!r}"
                    )
                for public_label in public_helper_labels:
                    if public_label in line:
                        offenders.append(
                            f"{runtime}:{workflow_name}: lines {fence.start_line}-{fence.end_line}: "
                            f"helper shell line used runtime label {public_label!r}"
                        )

    assert helper_reference_count > 0
    assert offenders == []


def test_installed_gemini_toml_policy_and_shell_fence_classification(real_installed_repo_factory) -> None:
    target = real_installed_repo_factory("gemini")
    bridge_command = _expected_local_bridge_for_runtime("gemini", target)
    policy = tomllib.loads((target / "policies" / "gpd-auto-edit.toml").read_text(encoding="utf-8"))
    rules = policy.get("rule")

    assert isinstance(rules, list) and len(rules) == 1
    rule = rules[0]
    assert rule["toolName"] == "run_shell_command"
    assert rule["decision"] == "allow"
    assert rule["modes"] == ["autoEdit"]
    assert rule["allowRedirection"] is True
    assert "allow_redirection" not in rule

    raw_policy_prefixes = rule["commandPrefix"]
    assert isinstance(raw_policy_prefixes, list)
    policy_prefixes = tuple(prefix for prefix in raw_policy_prefixes if isinstance(prefix, str))
    assert len(policy_prefixes) == len(raw_policy_prefixes)
    assert policy_prefixes[0] == bridge_command

    offenders: list[str] = []
    shell_note_commands = 0
    kind = _installed_command_kind("gemini")
    for command_name in INSTALLED_SHELL_SMOKE_COMMANDS:
        prompt = _read_runtime_command_prompt(target.parent, target, "gemini", command_name)
        label = f"gemini:{command_name}:{kind}"
        fences = shell_fences(prompt)
        assert fences, f"{label} should expose a shell fence"

        shell_note_commands += 1
        shell_note = single_runtime_note_block(prompt, "gemini_shell_runtime_notes", label=label)
        for prefix in policy_prefixes:
            assert f"`{prefix}`" in shell_note, f"{label} shell notes omit policy prefix {prefix!r}"

        for fence in fences:
            classification = _classify_installed_gemini_shell_fence(
                fence,
                bridge_command=bridge_command,
                policy_prefixes=policy_prefixes,
            )
            first_command = first_runnable_shell_command(fence)
            if classification not in {"runnable-bridge", "policy-static"}:
                offenders.append(
                    f"{label}: lines {fence.start_line}-{fence.end_line}: "
                    f"{classification} first command {first_command!r}"
                )
                continue
            assert first_command is not None
            if not first_command.startswith(policy_prefixes):
                offenders.append(
                    f"{label}: lines {fence.start_line}-{fence.end_line}: "
                    f"first command is outside installed policy prefixes: {first_command!r}"
                )
            for fragment in GEMINI_FORBIDDEN_INSTALLED_SHELL_FRAGMENTS:
                if fragment in fence.body:
                    offenders.append(f"{label}: lines {fence.start_line}-{fence.end_line}: contains {fragment!r}")
            for line in runnable_shell_lines(fence):
                if LEADING_SHELL_ASSIGNMENT_RE.match(line):
                    offenders.append(f"{label}: lines {fence.start_line}-{fence.end_line}: leading assignment {line!r}")

    assert shell_note_commands > 0
    assert offenders == []


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

    def test_generated_skills_stay_within_budget_and_basic_hygiene(self, installed: tuple[Path, Path]) -> None:
        """Generated Codex skills stay bounded and have no unresolved install syntax."""
        _, skills = installed
        skill_paths = sorted(skills.glob("gpd-*/SKILL.md"))

        assert skill_paths
        for skill_md in skill_paths:
            content = skill_md.read_text(encoding="utf-8")
            line_count = len(content.splitlines())
            char_count = len(content)

            if has_staged_shim_sentinel(content):
                assert line_count <= 300, f"{skill_md.parent.name} staged shim has {line_count} lines"
                assert char_count <= 20_000, f"{skill_md.parent.name} staged shim has {char_count} chars"
            assert line_count <= 2_700, f"{skill_md.parent.name} has {line_count} lines"
            assert char_count <= 145_000, f"{skill_md.parent.name} has {char_count} chars"
            assert content.count("<codex_runtime_notes>") == 1, skill_md.parent.name
            assert content.count("</codex_runtime_notes>") == 1, skill_md.parent.name
            assert content.count("<!-- Managed by Get Physics Done (GPD). -->") == 1, skill_md.parent.name
            assert "{GPD_INSTALL_DIR}" not in content, skill_md.parent.name
            assert "@{GPD_INSTALL_DIR}" not in content, skill_md.parent.name
            assert "/gpd:" not in content, skill_md.parent.name

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


def test_opencode_command_projection_rewrites_live_public_command_prefixes(real_installed_repo_factory) -> None:
    target = real_installed_repo_factory("opencode")
    command_paths = sorted((target / "command").glob("gpd-*.md"))

    assert {path.stem.removeprefix("gpd-") for path in command_paths} == set(_opencode_rewritten_command_stems())
    for command_path in command_paths:
        content = command_path.read_text(encoding="utf-8")
        match = _opencode_canonical_public_command_re().search(content)
        assert match is None, f"{command_path.name} still uses OpenCode-incompatible {match.group(0)!r}"


def test_help_like_skills_keep_canonical_local_cli_language(tmp_path: Path) -> None:
    """Codex skills keep canonical local CLI names in prose even when shell steps bridge."""
    _install_real_repo_for_runtime(tmp_path, "codex")
    skills = tmp_path / "skills"
    target = tmp_path / ".codex"
    help_skill = (skills / "gpd-help" / "SKILL.md").read_text(encoding="utf-8")
    tour_skill = (skills / "gpd-tour" / "SKILL.md").read_text(encoding="utf-8")
    settings_skill = (skills / "gpd-settings" / "SKILL.md").read_text(encoding="utf-8")
    help_reference = (
        _installed_workflow_text(target, "help") if has_help_bridge_shim_sentinel(help_skill) else help_skill
    )
    settings_reference = (
        _installed_workflow_text(target, "settings")
        if has_workflow_reference_shim_sentinel(settings_skill)
        else settings_skill
    )

    assert (
        "Use `gpd --help` to inspect the executable local install/readiness/permissions/diagnostics surface directly."
        in help_reference
    )
    assert "Recovery ladder: use `gpd resume` for the current-workspace read-only recovery snapshot." in help_reference
    assert "- `gpd cost`" in help_reference
    assert "The normal terminal is where you install GPD, run `gpd --help`, and run" in tour_skill
    assert "`gpd resume` is the normal-terminal recovery step for reopening the right" in tour_skill
    assert "use `gpd --help` when you need the broader local CLI entrypoint" in settings_reference
    assert (
        "use `gpd cost` after runs for advisory local usage / cost, optional USD budget guardrails, and the current profile tier mix"
        in settings_reference
    )
    assert re.search(r"`[^`\n]*gpd\.runtime_cli[^`\n]*(?:--help|resume|cost)[^`\n]*`", help_skill) is None
    assert re.search(r"`[^`\n]*gpd\.runtime_cli[^`\n]*(?:--help|resume|cost)[^`\n]*`", tour_skill) is None
    assert re.search(r"`[^`\n]*gpd\.runtime_cli[^`\n]*(?:--help|resume|cost)[^`\n]*`", settings_skill) is None


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_real_installed_help_prompt_keeps_relaxed_technical_analysis_contract(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    raw_help_prompt = _read_runtime_command_prompt(target.parent, target, runtime, "help")
    help_prompt = _command_or_workflow_authority_text(target, raw_help_prompt, runtime, "help")

    assert "Project-aware technical-analysis lane:" in help_prompt
    assert "GPD/analysis/" in help_prompt
    assert (
        "`gpd:graph` and `gpd:error-propagation` are separate commands and are not part of this relaxed current-workspace lane."
        in help_prompt
    )
    assert "`gpd:dimensional-analysis results/01-SUMMARY.md`" in help_prompt
    assert "`gpd:limiting-cases results/01-SUMMARY.md`" in help_prompt
    assert "`gpd:numerical-convergence results/mesh-study.csv`" in help_prompt


@pytest.mark.parametrize("runtime", FULL_RUNTIME_MATRIX)
def test_real_installed_help_prompt_surfaces_bounded_write_paper_external_authoring_lane(
    real_installed_repo_factory,
    runtime: str,
) -> None:
    target = real_installed_repo_factory(runtime)
    raw_help_prompt = _read_runtime_command_prompt(target.parent, target, runtime, "help")
    help_prompt = _command_or_workflow_authority_text(target, raw_help_prompt, runtime, "help")

    assert_publication_lane_boundary_contract(help_prompt)
    assert "`gpd:write-paper --intake intake/write-paper-authoring-input.json`" in help_prompt


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
    assert_prompt_contracts(
        bootstrap,
        semantic_anchor(
            "installed planner bootstrap names the late-loaded plan template and carried schema",
            (
                "phase-prompt.md",
                "plan-contract-schema.md",
                "before plan frontmatter",
            ),
        ),
    )
    assert "@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md" not in bootstrap
    if "# PLAN Contract Schema" in bootstrap:
        assert bootstrap.count("# PLAN Contract Schema") == 1
    assert "Read config.json for planning behavior settings." not in bootstrap
    assert "## Summary Template" not in bootstrap
    assert "Order-of-Limits Awareness" not in bootstrap
