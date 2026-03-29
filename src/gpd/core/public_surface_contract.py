"""Structured public-surface contract for repeated local CLI boundary guidance."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files

__all__ = [
    "LocalCliBridgeContract",
    "PostStartSettingsContract",
    "PublicSurfaceContract",
    "load_public_surface_contract",
    "local_cli_bridge_commands",
    "local_cli_bridge_contract",
    "local_cli_bridge_note",
    "post_start_settings_contract",
    "post_start_settings_note",
    "post_start_settings_recommendation",
]


@dataclass(frozen=True, slots=True)
class LocalCliBridgeContract:
    commands: tuple[str, ...]
    terminal_phrase: str
    purpose_phrase: str

    def render_note(self) -> str:
        return (
            f"Use {_join_backticked_commands(self.commands)} {self.terminal_phrase} "
            f"when you want {self.purpose_phrase}."
        )


@dataclass(frozen=True, slots=True)
class PostStartSettingsContract:
    primary_sentence: str
    default_sentence: str

    def render_note(self) -> str:
        return f"{self.primary_sentence} {self.default_sentence}"


@dataclass(frozen=True, slots=True)
class PublicSurfaceContract:
    local_cli_bridge: LocalCliBridgeContract
    post_start_settings: PostStartSettingsContract


def _join_backticked_commands(commands: tuple[str, ...]) -> str:
    rendered = tuple(f"`{command}`" for command in commands)
    if not rendered:
        raise ValueError("public surface contract requires at least one local CLI command")
    if len(rendered) == 1:
        return rendered[0]
    if len(rendered) == 2:
        return f"{rendered[0]} and {rendered[1]}"
    return ", ".join(rendered[:-1]) + f", and {rendered[-1]}"


def _require_object(payload: object, *, label: str) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _require_string(payload: dict[str, object], key: str, *, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{key} must be a non-empty string")
    return value


def _require_string_list(payload: dict[str, object], key: str, *, label: str) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label}.{key} must be a non-empty list")
    commands: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label}.{key} entries must be non-empty strings")
        commands.append(item)
    return tuple(commands)


@lru_cache(maxsize=1)
def load_public_surface_contract() -> PublicSurfaceContract:
    contract_path = files("gpd.core").joinpath("public_surface_contract.json")
    raw_payload = json.loads(contract_path.read_text(encoding="utf-8"))
    payload = _require_object(raw_payload, label="public_surface_contract")

    schema_version = payload.get("schema_version")
    if schema_version != 1:
        raise ValueError(f"Unsupported public surface contract schema_version: {schema_version!r}")

    bridge_payload = _require_object(payload.get("local_cli_bridge"), label="local_cli_bridge")
    settings_payload = _require_object(payload.get("post_start_settings"), label="post_start_settings")

    return PublicSurfaceContract(
        local_cli_bridge=LocalCliBridgeContract(
            commands=_require_string_list(bridge_payload, "commands", label="local_cli_bridge"),
            terminal_phrase=_require_string(bridge_payload, "terminal_phrase", label="local_cli_bridge"),
            purpose_phrase=_require_string(bridge_payload, "purpose_phrase", label="local_cli_bridge"),
        ),
        post_start_settings=PostStartSettingsContract(
            primary_sentence=_require_string(
                settings_payload,
                "primary_sentence",
                label="post_start_settings",
            ),
            default_sentence=_require_string(
                settings_payload,
                "default_sentence",
                label="post_start_settings",
            ),
        ),
    )


def local_cli_bridge_contract() -> LocalCliBridgeContract:
    return load_public_surface_contract().local_cli_bridge


def local_cli_bridge_commands() -> tuple[str, ...]:
    return local_cli_bridge_contract().commands


def local_cli_bridge_note() -> str:
    return local_cli_bridge_contract().render_note()


def post_start_settings_contract() -> PostStartSettingsContract:
    return load_public_surface_contract().post_start_settings


def post_start_settings_note() -> str:
    return post_start_settings_contract().primary_sentence


def post_start_settings_recommendation() -> str:
    return post_start_settings_contract().default_sentence
