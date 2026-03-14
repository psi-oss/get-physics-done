"""Guardrails for the checked-in repository graph README."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

from scripts.repo_graph_contract import (
    CONTRACT_PATH,
    GENERATED_ON_END,
    GENERATED_ON_START,
    GRAPH_PATH,
    REPO_ROOT,
    SCOPE_END,
    SCOPE_START,
    expected_scope_counts,
    extract_marked_block,
    live_repo_file_count,
    load_contract,
    parse_scope_count,
    read_graph_text,
    render_generated_on_block,
    render_scope_block,
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
                shutil.rmtree(sentinel_dir)
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


def test_graph_captures_staged_review_prompt_edges() -> None:
    graph = read_graph_text()
    expected_edges = [
        "`src/gpd/commands/write-paper.md -> src/gpd/agents/{gpd-paper-writer,gpd-bibliographer,gpd-review-reader,gpd-review-literature,gpd-review-math,gpd-review-physics,gpd-review-significance,gpd-referee}.md`",
        "`src/gpd/commands/peer-review.md -> src/gpd/agents/{gpd-review-reader,gpd-review-literature,gpd-review-math,gpd-review-physics,gpd-review-significance,gpd-referee}.md`",
        "`src/gpd/specs/workflows/write-paper.md -> src/gpd/specs/workflows/peer-review.md`",
        "`src/gpd/specs/workflows/peer-review.md -> src/gpd/agents/{gpd-review-reader,gpd-review-literature,gpd-review-math,gpd-review-physics,gpd-review-significance,gpd-referee}.md`",
        "`src/gpd/agents/{gpd-review-reader,gpd-review-literature,gpd-review-math,gpd-review-physics,gpd-review-significance,gpd-referee}.md -> src/gpd/specs/references/publication/peer-review-panel.md`",
    ]

    for edge in expected_edges:
        assert edge in graph


def test_graph_captures_paper_build_prompt_edges() -> None:
    graph = read_graph_text()
    expected_edges = [
        "`src/gpd/commands/write-paper.md -> gpd paper-build paper/PAPER-CONFIG.json`",
        "`src/gpd/commands/write-paper.md -> paper/{PAPER-CONFIG.json,main.tex,ARTIFACT-MANIFEST.json}`",
        "`src/gpd/commands/peer-review.md -> candidate manuscript roots {paper/main.tex, manuscript/main.tex, draft/main.tex}`",
        "`src/gpd/specs/workflows/write-paper.md -> src/gpd/cli.py::paper_build`",
        "`src/gpd/specs/workflows/write-paper.md -> paper/{PAPER-CONFIG.json,main.tex,ARTIFACT-MANIFEST.json}`",
        "`src/gpd/specs/workflows/peer-review.md -> candidate manuscript roots {paper/main.tex, manuscript/main.tex, draft/main.tex}`",
        "`src/gpd/specs/workflows/peer-review.md -> paper/{PAPER-CONFIG.json,ARTIFACT-MANIFEST.json,BIBLIOGRAPHY-AUDIT.json}`",
    ]

    for edge in expected_edges:
        assert edge in graph


def test_graph_captures_hook_runtime_wiring_edges() -> None:
    graph = read_graph_text()
    expected_edges = [
        "`src/gpd/hooks/statusline.py -> src/gpd/hooks/runtime_detect.py`",
        "`src/gpd/hooks/statusline.py -> src/gpd/adapters/__init__.py`",
        "`src/gpd/hooks/check_update.py -> src/gpd/hooks/runtime_detect.py`",
        "`src/gpd/hooks/notify.py -> src/gpd/hooks/check_update.py`",
        "`src/gpd/hooks/notify.py -> src/gpd/hooks/runtime_detect.py`",
    ]

    unexpected_edges = [
        "`src/gpd/hooks/notify.py -> src/gpd/adapters/__init__.py`",
    ]

    for edge in expected_edges:
        assert edge in graph

    for edge in unexpected_edges:
        assert edge not in graph


def test_graph_test_file_references_exist() -> None:
    missing = sorted(
        {
            ref
            for ref in re.findall(r"tests/[A-Za-z0-9_./-]+\.py", read_graph_text())
            if not (REPO_ROOT / ref).is_file()
        }
    )

    assert missing == []


def test_graph_claude_artifact_language_matches_tree() -> None:
    graph = read_graph_text()

    assert "## Installed Runtime Artifact Family: `.claude/**`" in graph
    assert ".claude/settings.local.json" not in graph
    assert "## Checked-In Installed Snapshot: `.claude/**`" not in graph
    assert "checked-in installed artifacts like `.claude/**`" not in graph

    if not (REPO_ROOT / ".claude").exists():
        assert "- `.claude/commands/gpd/*.md`" not in graph
        assert "- `.claude/agents/*.md`" not in graph
        assert "- `.claude/get-physics-done/workflows/**/*.md`" not in graph
        assert "- `.claude/get-physics-done/templates/**/*.md`" not in graph
        assert "- `.claude/get-physics-done/references/**/*.md`" not in graph


def test_graph_contract_scope_parser_matches_expected_counts() -> None:
    for label, count in expected_scope_counts().items():
        assert parse_scope_count(label) == count


def test_graph_contract_json_matches_live_scope_counts() -> None:
    contract = load_contract()
    assert contract["scope_counts"] == expected_scope_counts()


def test_graph_readme_generated_blocks_match_contract() -> None:
    contract = load_contract()
    graph_text = read_graph_text()

    assert extract_marked_block(graph_text, GENERATED_ON_START, GENERATED_ON_END) == render_generated_on_block(contract)
    assert extract_marked_block(graph_text, SCOPE_START, SCOPE_END) == render_scope_block(contract)


def test_live_repo_file_count_ignores_transient_root_artifacts() -> None:
    baseline = live_repo_file_count()

    with _transient_root_artifacts() as sentinel_files:
        assert all(path.is_file() for path in sentinel_files)
        assert live_repo_file_count() == baseline

    assert all(not path.exists() for path in sentinel_files)


def test_live_repo_file_count_ignores_untracked_worktree_files(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    tracked_file = tmp_path / "tracked.txt"
    tracked_file.write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "add", tracked_file.name], cwd=tmp_path, check=True, capture_output=True, text=True)

    untracked_file = tmp_path / "docs" / "scratch.md"
    untracked_file.parent.mkdir(parents=True, exist_ok=True)
    untracked_file.write_text("untracked\n", encoding="utf-8")

    assert live_repo_file_count(tmp_path) == 1


def test_live_repo_file_count_ignores_deleted_tracked_files(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    tracked_file = tmp_path / "tracked.txt"
    tracked_file.write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "add", tracked_file.name], cwd=tmp_path, check=True, capture_output=True, text=True)

    tracked_file.unlink()

    assert live_repo_file_count(tmp_path) == 0


def test_live_repo_file_count_ignores_runtime_mirror_dirs(tmp_path: Path) -> None:
    for rel_path in (".claude/a.txt", ".codex/b.txt", ".gemini/c.txt", ".opencode/d.txt"):
        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("runtime mirror sentinel\n", encoding="utf-8")

    assert live_repo_file_count(tmp_path) == 0


def test_sync_repo_graph_script_runs_as_direct_file() -> None:
    graph_before = GRAPH_PATH.read_text(encoding="utf-8")
    contract_before = CONTRACT_PATH.read_text(encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "scripts/sync_repo_graph_contract.py"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert GRAPH_PATH.read_text(encoding="utf-8") == graph_before
    assert CONTRACT_PATH.read_text(encoding="utf-8") == contract_before
