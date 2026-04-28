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
RESEARCH_REFERENCES_DIR = SPECS_DIR / "references" / "research"
TEMPLATES_DIR = SPECS_DIR / "templates"

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


def test_model_facing_prompts_do_not_use_informal_gap_markers() -> None:
    for directory in MODEL_FACING_DIRS:
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            assert "???" not in text, f"{path.relative_to(REPO_ROOT)} still contains an informal ??? marker"


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


def test_researcher_shared_does_not_label_arxiv_as_peer_reviewed() -> None:
    text = (RESEARCH_REFERENCES_DIR / "researcher-shared.md").read_text(encoding="utf-8")
    arxiv_search_rows = [line for line in text.splitlines() if "web_search (arXiv)" in line]

    assert len(arxiv_search_rows) == 1
    assert "HIGH for discovery; publication status varies" in arxiv_search_rows[0]
    assert all("peer-reviewed" not in line.lower() for line in arxiv_search_rows)


def test_learned_pattern_template_uses_install_dir_reference_not_legacy_alias() -> None:
    text = (TEMPLATES_DIR / "learned-pattern.md").read_text(encoding="utf-8")

    legacy_alias = "@" + "get-physics-done"
    assert legacy_alias not in text
    assert "{GPD_INSTALL_DIR}/references/verification/core/verification-core.md" in text


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


def test_error_propagation_command_wrapper_delegates_mechanics_to_workflow() -> None:
    text = (COMMANDS_DIR / "error-propagation.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/workflows/error-propagation.md" in text
    assert "The workflow owns project bootstrap, context validation, dependency tracing" in text
    assert "S_i = (x_i / f)" not in text
    assert "np.random.normal" not in text
    assert "Error Budget Table" not in text


def test_error_patterns_command_wrapper_delegates_category_vocabulary_to_workflow() -> None:
    text = (COMMANDS_DIR / "error-patterns.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/workflows/error-patterns.md" in text
    assert "same-named workflow owns category validation" in text
    assert "Categories:" not in text
    for stale_category in ("`sign`", "`factor`", "`convention`", "`numerical`", "`approximation`"):
        assert stale_category not in text
    for removed_category in ("`boundary`", "`gauge`", "`combinatorial`"):
        assert removed_category not in text


def test_debug_command_wrapper_delegates_mechanics_to_workflow() -> None:
    text = (COMMANDS_DIR / "debug.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/workflows/debug.md" in text
    assert "The workflow owns workspace bootstrap, active-session handling, symptom gathering" in text
    assert 'subagent_type="gpd-debugger"' in text
    assert "gpd_return.status" in text
    assert "Use ask_user for each." not in text
    assert "Spawn Fresh Continuation agent" not in text
    assert "Check Active Sessions" not in text


def test_complete_milestone_command_wrapper_delegates_mechanics_to_workflow() -> None:
    text = (COMMANDS_DIR / "complete-milestone.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/workflows/complete-milestone.md" in text
    assert "@{GPD_INSTALL_DIR}/templates/milestone.md" in text
    assert "@{GPD_INSTALL_DIR}/templates/milestone-archive.md" in text
    assert "The workflow owns audit/readiness checks" in text
    assert "This wrapper owns the public command surface and required version argument." in text
    assert "If audit status is `gaps_found`" not in text
    assert "Stage: MILESTONES.md" not in text
    assert "Ask about pushing tag" not in text


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


def test_review_knowledge_command_delegates_schema_surfaces_to_workflow() -> None:
    text = (COMMANDS_DIR / "review-knowledge.md").read_text(encoding="utf-8")
    workflow = (WORKFLOWS_DIR / "review-knowledge.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/workflows/review-knowledge.md" in text
    assert "The workflow owns schema loading" in text
    assert "@{GPD_INSTALL_DIR}/templates/knowledge-schema.md" not in text
    assert "@{GPD_INSTALL_DIR}/templates/knowledge.md" not in text
    assert "@{GPD_INSTALL_DIR}/references/shared/canonical-schema-discipline.md" not in text
    assert "@{GPD_INSTALL_DIR}/templates/knowledge-schema.md" in workflow
    assert "@{GPD_INSTALL_DIR}/templates/knowledge.md" in workflow
    assert "@{GPD_INSTALL_DIR}/references/shared/canonical-schema-discipline.md" in workflow


def test_legacy_publication_contract_stubs_are_removed_in_favor_of_canonical_files() -> None:
    canonical_files = (
        "publication-review-round-artifacts.md",
        "publication-response-artifacts.md",
    )
    removed_files = (
        "review-round-artifact-contract.md",
        "response-artifact-contract.md",
    )

    for filename in canonical_files:
        assert (PUBLICATION_REFERENCES_DIR / filename).is_file()

    for filename in removed_files:
        assert not (PUBLICATION_REFERENCES_DIR / filename).exists()
