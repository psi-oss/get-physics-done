"""Refresh or check the checked-in repo graph contract and README blocks."""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parent.parent
    sys.path[:0] = [str(repo_root), str(repo_root / "src")]

from scripts.repo_graph_contract import (
    CONTRACT_PATH,
    GRAPH_PATH,
    REPO_ROOT,
    build_contract,
    sync_readme_text,
    untracked_graph_scope_files,
    write_contract,
)


def _contract_text(contract: dict[str, object]) -> str:
    return json.dumps(contract, indent=2) + "\n"


def _diff(expected: str, actual: str, *, path: Path) -> str:
    return "".join(
        difflib.unified_diff(
            actual.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile=f"{path.as_posix()} (current)",
            tofile=f"{path.as_posix()} (expected)",
        )
    )


def expected_generated_artifacts(
    *,
    graph_path: Path = GRAPH_PATH,
    repo_root: Path = REPO_ROOT,
) -> tuple[str, str]:
    contract = build_contract(repo_root)
    return (
        _contract_text(contract),
        sync_readme_text(graph_path.read_text(encoding="utf-8"), contract, repo_root),
    )


def check_generated_artifacts(
    *,
    graph_path: Path = GRAPH_PATH,
    contract_path: Path = CONTRACT_PATH,
    repo_root: Path = REPO_ROOT,
) -> tuple[str, ...]:
    expected_contract, expected_graph = expected_generated_artifacts(
        graph_path=graph_path,
        repo_root=repo_root,
    )
    current_contract = contract_path.read_text(encoding="utf-8")
    current_graph = graph_path.read_text(encoding="utf-8")

    diffs: list[str] = []
    if current_contract != expected_contract:
        diffs.append(_diff(expected_contract, current_contract, path=contract_path))
    if current_graph != expected_graph:
        diffs.append(_diff(expected_graph, current_graph, path=graph_path))
    untracked_scope_files = untracked_graph_scope_files(repo_root)
    if untracked_scope_files:
        formatted_paths = "\n".join(f"- {path.as_posix()}" for path in untracked_scope_files)
        diffs.append(
            "Untracked repo graph scoped files are not represented in the generated contract. "
            "Add them to git or move them out of the repo-graph scope before running the check.\n\n"
            f"{formatted_paths}\n"
        )
    return tuple(diffs)


def sync_generated_artifacts(
    *,
    graph_path: Path = GRAPH_PATH,
    contract_path: Path = CONTRACT_PATH,
    repo_root: Path = REPO_ROOT,
) -> None:
    contract = build_contract(repo_root)
    write_contract(contract, contract_path)
    graph_path.write_text(
        sync_readme_text(graph_path.read_text(encoding="utf-8"), contract, repo_root), encoding="utf-8"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify generated artifacts without modifying them",
    )
    args = parser.parse_args(argv)

    if args.check:
        diffs = check_generated_artifacts()
        if diffs:
            sys.stderr.write(
                "Repo graph generated artifacts are stale. "
                "Run `uv run python scripts/sync_repo_graph_contract.py` and commit the result.\n\n"
            )
            sys.stderr.write("\n".join(diffs))
            return 1
        return 0

    sync_generated_artifacts()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
