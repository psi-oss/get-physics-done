"""Fast strictness regressions for the public surface contract loader."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import gpd.core.public_surface_contract as public_surface_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "src/gpd/core/public_surface_contract.json"


def _load_contract_payload() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _load_schema_payload() -> dict[str, object]:
    schema_path = REPO_ROOT / "src/gpd/core/public_surface_contract_schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _bind_public_surface_contract_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, contract_payload: dict[str, object]) -> None:
    (tmp_path / "public_surface_contract.json").write_text(json.dumps(contract_payload), encoding="utf-8")
    (tmp_path / "public_surface_contract_schema.json").write_text(json.dumps(_load_schema_payload()), encoding="utf-8")
    monkeypatch.setattr(public_surface_contract, "files", lambda _package: tmp_path)
    public_surface_contract.load_public_surface_contract.cache_clear()
    public_surface_contract.load_public_surface_contract_schema.cache_clear()


def test_fast_public_surface_contract_rejects_schema_version_bool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _load_contract_payload()
    payload["schema_version"] = True
    _bind_public_surface_contract_files(tmp_path, monkeypatch, contract_payload=payload)

    try:
        with pytest.raises(ValueError, match=r"Unsupported public surface contract schema_version: True"):
            public_surface_contract.load_public_surface_contract()
    finally:
        public_surface_contract.load_public_surface_contract.cache_clear()
        public_surface_contract.load_public_surface_contract_schema.cache_clear()


def test_fast_public_surface_contract_rejects_bridge_command_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = copy.deepcopy(_load_contract_payload())
    commands = payload["local_cli_bridge"]["commands"]
    commands[0], commands[1] = commands[1], commands[0]
    _bind_public_surface_contract_files(tmp_path, monkeypatch, contract_payload=payload)

    try:
        with pytest.raises(
            ValueError,
            match=r"local_cli_bridge\.commands must exactly match local_cli_bridge\.named_commands in canonical order",
        ):
            public_surface_contract.load_public_surface_contract()
    finally:
        public_surface_contract.load_public_surface_contract.cache_clear()
        public_surface_contract.load_public_surface_contract_schema.cache_clear()


def test_fast_public_surface_contract_reports_missing_package_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "public_surface_contract_schema.json").write_text(json.dumps(_load_schema_payload()), encoding="utf-8")
    monkeypatch.setattr(public_surface_contract, "files", lambda _package: tmp_path)
    public_surface_contract.load_public_surface_contract.cache_clear()
    public_surface_contract.load_public_surface_contract_schema.cache_clear()

    try:
        with pytest.raises(
            public_surface_contract.PublicSurfaceContractResourceError,
            match=r"GPD package data missing/corrupt: public_surface_contract\.json",
        ):
            public_surface_contract.load_public_surface_contract()
    finally:
        public_surface_contract.load_public_surface_contract.cache_clear()
        public_surface_contract.load_public_surface_contract_schema.cache_clear()


def test_fast_public_surface_contract_reports_corrupt_schema_package_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "public_surface_contract_schema.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(public_surface_contract, "files", lambda _package: tmp_path)
    public_surface_contract.load_public_surface_contract.cache_clear()
    public_surface_contract.load_public_surface_contract_schema.cache_clear()

    try:
        with pytest.raises(
            public_surface_contract.PublicSurfaceContractResourceError,
            match=r"GPD package data missing/corrupt: public_surface_contract_schema\.json",
        ):
            public_surface_contract.load_public_surface_contract_schema()
    finally:
        public_surface_contract.load_public_surface_contract.cache_clear()
        public_surface_contract.load_public_surface_contract_schema.cache_clear()
