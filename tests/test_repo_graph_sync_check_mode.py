from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.sync_repo_graph_contract as sync_script


def _prepare_check_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    contract_data: dict[str, object],
    current_readme: str,
    synced_readme: str,
) -> tuple[Path, Path]:
    contract_path = tmp_path / "repo_graph_contract.json"
    contract_path.write_text(json.dumps(contract_data, indent=2) + "\n", encoding="utf-8")
    readme_path = tmp_path / "README.md"
    readme_path.write_text(current_readme, encoding="utf-8")

    monkeypatch.setattr(sync_script, "CONTRACT_PATH", contract_path)
    monkeypatch.setattr(sync_script, "GRAPH_PATH", readme_path)
    monkeypatch.setattr(sync_script, "build_contract", lambda: contract_data)
    monkeypatch.setattr(
        sync_script,
        "render_contract_text",
        lambda contract: json.dumps(contract, indent=2) + "\n",
    )
    monkeypatch.setattr(sync_script, "read_graph_text", lambda: readme_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(sync_script, "sync_readme_text", lambda *_: synced_readme)

    return contract_path, readme_path


def _run_check(monkeypatch, args: list[str]) -> None:
    monkeypatch.setattr(sync_script.sys, "argv", ["scripts/sync_repo_graph_contract.py", *args])
    sync_script.main()


def test_repo_graph_sync_check_mode_passes_when_artifacts_are_current(monkeypatch, tmp_path: Path) -> None:
    contract_data = {"schema_version": 1}
    readme_text = "current graph block"
    _prepare_check_fixture(
        monkeypatch,
        tmp_path,
        contract_data=contract_data,
        current_readme=readme_text,
        synced_readme=readme_text,
    )

    _run_check(monkeypatch, ["--check"])


def test_repo_graph_sync_check_mode_reports_drift(monkeypatch, tmp_path: Path, capsys: pytest.CapsysFixture) -> None:
    contract_data = {"schema_version": 1}
    readme_text = "current graph block"
    synced_readme = "updated graph block"
    contract_path, _ = _prepare_check_fixture(
        monkeypatch,
        tmp_path,
        contract_data=contract_data,
        current_readme=readme_text,
        synced_readme=synced_readme,
    )

    contract_path.write_text(json.dumps({"schema_version": 2}, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        _run_check(monkeypatch, ["--check"])

    stderr = capsys.readouterr().err
    assert excinfo.value.code == 1
    assert "tests/repo_graph_contract.json is out of date" in stderr
    assert "tests/README.md repo graph section is out of date" in stderr
