"""Prompt-safe runtime bridge for Research Persona capsules.

Workflow code should use this module when it needs persona-aware context at
prompt time. The bridge only returns role capsules produced by the existing
Research Persona projection helpers; it does not expose or mutate the private
profile snapshot.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from gpd.core.research_persona import (
    RESEARCH_PERSONA_CAPSULE_ROLE_VALUES,
    ResearchPersona,
    ResearchPersonaCapsule,
    ResearchPersonaCapsuleRole,
    ResearchPersonaError,
    build_research_persona_capsule,
)
from gpd.core.research_persona import load_research_persona as _load_stored_persona
from gpd.core.research_persona import research_persona_path as _stored_persona_path

__all__ = [
    "DEFAULT_RESEARCH_PERSONA_RUNTIME_ROLES",
    "RESEARCH_PERSONA_RUNTIME_ROLE_VALUES",
    "ResearchPersonaCapsuleBundle",
    "ResearchPersonaRuntimeContext",
    "ResearchPersonaWorkflowCapsuleSelection",
    "build_research_persona_capsule_bundle",
    "build_research_persona_runtime_context",
    "select_research_persona_capsules_for_workflow",
]


RESEARCH_PERSONA_RUNTIME_SCHEMA_VERSION = 1
RESEARCH_PERSONA_RUNTIME_ROLE_VALUES: tuple[str, ...] = RESEARCH_PERSONA_CAPSULE_ROLE_VALUES
DEFAULT_RESEARCH_PERSONA_RUNTIME_ROLES: tuple[str, ...] = RESEARCH_PERSONA_RUNTIME_ROLE_VALUES

ResearchPersonaRuntimeSource = Literal[
    "stored_profile",
    "provided_persona",
    "missing_profile",
    "disabled",
    "invalid_profile",
]

_ROLE_ALIASES: dict[str, str] = {
    "plan": "planner",
    "planning": "planner",
    "execute": "executor",
    "execution": "executor",
    "verify": "verifier",
    "verification": "verifier",
    "writer": "paper_writer",
    "paper": "paper_writer",
    "paper-writer": "paper_writer",
    "paper_writer": "paper_writer",
    "lit": "literature",
    "bibliography": "literature",
    "bibliographer": "literature",
    "recover": "recovery",
    "debug": "recovery",
    "explain": "explainer",
    "expertise": "explainer",
    "expertise-aware": "explainer",
    "expertise_aware": "explainer",
    "researcher-doppelganger": "doppelganger",
    "researcher_doppelganger": "doppelganger",
    "scientific-taste": "taste",
    "scientific_taste": "taste",
    "taste-model": "taste",
    "taste_model": "taste",
}
_WORKFLOW_ROLE_HINTS: dict[str, tuple[str, ...]] = {
    "plan": ("planner", "explainer", "taste"),
    "planning": ("planner", "explainer", "taste"),
    "new-project": ("planner", "explainer", "taste"),
    "execute": ("executor", "verifier", "recovery"),
    "execution": ("executor", "verifier", "recovery"),
    "verify": ("verifier", "explainer"),
    "verification": ("verifier", "explainer"),
    "review": ("verifier", "explainer"),
    "write-paper": ("paper_writer", "literature", "verifier"),
    "paper": ("paper_writer", "literature", "verifier"),
    "literature": ("literature", "planner"),
    "recovery": ("recovery", "verifier"),
    "debug": ("recovery", "verifier"),
    "persona-applications": ("doppelganger", "explainer", "taste"),
    "doppelganger": ("doppelganger",),
    "explain": ("explainer",),
    "taste": ("taste",),
}
_WORKFLOW_FALLBACK_ROLES: tuple[str, ...] = ("planner", "executor", "verifier")


class _RuntimeModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _strict_bool(value: object) -> bool:
    if type(value) is bool:
        return value
    raise ValueError("must be a boolean")


def _required_string(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("must be a string")
    text = value.strip()
    if not text:
        raise ValueError("must not be blank")
    return text


def _strict_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("must be a list of strings")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise ValueError("must contain only strings")
        text = item.strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized


def _strict_counts(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError("must be a mapping")
    counts: dict[str, int] = {}
    for key, count in value.items():
        if not isinstance(key, str):
            raise ValueError("count keys must be strings")
        if type(count) is bool or not isinstance(count, int) or count < 0:
            raise ValueError("count values must be non-negative integers")
        counts[key] = count
    return counts


def _strict_prompt_safety(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("must be a mapping")
    return dict(value)


def _normalize_role(role: object) -> ResearchPersonaCapsuleRole:
    if not isinstance(role, str):
        raise ResearchPersonaError("research persona capsule role must be a string")
    raw = role.strip()
    if not raw:
        raise ResearchPersonaError("research persona capsule role must not be blank")
    normalized = raw.casefold().replace("_", "-")
    canonical = _ROLE_ALIASES.get(normalized, raw.strip().casefold().replace("-", "_"))
    for supported in RESEARCH_PERSONA_RUNTIME_ROLE_VALUES:
        if canonical.casefold() == supported.casefold():
            return supported  # type: ignore[return-value]
    choices = ", ".join(RESEARCH_PERSONA_RUNTIME_ROLE_VALUES)
    raise ResearchPersonaError(f"research persona capsule role must be one of: {choices}")


def _normalize_roles(
    roles: object | None,
    *,
    default_roles: Iterable[object] = DEFAULT_RESEARCH_PERSONA_RUNTIME_ROLES,
) -> tuple[ResearchPersonaCapsuleRole, ...]:
    if roles is None:
        raw_roles = tuple(default_roles)
    elif isinstance(roles, str):
        raw_roles = (roles,)
    else:
        try:
            raw_roles = tuple(roles)  # type: ignore[arg-type]
        except TypeError as exc:
            raise ResearchPersonaError("research persona roles must be a string or iterable of strings") from exc
    normalized: list[ResearchPersonaCapsuleRole] = []
    seen: set[str] = set()
    for role in raw_roles:
        canonical = _normalize_role(role)
        if canonical in seen:
            continue
        seen.add(canonical)
        normalized.append(canonical)
    return tuple(normalized)


def _workflow_key(workflow_id: object) -> str:
    if not isinstance(workflow_id, str):
        raise ResearchPersonaError("workflow_id must be a string")
    text = workflow_id.strip().casefold()
    if not text:
        raise ResearchPersonaError("workflow_id must not be blank")
    if text.startswith("gpd:"):
        text = text.removeprefix("gpd:")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _workflow_roles(workflow_id: str) -> tuple[ResearchPersonaCapsuleRole, ...]:
    key = _workflow_key(workflow_id)
    if key in _WORKFLOW_ROLE_HINTS:
        return _normalize_roles(_WORKFLOW_ROLE_HINTS[key])
    for fragment, roles in _WORKFLOW_ROLE_HINTS.items():
        if fragment in key:
            return _normalize_roles(roles)
    return _normalize_roles(_WORKFLOW_FALLBACK_ROLES)


def _capsule_has_prompt_signals(capsule: ResearchPersonaCapsule) -> bool:
    return bool(
        capsule.facts
        or capsule.axes
        or capsule.standing_preferences
        or capsule.negative_preferences
        or capsule.tools
        or capsule.research_areas
        or capsule.expertise
        or capsule.workstyle
        or capsule.scientific_taste
    )


def _role_counts(
    *,
    requested_roles: Iterable[str],
    capsules: Mapping[str, ResearchPersonaCapsule],
) -> dict[str, int]:
    requested = tuple(requested_roles)
    return {
        "requested": len(requested),
        "capsules": len(capsules),
        "available": len(capsules),
        "missing": max(len(requested) - len(capsules), 0),
        "with_prompt_safe_signals": sum(1 for capsule in capsules.values() if _capsule_has_prompt_signals(capsule)),
        "with_prompt_safe_facts": sum(1 for capsule in capsules.values() if capsule.facts),
    }


def _prompt_safety_payload() -> dict[str, object]:
    return {
        "capsule_purpose": "prompt",
        "capsule_builder": "build_research_persona_capsule",
        "raw_profile_exposed": False,
        "private_local_exposed": False,
        "project_private_exposed": False,
        "never_prompt_exposed": False,
        "store_mutation": False,
    }


def _integration_instructions(*, enabled: bool, workflow_id: str | None = None) -> list[str]:
    workflow_hint = f" for workflow {workflow_id}" if workflow_id else ""
    if not enabled:
        return [
            f"Proceed{workflow_hint} without Research Persona personalization.",
            "Do not read raw profile storage from workflow prompts.",
            "If personalization is needed, ask for an approved persona patch before retrying.",
        ]
    return [
        f"Use only the selected ResearchPersonaCapsule objects{workflow_hint} as prompt context.",
        "Treat capsules as advisory style and preference hints, not as durable memory.",
        "If a persona change is needed, emit a ResearchPersonaPatch for explicit approval.",
    ]


def _empty_bundle(
    *,
    requested_roles: tuple[ResearchPersonaCapsuleRole, ...],
    profile_exists: bool,
    profile_source: ResearchPersonaRuntimeSource,
    warnings: Iterable[str],
) -> ResearchPersonaCapsuleBundle:
    warning_list = _strict_string_list(list(warnings))
    return ResearchPersonaCapsuleBundle(
        enabled=False,
        profile_exists=profile_exists,
        profile_source=profile_source,
        requested_roles=list(requested_roles),
        capsules={},
        role_counts=_role_counts(requested_roles=requested_roles, capsules={}),
        warnings=warning_list,
        integration_instructions=_integration_instructions(enabled=False),
        prompt_safety=_prompt_safety_payload(),
    )


class ResearchPersonaCapsuleBundle(_RuntimeModel):
    """A prompt-safe bundle of role capsules plus runtime metadata."""

    schema_version: int = RESEARCH_PERSONA_RUNTIME_SCHEMA_VERSION
    enabled: bool
    profile_exists: bool
    profile_source: ResearchPersonaRuntimeSource
    requested_roles: list[ResearchPersonaCapsuleRole] = Field(default_factory=list)
    capsules: dict[ResearchPersonaCapsuleRole, ResearchPersonaCapsule] = Field(default_factory=dict)
    role_counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    integration_instructions: list[str] = Field(default_factory=list)
    prompt_safety: dict[str, object] = Field(default_factory=dict)

    @field_validator("enabled", "profile_exists", mode="before")
    @classmethod
    def _normalize_bool(cls, value: object) -> bool:
        return _strict_bool(value)

    @field_validator("requested_roles", mode="before")
    @classmethod
    def _normalize_requested_roles(cls, value: object) -> list[ResearchPersonaCapsuleRole]:
        return list(_normalize_roles(value))

    @field_validator("role_counts", mode="before")
    @classmethod
    def _normalize_role_counts(cls, value: object) -> dict[str, int]:
        return _strict_counts(value)

    @field_validator("warnings", "integration_instructions", mode="before")
    @classmethod
    def _normalize_text_list(cls, value: object) -> list[str]:
        return _strict_string_list(value)

    @field_validator("prompt_safety", mode="before")
    @classmethod
    def _normalize_prompt_safety(cls, value: object) -> dict[str, object]:
        return _strict_prompt_safety(value)


class ResearchPersonaRuntimeContext(ResearchPersonaCapsuleBundle):
    """Workflow-facing Research Persona runtime context.

    The context is intentionally the same shape as a capsule bundle, with an
    explicit kind marker for routing code that handles multiple context types.
    """

    runtime_kind: Literal["research_persona_runtime_context"] = "research_persona_runtime_context"


class ResearchPersonaWorkflowCapsuleSelection(_RuntimeModel):
    """Selected capsule subset for a concrete workflow."""

    schema_version: int = RESEARCH_PERSONA_RUNTIME_SCHEMA_VERSION
    workflow_id: str
    enabled: bool
    profile_exists: bool
    selected_roles: list[ResearchPersonaCapsuleRole] = Field(default_factory=list)
    missing_roles: list[ResearchPersonaCapsuleRole] = Field(default_factory=list)
    capsules: dict[ResearchPersonaCapsuleRole, ResearchPersonaCapsule] = Field(default_factory=dict)
    role_counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    integration_instructions: list[str] = Field(default_factory=list)
    prompt_safety: dict[str, object] = Field(default_factory=dict)

    @field_validator("workflow_id", mode="before")
    @classmethod
    def _normalize_workflow_id(cls, value: object) -> str:
        return _required_string(value)

    @field_validator("enabled", "profile_exists", mode="before")
    @classmethod
    def _normalize_bool(cls, value: object) -> bool:
        return _strict_bool(value)

    @field_validator("selected_roles", "missing_roles", mode="before")
    @classmethod
    def _normalize_roles_field(cls, value: object) -> list[ResearchPersonaCapsuleRole]:
        return list(_normalize_roles(value, default_roles=()))

    @field_validator("role_counts", mode="before")
    @classmethod
    def _normalize_role_counts(cls, value: object) -> dict[str, int]:
        return _strict_counts(value)

    @field_validator("warnings", "integration_instructions", mode="before")
    @classmethod
    def _normalize_text_list(cls, value: object) -> list[str]:
        return _strict_string_list(value)

    @field_validator("prompt_safety", mode="before")
    @classmethod
    def _normalize_prompt_safety(cls, value: object) -> dict[str, object]:
        return _strict_prompt_safety(value)


def build_research_persona_capsule_bundle(
    *,
    roles: Iterable[object] | str | None = None,
    data_root: Path | None = None,
    persona: ResearchPersona | None = None,
    enabled: bool = True,
) -> ResearchPersonaCapsuleBundle:
    """Build a deterministic prompt-safe capsule bundle for runtime use."""

    requested_roles = _normalize_roles(roles)
    if not enabled:
        profile_exists = False if persona is not None else _stored_persona_path(data_root).is_file()
        return _empty_bundle(
            requested_roles=requested_roles,
            profile_exists=profile_exists,
            profile_source="disabled",
            warnings=("Research Persona runtime bridge is disabled for this request.",),
        )

    if persona is not None and not isinstance(persona, ResearchPersona):
        raise ResearchPersonaError("runtime context requires a ResearchPersona instance or stored profile")

    profile_source: ResearchPersonaRuntimeSource
    profile_exists: bool
    if persona is None:
        profile_exists = _stored_persona_path(data_root).is_file()
        if not profile_exists:
            return _empty_bundle(
                requested_roles=requested_roles,
                profile_exists=False,
                profile_source="missing_profile",
                warnings=("No stored Research Persona profile was found.",),
            )
        try:
            persona = _load_stored_persona(data_root, strict=True)
        except ResearchPersonaError as exc:
            return _empty_bundle(
                requested_roles=requested_roles,
                profile_exists=True,
                profile_source="invalid_profile",
                warnings=(f"Stored Research Persona profile could not be loaded: {exc}",),
            )
        profile_source = "stored_profile"
    else:
        profile_exists = False
        profile_source = "provided_persona"

    capsules: dict[ResearchPersonaCapsuleRole, ResearchPersonaCapsule] = {}
    warnings: list[str] = []
    for role in requested_roles:
        capsule = build_research_persona_capsule(persona, role=role)
        capsules[role] = capsule
        if not _capsule_has_prompt_signals(capsule):
            warnings.append(f"{role} capsule has no prompt-safe persona signals.")

    return ResearchPersonaCapsuleBundle(
        enabled=bool(capsules),
        profile_exists=profile_exists,
        profile_source=profile_source,
        requested_roles=list(requested_roles),
        capsules=capsules,
        role_counts=_role_counts(requested_roles=requested_roles, capsules=capsules),
        warnings=warnings,
        integration_instructions=_integration_instructions(enabled=bool(capsules)),
        prompt_safety=_prompt_safety_payload(),
    )


def build_research_persona_runtime_context(
    *,
    roles: Iterable[object] | str | None = None,
    data_root: Path | None = None,
    persona: ResearchPersona | None = None,
    enabled: bool = True,
) -> ResearchPersonaRuntimeContext:
    """Return workflow-facing Research Persona runtime context."""

    bundle = build_research_persona_capsule_bundle(
        roles=roles,
        data_root=data_root,
        persona=persona,
        enabled=enabled,
    )
    payload = bundle.model_dump(mode="python")
    return ResearchPersonaRuntimeContext.model_validate(payload)


def select_research_persona_capsules_for_workflow(
    runtime_context: ResearchPersonaRuntimeContext | ResearchPersonaCapsuleBundle,
    *,
    workflow_id: str,
    roles: Iterable[object] | str | None = None,
) -> ResearchPersonaWorkflowCapsuleSelection:
    """Select prompt-safe role capsules for one workflow."""

    if not isinstance(runtime_context, (ResearchPersonaRuntimeContext, ResearchPersonaCapsuleBundle)):
        raise ResearchPersonaError("workflow capsule selection requires a ResearchPersona runtime context")

    selected_roles = _normalize_roles(roles) if roles is not None else _workflow_roles(workflow_id)
    capsules = {role: runtime_context.capsules[role] for role in selected_roles if role in runtime_context.capsules}
    missing_roles = [role for role in selected_roles if role not in capsules]
    enabled = runtime_context.enabled and bool(capsules)
    warnings = list(runtime_context.warnings)
    if missing_roles:
        warnings.append("Some requested Research Persona capsules were unavailable.")

    return ResearchPersonaWorkflowCapsuleSelection(
        workflow_id=workflow_id,
        enabled=enabled,
        profile_exists=runtime_context.profile_exists,
        selected_roles=list(selected_roles),
        missing_roles=missing_roles,
        capsules=capsules,
        role_counts=_role_counts(requested_roles=selected_roles, capsules=capsules),
        warnings=warnings,
        integration_instructions=_integration_instructions(enabled=enabled, workflow_id=workflow_id),
        prompt_safety=runtime_context.prompt_safety,
    )
