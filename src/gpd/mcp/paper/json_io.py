"""Shared JSON persistence helpers for paper-side Pydantic artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

_ModelT = TypeVar("_ModelT", bound=BaseModel)


def model_json_text(model: BaseModel, *, trailing_newline: bool = False) -> str:
    """Serialize a paper artifact model with one JSON formatting policy."""

    text = json.dumps(model.model_dump(mode="json"), indent=2, ensure_ascii=False)
    return text + "\n" if trailing_newline else text


def write_model_json(model: BaseModel, output_path: Path, *, trailing_newline: bool = False) -> None:
    """Persist a paper artifact model as UTF-8 JSON."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(model_json_text(model, trailing_newline=trailing_newline), encoding="utf-8")


def read_model_json(model_cls: type[_ModelT], input_path: Path) -> _ModelT:
    """Load a UTF-8 JSON artifact into a strict Pydantic model."""

    try:
        raw = input_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise OSError(f"{input_path.as_posix()} is not valid UTF-8") from exc
    payload = json.loads(raw)
    return model_cls.model_validate(payload)
