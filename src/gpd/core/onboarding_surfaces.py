"""Shared beginner-onboarding surface helpers.

This module keeps the beginner startup ladder and runtime-facing command matrix
derived from one place so README/docs/help/install tests do not need to repeat
runtime literals by hand.
"""

from __future__ import annotations

from dataclasses import dataclass

from gpd.adapters import get_adapter, iter_runtime_descriptors
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


def beginner_runtime_surface(runtime_name: str) -> BeginnerRuntimeSurface:
    adapter = get_adapter(runtime_name)
    descriptor = next(
        descriptor
        for descriptor in iter_runtime_descriptors()
        if descriptor.runtime_name == runtime_name
    )
    new_project_command = adapter.new_project_command
    return BeginnerRuntimeSurface(
        runtime_name=runtime_name,
        display_name=descriptor.display_name,
        install_flag=descriptor.install_flag,
        launch_command=adapter.launch_command,
        help_command=adapter.help_command,
        start_command=adapter.format_command("start"),
        tour_command=adapter.format_command("tour"),
        new_project_command=new_project_command,
        new_project_minimal_command=f"{new_project_command} --minimal",
        map_research_command=adapter.map_research_command,
        resume_work_command=adapter.format_command("resume-work"),
        settings_command=adapter.format_command("settings"),
    )


def beginner_runtime_surfaces() -> tuple[BeginnerRuntimeSurface, ...]:
    return tuple(beginner_runtime_surface(descriptor.runtime_name) for descriptor in iter_runtime_descriptors())
