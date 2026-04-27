"""Assert command prompts stay free of cross-runtime boilerplate."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
SPECS_DIR = REPO_ROOT / "src" / "gpd" / "specs"
WORKFLOWS_DIR = SPECS_DIR / "workflows"
PUBLICATION_REFERENCES_DIR = SPECS_DIR / "references" / "publication"

LEGACY_COMMENT_FRAGMENTS = (
    "Tool names and @ includes are platform-specific.",
    "Allowed-tools are runtime-specific.",
    "Tool names and @ includes are runtime-specific.",
    "installer rewrites paths for your runtime.",
)

MODEL_FACING_DIRS = (COMMANDS_DIR, AGENTS_DIR)
FRESH_CONTEXT_MODEL_DIRS = (COMMANDS_DIR, AGENTS_DIR, SPECS_DIR)

UNRESOLVED_PLACEHOLDER_RE = re.compile(r"(?:^|\n)\s*(?:<!--\s*)?(?:TODO|FIXME|PLACEHOLDER)(?:\b|:)")

LEGACY_BACKCOMPAT_WORDING = (
    "backcompat",
    "back-compat",
    "backward compatibility",
    "backwards compatibility",
)
STALE_MODEL_FACING_WORDING = (
    "runtime-installer",
    "test alignment",
    "regression guardrail",
)


def test_command_sources_do_not_keep_runtime_boilerplate_html_comments() -> None:
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for fragment in LEGACY_COMMENT_FRAGMENTS:
            assert fragment not in text, f"{path.relative_to(REPO_ROOT)} still contains: {fragment}"


def test_command_sources_use_runtime_neutral_fresh_context_wording() -> None:
    for directory in FRESH_CONTEXT_MODEL_DIRS:
        for path in sorted(directory.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            assert "/clear" not in text, f"{path.relative_to(REPO_ROOT)} still hardcodes runtime reset wording"


def test_shared_prompt_surfaces_use_runtime_installed_command_wording_not_raw_skill_calls() -> None:
    for directory in FRESH_CONTEXT_MODEL_DIRS:
        for path in sorted(directory.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            assert "Skill(" not in text, f"{path.relative_to(REPO_ROOT)} still uses raw Skill(...) syntax"


def test_model_facing_prompts_do_not_ship_unresolved_placeholders() -> None:
    for directory in MODEL_FACING_DIRS:
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            assert not UNRESOLVED_PLACEHOLDER_RE.search(text), (
                f"{path.relative_to(REPO_ROOT)} still contains an unresolved placeholder marker"
            )


def test_model_facing_prompts_do_not_use_legacy_backcompat_wording() -> None:
    for directory in MODEL_FACING_DIRS:
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8").lower()
            for phrase in LEGACY_BACKCOMPAT_WORDING:
                assert phrase not in text, f"{path.relative_to(REPO_ROOT)} still contains {phrase}"


def test_model_facing_prompts_do_not_explain_test_or_installer_scaffolding() -> None:
    for directory in MODEL_FACING_DIRS:
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8").lower()
            for phrase in STALE_MODEL_FACING_WORDING:
                assert phrase not in text, f"{path.relative_to(REPO_ROOT)} still contains {phrase}"


def test_parameter_sweep_command_wrapper_delegates_mechanics_to_workflow() -> None:
    text = (COMMANDS_DIR / "parameter-sweep.md").read_text(encoding="utf-8")

    assert "gpd --raw validate command-context parameter-sweep" in text
    assert "@{GPD_INSTALL_DIR}/workflows/parameter-sweep.md" in text
    assert "same-named workflow owns sweep design" in text
    assert "GPD/sweeps/" in text
    assert "GPD/phases/XX-sweep" in text
    assert "artifacts/" in text
    assert "np.linspace" not in text
    assert "adaptive_sweep" not in text
    assert "Grid Type" not in text


def test_digest_knowledge_command_wrapper_delegates_mechanics_to_workflow() -> None:
    text = (COMMANDS_DIR / "digest-knowledge.md").read_text(encoding="utf-8")

    assert "gpd --raw validate command-context digest-knowledge" in text
    assert "@{GPD_INSTALL_DIR}/workflows/digest-knowledge.md" in text
    assert "same-named workflow owns classification" in text
    assert "current workspace's `GPD/knowledge/` tree" in text
    assert "External source material may live anywhere." in text
    assert "gpd validate artifact-text <path> --output <txt-path>" in text
    assert "INIT=$(gpd --raw init progress" not in text
    assert "ls GPD/knowledge/*.md" not in text


def test_autonomous_surfaces_use_installed_command_wording_not_raw_skill_calls() -> None:
    for path in (COMMANDS_DIR / "autonomous.md", WORKFLOWS_DIR / "autonomous.md"):
        text = path.read_text(encoding="utf-8")
        assert "Skill(" not in text, path.relative_to(REPO_ROOT)

    workflow = (WORKFLOWS_DIR / "autonomous.md").read_text(encoding="utf-8")
    for command_name in (
        "gpd:write-paper",
        "gpd:plan-phase",
        "gpd:execute-phase",
        "gpd:verify-work",
        "gpd:audit-milestone",
        "gpd:complete-milestone",
    ):
        assert f"runtime-installed `{command_name}` command" in workflow


def test_legacy_publication_contract_stubs_are_not_keyword_loadable_redirect_prompts() -> None:
    for filename, canonical in (
        ("review-round-artifact-contract.md", "publication-review-round-artifacts.md"),
        ("response-artifact-contract.md", "publication-response-artifacts.md"),
    ):
        text = (PUBLICATION_REFERENCES_DIR / filename).read_text(encoding="utf-8")
        assert "load_when:" not in text
        assert "Compatibility entry point" not in text
        assert "authoritative source now lives" not in text
        assert canonical in text
