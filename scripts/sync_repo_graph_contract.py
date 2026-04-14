"""Refresh the checked-in repo graph contract and README generated blocks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parent.parent
    sys.path[:0] = [str(repo_root), str(repo_root / "src")]

from scripts.repo_graph_contract import (
    CONTRACT_PATH,
    GRAPH_PATH,
    build_contract,
    read_graph_text,
    render_contract_text,
    sync_readme_text,
    write_contract,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh or check the checked-in repo graph contract and README sections.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify that the contract and README graph block are current without writing changes.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    contract = build_contract()
    contract_text = render_contract_text(contract)
    current_readme = read_graph_text()
    synced_readme = sync_readme_text(current_readme, contract)

    if args.check:
        contract_matches = CONTRACT_PATH.read_text(encoding="utf-8") == contract_text
        readme_matches = current_readme == synced_readme

        if contract_matches and readme_matches:
            return

        if not contract_matches:
            print(
                "tests/repo_graph_contract.json is out of date; run "
                "`python scripts/sync_repo_graph_contract.py` to update it.",
                file=sys.stderr,
            )
        if not readme_matches:
            print(
                "tests/README.md repo graph section is out of date; regenerate with "
                "`python scripts/sync_repo_graph_contract.py`.",
                file=sys.stderr,
            )
        sys.exit(1)

    write_contract(contract)
    GRAPH_PATH.write_text(synced_readme, encoding="utf-8")


if __name__ == "__main__":
    main()
