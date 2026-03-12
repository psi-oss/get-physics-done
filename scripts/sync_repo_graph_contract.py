"""Refresh the checked-in repo graph contract and README generated blocks."""

from __future__ import annotations

from scripts.repo_graph_contract import (
    GRAPH_PATH,
    build_contract,
    read_graph_text,
    sync_readme_text,
    write_contract,
)


def main() -> None:
    contract = build_contract()
    write_contract(contract)
    GRAPH_PATH.write_text(sync_readme_text(read_graph_text(), contract), encoding="utf-8")


if __name__ == "__main__":
    main()
