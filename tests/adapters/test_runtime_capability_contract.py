"""Dedicated conformance tests for the runtime capability contract."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

import gpd.core.config as config_module
import gpd.core.costs as costs
import gpd.hooks.runtime_detect as runtime_detect
from gpd.adapters import get_adapter
from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.runtime_catalog import (
    RuntimeDescriptor,
    get_hook_payload_policy,
    get_runtime_capabilities,
    get_runtime_descriptor,
    iter_runtime_descriptors,
)
from gpd.core.costs import build_cost_summary, record_usage_from_runtime_payload
from gpd.core.surface_phrases import cost_summary_surface_note
from tests.doc_surface_contracts import assert_settings_local_terminal_follow_up_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_ROOT = REPO_ROOT / "src/gpd/adapters"


def _public_method_names(module_path: Path) -> set[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    public_methods: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or not node.name.endswith("Adapter"):
            continue
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and not item.name.startswith("_"):
                public_methods.add(item.name)
    return public_methods


def _ordered_unique(groups: list[tuple[str, ...]]) -> tuple[str, ...]:
    seen: set[str] = set()
    merged: list[str] = []
    for group in groups:
        for value in group:
            if value in seen:
                continue
            seen.add(value)
            merged.append(value)
    return tuple(merged)


def _project_root(tmp_path: Path, runtime_name: str) -> Path:
    project = tmp_path / runtime_name / "project"
    (project / "GPD").mkdir(parents=True, exist_ok=True)
    return project


def _telemetry_payload(runtime_name: str) -> dict[str, object]:
    policy = get_hook_payload_policy(runtime_name)
    assert policy.notify_event_types
    assert policy.usage_keys
    assert policy.model_keys

    usage_key = policy.usage_keys[0]
    input_key = policy.input_tokens_keys[0]
    output_key = policy.output_tokens_keys[0]
    cached_key = policy.cached_input_tokens_keys[0]
    cache_write_key = policy.cache_write_input_tokens_keys[0]
    cost_key = policy.cost_usd_keys[0]
    model_key = policy.model_keys[0]
    provider_key = policy.provider_keys[0]

    return {
        "type": policy.notify_event_types[0],
        "model": {model_key: "gpt-5", provider_key: "openai"},
        usage_key: {
            input_key: 120,
            output_key: 30,
            cached_key: 12,
            cache_write_key: 5,
            cost_key: 0.42,
        },
    }


def _adapter_aliases(descriptor: RuntimeDescriptor) -> tuple[str, ...]:
    candidates = (
        descriptor.runtime_name,
        descriptor.display_name,
        descriptor.install_flag,
        descriptor.adapter_module,
        *descriptor.selection_flags,
        *descriptor.selection_aliases,
    )
    seen: set[str] = set()
    aliases: list[str] = []
    for alias in candidates:
        if not alias or alias in seen:
            continue
        seen.add(alias)
        aliases.append(alias)
    return tuple(aliases)


def test_runtime_adapters_expose_same_public_method_surface() -> None:
    base_surface = _public_method_names(ADAPTER_ROOT / "base.py")
    method_surfaces = {
        descriptor.runtime_name: _public_method_names(ADAPTER_ROOT / f"{descriptor.runtime_name.replace('-', '_')}.py")
        for descriptor in iter_runtime_descriptors()
    }
    adapter_specific_hooks = {"finish_install"}
    unexpected_public_methods = {
        runtime_name: sorted(methods - base_surface)
        for runtime_name, methods in method_surfaces.items()
        if methods - base_surface - adapter_specific_hooks
    }

    assert unexpected_public_methods == {}


def test_merged_hook_payload_policy_is_exact_ordered_union_of_runtime_contracts() -> None:
    descriptors = iter_runtime_descriptors()
    merged_policy = get_hook_payload_policy()

    for field_name in (
        "notify_event_types",
        "workspace_keys",
        "project_dir_keys",
        "runtime_session_id_keys",
        "model_keys",
        "provider_keys",
        "usage_keys",
        "input_tokens_keys",
        "output_tokens_keys",
        "total_tokens_keys",
        "cached_input_tokens_keys",
        "cache_write_input_tokens_keys",
        "cost_usd_keys",
        "agent_id_keys",
        "agent_name_keys",
        "agent_scope_keys",
        "context_window_size_keys",
        "context_remaining_keys",
    ):
        expected = _ordered_unique([getattr(descriptor.hook_payload, field_name) for descriptor in descriptors])
        assert getattr(merged_policy, field_name) == expected


def test_runtime_hook_payload_attribution_fields_stay_explicitly_opt_in() -> None:
    merged_policy = get_hook_payload_policy()

    assert merged_policy.supports_runtime_session_payload_attribution is False
    assert merged_policy.supports_agent_payload_attribution is False
    assert merged_policy.runtime_session_id_keys == ()
    assert merged_policy.agent_id_keys == ()
    assert merged_policy.agent_name_keys == ()
    assert merged_policy.agent_scope_keys == ()

    for descriptor in iter_runtime_descriptors():
        policy = descriptor.hook_payload
        assert policy.supports_runtime_session_payload_attribution is False
        assert policy.supports_agent_payload_attribution is False
        assert policy.runtime_session_id_keys == ()
        assert policy.agent_id_keys == ()
        assert policy.agent_name_keys == ()
        assert policy.agent_scope_keys == ()


def test_runtime_capability_matrix_locks_hook_surfacing_surfaces() -> None:
    descriptors = iter_runtime_descriptors()
    capabilities_by_runtime = {
        descriptor.runtime_name: descriptor.capabilities for descriptor in descriptors
    }

    explicit_statusline = {
        runtime_name
        for runtime_name, capabilities in capabilities_by_runtime.items()
        if capabilities.statusline_surface == "explicit"
    }
    explicit_notify = {
        runtime_name
        for runtime_name, capabilities in capabilities_by_runtime.items()
        if capabilities.notify_surface == "explicit"
    }

    assert explicit_statusline == {"claude-code", "gemini"}
    assert explicit_notify == {"codex"}

    for runtime_name, capabilities in capabilities_by_runtime.items():
        if runtime_name in explicit_statusline:
            assert capabilities.statusline_config_surface == "settings.json:statusLine"
            assert capabilities.supports_context_meter is True
        else:
            assert capabilities.statusline_surface == "none"
            assert capabilities.statusline_config_surface == "none"
            assert capabilities.supports_context_meter is False

        if runtime_name in explicit_notify:
            assert capabilities.notify_config_surface == "config.toml:notify"
        else:
            assert capabilities.notify_surface == "none"
            assert capabilities.notify_config_surface == "none"


def test_runtime_capability_matrix_locks_telemetry_source_and_completeness() -> None:
    descriptors = iter_runtime_descriptors()
    capabilities_by_runtime = {
        descriptor.runtime_name: descriptor.capabilities for descriptor in descriptors
    }

    best_effort_telemetry = {
        runtime_name
        for runtime_name, capabilities in capabilities_by_runtime.items()
        if capabilities.telemetry_completeness == "best-effort"
    }

    assert best_effort_telemetry == {"codex"}

    for runtime_name, capabilities in capabilities_by_runtime.items():
        policy = get_hook_payload_policy(runtime_name)
        if runtime_name == "codex":
            assert capabilities.telemetry_source == "notify-hook"
            assert capabilities.telemetry_completeness == "best-effort"
            assert capabilities.supports_usage_tokens is True
            assert capabilities.supports_cost_usd is True
        else:
            assert capabilities.telemetry_source == "none"
            assert capabilities.telemetry_completeness == "none"
            assert capabilities.supports_usage_tokens is False
            assert capabilities.supports_cost_usd is False

        if policy.supports_runtime_session_payload_attribution or policy.supports_agent_payload_attribution:
            assert capabilities.notify_surface == "explicit"
            assert capabilities.telemetry_source == "notify-hook"


@pytest.mark.parametrize(
    "runtime_name",
    [descriptor.runtime_name for descriptor in iter_runtime_descriptors()],
)
def test_runtime_capability_contract_matches_adapter_permission_surface(runtime_name: str, tmp_path: Path) -> None:
    descriptor = next(descriptor for descriptor in iter_runtime_descriptors() if descriptor.runtime_name == runtime_name)
    capabilities = get_runtime_capabilities(runtime_name)
    adapter = get_adapter(runtime_name)
    target_dir = tmp_path / runtime_name
    target_dir.mkdir()

    assert adapter.runtime_name == descriptor.runtime_name
    assert adapter.display_name == descriptor.display_name
    assert adapter.__class__.runtime_permissions_status is not RuntimeAdapter.runtime_permissions_status
    assert adapter.__class__.sync_runtime_permissions is not RuntimeAdapter.sync_runtime_permissions

    status = adapter.runtime_permissions_status(target_dir, autonomy="balanced")

    assert status["runtime"] == runtime_name
    assert status["desired_mode"] == "default"
    assert isinstance(status["configured_mode"], str) and status["configured_mode"]
    assert isinstance(status["config_aligned"], bool)
    assert isinstance(status["requires_relaunch"], bool)
    assert isinstance(status["managed_by_gpd"], bool)
    assert isinstance(status["message"], str) and status["message"]

    if capabilities.permissions_surface == "config-file":
        assert "settings_path" in status
    elif capabilities.permissions_surface == "launch-wrapper":
        assert "launch_command" in status
    else:
        assert status["configured_mode"] == "unsupported"


@pytest.mark.parametrize(
    "runtime_name",
    [descriptor.runtime_name for descriptor in iter_runtime_descriptors()],
)
def test_runtime_catalog_adapter_aliases(runtime_name: str) -> None:
    descriptor = get_runtime_descriptor(runtime_name)
    for alias in _adapter_aliases(descriptor):
        adapter = get_adapter(alias)
        assert adapter.runtime_name == descriptor.runtime_name
        assert adapter.display_name == descriptor.display_name
        assert adapter.__class__.__module__ == f"gpd.adapters.{descriptor.adapter_module}"


@pytest.mark.parametrize(
    "runtime_name",
    [descriptor.runtime_name for descriptor in iter_runtime_descriptors()],
)
def test_runtime_capabilities_gate_usage_recording(runtime_name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    capabilities = get_runtime_capabilities(runtime_name)
    project = _project_root(tmp_path, runtime_name)
    data_root = tmp_path / "machine-data"

    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: f"sess-{runtime_name}")
    monkeypatch.setattr(costs, "_now_iso", lambda: "2026-03-27T12:00:00+00:00")

    payload = (
        _telemetry_payload(runtime_name)
        if capabilities.telemetry_completeness != "none"
        else {"type": "agent-turn-complete", "usage": {"input_tokens": 120}, "model": "gpt-5"}
    )

    record = record_usage_from_runtime_payload(
        payload,
        runtime=runtime_name,
        cwd=project,
        data_root=data_root,
    )

    if capabilities.telemetry_completeness == "none":
        assert record is None
        return

    assert record is not None
    assert record.runtime == runtime_name
    assert record.provider == "openai"
    assert record.model == "gpt-5"
    assert record.input_tokens == 120
    assert record.output_tokens == 30
    assert record.total_tokens == 150
    assert record.cached_input_tokens == 12
    assert record.cache_write_input_tokens == 5
    assert record.cost_usd == pytest.approx(0.42)
    assert record.cost_status == "measured"
    assert record.runtime_session_id is None
    assert record.agent_scope == "unknown"
    assert record.agent_id is None
    assert record.agent_name is None
    assert record.agent_kind is None
    assert record.agent_attribution_source == "unknown"


@pytest.mark.parametrize(
    "runtime_name",
    [descriptor.runtime_name for descriptor in iter_runtime_descriptors()],
)
def test_build_cost_summary_empty_workspace_guidance_tracks_runtime_capabilities(
    runtime_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _project_root(tmp_path, runtime_name)
    capabilities = get_runtime_capabilities(runtime_name)

    monkeypatch.setattr(
        config_module,
        "load_config",
        lambda _cwd: SimpleNamespace(
            model_profile=SimpleNamespace(value="review"),
            model_overrides={},
        ),
    )
    monkeypatch.setattr(runtime_detect, "detect_runtime_for_gpd_use", lambda cwd=None: runtime_name)

    summary = build_cost_summary(project, data_root=tmp_path / "machine-data", last_sessions=2)

    assert summary.active_runtime == runtime_name
    assert summary.model_profile == "review"
    assert summary.runtime_model_selection == "runtime defaults"
    assert any(
        f"Current model posture: profile `review` with {runtime_name} runtime defaults." in item
        for item in summary.guidance
    )

    if capabilities.telemetry_completeness == "none":
        assert any(
            f"{runtime_name} does not currently expose a GPD-managed usage telemetry collection path" in item
            for item in summary.guidance
        )
        assert not any(
            "No measured usage telemetry is recorded for this workspace yet." in item for item in summary.guidance
        )
    else:
        assert any(
            f"{runtime_name} only exposes best-effort usage telemetry through {capabilities.telemetry_source}" in item
            for item in summary.guidance
        )
        assert not any(
            "No measured usage telemetry is recorded for this workspace yet." in item for item in summary.guidance
        )


def test_public_runtime_surfaces_stay_conservative_when_capabilities_differ() -> None:
    descriptors = iter_runtime_descriptors()
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    help_workflow = (REPO_ROOT / "src/gpd/specs/workflows/help.md").read_text(encoding="utf-8")
    settings_workflow = (REPO_ROOT / "src/gpd/specs/workflows/settings.md").read_text(encoding="utf-8")

    if any(descriptor.capabilities.telemetry_completeness == "none" for descriptor in descriptors):
        for content in (readme, help_workflow):
            assert "gpd cost" in content
            assert "recorded local telemetry" in content
        assert cost_summary_surface_note() in help_workflow
        assert "provider billing truth" in help_workflow

    if any(descriptor.capabilities.permissions_surface != "unsupported" for descriptor in descriptors):
        assert "gpd validate unattended-readiness --runtime <runtime> --autonomy balanced" in readme
        assert "relaunch-required" in readme
        assert_settings_local_terminal_follow_up_contract(settings_workflow)
        assert "requires_relaunch" in settings_workflow

@pytest.mark.parametrize(
    ("line", "index", "expected"),
    [
        ("gpd plan", 0, True),
        ("  gpd plan", 2, True),
        ("uv run gpd plan", 7, False),
        ("gpd-plan", 0, False),
        ("mygpd plan", 2, False),
        ("echo ok && gpd plan", 11, True),
        ("echo ok || gpd plan", 11, True),
        ("$(gpd plan)", 2, True),
        ("echo|gpd plan", 5, True),
        ("(gpd plan)", 1, True),
    ],
)
def test_gpd_command_token_helpers_detect_only_shell_command_positions(
    line: str, index: int, expected: bool
) -> None:
    from gpd.adapters.command_tokens import is_gpd_command_start, is_gpd_token_end

    assert (is_gpd_command_start(line, index) and is_gpd_token_end(line, index + 3)) is expected
