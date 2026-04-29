"""Structured public-surface contract for repeated onboarding and local CLI guidance."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files

__all__ = [
    "BeginnerOnboardingContract",
    "LocalCliBridgeContract",
    "LocalCliNamedCommandsContract",
    "PostStartSettingsContract",
    "PublicSurfaceContract",
    "RecoveryLadderContract",
    "ResumeAuthorityContract",
    "beginner_onboarding_contract",
    "beginner_onboarding_caveats",
    "beginner_onboarding_hub_url",
    "beginner_preflight_requirements",
    "beginner_startup_ladder",
    "beginner_startup_ladder_text",
    "load_public_surface_contract",
    "local_cli_bridge_commands",
    "local_cli_bridge_contract",
    "local_cli_cost_command",
    "local_cli_doctor_command",
    "local_cli_doctor_global_command",
    "local_cli_doctor_local_command",
    "local_cli_help_command",
    "local_cli_install_local_example_command",
    "local_cli_integrations_status_wolfram_command",
    "local_cli_observe_execution_command",
    "local_cli_permissions_status_command",
    "local_cli_bridge_note",
    "local_cli_presets_list_command",
    "local_cli_plan_preflight_command",
    "local_cli_resume_command",
    "local_cli_resume_recent_command",
    "local_cli_permissions_sync_command",
    "local_cli_unattended_readiness_command",
    "local_cli_validate_command_context_command",
    "local_cli_bridge_purpose_phrase",
    "post_start_settings_contract",
    "post_start_settings_note",
    "post_start_settings_recommendation",
    "recovery_cross_workspace_command",
    "recovery_ladder_contract",
    "recovery_local_snapshot_command",
    "recovery_ladder_note",
    "resume_authority_contract",
    "resume_authority_fields",
]


@dataclass(frozen=True, slots=True)
class BeginnerOnboardingContract:
    hub_url: str
    preflight_requirements: tuple[str, ...]
    caveats: tuple[str, ...]
    startup_ladder: tuple[str, ...]

    def render_startup_ladder(self) -> str:
        return "`" + " -> ".join(self.startup_ladder) + "`"


@dataclass(frozen=True, slots=True)
class LocalCliNamedCommandsContract:
    help: str
    doctor: str
    unattended_readiness: str
    permissions_status: str
    permissions_sync: str
    resume: str
    resume_recent: str
    observe_execution: str
    cost: str
    presets_list: str
    plan_preflight: str
    integrations_status_wolfram: str

    def ordered(self) -> tuple[str, ...]:
        return (
            self.help,
            self.doctor,
            self.unattended_readiness,
            self.permissions_status,
            self.permissions_sync,
            self.resume,
            self.resume_recent,
            self.observe_execution,
            self.cost,
            self.presets_list,
            self.plan_preflight,
            self.integrations_status_wolfram,
        )


@dataclass(frozen=True, slots=True)
class LocalCliBridgeContract:
    commands: tuple[str, ...]
    named_commands: LocalCliNamedCommandsContract
    terminal_phrase: str
    purpose_phrase: str
    install_local_example: str
    doctor_local_command: str
    doctor_global_command: str
    validate_command_context_command: str

    def render_note(self) -> str:
        return (
            f"Use `{self.named_commands.help}` {self.terminal_phrase} for the broader local CLI surface: "
            f"{self.purpose_phrase}."
        )


@dataclass(frozen=True, slots=True)
class PostStartSettingsContract:
    primary_sentence: str
    default_sentence: str

    def render_note(self) -> str:
        return f"{self.primary_sentence} {self.default_sentence}"


@dataclass(frozen=True, slots=True)
class ResumeAuthorityContract:
    durable_authority_phrase: str
    public_vocabulary_intro: str
    public_fields: tuple[str, ...]

    def render_public_field_list(self) -> str:
        return ", ".join(f"`{field}`" for field in self.public_fields)


@dataclass(frozen=True, slots=True)
class RecoveryLadderContract:
    title: str
    local_snapshot_command: str
    local_snapshot_phrase: str
    cross_workspace_command: str
    cross_workspace_phrase: str
    resume_phrase: str
    next_phrase: str
    pause_phrase: str

    def render_note(
        self,
        *,
        resume_work_phrase: str,
        suggest_next_phrase: str,
        pause_work_phrase: str,
    ) -> str:
        return (
            f"{self.title}: use `{self.local_snapshot_command}` for {self.local_snapshot_phrase}. "
            f"If that is the wrong workspace, use `{self.cross_workspace_command}` to {self.cross_workspace_phrase}, "
            f"then {self.resume_phrase} with {resume_work_phrase}. After resuming, "
            f"{suggest_next_phrase} is {self.next_phrase}. Before stepping away mid-phase, "
            f"run {pause_work_phrase} so that ladder has {self.pause_phrase}."
        )


@dataclass(frozen=True, slots=True)
class PublicSurfaceContract:
    beginner_onboarding: BeginnerOnboardingContract
    local_cli_bridge: LocalCliBridgeContract
    post_start_settings: PostStartSettingsContract
    resume_authority: ResumeAuthorityContract
    recovery_ladder: RecoveryLadderContract


_LOCAL_CLI_INSTALL_LOCAL_EXAMPLE_COMMAND = "gpd install <runtime> --local"
_LOCAL_CLI_DOCTOR_LOCAL_COMMAND = "gpd doctor --runtime <runtime> --local"
_LOCAL_CLI_DOCTOR_GLOBAL_COMMAND = "gpd doctor --runtime <runtime> --global"
_LOCAL_CLI_VALIDATE_COMMAND_CONTEXT_COMMAND = "gpd validate command-context <name>"


def _require_object(payload: object, *, label: str) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _require_present_keys(payload: dict[str, object], *, label: str, keys: tuple[str, ...]) -> None:
    missing = sorted(key for key in keys if key not in payload)
    if not missing:
        return
    raise ValueError(f"{label} is missing required key(s): {', '.join(missing)}")


def _require_allowed_keys(payload: dict[str, object], *, label: str, keys: tuple[str, ...]) -> None:
    unknown = sorted(key for key in payload if key not in keys)
    if not unknown:
        return
    raise ValueError(f"{label} contains unknown key(s): {', '.join(unknown)}")


@dataclass(frozen=True, slots=True)
class PublicSurfaceContractSchema:
    top_level_keys: tuple[str, ...]
    section_keys: dict[str, tuple[str, ...]]
    local_cli_named_command_keys: tuple[str, ...]


def _dataclass_field_names(contract_type: type[object]) -> tuple[str, ...]:
    return tuple(contract_type.__dataclass_fields__)


def _require_schema_matches_code(schema: PublicSurfaceContractSchema) -> None:
    expected_top_level_keys = ("schema_version", *_dataclass_field_names(PublicSurfaceContract))
    if schema.top_level_keys != expected_top_level_keys:
        raise ValueError(
            "public_surface_contract_schema.top_level_keys must exactly match the code-supported public surface fields"
        )

    expected_section_keys = {
        "beginner_onboarding": _dataclass_field_names(BeginnerOnboardingContract),
        "local_cli_bridge": _dataclass_field_names(LocalCliBridgeContract),
        "post_start_settings": _dataclass_field_names(PostStartSettingsContract),
        "resume_authority": _dataclass_field_names(ResumeAuthorityContract),
        "recovery_ladder": _dataclass_field_names(RecoveryLadderContract),
    }
    for section_name, expected_keys in expected_section_keys.items():
        if schema.section_keys.get(section_name) != expected_keys:
            raise ValueError(
                f"public_surface_contract_schema.sections.{section_name}.keys must exactly match "
                "the code-supported contract fields"
            )

    expected_named_command_keys = _dataclass_field_names(LocalCliNamedCommandsContract)
    if schema.local_cli_named_command_keys != expected_named_command_keys:
        raise ValueError(
            "public_surface_contract_schema.sections.local_cli_bridge.named_commands.ordered_keys "
            "must exactly match the code-supported named command fields"
        )


def _require_schema_string_tuple(value: object, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty list")
    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label} entries must be non-empty strings")
        normalized = item.strip()
        if normalized in seen:
            raise ValueError(f"{label} must not contain duplicates")
        seen.add(normalized)
        items.append(normalized)
    return tuple(items)


@lru_cache(maxsize=1)
def load_public_surface_contract_schema() -> PublicSurfaceContractSchema:
    """Load the static schema that governs the public surface contract payload."""

    schema_path = files("gpd.core").joinpath("public_surface_contract_schema.json")
    raw_payload = json.loads(schema_path.read_text(encoding="utf-8"))
    payload = _require_object(raw_payload, label="public_surface_contract_schema")
    _require_present_keys(
        payload,
        label="public_surface_contract_schema",
        keys=("schema_version", "top_level_keys", "sections"),
    )
    _require_allowed_keys(
        payload,
        label="public_surface_contract_schema",
        keys=("schema_version", "top_level_keys", "sections"),
    )

    schema_version = payload.get("schema_version")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version != 1:
        raise ValueError(f"Unsupported public surface contract schema_version: {schema_version!r}")

    top_level_keys = _require_schema_string_tuple(
        payload.get("top_level_keys"),
        label="public_surface_contract_schema.top_level_keys",
    )
    sections_payload = _require_object(payload.get("sections"), label="public_surface_contract_schema.sections")
    section_names = (
        "beginner_onboarding",
        "local_cli_bridge",
        "post_start_settings",
        "resume_authority",
        "recovery_ladder",
    )
    _require_present_keys(
        sections_payload,
        label="public_surface_contract_schema.sections",
        keys=section_names,
    )
    _require_allowed_keys(
        sections_payload,
        label="public_surface_contract_schema.sections",
        keys=section_names,
    )

    section_keys: dict[str, tuple[str, ...]] = {}
    local_cli_named_command_keys: tuple[str, ...] | None = None
    section_key_names = {
        "beginner_onboarding": ("keys",),
        "local_cli_bridge": ("keys", "named_commands"),
        "post_start_settings": ("keys",),
        "resume_authority": ("keys",),
        "recovery_ladder": ("keys",),
    }

    for section_name in section_names:
        section_payload = _require_object(
            sections_payload.get(section_name),
            label=f"public_surface_contract_schema.sections.{section_name}",
        )
        allowed_schema_keys = section_key_names[section_name]
        _require_present_keys(
            section_payload,
            label=f"public_surface_contract_schema.sections.{section_name}",
            keys=allowed_schema_keys,
        )
        _require_allowed_keys(
            section_payload,
            label=f"public_surface_contract_schema.sections.{section_name}",
            keys=allowed_schema_keys,
        )
        section_keys[section_name] = _require_schema_string_tuple(
            section_payload.get("keys"),
            label=f"public_surface_contract_schema.sections.{section_name}.keys",
        )

        if section_name != "local_cli_bridge":
            continue

        named_commands_payload = _require_object(
            section_payload.get("named_commands"),
            label="public_surface_contract_schema.sections.local_cli_bridge.named_commands",
        )
        _require_present_keys(
            named_commands_payload,
            label="public_surface_contract_schema.sections.local_cli_bridge.named_commands",
            keys=("ordered_keys",),
        )
        _require_allowed_keys(
            named_commands_payload,
            label="public_surface_contract_schema.sections.local_cli_bridge.named_commands",
            keys=("ordered_keys",),
        )
        local_cli_named_command_keys = _require_schema_string_tuple(
            named_commands_payload.get("ordered_keys"),
            label="public_surface_contract_schema.sections.local_cli_bridge.named_commands.ordered_keys",
        )

    if local_cli_named_command_keys is None:
        raise ValueError("public_surface_contract_schema.local_cli_bridge is incomplete")

    schema = PublicSurfaceContractSchema(
        top_level_keys=top_level_keys,
        section_keys=section_keys,
        local_cli_named_command_keys=local_cli_named_command_keys,
    )
    _require_schema_matches_code(schema)
    return schema


def _require_string(payload: dict[str, object], key: str, *, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{key} must be a non-empty string")
    return value.strip()


def _require_string_list(payload: dict[str, object], key: str, *, label: str) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label}.{key} must be a non-empty list")
    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label}.{key} entries must be non-empty strings")
        normalized = item.strip()
        if normalized in seen:
            raise ValueError(f"{label}.{key} must not contain duplicates")
        seen.add(normalized)
        items.append(normalized)
    return tuple(items)


def _require_exact_command(commands: tuple[str, ...], *, label: str, command: str) -> str:
    if command not in commands:
        raise ValueError(f"{label}.commands must include {command!r}")
    return command


def _local_cli_bridge_command(command: str) -> str:
    return _require_exact_command(local_cli_bridge_commands(), label="local_cli_bridge", command=command)


def _require_local_cli_bridge_template(command: str, *, label: str, expected: str) -> str:
    if command != expected:
        raise ValueError(f"{label} must equal {expected!r}")
    return command


def _require_local_cli_named_commands(
    payload: dict[str, object],
    *,
    bridge_commands: tuple[str, ...],
    named_command_keys: tuple[str, ...],
) -> LocalCliNamedCommandsContract:
    named_payload = _require_object(payload.get("named_commands"), label="local_cli_bridge.named_commands")
    _require_present_keys(
        named_payload,
        label="local_cli_bridge.named_commands",
        keys=named_command_keys,
    )
    _require_allowed_keys(
        named_payload,
        label="local_cli_bridge.named_commands",
        keys=named_command_keys,
    )
    named_commands = LocalCliNamedCommandsContract(
        help=_require_string(named_payload, "help", label="local_cli_bridge.named_commands"),
        doctor=_require_string(named_payload, "doctor", label="local_cli_bridge.named_commands"),
        unattended_readiness=_require_string(
            named_payload,
            "unattended_readiness",
            label="local_cli_bridge.named_commands",
        ),
        permissions_status=_require_string(
            named_payload,
            "permissions_status",
            label="local_cli_bridge.named_commands",
        ),
        permissions_sync=_require_string(
            named_payload,
            "permissions_sync",
            label="local_cli_bridge.named_commands",
        ),
        resume=_require_string(named_payload, "resume", label="local_cli_bridge.named_commands"),
        resume_recent=_require_string(named_payload, "resume_recent", label="local_cli_bridge.named_commands"),
        observe_execution=_require_string(
            named_payload,
            "observe_execution",
            label="local_cli_bridge.named_commands",
        ),
        cost=_require_string(named_payload, "cost", label="local_cli_bridge.named_commands"),
        presets_list=_require_string(named_payload, "presets_list", label="local_cli_bridge.named_commands"),
        plan_preflight=_require_string(named_payload, "plan_preflight", label="local_cli_bridge.named_commands"),
        integrations_status_wolfram=_require_string(
            named_payload,
            "integrations_status_wolfram",
            label="local_cli_bridge.named_commands",
        ),
    )
    for command in named_commands.ordered():
        _require_exact_command(bridge_commands, label="local_cli_bridge", command=command)
    if bridge_commands != named_commands.ordered():
        raise ValueError("local_cli_bridge.commands must exactly match local_cli_bridge.named_commands in canonical order")
    return named_commands


@lru_cache(maxsize=1)
def load_public_surface_contract() -> PublicSurfaceContract:
    schema = load_public_surface_contract_schema()
    contract_path = files("gpd.core").joinpath("public_surface_contract.json")
    raw_payload = json.loads(contract_path.read_text(encoding="utf-8"))
    payload = _require_object(raw_payload, label="public_surface_contract")
    _require_present_keys(
        payload,
        label="public_surface_contract",
        keys=schema.top_level_keys,
    )
    _require_allowed_keys(payload, label="public_surface_contract", keys=schema.top_level_keys)

    schema_version = payload.get("schema_version")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version != 1:
        raise ValueError(f"Unsupported public surface contract schema_version: {schema_version!r}")

    beginner_payload = _require_object(payload.get("beginner_onboarding"), label="beginner_onboarding")
    _require_present_keys(
        beginner_payload,
        label="beginner_onboarding",
        keys=schema.section_keys["beginner_onboarding"],
    )
    _require_allowed_keys(
        beginner_payload,
        label="beginner_onboarding",
        keys=schema.section_keys["beginner_onboarding"],
    )
    bridge_payload = _require_object(payload.get("local_cli_bridge"), label="local_cli_bridge")
    _require_present_keys(
        bridge_payload,
        label="local_cli_bridge",
        keys=schema.section_keys["local_cli_bridge"],
    )
    _require_allowed_keys(
        bridge_payload,
        label="local_cli_bridge",
        keys=schema.section_keys["local_cli_bridge"],
    )
    settings_payload = _require_object(payload.get("post_start_settings"), label="post_start_settings")
    _require_present_keys(
        settings_payload,
        label="post_start_settings",
        keys=schema.section_keys["post_start_settings"],
    )
    _require_allowed_keys(
        settings_payload,
        label="post_start_settings",
        keys=schema.section_keys["post_start_settings"],
    )
    resume_authority_payload = _require_object(payload.get("resume_authority"), label="resume_authority")
    _require_present_keys(
        resume_authority_payload,
        label="resume_authority",
        keys=schema.section_keys["resume_authority"],
    )
    _require_allowed_keys(
        resume_authority_payload,
        label="resume_authority",
        keys=schema.section_keys["resume_authority"],
    )
    recovery_payload = _require_object(payload.get("recovery_ladder"), label="recovery_ladder")
    _require_present_keys(
        recovery_payload,
        label="recovery_ladder",
        keys=schema.section_keys["recovery_ladder"],
    )
    _require_allowed_keys(
        recovery_payload,
        label="recovery_ladder",
        keys=schema.section_keys["recovery_ladder"],
    )
    bridge_commands = _require_string_list(bridge_payload, "commands", label="local_cli_bridge")
    named_commands = _require_local_cli_named_commands(
        bridge_payload,
        bridge_commands=bridge_commands,
        named_command_keys=schema.local_cli_named_command_keys,
    )
    recovery_local_snapshot_command = _require_string(
        recovery_payload,
        "local_snapshot_command",
        label="recovery_ladder",
    )
    recovery_cross_workspace_command = _require_string(
        recovery_payload,
        "cross_workspace_command",
        label="recovery_ladder",
    )
    _require_exact_command(bridge_commands, label="local_cli_bridge", command=recovery_local_snapshot_command)
    _require_exact_command(bridge_commands, label="local_cli_bridge", command=recovery_cross_workspace_command)
    if recovery_local_snapshot_command != named_commands.resume:
        raise ValueError(
            "recovery_ladder.local_snapshot_command must equal local_cli_bridge.named_commands.resume"
        )
    if recovery_cross_workspace_command != named_commands.resume_recent:
        raise ValueError(
            "recovery_ladder.cross_workspace_command must equal local_cli_bridge.named_commands.resume_recent"
        )
    resume_authority_public_fields = _require_string_list(
        resume_authority_payload,
        "public_fields",
        label="resume_authority",
    )
    resume_authority_public_vocabulary_intro = _require_string(
        resume_authority_payload,
        "public_vocabulary_intro",
        label="resume_authority",
    )

    return PublicSurfaceContract(
        beginner_onboarding=BeginnerOnboardingContract(
            hub_url=_require_string(beginner_payload, "hub_url", label="beginner_onboarding"),
            preflight_requirements=_require_string_list(
                beginner_payload,
                "preflight_requirements",
                label="beginner_onboarding",
            ),
            caveats=_require_string_list(beginner_payload, "caveats", label="beginner_onboarding"),
            startup_ladder=_require_string_list(beginner_payload, "startup_ladder", label="beginner_onboarding"),
        ),
        local_cli_bridge=LocalCliBridgeContract(
            commands=bridge_commands,
            named_commands=named_commands,
            terminal_phrase=_require_string(bridge_payload, "terminal_phrase", label="local_cli_bridge"),
            purpose_phrase=_require_string(bridge_payload, "purpose_phrase", label="local_cli_bridge"),
            install_local_example=_require_local_cli_bridge_template(
                _require_string(bridge_payload, "install_local_example", label="local_cli_bridge"),
                label="local_cli_bridge.install_local_example",
                expected=_LOCAL_CLI_INSTALL_LOCAL_EXAMPLE_COMMAND,
            ),
            doctor_local_command=_require_local_cli_bridge_template(
                _require_string(
                    bridge_payload,
                    "doctor_local_command",
                    label="local_cli_bridge",
                ),
                label="local_cli_bridge.doctor_local_command",
                expected=_LOCAL_CLI_DOCTOR_LOCAL_COMMAND,
            ),
            doctor_global_command=_require_local_cli_bridge_template(
                _require_string(
                    bridge_payload,
                    "doctor_global_command",
                    label="local_cli_bridge",
                ),
                label="local_cli_bridge.doctor_global_command",
                expected=_LOCAL_CLI_DOCTOR_GLOBAL_COMMAND,
            ),
            validate_command_context_command=_require_local_cli_bridge_template(
                _require_string(
                    bridge_payload,
                    "validate_command_context_command",
                    label="local_cli_bridge",
                ),
                label="local_cli_bridge.validate_command_context_command",
                expected=_LOCAL_CLI_VALIDATE_COMMAND_CONTEXT_COMMAND,
            ),
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
        resume_authority=ResumeAuthorityContract(
            durable_authority_phrase=_require_string(
                resume_authority_payload,
                "durable_authority_phrase",
                label="resume_authority",
            ),
            public_fields=resume_authority_public_fields,
            public_vocabulary_intro=resume_authority_public_vocabulary_intro,
        ),
        recovery_ladder=RecoveryLadderContract(
            title=_require_string(recovery_payload, "title", label="recovery_ladder"),
            local_snapshot_command=recovery_local_snapshot_command,
            local_snapshot_phrase=_require_string(
                recovery_payload,
                "local_snapshot_phrase",
                label="recovery_ladder",
            ),
            cross_workspace_command=recovery_cross_workspace_command,
            cross_workspace_phrase=_require_string(
                recovery_payload,
                "cross_workspace_phrase",
                label="recovery_ladder",
            ),
            resume_phrase=_require_string(
                recovery_payload,
                "resume_phrase",
                label="recovery_ladder",
            ),
            next_phrase=_require_string(
                recovery_payload,
                "next_phrase",
                label="recovery_ladder",
            ),
            pause_phrase=_require_string(
                recovery_payload,
                "pause_phrase",
                label="recovery_ladder",
            ),
        ),
    )


_load_public_surface_contract_cache_clear = load_public_surface_contract.cache_clear


def _clear_public_surface_contract_cache() -> None:
    _load_public_surface_contract_cache_clear()
    load_public_surface_contract_schema.cache_clear()


load_public_surface_contract.cache_clear = _clear_public_surface_contract_cache


def beginner_onboarding_contract() -> BeginnerOnboardingContract:
    return load_public_surface_contract().beginner_onboarding


def beginner_onboarding_hub_url() -> str:
    return beginner_onboarding_contract().hub_url


def beginner_preflight_requirements() -> tuple[str, ...]:
    return beginner_onboarding_contract().preflight_requirements


def beginner_onboarding_caveats() -> tuple[str, ...]:
    return beginner_onboarding_contract().caveats


def beginner_startup_ladder() -> tuple[str, ...]:
    return beginner_onboarding_contract().startup_ladder


def beginner_startup_ladder_text() -> str:
    return beginner_onboarding_contract().render_startup_ladder()


def local_cli_bridge_contract() -> LocalCliBridgeContract:
    return load_public_surface_contract().local_cli_bridge


def local_cli_bridge_commands() -> tuple[str, ...]:
    return local_cli_bridge_contract().commands


def local_cli_help_command() -> str:
    return _local_cli_bridge_command(local_cli_bridge_contract().named_commands.help)


def local_cli_doctor_command() -> str:
    return _local_cli_bridge_command(local_cli_bridge_contract().named_commands.doctor)


def local_cli_install_local_example_command() -> str:
    return local_cli_bridge_contract().install_local_example


def local_cli_doctor_local_command() -> str:
    return local_cli_bridge_contract().doctor_local_command


def local_cli_doctor_global_command() -> str:
    return local_cli_bridge_contract().doctor_global_command


def local_cli_unattended_readiness_command() -> str:
    return _local_cli_bridge_command(local_cli_bridge_contract().named_commands.unattended_readiness)


def local_cli_permissions_status_command() -> str:
    return _local_cli_bridge_command(local_cli_bridge_contract().named_commands.permissions_status)


def local_cli_permissions_sync_command() -> str:
    return _local_cli_bridge_command(local_cli_bridge_contract().named_commands.permissions_sync)


def local_cli_resume_command() -> str:
    return _local_cli_bridge_command(local_cli_bridge_contract().named_commands.resume)


def local_cli_resume_recent_command() -> str:
    return _local_cli_bridge_command(local_cli_bridge_contract().named_commands.resume_recent)


def local_cli_observe_execution_command() -> str:
    return _local_cli_bridge_command(local_cli_bridge_contract().named_commands.observe_execution)


def local_cli_cost_command() -> str:
    return _local_cli_bridge_command(local_cli_bridge_contract().named_commands.cost)


def local_cli_presets_list_command() -> str:
    return _local_cli_bridge_command(local_cli_bridge_contract().named_commands.presets_list)


def local_cli_plan_preflight_command() -> str:
    return _local_cli_bridge_command(local_cli_bridge_contract().named_commands.plan_preflight)


def local_cli_integrations_status_wolfram_command() -> str:
    return _local_cli_bridge_command(local_cli_bridge_contract().named_commands.integrations_status_wolfram)


def local_cli_validate_command_context_command() -> str:
    return local_cli_bridge_contract().validate_command_context_command


def local_cli_bridge_note() -> str:
    return local_cli_bridge_contract().render_note()


def local_cli_bridge_purpose_phrase() -> str:
    return local_cli_bridge_contract().purpose_phrase


def post_start_settings_contract() -> PostStartSettingsContract:
    return load_public_surface_contract().post_start_settings


def post_start_settings_note() -> str:
    return post_start_settings_contract().primary_sentence


def post_start_settings_recommendation() -> str:
    return post_start_settings_contract().default_sentence


def resume_authority_contract() -> ResumeAuthorityContract:
    return load_public_surface_contract().resume_authority


def resume_authority_fields() -> tuple[str, ...]:
    return resume_authority_contract().public_fields


def recovery_ladder_contract() -> RecoveryLadderContract:
    return load_public_surface_contract().recovery_ladder


def recovery_local_snapshot_command() -> str:
    return recovery_ladder_contract().local_snapshot_command


def recovery_cross_workspace_command() -> str:
    return recovery_ladder_contract().cross_workspace_command


def recovery_ladder_note(
    *,
    resume_work_phrase: str,
    suggest_next_phrase: str,
    pause_work_phrase: str,
) -> str:
    return recovery_ladder_contract().render_note(
        resume_work_phrase=resume_work_phrase,
        suggest_next_phrase=suggest_next_phrase,
        pause_work_phrase=pause_work_phrase,
    )
