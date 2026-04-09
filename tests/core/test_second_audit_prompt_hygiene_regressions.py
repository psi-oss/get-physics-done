from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes

WORKFLOWS_DIR = Path("src/gpd/specs/workflows")
COMMANDS_DIR = Path("src/gpd/commands")
AGENTS_DIR = Path("src/gpd/agents")
REFERENCES_DIR = Path("src/gpd/specs/references")
TEMPLATES_DIR = Path("src/gpd/specs/templates")
PUBLICATION_SHARED_PREFLIGHT = TEMPLATES_DIR / "paper" / "publication-manuscript-root-preflight.md"
PUBLICATION_BOOTSTRAP_PREFLIGHT = REFERENCES_DIR / "publication" / "publication-bootstrap-preflight.md"
PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE = (
    "@{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md"
)
PUBLICATION_ROUND_ARTIFACTS_INCLUDE = (
    "@{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md"
)
PUBLICATION_RESPONSE_ARTIFACTS_INCLUDE = (
    "@{GPD_INSTALL_DIR}/references/publication/publication-response-artifacts.md"
)
PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE = (
    "@{GPD_INSTALL_DIR}/references/publication/publication-response-writer-handoff.md"
)
PUBLICATION_REVIEW_RELIABILITY_INCLUDE = "@{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md"
OWNED_COMMANDS = (
    COMMANDS_DIR / "debug.md",
    COMMANDS_DIR / "research-phase.md",
    COMMANDS_DIR / "literature-review.md",
    COMMANDS_DIR / "explain.md",
    COMMANDS_DIR / "respond-to-referees.md",
    COMMANDS_DIR / "write-paper.md",
)
FRESH_CONTEXT_PHRASE_EXEMPTIONS = {
    COMMANDS_DIR / "write-paper.md",
}


def test_help_resume_boundary_note_is_concise_and_contract_aligned() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8").lower()
    expanded_help_workflow = expand_at_includes(
        (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8"),
        Path("src/gpd"),
        "/runtime/",
    ).lower()

    assert help_workflow.count("@{gpd_install_dir}/references/orchestration/resume-vocabulary.md") == 1
    assert expanded_help_workflow.count("compatibility-only intake fields stay internal") == 1
    assert "canonical continuation fields define the public resume vocabulary" in expanded_help_workflow
    assert "public top-level resume vocabulary" not in help_workflow


def test_transition_workflow_stays_runtime_neutral() -> None:
    transition_workflow = (WORKFLOWS_DIR / "transition.md").read_text(encoding="utf-8")

    assert "slash_command(" not in transition_workflow
    assert "installed runtime command surface" in transition_workflow


def test_quick_command_and_workflow_keep_the_project_gate_and_drop_the_custom_state_table() -> None:
    quick_command = (COMMANDS_DIR / "quick.md").read_text(encoding="utf-8")
    quick_workflow = (WORKFLOWS_DIR / "quick.md").read_text(encoding="utf-8")

    assert "context_mode: project-required" in quick_command
    assert "Quick Tasks Completed" not in quick_command
    assert "Quick Tasks Completed" not in quick_workflow
    assert "Records completion through structured `gpd state` commands" in quick_command
    assert "project_exists" in quick_workflow
    assert "**Project Exists:** {project_exists}" in quick_workflow
    assert "Quick tasks can run mid-phase and do NOT require ROADMAP.md." in quick_workflow
    assert "They still require an initialized project workspace with `GPD/PROJECT.md` and the `GPD/` directory." in quick_workflow
    assert "They only need `GPD/` to exist for directory structure." not in quick_workflow


def test_branch_hypothesis_and_transition_workflows_keep_state_updates_structured() -> None:
    branch_hypothesis = (WORKFLOWS_DIR / "branch-hypothesis.md").read_text(encoding="utf-8")
    transition_workflow = (WORKFLOWS_DIR / "transition.md").read_text(encoding="utf-8")

    assert "Active Hypothesis" not in branch_hypothesis
    assert "file_edit tool" not in branch_hypothesis
    assert "gpd state add-decision" in branch_hypothesis
    assert "save_state_markdown" not in transition_workflow
    assert "STATE.md directly" not in transition_workflow
    assert "gpd state update-progress" in transition_workflow
    assert "gpd state update" in transition_workflow
    assert "gpd state patch" in transition_workflow


def test_write_paper_workflow_drops_authoring_note_placeholders() -> None:
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")

    assert "Default bootstrap wording:" not in write_paper


def test_publication_commands_keep_shared_manuscript_root_preflight_out_of_wrappers() -> None:
    shared_preflight = PUBLICATION_SHARED_PREFLIGHT.read_text(encoding="utf-8")
    bootstrap_preflight = PUBLICATION_BOOTSTRAP_PREFLIGHT.read_text(encoding="utf-8")

    assert (
        "strict preflight reads `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and "
        "`reproducibility-manifest.json` from the resolved manuscript directory itself."
        in shared_preflight
    )
    assert "Do not use ad hoc wildcard discovery or first-match filename scans." in shared_preflight
    assert "bibliography_audit_clean" in shared_preflight
    assert "reproducibility_ready" in shared_preflight
    assert "publication-manuscript-root-preflight.md" in bootstrap_preflight
    assert "publication-review-round-artifacts.md" in bootstrap_preflight
    assert "publication-response-artifacts.md" in bootstrap_preflight

    for path in (
        COMMANDS_DIR / "write-paper.md",
        COMMANDS_DIR / "peer-review.md",
        COMMANDS_DIR / "respond-to-referees.md",
        COMMANDS_DIR / "arxiv-submission.md",
    ):
        text = path.read_text(encoding="utf-8")
        assert text.count(PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE) == 0, path
        assert text.count(PUBLICATION_ROUND_ARTIFACTS_INCLUDE) == 0, path
        assert text.count(PUBLICATION_RESPONSE_ARTIFACTS_INCLUDE) == 0, path
        assert text.count(PUBLICATION_REVIEW_RELIABILITY_INCLUDE) == 0, path

    for path in (
        WORKFLOWS_DIR / "write-paper.md",
        WORKFLOWS_DIR / "peer-review.md",
        WORKFLOWS_DIR / "respond-to-referees.md",
        WORKFLOWS_DIR / "arxiv-submission.md",
    ):
        text = path.read_text(encoding="utf-8")
        expected_bootstrap_counts = {
            "write-paper.md": 1,
            "peer-review.md": 0,
            "respond-to-referees.md": 1,
            "arxiv-submission.md": 1,
        }
        assert text.count(PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE) == expected_bootstrap_counts[path.name], path
        expected_round_counts = {
            "write-paper.md": 1,
            "peer-review.md": 0,
            "respond-to-referees.md": 0,
            "arxiv-submission.md": 1,
        }
        expected_response_artifact_counts = {}
        expected_response_handoff_counts = {
            "write-paper.md": 1,
            "respond-to-referees.md": 1,
        }

        assert text.count(PUBLICATION_ROUND_ARTIFACTS_INCLUDE) >= expected_round_counts[path.name], path
        if path.name in expected_response_artifact_counts:
            assert text.count(PUBLICATION_RESPONSE_ARTIFACTS_INCLUDE) >= expected_response_artifact_counts[path.name], path
        else:
            assert PUBLICATION_RESPONSE_ARTIFACTS_INCLUDE not in text, path
        if path.name in expected_response_handoff_counts:
            assert text.count(PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE) >= expected_response_handoff_counts[path.name], path
        else:
            assert PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE not in text, path
        if path.name in {"peer-review.md", "respond-to-referees.md", "arxiv-submission.md"}:
            assert text.count(PUBLICATION_REVIEW_RELIABILITY_INCLUDE) >= 1, path
        else:
            assert PUBLICATION_REVIEW_RELIABILITY_INCLUDE not in text, path


def test_literature_and_research_commands_trim_inline_methodology_blocks() -> None:
    literature = (COMMANDS_DIR / "literature-review.md").read_text(encoding="utf-8")
    research_phase = (COMMANDS_DIR / "research-phase.md").read_text(encoding="utf-8")

    assert "Run the literature-review workflow as a thin wrapper" in literature
    assert "Follow `@{GPD_INSTALL_DIR}/workflows/literature-review.md` exactly." in literature
    assert "A physics literature review is not a bibliography." not in literature
    assert "Method A lineage: paper1 -> paper2 -> paper3" not in literature
    assert "What do I not know that I don't know?" not in research_phase
    assert "What mathematical methods and computational tools form the standard approach?" not in research_phase
    assert "Research depth follows the workflow-owned `research_mode`." in research_phase
    assert "Active Anchor Registry" not in literature


def test_shared_context_budget_guidance_stays_runtime_neutral() -> None:
    owned_surfaces = (
        COMMANDS_DIR / "debug.md",
        COMMANDS_DIR / "research-phase.md",
        COMMANDS_DIR / "literature-review.md",
        COMMANDS_DIR / "respond-to-referees.md",
        WORKFLOWS_DIR / "plan-phase.md",
        WORKFLOWS_DIR / "execute-phase.md",
        WORKFLOWS_DIR / "execute-plan.md",
        REFERENCES_DIR / "orchestration" / "context-budget.md",
    )

    for path in owned_surfaces:
        text = path.read_text(encoding="utf-8").lower()
        assert "200k" not in text, path


def test_owned_commands_keep_a_single_concise_subagent_rationale() -> None:
    for path in OWNED_COMMANDS:
        text = path.read_text(encoding="utf-8")
        assert text.count("Why subagent:") == 1, path
        if path in FRESH_CONTEXT_PHRASE_EXEMPTIONS:
            assert "Fresh context" not in text, path
        else:
            assert text.count("Fresh context") == 1, path


def test_research_phase_command_drops_dead_command_local_mode_labels() -> None:
    research_phase = (COMMANDS_DIR / "research-phase.md").read_text(encoding="utf-8")

    assert "Research modes: literature (default), feasibility, methodology, comparison." not in research_phase
    assert "Mode: literature" not in research_phase
    assert "Research depth follows the workflow-owned `research_mode`." in research_phase


def test_write_paper_command_defers_the_route_list_to_the_workflow() -> None:
    write_paper = (COMMANDS_DIR / "write-paper.md").read_text(encoding="utf-8")
    write_paper_workflow = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")

    assert "Routes to the write-paper workflow:" not in write_paper
    assert "@{GPD_INSTALL_DIR}/workflows/write-paper.md" in write_paper
    assert PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE in write_paper_workflow
    assert PUBLICATION_ROUND_ARTIFACTS_INCLUDE in write_paper_workflow
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-response-writer-handoff.md" in write_paper_workflow


def test_debug_workflow_path_note_is_not_self_contradictory() -> None:
    debug_workflow = (WORKFLOWS_DIR / "debug.md").read_text(encoding="utf-8")

    assert "Debug files use the `GPD/debug/` path." in debug_workflow
    assert "hidden directory with leading dot" not in debug_workflow


def test_debugger_session_paths_keep_the_active_and_resolved_lifecycles_separate() -> None:
    debug_command = (COMMANDS_DIR / "debug.md").read_text(encoding="utf-8")
    debug_agent = (AGENTS_DIR / "gpd-debugger.md").read_text(encoding="utf-8")
    debug_workflow = (WORKFLOWS_DIR / "debug.md").read_text(encoding="utf-8")

    assert "Create: GPD/debug/{slug}.md" in debug_command
    assert "Debug file path: GPD/debug/{slug}.md" in debug_command
    assert "files_written: [GPD/debug/{slug}.md, ...]" in debug_agent
    assert "session_file: GPD/debug/{slug}.md" in debug_agent
    assert "**Troubleshooting Session:** GPD/debug/resolved/{slug}.md" in debug_agent
    assert "session_status: diagnosed" in debug_workflow
    assert "Do not route on heading markers in the returned text" in debug_workflow
    assert "typed `gpd_return` envelope and the session file instead" in debug_workflow


def test_settings_workflow_reuses_one_terminal_follow_up_list() -> None:
    settings_workflow = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")

    assert settings_workflow.count("For normal-terminal follow-up around these settings:") == 1
    assert "reuse the normal-terminal follow-up list from the `present_settings` step" in settings_workflow
    assert settings_workflow.count("gpd validate unattended-readiness --runtime <runtime> --autonomy <mode>") == 1


def test_sync_state_workflow_keeps_optional_commit_outside_core_reconcile_path() -> None:
    sync_state = (WORKFLOWS_DIR / "sync-state.md").read_text(encoding="utf-8")

    assert "This workflow is intentionally fail-closed" in sync_state
    assert "No state files found. Run gpd:new-project" in sync_state
    assert "Proceed with reconciliation? (y/n)" not in sync_state
    assert "determine which source is more recent" not in sync_state
    assert "Only if the operator explicitly asks to commit the reconciled state" in sync_state
    assert sync_state.index("<step name=\"reconcile\">") < sync_state.index("<step name=\"optional_commit\">")
    assert sync_state.index("gpd --raw state validate") < sync_state.index("<step name=\"optional_commit\">")
