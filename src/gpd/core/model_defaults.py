"""Default PydanticAI model identifiers for GPD agents.

Centralizes model selection so that every GPD agent uses a single source of
truth.  Override via environment variables:

    GPD_MODEL       — default model for most agents (sonnet-tier)
    GPD_FAST_MODEL  — fast/cheap model for curation, triage, etc. (haiku-tier)

Model specs may include an effort suffix (e.g. ``"openai:gpt-5.2-low"``).
Use :func:`resolve_model_and_settings` to split into a base model ID for
the ``Agent()`` constructor and a ``model_settings`` dict for ``.run()``.
"""

from __future__ import annotations

import os

__all__ = [
    "GPD_DEFAULT_FAST_MODEL",
    "GPD_DEFAULT_MODEL",
    "resolve_model_and_settings",
]

GPD_DEFAULT_MODEL: str = os.environ.get("GPD_MODEL", "anthropic:claude-sonnet-4-5-20250929")
"""Primary model used by most GPD PydanticAI agents."""

GPD_DEFAULT_FAST_MODEL: str = os.environ.get("GPD_FAST_MODEL", "anthropic:claude-haiku-4-5-20251001")
"""Cheap/fast model used for curation gating and lightweight classification."""


def resolve_model_and_settings(spec: str) -> tuple[str, dict[str, object]]:
    """Parse a PSI model spec into ``(agent_model_id, model_settings)``.

    Strips effort suffixes like ``-low``, ``-high-budget`` and returns
    provider-specific PydanticAI ``model_settings`` for ``.run()`` calls.
    When no effort suffix is present, returns baseline settings (e.g.
    Anthropic prompt caching and context betas).

    Examples::

        resolve_model_and_settings("openai:gpt-5.2-low")
        # -> ("openai:gpt-5.2", {"openai_reasoning_effort": "low"})

        resolve_model_and_settings("anthropic:claude-sonnet-4-5-20250929")
        # -> ("anthropic:claude-sonnet-4-5-20250929", {<baseline Anthropic settings>})
    """
    from inference_providers.effort import (
        base_model_settings,
        effort_to_model_settings,
        parse_model_spec,
    )

    provider, base, effort = parse_model_spec(spec)
    if base is None:
        return spec, {}
    agent_model = f"{provider}:{base}" if provider else base
    if effort:
        settings = effort_to_model_settings(provider, base, effort)
    else:
        settings = base_model_settings(provider, base) if provider else {}
    return agent_model, settings
