"""Guardrails for the checked-in repository graph README."""

from __future__ import annotations

import re
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from scripts.repo_graph_contract import (
    GENERATED_ON_END,
    GENERATED_ON_START,
    REPO_ROOT,
    SAME_STEM_COMMAND_WORKFLOW_END,
    SAME_STEM_COMMAND_WORKFLOW_START,
    SCOPE_END,
    SCOPE_START,
    expected_scope_counts,
    extract_marked_block,
    graph_has_edge,
    live_repo_file_count,
    load_contract,
    parse_scope_count,
    read_graph_text,
    render_generated_on_block,
    render_scope_block,
    replace_marked_block,
    sync_readme_text,
)


@contextmanager
def _transient_root_artifacts():
    sentinel_root = "__gpd_repo_graph_test__"
    transient_roots = (
        ".npm-cache",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
    )
    created_paths: list[tuple[Path, bool]] = []

    try:
        for root_name in transient_roots:
            root_path = REPO_ROOT / root_name
            sentinel_dir = root_path / sentinel_root
            root_existed = root_path.exists()
            sentinel_dir.mkdir(parents=True, exist_ok=True)
            (sentinel_dir / "sentinel.txt").write_text("graph regression coverage\n", encoding="utf-8")
            created_paths.append((root_path, root_existed))
        yield [root_path / sentinel_root / "sentinel.txt" for root_path, _ in created_paths]
    finally:
        for root_path, root_existed in created_paths:
            sentinel_dir = root_path / sentinel_root
            if sentinel_dir.exists():
                shutil.rmtree(sentinel_dir, ignore_errors=True)
            if not root_existed and root_path.exists() and not any(root_path.iterdir()):
                root_path.rmdir()


def test_graph_scope_counts_match_live_prompt_inventory() -> None:
    expected = expected_scope_counts()

    mismatches = [
        f"{label}: graph={parse_scope_count(label)} live={count}"
        for label, count in expected.items()
        if parse_scope_count(label) != count
    ]

    assert not mismatches, "Graph scope counts are stale:\n" + "\n".join(mismatches)


def test_graph_same_stem_command_workflow_inventory_matches_tree() -> None:
    graph = read_graph_text()
    match = re.search(
        r"src/gpd/commands/\{([^}]*)\}\.md -> src/gpd/specs/workflows/\{same stems\}\.md",
        graph,
    )
    assert match is not None, "Missing same-stem command/workflow edge inventory"

    graph_stems = [stem.strip() for stem in match.group(1).split(",") if stem.strip()]
    actual_stems = sorted(
        {path.stem for path in (REPO_ROOT / "src/gpd/commands").glob("*.md")}
        & {path.stem for path in (REPO_ROOT / "src/gpd/specs/workflows").glob("*.md")}
    )

    assert graph_stems == actual_stems


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
    baseline = live_repo_file_count()

    with _transient_root_artifacts() as sentinel_files:
        assert all(path.is_file() for path in sentinel_files)
        assert live_repo_file_count() == baseline

    assert all(not path.exists() for path in sentinel_files)

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

    for config_dir_name in {descriptor.config_dir_name for descriptor in iter_runtime_descriptors()}:
        rel_path = f"{config_dir_name}/sentinel.txt"
        path = tmp_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("runtime mirror sentinel\n", encoding="utf-8")

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
