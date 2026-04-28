"""Guardrails for the checked-in repository graph README."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from gpd.registry import LOCAL_CLI_BRIDGE_WORKFLOW_EXEMPT_COMMANDS
from scripts.repo_graph_contract import (
    EXCLUDED_GRAPH_DIRS,
    GENERATED_ON_END,
    GENERATED_ON_START,
    REPO_ROOT,
    SAME_STEM_COMMAND_WORKFLOW_END,
    SAME_STEM_COMMAND_WORKFLOW_START,
    SCOPE_END,
    SCOPE_START,
    build_contract,
    expected_scope_counts,
    extract_marked_block,
    graph_has_edge,
    live_repo_file_count,
    load_contract,
    parse_scope_count,
    read_graph_text,
    render_generated_on_block,
    render_same_stem_command_workflow_block,
    render_scope_block,
    replace_marked_block,
    sync_readme_text,
    untracked_graph_scope_files,
)
from scripts.sync_repo_graph_contract import check_generated_artifacts

_WORKFLOW_ONLY_STEMS = {"execute-plan", "transition", "verify-phase"}


def _tracked_prompt_stems() -> tuple[set[str], set[str]]:
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=False,
    )
    tracked_paths = [Path(path) for path in tracked.stdout.decode("utf-8").split("\0") if path]
    command_stems = {
        path.stem
        for path in tracked_paths
        if path.parts[:-1] == ("src", "gpd", "commands") and path.suffix == ".md"
    }
    workflow_stems = {
        path.stem
        for path in tracked_paths
        if path.parts[:-1] == ("src", "gpd", "specs", "workflows") and path.suffix == ".md"
    }
    return command_stems, workflow_stems


def test_graph_same_stem_command_workflow_inventory_matches_tree() -> None:
    graph = read_graph_text()
    match = re.search(
        r"src/gpd/commands/\{([^}]*)\}\.md -> src/gpd/specs/workflows/\{same stems\}\.md",
        graph,
    )
    assert match is not None, "Missing same-stem command/workflow edge inventory"

    graph_stems = [stem.strip() for stem in match.group(1).split(",") if stem.strip()]
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=False,
    )
    tracked_paths = [Path(path) for path in tracked.stdout.decode("utf-8").split("\0") if path]
    command_stems = {
        path.stem
        for path in tracked_paths
        if path.parts[:-1] == ("src", "gpd", "commands") and path.suffix == ".md"
    }
    workflow_stems = {
        path.stem
        for path in tracked_paths
        if path.parts[:-1] == ("src", "gpd", "specs", "workflows") and path.suffix == ".md"
    }
    actual_stems = sorted(command_stems & workflow_stems)

    assert graph_stems == actual_stems


def test_workflow_only_and_command_only_prompt_inventory_is_explicit() -> None:
    command_stems, workflow_stems = _tracked_prompt_stems()

    assert workflow_stems - command_stems == _WORKFLOW_ONLY_STEMS
    assert command_stems - workflow_stems == LOCAL_CLI_BRIDGE_WORKFLOW_EXEMPT_COMMANDS


def test_graph_same_stem_inventory_ignores_untracked_matching_files(tmp_path: Path) -> None:
    tmp_root = tmp_path / "repo"
    commands_dir = tmp_root / "src" / "gpd" / "commands"
    workflows_dir = tmp_root / "src" / "gpd" / "specs" / "workflows"
    commands_dir.mkdir(parents=True)
    workflows_dir.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=tmp_root, check=True, capture_output=True, text=True)

    for directory in (commands_dir, workflows_dir):
        (directory / "tracked.md").write_text("tracked\n", encoding="utf-8")
        (directory / "scratch.md").write_text("untracked\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "src/gpd/commands/tracked.md", "src/gpd/specs/workflows/tracked.md"],
        cwd=tmp_root,
        check=True,
        capture_output=True,
        text=True,
    )

    block = render_same_stem_command_workflow_block(tmp_root)

    assert "{tracked}" in block
    assert "scratch" not in block


def test_graph_captures_current_ci_action_and_shard_edges() -> None:
    graph = read_graph_text()

    assert graph_has_edge(".github/workflows/test.yml", "tests/ci_sharding.py", graph)
    assert graph_has_edge(".github/workflows/test.yml", "actions/checkout@v6", graph)
    assert graph_has_edge(".github/workflows/test.yml", "actions/setup-node@v6", graph)
    assert not graph_has_edge(".github/workflows/test.yml", "actions/checkout@v5", graph)
    assert not graph_has_edge(".github/workflows/test.yml", "actions/setup-node@v5", graph)


def test_graph_captures_shared_mcp_descriptor_text_edges() -> None:
    graph = read_graph_text()

    assert graph_has_edge("src/gpd/mcp/builtin_servers.py", "src/gpd/mcp/descriptor_text.py", graph)
    assert graph_has_edge("src/gpd/mcp/servers/skills_server.py", "src/gpd/mcp/descriptor_text.py", graph)


def test_graph_captures_hook_runtime_wiring_edges() -> None:
    graph = read_graph_text()
    assert graph_has_edge("src/gpd/hooks/statusline.py", "src/gpd/hooks/runtime_detect.py", graph)
    assert graph_has_edge("src/gpd/hooks/statusline.py", "src/gpd/adapters/__init__.py", graph)
    assert graph_has_edge("src/gpd/hooks/check_update.py", "src/gpd/hooks/runtime_detect.py", graph)
    assert graph_has_edge("src/gpd/hooks/notify.py", "src/gpd/hooks/check_update.py", graph)
    assert graph_has_edge("src/gpd/hooks/notify.py", "src/gpd/hooks/runtime_detect.py", graph)
    assert not graph_has_edge("src/gpd/hooks/notify.py", "src/gpd/adapters/__init__.py", graph)


def test_graph_captures_checkpoint_feature_edges() -> None:
    graph = read_graph_text()
    assert graph_has_edge("src/gpd/cli.py::sync_phase_checkpoints", "src/gpd/core/checkpoints.py::sync_phase_checkpoints", graph)
    assert graph_has_edge("src/gpd/core/phases.py", "src/gpd/core/checkpoints.py::sync_phase_checkpoints", graph)
    assert graph_has_edge("src/gpd/core/state.py", "<cwd>/GPD/.state-write-intent", graph)
    assert graph_has_edge("src/gpd/core/checkpoints.py", "generated outputs {GPD/CHECKPOINTS.md, GPD/phase-checkpoints/*.md}", graph)
    assert graph_has_edge("src/gpd/core/checkpoints.py", "<cwd>/GPD/CHECKPOINTS.md", graph)
    assert graph_has_edge("src/gpd/core/checkpoints.py", "<cwd>/GPD/phase-checkpoints/*.md", graph)
    assert not graph_has_edge("src/gpd/core/state.py", "src/gpd/core/checkpoints.py::sync_phase_checkpoints", graph)


def test_graph_captures_workflow_and_schema_edges() -> None:
    graph = read_graph_text()

    assert graph_has_edge(
        "src/gpd/specs/workflows/execute-phase.md",
        "src/gpd/specs/{references/orchestration/meta-orchestration.md,references/orchestration/artifact-surfacing.md,",
        graph,
    )
    assert graph_has_edge(
        "src/gpd/specs/workflows/execute-phase.md",
        "src/gpd/specs/{references/orchestration/meta-orchestration.md,references/orchestration/checkpoints.md,",
        graph,
    )
    assert graph_has_edge(
        "src/gpd/specs/workflows/execute-plan.md",
        "src/gpd/specs/{references/execution/git-integration.md,references/execution/github-lifecycle.md,",
        graph,
    )
    assert graph_has_edge(
        "src/gpd/specs/workflows/plan-phase.md",
        "src/gpd/specs/templates/plan-contract-schema.md",
        graph,
    )
    assert graph_has_edge(
        "src/gpd/specs/workflows/execute-plan.md",
        "src/gpd/specs/templates/contract-results-schema.md",
        graph,
    )
    assert graph_has_edge(
        "src/gpd/specs/workflows/verify-work.md",
        "src/gpd/specs/templates/contract-results-schema.md",
        graph,
    )
    assert graph_has_edge(
        "src/gpd/specs/workflows/verify-work.md",
        "src/gpd/specs/templates/plan-contract-schema.md",
        graph,
    )
    assert graph_has_edge(
        "src/gpd/specs/workflows/write-paper.md",
        "src/gpd/specs/templates/paper/{paper-config-schema.md,artifact-manifest-schema.md,bibliography-audit-schema.md,reproducibility-manifest.md}",
        graph,
    )
    assert graph_has_edge(
        "src/gpd/specs/workflows/new-project.md",
        "src/gpd/specs/templates/project-contract-schema.md",
        graph,
    )


def test_graph_captures_staged_review_panel_wiring() -> None:
    graph = read_graph_text()

    assert graph_has_edge(
        "src/gpd/commands/peer-review.md",
        "src/gpd/agents/{gpd-review-reader,gpd-review-literature,gpd-review-math,gpd-check-proof,gpd-review-physics,gpd-review-significance,gpd-referee}.md",
        graph,
    )
    assert graph_has_edge(
        "src/gpd/specs/workflows/peer-review.md",
        "src/gpd/agents/{gpd-review-reader,gpd-review-literature,gpd-review-math,gpd-check-proof,gpd-review-physics,gpd-review-significance,gpd-referee}.md",
        graph,
    )
    assert graph_has_edge(
        "src/gpd/agents/{gpd-review-reader,gpd-review-literature,gpd-review-math,gpd-check-proof,gpd-review-physics,gpd-review-significance,gpd-referee}.md",
        "src/gpd/specs/references/publication/peer-review-panel.md",
        graph,
    )



def test_graph_contract_scope_counts_match_live_inventory() -> None:
    expected = expected_scope_counts()

    mismatches = [
        f"{label}: graph={parse_scope_count(label)} live={count}"
        for label, count in expected.items()
        if parse_scope_count(label) != count
    ]

    assert not mismatches, "Graph scope counts are stale:\n" + "\n".join(mismatches)
    assert load_contract()["scope_counts"] == expected


def test_graph_readme_generated_blocks_match_contract() -> None:
    contract = load_contract()
    graph_text = read_graph_text()

    assert extract_marked_block(graph_text, GENERATED_ON_START, GENERATED_ON_END) == render_generated_on_block(contract)
    assert extract_marked_block(graph_text, SCOPE_START, SCOPE_END) == render_scope_block(contract)


def test_graph_check_detects_stale_generated_contract_without_mutation(tmp_path: Path) -> None:
    graph_path = tmp_path / "README.md"
    contract_path = tmp_path / "repo_graph_contract.json"
    contract = load_contract()
    stale_contract = dict(contract)
    stale_contract["scope_counts"] = {
        label: int(value) + 1 for label, value in contract["scope_counts"].items()
    }
    graph_path.write_text(read_graph_text(), encoding="utf-8")
    contract_path.write_text(json.dumps(stale_contract, indent=2) + "\n", encoding="utf-8")

    before_graph = graph_path.read_text(encoding="utf-8")
    before_contract = contract_path.read_text(encoding="utf-8")

    diffs = check_generated_artifacts(graph_path=graph_path, contract_path=contract_path)

    assert any("repo_graph_contract.json" in diff for diff in diffs)
    assert graph_path.read_text(encoding="utf-8") == before_graph
    assert contract_path.read_text(encoding="utf-8") == before_contract


def test_graph_check_detects_untracked_scope_files_without_mutation(tmp_path: Path) -> None:
    tmp_root = tmp_path / "repo"
    tmp_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=tmp_root, check=True, capture_output=True, text=True)

    tracked_file = tmp_root / "src" / "gpd" / "commands" / "tracked.md"
    tracked_file.parent.mkdir(parents=True)
    tracked_file.write_text("tracked\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", tracked_file.relative_to(tmp_root).as_posix()],
        cwd=tmp_root,
        check=True,
        capture_output=True,
        text=True,
    )

    graph_path = tmp_path / "README.md"
    contract_path = tmp_path / "repo_graph_contract.json"
    contract = build_contract(tmp_root)
    graph_template = "\n".join(
        (
            GENERATED_ON_START,
            GENERATED_ON_END,
            SCOPE_START,
            SCOPE_END,
            SAME_STEM_COMMAND_WORKFLOW_START,
            SAME_STEM_COMMAND_WORKFLOW_END,
            "",
        )
    )
    graph_path.write_text(sync_readme_text(graph_template, contract, tmp_root), encoding="utf-8")
    contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

    untracked_file = tmp_root / "src" / "gpd" / "commands" / "untracked.md"
    untracked_file.write_text("untracked\n", encoding="utf-8")
    before_graph = graph_path.read_text(encoding="utf-8")
    before_contract = contract_path.read_text(encoding="utf-8")

    diffs = check_generated_artifacts(graph_path=graph_path, contract_path=contract_path, repo_root=tmp_root)

    assert untracked_graph_scope_files(tmp_root) == (Path("src/gpd/commands/untracked.md"),)
    assert any(
        "Untracked repo graph scoped files" in diff and "src/gpd/commands/untracked.md" in diff
        for diff in diffs
    )
    assert graph_path.read_text(encoding="utf-8") == before_graph
    assert contract_path.read_text(encoding="utf-8") == before_contract


def test_graph_sync_repairs_stale_marked_blocks() -> None:
    original = read_graph_text()
    contract = load_contract()
    stale_contract = dict(contract)
    stale_contract["scope_counts"] = {
        label: int(value) + 1 for label, value in contract["scope_counts"].items()
    }

    stale = replace_marked_block(
        original,
        GENERATED_ON_START,
        GENERATED_ON_END,
        "\n".join((GENERATED_ON_START, "Generated from an outdated contract.", GENERATED_ON_END)),
    )
    stale = replace_marked_block(
        stale,
        SCOPE_START,
        SCOPE_END,
        render_scope_block(stale_contract),
    )
    stale = replace_marked_block(
        stale,
        SAME_STEM_COMMAND_WORKFLOW_START,
        SAME_STEM_COMMAND_WORKFLOW_END,
        "\n".join(
            (
                SAME_STEM_COMMAND_WORKFLOW_START,
                "- `src/gpd/commands/old.md -> src/gpd/specs/workflows/old.md`",
                SAME_STEM_COMMAND_WORKFLOW_END,
            )
        ),
    )

    repaired = sync_readme_text(stale, contract)

    assert repaired == original


def test_live_repo_file_count_ignores_worktree_artifacts(tmp_path: Path) -> None:
    tmp_root = tmp_path / "repo"
    tmp_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=tmp_root, check=True, capture_output=True, text=True)

    tracked_file = tmp_root / "tracked.txt"
    tracked_file.write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "add", tracked_file.name], cwd=tmp_root, check=True, capture_output=True, text=True)

    untracked_file = tmp_root / "docs" / "scratch.md"
    untracked_file.parent.mkdir(parents=True, exist_ok=True)
    untracked_file.write_text("untracked\n", encoding="utf-8")

    assert live_repo_file_count(tmp_root) == 1

    tracked_file.unlink()
    assert live_repo_file_count(tmp_root) == 0

    excluded_sentinels: list[Path] = []
    for excluded_name in EXCLUDED_GRAPH_DIRS:
        if excluded_name == ".git":
            continue
        if excluded_name == ".mcp.json":
            path = tmp_root / excluded_name
        else:
            path = tmp_root / excluded_name / "sentinel.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("runtime mirror sentinel\n", encoding="utf-8")
        excluded_sentinels.append(path)

    subprocess.run(
        ["git", "add", *[path.relative_to(tmp_root).as_posix() for path in excluded_sentinels]],
        cwd=tmp_root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert live_repo_file_count(tmp_root) == 0


def test_graph_test_file_references_exist() -> None:
    missing = sorted(
        {
            ref
            for ref in re.findall(r"tests/[A-Za-z0-9_./-]+\.py", read_graph_text())
            if not (REPO_ROOT / ref).is_file()
        }
    )

    assert missing == []


def test_graph_docs_file_references_exist() -> None:
    missing = sorted(
        {
            ref
            for ref in re.findall(r"docs/[A-Za-z0-9_./-]+\.md", read_graph_text())
            if not (REPO_ROOT / ref).is_file()
        }
    )

    assert missing == []
