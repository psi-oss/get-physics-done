"""Contract test for help inventory coverage."""

from __future__ import annotations

import re

from gpd import registry as content_registry
from tests.doc_surface_contracts import assert_publication_lane_boundary_contract


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


def test_help_wrapper_followups_do_not_hard_code_gpd_help_runtime_syntax() -> None:
    help_command = _read("src/gpd/commands/help.md")

    assert "gpd:help --all" not in help_command
    assert "gpd:help --command <name>" not in help_command
    assert "this runtime's help command" not in help_command
    assert "never print the placeholder" in help_command
    assert "Run <current-help-command> --all for the compact command index." in help_command
    assert "Run <current-help-command> --command <name> for detailed help on one command." in help_command
    assert "Unknown command. Run <current-help-command> --all for the compact command index." in help_command


def test_help_wrapper_documents_inline_argument_command_lookup_normalization() -> None:
    help_command = _read("src/gpd/commands/help.md")

    assert "gpd:new-project --minimal" in help_command
    assert "current runtime's native command label" in help_command
    assert "new-project --minimal" in help_command
    assert "parse the inline arguments separately" in help_command
    assert "base command block" in help_command


def test_help_workflow_removes_unreachable_contextual_help_variant() -> None:
    help_workflow = _read("src/gpd/specs/workflows/help.md")
    quick_start = _section(help_workflow, "## Quick Start", "## Command Index")

    assert '<step name="contextual_help">' not in help_workflow
    assert "## Contextual Help (State-Aware Variant)" not in help_workflow
    assert "Returning work" in quick_start
    assert "gpd:resume-work" in quick_start


def test_peer_review_detailed_help_uses_command_policy_instead_of_suffix_inventory() -> None:
    help_workflow = _read("src/gpd/specs/workflows/help.md")
    peer_review_detail = _section(
        help_workflow,
        "**`gpd:peer-review [paper directory | manuscript path | explicit artifact path]`**",
        "**`gpd:respond-to-referees",
    )

    assert "one explicit subject allowed by its command policy" in help_workflow
    assert "command-policy supported suffixes for publication-artifact paths" in peer_review_detail
    assert "`.txt`, `.pdf`, `.docx`, `.csv`, `.tsv`, and `.xlsx`" not in peer_review_detail


def test_help_workflow_paper_toolchain_doctor_row_is_single_sourced() -> None:
    help_workflow = _read("src/gpd/specs/workflows/help.md")

    assert help_workflow.count("`gpd doctor --runtime <runtime> --local` / `gpd doctor --runtime <runtime> --global`") == 1
    assert len(re.findall(r"(?m)^\s*gpd doctor --runtime <runtime> --local\|--global\b.*$", help_workflow)) == 0


def test_public_docs_frame_typed_review_surfaces_as_command_policy_specializations() -> None:
    readme = _read("README.md")
    help_workflow = _read("src/gpd/specs/workflows/help.md")

    assert "Typed command metadata is not review-only." in readme
    assert "shared command applicability surface for public commands" in readme
    assert "specialized typed surfaces for commands that expose review/publication contracts" in readme

    assert "generic typed command-policy check for the public runtime surface" in help_workflow
    assert "specialized typed surfaces for commands that expose review/publication contracts" in help_workflow


def test_public_docs_explain_publication_lane_boundary_and_follow_on_command_args() -> None:
    readme = _read("README.md")
    help_workflow = _read("src/gpd/specs/workflows/help.md")

    assert_publication_lane_boundary_contract(readme)
    assert_publication_lane_boundary_contract(help_workflow)
    assert "bounded external-authoring lane driven by an explicit intake manifest only" in readme
    assert "bounded external-authoring lane driven by an explicit intake manifest only" in help_workflow
    assert (
        "subject-owned publication root at `GPD/publication/{subject_slug}`" in readme
        or "subject-owned publication root at `GPD/publication/{subject_slug}/...`" in readme
    )
    assert "subject-owned publication root at `GPD/publication/{subject_slug}`" in help_workflow
    assert (
        "`GPD/publication/{subject_slug}/intake/` for intake and provenance state only" in readme
        or "`GPD/publication/{subject_slug}/intake/` keeps intake/provenance state only" in readme
    )
    assert "`GPD/publication/{subject_slug}/intake/` for intake and provenance state only" in help_workflow
    assert "Project-backed review/response/package outputs stay on the `GPD/` and `GPD/review/` paths" in readme
    assert "Project-backed review/response/package outputs stay on their current `GPD/` and `GPD/review/` paths." in help_workflow
    assert "The later publication commands stay stricter:" in readme
    assert "**`gpd:respond-to-referees [--manuscript PATH --report PATH | report path | paste]`**" in help_workflow
    assert "**`gpd:arxiv-submission [GPD-owned manuscript root]`**" in help_workflow
    assert "Usage: `gpd:respond-to-referees --manuscript paper/main.tex --report reports/referee-report.md`" in help_workflow
    assert "Usage: `gpd:respond-to-referees reports/referee-report.md`" in help_workflow
    assert "Usage: `gpd:respond-to-referees paste`" in help_workflow
    assert "Usage: `gpd:arxiv-submission paper/`" in help_workflow
    assert "Usage: `gpd:write-paper --intake intake/paper-authoring-input.json`" in help_workflow
    assert "`gpd:arxiv-submission` only packages a GPD-owned manuscript root" in readme
    assert "`gpd:arxiv-submission` packages only a GPD-owned manuscript root" in help_workflow


def test_public_write_paper_help_surfaces_match_supported_command_metadata() -> None:
    readme = _read("README.md")
    help_workflow = _read("src/gpd/specs/workflows/help.md")
    write_paper_workflow = _read("src/gpd/specs/workflows/write-paper.md")
    public_surfaces = (readme, help_workflow)

    for content in public_surfaces:
        assert "gpd:write-paper [title or topic]" not in content
        assert "--from-phases" not in content
        assert 'gpd:write-paper "' not in content
        assert "gpd:write-paper --intake intake/paper-authoring-input.json" in content

    assert "Usage: `gpd:write-paper`" in help_workflow
    assert "--from-phases" not in write_paper_workflow


def test_help_workflow_export_logs_surfaces_passthrough_filters() -> None:
    help_workflow = _read("src/gpd/specs/workflows/help.md")

    export_index = "- `gpd:export-logs"
    export_detail = "**`gpd:export-logs"
    assert export_index in help_workflow
    assert export_detail in help_workflow
    for flag in ("--command <label>", "--phase <phase>", "--category <name>"):
        assert flag in help_workflow
    assert "Supports passthrough filters" in help_workflow
    assert "Usage: `gpd:export-logs --command gpd:execute-phase --phase 3 --category workflow`" in help_workflow


def test_help_workflow_error_patterns_uses_pattern_library_categories() -> None:
    help_workflow = _read("src/gpd/specs/workflows/help.md")
    error_patterns_section = _section(
        help_workflow,
        "**`gpd:error-patterns [category]`**",
        "**`gpd:record-backtrack [description]`**",
    )
    expected_categories = {
        "sign-error",
        "factor-error",
        "convention-pitfall",
        "convergence-issue",
        "approximation-failure",
        "numerical-instability",
        "conceptual-error",
        "dimensional-error",
    }

    for category in expected_categories:
        assert category in error_patterns_section
    assert "Usage: `gpd:error-patterns sign-error`" in error_patterns_section
    assert "Usage: `gpd:error-patterns sign`" not in error_patterns_section
    assert "boundary, gauge, combinatorial" not in error_patterns_section


def test_help_command_uses_one_shared_extract_warning() -> None:
    help_command = _read("src/gpd/commands/help.md")

    assert help_command.count("Shared wrapper rule for every extract below") == 1
    assert help_command.count("Return the requested section without rewriting, summarizing, or inventing alternate wording") == 1


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
    assert (
        "Use canonical `GPD/knowledge/{knowledge_id}.md` targets for existing knowledge docs; "
        "new draft targets are created under the current workspace `GPD/knowledge/` tree."
    ) in help_workflow
    assert (
        help_workflow.count(
            "- Resolves one canonical `GPD/knowledge/{knowledge_id}.md` target in the current workspace or stops on ambiguity"
        )
        == 1
    )
    assert "stable` docs can later become `superseded`; superseded docs remain addressable and traceable rather than disappearing" in help_workflow
    assert "Example topic: `gpd:digest-knowledge \"renormalization group fixed points\"`" in help_workflow
    assert "Example modern arXiv: `gpd:digest-knowledge 2401.12345v2`" in help_workflow
    assert "Example legacy arXiv: `gpd:digest-knowledge hep-th/9901001`" in help_workflow
    assert "Example source file: `gpd:digest-knowledge ./notes/rg-notes.md`" in help_workflow
    assert "Example explicit knowledge path: `gpd:digest-knowledge GPD/knowledge/K-renormalization-group-fixed-points.md`" in help_workflow
    assert "Stable knowledge is already visible through the shared runtime reference surfaces" in help_workflow
    assert "Stable knowledge is available through the shared runtime reference surfaces" in help_workflow


def test_help_workflow_current_workspace_helpers_and_discover_quick_mode_wording() -> None:
    help_workflow = _read("src/gpd/specs/workflows/help.md")

    assert "- `gpd:discover [phase or topic]` - Survey methods, literature, and tools before planning; `quick` is verification-only" in help_workflow
    assert "- `quick` is verification-only and writes no file; `medium` and `deep` write discovery artifacts" in help_workflow
    assert "- Written discovery artifacts feed planning or standalone analysis" in help_workflow
    assert "- Writes the decisive comparison artifact under `GPD/comparisons/` in the current workspace" in help_workflow
    assert "Create or update a current-workspace knowledge document draft from a topic, paper, source file, or explicit knowledge path." in help_workflow
    assert "- Resolves one canonical `GPD/knowledge/{knowledge_id}.md` target in the current workspace or stops on ambiguity" in help_workflow
    assert "Review one canonical current-workspace knowledge document, record typed approval evidence, and promote a fresh approved draft to stable." in help_workflow
    assert "- Resolves an exact existing current-workspace knowledge target by canonical path or knowledge id" in help_workflow
    assert "- Writes a deterministic review artifact under `GPD/knowledge/reviews/` in the current workspace" in help_workflow
    assert "Structured literature review for a physics research topic from the current project or one explicit topic or research question." in help_workflow
    assert "- Writes the review and citation-source sidecar under `GPD/literature/` in the current workspace" in help_workflow


def test_help_workflow_relaxed_technical_analysis_lane_stays_honest() -> None:
    help_workflow = _read("src/gpd/specs/workflows/help.md")

    assert "Project-aware technical-analysis lane:" in help_workflow
    assert (
        "`gpd:derive-equation`, `gpd:dimensional-analysis`, `gpd:limiting-cases`, "
        "`gpd:numerical-convergence`, and `gpd:sensitivity-analysis`"
    ) in help_workflow
    assert "durable outputs under the invoking workspace's `GPD/analysis/` tree" in help_workflow
    assert "`gpd:graph` and `gpd:error-propagation` are separate commands and are not part of this relaxed current-workspace lane." in help_workflow
