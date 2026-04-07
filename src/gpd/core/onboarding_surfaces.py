"""Shared beginner-onboarding surface helpers.

This module keeps the beginner startup ladder and runtime-facing command matrix
derived from descriptor-owned runtime metadata so README/docs/help/install tests
do not need to repeat runtime literals by hand.
"""

from __future__ import annotations

from dataclasses import dataclass

from gpd.adapters import iter_runtime_descriptors
from gpd.adapters.runtime_catalog import RuntimeDescriptor, get_runtime_descriptor, normalize_runtime_name
from gpd.command_labels import validated_public_command_prefix
from gpd.core.public_surface_contract import beginner_onboarding_hub_url, beginner_startup_ladder_text

__all__ = [
    "BeginnerRuntimeSurface",
    "beginner_onboarding_hub_url",
    "beginner_runtime_surface",
    "beginner_runtime_surfaces",
    "beginner_startup_ladder_text",
]


@dataclass(frozen=True, slots=True)
class BeginnerRuntimeSurface:
    runtime_name: str
    display_name: str
    install_flag: str
    launch_command: str
    help_command: str
    start_command: str
    tour_command: str
    new_project_command: str
    new_project_minimal_command: str
    map_research_command: str
    resume_work_command: str
    settings_command: str


def _public_command_prefix(descriptor: RuntimeDescriptor) -> str:
    return validated_public_command_prefix(descriptor)


def _beginner_runtime_surface_from_descriptor(descriptor: RuntimeDescriptor) -> BeginnerRuntimeSurface:
    public_prefix = _public_command_prefix(descriptor)
    return BeginnerRuntimeSurface(
        runtime_name=descriptor.runtime_name,
        display_name=descriptor.display_name,
        install_flag=descriptor.install_flag,
        launch_command=descriptor.launch_command,
        help_command=f"{public_prefix}help",
        start_command=f"{public_prefix}start",
        tour_command=f"{public_prefix}tour",
        new_project_command=f"{public_prefix}new-project",
        new_project_minimal_command=f"{public_prefix}new-project --minimal",
        map_research_command=f"{public_prefix}map-research",
        resume_work_command=f"{public_prefix}resume-work",
        settings_command=f"{public_prefix}settings",
    )


def beginner_runtime_surface(runtime_name: str) -> BeginnerRuntimeSurface:
    try:
        descriptor = get_runtime_descriptor(runtime_name)
    except KeyError:
        normalized_runtime = normalize_runtime_name(runtime_name)
        if normalized_runtime is None:
            raise
        descriptor = get_runtime_descriptor(normalized_runtime)
    return _beginner_runtime_surface_from_descriptor(descriptor)


def beginner_runtime_surfaces() -> tuple[BeginnerRuntimeSurface, ...]:
    return tuple(_beginner_runtime_surface_from_descriptor(descriptor) for descriptor in iter_runtime_descriptors())
