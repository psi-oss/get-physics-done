from __future__ import annotations

from pathlib import Path

from gpd.adapters import get_adapter
from gpd.adapters.runtime_catalog import get_runtime_capabilities, iter_runtime_descriptors

_RUNTIME_DESCRIPTORS = tuple(iter_runtime_descriptors())
RUNTIME_NAMES = tuple(descriptor.runtime_name for descriptor in _RUNTIME_DESCRIPTORS)


def _runtime_with_permissions_surface_or_first(surface: str) -> str:
    for descriptor in _RUNTIME_DESCRIPTORS:
        if get_runtime_capabilities(descriptor.runtime_name).permissions_surface == surface:
            return descriptor.runtime_name
    return RUNTIME_NAMES[0]


PRIMARY_RUNTIME = _runtime_with_permissions_surface_or_first("config-file")
FOREIGN_RUNTIME = next((runtime_name for runtime_name in RUNTIME_NAMES if runtime_name != PRIMARY_RUNTIME), PRIMARY_RUNTIME)


def runtime_descriptor(runtime_name: str):
    return next(descriptor for descriptor in _RUNTIME_DESCRIPTORS if descriptor.runtime_name == runtime_name)


def runtime_config_dir_name(runtime_name: str) -> str:
    return get_adapter(runtime_name).config_dir_name


def runtime_launch_executable(runtime_name: str) -> str:
    launch_command = get_adapter(runtime_name).launch_command
    return launch_command.split()[0] if launch_command.split() else launch_command


def runtime_display_name(runtime_name: str) -> str:
    return get_adapter(runtime_name).display_name


def runtime_install_flag(runtime_name: str) -> str:
    return runtime_descriptor(runtime_name).install_flag


def runtime_help_command(runtime_name: str) -> str:
    return get_adapter(runtime_name).help_command


def runtime_start_command(runtime_name: str) -> str:
    return get_adapter(runtime_name).format_command("start")


def runtime_tour_command(runtime_name: str) -> str:
    return get_adapter(runtime_name).format_command("tour")


def runtime_new_project_command(runtime_name: str) -> str:
    return get_adapter(runtime_name).new_project_command


def runtime_map_research_command(runtime_name: str) -> str:
    return get_adapter(runtime_name).map_research_command


def runtime_resume_work_command(runtime_name: str) -> str:
    return get_adapter(runtime_name).format_command("resume-work")


def runtime_suggest_next_command(runtime_name: str) -> str:
    return get_adapter(runtime_name).format_command("suggest-next")


def runtime_pause_work_command(runtime_name: str) -> str:
    return get_adapter(runtime_name).format_command("pause-work")


def runtime_with_permissions_surface(surface: str) -> str:
    return next(
        descriptor.runtime_name
        for descriptor in _RUNTIME_DESCRIPTORS
        if get_runtime_capabilities(descriptor.runtime_name).permissions_surface == surface
    )


def runtime_with_multiword_alias(*, exclude: tuple[str, ...] = ()) -> tuple[str, str]:
    excluded = set(exclude)
    for descriptor in _RUNTIME_DESCRIPTORS:
        if descriptor.runtime_name in excluded:
            continue
        aliases = tuple(alias for alias in descriptor.selection_aliases if " " in alias)
        if aliases:
            return descriptor.runtime_name, aliases[0]
    raise LookupError("No runtime with a multiword selection alias was found")


def runtime_target_dir(root: Path, runtime_name: str = PRIMARY_RUNTIME) -> Path:
    return root / runtime_config_dir_name(runtime_name)
