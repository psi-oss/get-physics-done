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
class ResumeAuthorityContract:
    durable_authority_phrase: str
    public_vocabulary_intro: str
    public_fields: tuple[str, ...]
    top_level_boundary_phrase: str

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


_PUBLIC_SURFACE_CONTRACT_KEYS = (
    "schema_version",
    "beginner_onboarding",
    "local_cli_bridge",
    "post_start_settings",
    "resume_authority",
    "recovery_ladder",
)
_PUBLIC_SURFACE_SECTION_KEYS = {
    "beginner_onboarding": ("hub_url", "preflight_requirements", "caveats", "startup_ladder"),
    "local_cli_bridge": (
        "commands",
        "named_commands",
        "terminal_phrase",
        "purpose_phrase",
        "install_local_example",
        "doctor_local_command",
        "doctor_global_command",
        "validate_command_context_command",
    ),
    "post_start_settings": ("primary_sentence", "default_sentence"),
    "resume_authority": (
        "durable_authority_phrase",
        "public_vocabulary_intro",
        "public_fields",
        "top_level_boundary_phrase",
    ),
    "recovery_ladder": (
        "title",
        "local_snapshot_command",
        "local_snapshot_phrase",
        "cross_workspace_command",
        "cross_workspace_phrase",
        "resume_phrase",
        "next_phrase",
        "pause_phrase",
    ),
}
_LOCAL_CLI_NAMED_COMMAND_KEYS = (
    "help",
    "doctor",
    "unattended_readiness",
    "permissions_status",
    "permissions_sync",
    "resume",
    "resume_recent",
    "observe_execution",
    "cost",
    "presets_list",
    "plan_preflight",
    "integrations_status_wolfram",
)


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


def _require_local_cli_named_commands(
    payload: dict[str, object],
    *,
    bridge_commands: tuple[str, ...],
) -> LocalCliNamedCommandsContract:
    named_payload = _require_object(payload.get("named_commands"), label="local_cli_bridge.named_commands")
    _require_present_keys(
        named_payload,
        label="local_cli_bridge.named_commands",
        keys=_LOCAL_CLI_NAMED_COMMAND_KEYS,
    )
    _require_allowed_keys(
        named_payload,
        label="local_cli_bridge.named_commands",
        keys=_LOCAL_CLI_NAMED_COMMAND_KEYS,
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
    contract_path = files("gpd.core").joinpath("public_surface_contract.json")
    raw_payload = json.loads(contract_path.read_text(encoding="utf-8"))
    payload = _require_object(raw_payload, label="public_surface_contract")
    _require_present_keys(
        payload,
        label="public_surface_contract",
        keys=_PUBLIC_SURFACE_CONTRACT_KEYS,
    )
    _require_allowed_keys(payload, label="public_surface_contract", keys=_PUBLIC_SURFACE_CONTRACT_KEYS)

    schema_version = payload.get("schema_version")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version != 1:
        raise ValueError(f"Unsupported public surface contract schema_version: {schema_version!r}")

    beginner_payload = _require_object(payload.get("beginner_onboarding"), label="beginner_onboarding")
    _require_present_keys(
        beginner_payload,
        label="beginner_onboarding",
        keys=_PUBLIC_SURFACE_SECTION_KEYS["beginner_onboarding"],
    )
    _require_allowed_keys(
        beginner_payload,
        label="beginner_onboarding",
        keys=_PUBLIC_SURFACE_SECTION_KEYS["beginner_onboarding"],
    )
    bridge_payload = _require_object(payload.get("local_cli_bridge"), label="local_cli_bridge")
    _require_present_keys(
        bridge_payload,
        label="local_cli_bridge",
        keys=_PUBLIC_SURFACE_SECTION_KEYS["local_cli_bridge"],
    )
    _require_allowed_keys(
        bridge_payload,
        label="local_cli_bridge",
        keys=_PUBLIC_SURFACE_SECTION_KEYS["local_cli_bridge"],
    )
    settings_payload = _require_object(payload.get("post_start_settings"), label="post_start_settings")
    _require_present_keys(
        settings_payload,
        label="post_start_settings",
        keys=_PUBLIC_SURFACE_SECTION_KEYS["post_start_settings"],
    )
    _require_allowed_keys(
        settings_payload,
        label="post_start_settings",
        keys=_PUBLIC_SURFACE_SECTION_KEYS["post_start_settings"],
    )
    resume_authority_payload = _require_object(payload.get("resume_authority"), label="resume_authority")
    _require_present_keys(
        resume_authority_payload,
        label="resume_authority",
        keys=_PUBLIC_SURFACE_SECTION_KEYS["resume_authority"],
    )
    _require_allowed_keys(
        resume_authority_payload,
        label="resume_authority",
        keys=_PUBLIC_SURFACE_SECTION_KEYS["resume_authority"],
    )
    recovery_payload = _require_object(payload.get("recovery_ladder"), label="recovery_ladder")
    _require_present_keys(
        recovery_payload,
        label="recovery_ladder",
        keys=_PUBLIC_SURFACE_SECTION_KEYS["recovery_ladder"],
    )
    _require_allowed_keys(
        recovery_payload,
        label="recovery_ladder",
        keys=_PUBLIC_SURFACE_SECTION_KEYS["recovery_ladder"],
    )
    bridge_commands = _require_string_list(bridge_payload, "commands", label="local_cli_bridge")
    named_commands = _require_local_cli_named_commands(bridge_payload, bridge_commands=bridge_commands)
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
            install_local_example=_require_string(
                bridge_payload,
                "install_local_example",
                label="local_cli_bridge",
            ),
            doctor_local_command=_require_string(
                bridge_payload,
                "doctor_local_command",
                label="local_cli_bridge",
            ),
            doctor_global_command=_require_string(
                bridge_payload,
                "doctor_global_command",
                label="local_cli_bridge",
            ),
            validate_command_context_command=_require_string(
                bridge_payload,
                "validate_command_context_command",
                label="local_cli_bridge",
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
            top_level_boundary_phrase=_require_string(
                resume_authority_payload,
                "top_level_boundary_phrase",
                label="resume_authority",
            ),
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
