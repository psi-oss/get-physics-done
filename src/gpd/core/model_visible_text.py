"""Tiny dependency-free strings shared by model-visible prompt wrappers."""

from __future__ import annotations

__all__ = [
    "agent_visibility_note",
    "command_visibility_note",
    "review_contract_visibility_note",
]


def agent_visibility_note() -> str:
    return "Model-visible agent requirements. Follow this YAML."


def command_visibility_note() -> str:
    return "Model-visible command constraints. Follow this YAML."


def review_contract_visibility_note() -> str:
    return "Review contract schema. Follow this YAML."
