"""Assertions for runtime catalog config resolution and ordering."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import asdict, fields, replace
from pathlib import Path

import pytest

import gpd.adapters.runtime_catalog as runtime_catalog
from gpd.adapters.runtime_catalog import (
    get_hook_payload_policy,
    get_managed_install_surface_policy,
    get_manifest_metadata_list_policy_key,
    get_runtime_capabilities,
    get_runtime_descriptor,
    get_runtime_help_example_runtime,
    get_shared_install_metadata,
    has_global_config_env_override,
    iter_runtime_descriptors,
    list_runtime_names,
    normalize_runtime_name,
    resolve_global_config_dir,
)

_RUNTIME_CATALOG_PATH = Path(__file__).resolve().parents[2] / "src" / "gpd" / "adapters" / "runtime_catalog.json"
_RUNTIME_CATALOG_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "gpd" / "adapters" / "runtime_catalog_schema.json"
)
_RUNTIME_CONFIG_SURFACE_LABEL_RE = re.compile(r"^[A-Za-z0-9._-]+:[A-Za-z0-9+._-]+$")


def _special_permission_surface_kinds() -> frozenset[str]:
    return frozenset(
        descriptor.capabilities.permission_surface_kind
        for descriptor in iter_runtime_descriptors()
        if descriptor.capabilities.permissions_surface != "config-file"
        and descriptor.capabilities.permission_surface_kind != "none"
    )


def _catalog_entry_by_runtime_name(payload: list[dict[str, object]], runtime_name: str) -> dict[str, object]:
    for entry in payload:
        if entry.get("runtime_name") == runtime_name:
            return entry
    raise AssertionError(f"No runtime catalog entry found for {runtime_name}")


def _iter_runtime_descriptors_from_payload(
    payload: list[dict[str, object]],
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    catalog_path = tmp_path / "runtime_catalog.json"
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(runtime_catalog, "_catalog_path", lambda: catalog_path)
    runtime_catalog._load_catalog.cache_clear()
    try:
        return runtime_catalog.iter_runtime_descriptors()
    finally:
        runtime_catalog._load_catalog.cache_clear()


def _iter_runtime_descriptors_from_schema(
    schema_payload: dict[str, object],
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    schema_path = tmp_path / "runtime_catalog_schema.json"
    schema_path.write_text(json.dumps(schema_payload), encoding="utf-8")
    monkeypatch.setattr(runtime_catalog, "_runtime_catalog_schema_path", lambda: schema_path)
    runtime_catalog._load_runtime_catalog_schema_shape.cache_clear()
    schema_shape = runtime_catalog._load_runtime_catalog_schema_shape()
    monkeypatch.setattr(runtime_catalog, "_RUNTIME_CATALOG_SHAPE", schema_shape)
    monkeypatch.setattr(runtime_catalog, "_RUNTIME_ENTRY_REQUIRED_KEYS", schema_shape["entry_required_keys"])
    monkeypatch.setattr(runtime_catalog, "_RUNTIME_ENTRY_OPTIONAL_KEYS", schema_shape["entry_optional_keys"])
    monkeypatch.setattr(
        runtime_catalog,
        "_RUNTIME_ENTRY_ALLOWED_KEYS",
        schema_shape["entry_required_keys"] | schema_shape["entry_optional_keys"],
    )
    monkeypatch.setattr(
        runtime_catalog, "_RUNTIME_GLOBAL_CONFIG_STRATEGIES", frozenset(schema_shape["global_config_keys"].keys())
    )
    monkeypatch.setattr(
        runtime_catalog, "_RUNTIME_INSTALL_HELP_EXAMPLE_SCOPES", schema_shape["install_help_example_scopes"]
    )
    monkeypatch.setattr(runtime_catalog, "_RUNTIME_CAPABILITY_ENUMS", schema_shape["capability_enums"])
    monkeypatch.setattr(runtime_catalog, "_RUNTIME_GLOBAL_CONFIG_KEYS", schema_shape["global_config_keys"])
    monkeypatch.setattr(runtime_catalog, "_RUNTIME_CAPABILITY_KEYS", schema_shape["capability_keys"])
    monkeypatch.setattr(runtime_catalog, "_RUNTIME_CAPABILITY_DEFAULTS", schema_shape["capability_defaults"])
    monkeypatch.setattr(runtime_catalog, "_RUNTIME_HOOK_PAYLOAD_KEYS", schema_shape["hook_payload_keys"])
    monkeypatch.setattr(runtime_catalog, "_RUNTIME_HOOK_PAYLOAD_DEFAULTS", schema_shape["hook_payload_defaults"])
    monkeypatch.setattr(
        runtime_catalog,
        "_RUNTIME_MANAGED_INSTALL_SURFACE_KEYS",
        schema_shape["managed_install_surface_keys"],
    )
    monkeypatch.setattr(
        runtime_catalog,
        "_RUNTIME_MANAGED_INSTALL_SURFACE_DEFAULTS",
        schema_shape["managed_install_surface_defaults"],
    )
    monkeypatch.setattr(
        runtime_catalog,
        "_RUNTIME_MANIFEST_METADATA_LIST_VALUE_KINDS",
        schema_shape["manifest_metadata_list_value_kinds"],
    )
    monkeypatch.setattr(
        runtime_catalog,
        "_RUNTIME_LAUNCH_WRAPPER_PERMISSION_SURFACE_KINDS",
        schema_shape["launch_wrapper_permission_surface_kinds"],
    )
    runtime_catalog._load_catalog.cache_clear()
    try:
        return runtime_catalog.iter_runtime_descriptors()
    finally:
        runtime_catalog._load_runtime_catalog_schema_shape.cache_clear()
        runtime_catalog._load_catalog.cache_clear()


def _iter_runtime_descriptors_from_schema_and_payload(
    schema_payload: dict[str, object],
    catalog_payload: list[dict[str, object]],
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    catalog_path = tmp_path / "runtime_catalog.json"
    catalog_path.write_text(json.dumps(catalog_payload), encoding="utf-8")
    monkeypatch.setattr(runtime_catalog, "_catalog_path", lambda: catalog_path)
    return _iter_runtime_descriptors_from_schema(schema_payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_resolve_global_config_dir_env_or_home_respects_explicit_empty_environ(monkeypatch) -> None:
    monkeypatch.setenv("CODEX_CONFIG_DIR", "/tmp/process-codex-config")

    resolved = resolve_global_config_dir(
        get_runtime_descriptor("codex"),
        home=Path("/tmp/home"),
        environ={},
    )

    assert resolved == Path("/tmp/home/.codex").resolve(strict=False)


def test_resolve_global_config_dir_xdg_app_respects_explicit_empty_environ(monkeypatch) -> None:
    monkeypatch.setenv("OPENCODE_CONFIG_DIR", "/tmp/process-opencode-config")
    monkeypatch.setenv("OPENCODE_CONFIG", "/tmp/process-opencode/opencode.json")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/process-xdg")

    resolved = resolve_global_config_dir(
        get_runtime_descriptor("opencode"),
        home=Path("/tmp/home"),
        environ={},
    )

    assert resolved == Path("/tmp/home/.config/opencode").resolve(strict=False)


def test_resolve_global_config_dir_env_or_home_normalizes_env_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))

    resolved = resolve_global_config_dir(
        get_runtime_descriptor("codex"),
        home=tmp_path / "ignored-home",
        environ={"CODEX_CONFIG_DIR": "~/codex-config/../codex-final"},
    )

    assert resolved == (home / "codex-final").resolve(strict=False)
    assert resolved.is_absolute()


def test_resolve_global_config_dir_xdg_dir_normalizes_relative_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    resolved = resolve_global_config_dir(
        get_runtime_descriptor("opencode"),
        home=tmp_path / "home",
        environ={"OPENCODE_CONFIG_DIR": "relative/opencode/../custom-opencode"},
    )

    assert resolved == (tmp_path / "relative/custom-opencode").resolve(strict=False)
    assert resolved.is_absolute()


def test_resolve_global_config_dir_xdg_file_uses_normalized_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))

    resolved = resolve_global_config_dir(
        get_runtime_descriptor("opencode"),
        home=tmp_path / "ignored-home",
        environ={"OPENCODE_CONFIG": "~/opencode/config/opencode.json"},
    )

    assert resolved == (home / "opencode/config").resolve(strict=False)
    assert resolved.is_absolute()


def test_resolve_global_config_dir_xdg_home_normalizes_relative_base(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    resolved = resolve_global_config_dir(
        get_runtime_descriptor("opencode"),
        home=tmp_path / "home",
        environ={"XDG_CONFIG_HOME": "xdg-config"},
    )

    assert resolved == (tmp_path / "xdg-config/opencode").resolve(strict=False)
    assert resolved.is_absolute()


def test_has_global_config_env_override_is_catalog_owned() -> None:
    env_or_home_descriptor = next(
        descriptor for descriptor in iter_runtime_descriptors() if descriptor.global_config.strategy == "env_or_home"
    )
    xdg_descriptor = next(
        descriptor for descriptor in iter_runtime_descriptors() if descriptor.global_config.strategy == "xdg_app"
    )

    assert has_global_config_env_override(env_or_home_descriptor, environ={}) is False
    assert (
        has_global_config_env_override(
            env_or_home_descriptor,
            environ={env_or_home_descriptor.global_config.env_var: "/tmp/runtime-config"},
        )
        is True
    )
    assert (
        has_global_config_env_override(
            env_or_home_descriptor,
            environ={"XDG_CONFIG_HOME": "/tmp/xdg"},
        )
        is False
    )

    assert has_global_config_env_override(xdg_descriptor, environ={}) is False
    assert (
        has_global_config_env_override(
            xdg_descriptor,
            environ={xdg_descriptor.global_config.env_dir_var: "/tmp/runtime-config"},
        )
        is True
    )
    assert (
        has_global_config_env_override(
            xdg_descriptor,
            environ={xdg_descriptor.global_config.env_file_var: "/tmp/runtime/config.json"},
        )
        is True
    )
    assert (
        has_global_config_env_override(
            xdg_descriptor,
            environ={"XDG_CONFIG_HOME": "/tmp/xdg"},
        )
        is True
    )


def test_runtime_catalog_explicit_priority_order() -> None:
    descriptors = iter_runtime_descriptors()
    assert [descriptor.runtime_name for descriptor in descriptors] == list_runtime_names()
    assert [descriptor.priority for descriptor in descriptors] == sorted(
        descriptor.priority for descriptor in descriptors
    )


def test_runtime_catalog_priority_order_is_intentional() -> None:
    assert [(descriptor.runtime_name, descriptor.priority) for descriptor in iter_runtime_descriptors()] == [
        ("claude-code", 10),
        ("gemini", 20),
        ("codex", 30),
        ("opencode", 40),
    ]


def test_runtime_catalog_schema_dataclass_keys_stay_in_sync() -> None:
    schema = json.loads(_RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert set(schema["entry_required_keys"]) | set(schema["entry_optional_keys"]) == {
        field.name for field in fields(runtime_catalog.RuntimeDescriptor)
    }
    assert set(schema["global_config_keys"]["env_or_home"]) | set(schema["global_config_keys"]["xdg_app"]) == {
        field.name for field in fields(runtime_catalog.GlobalConfigPolicy)
    }
    assert set(schema["capability_keys"]) == {field.name for field in fields(runtime_catalog.RuntimeCapabilityPolicy)}
    assert schema["capability_defaults"] == asdict(runtime_catalog.RuntimeCapabilityPolicy())
    assert set(schema["capability_enum_required_keys"]) <= set(schema["capability_keys"])
    assert set(schema["capability_enum_required_keys"]) <= set(schema["capability_enums"])
    assert set(schema["hook_payload_keys"]) == {field.name for field in fields(runtime_catalog.HookPayloadPolicy)}
    assert {key: tuple(value) for key, value in schema["hook_payload_defaults"].items()} == asdict(
        runtime_catalog.HookPayloadPolicy()
    )
    assert set(schema["managed_install_surface_keys"]) == {
        field.name for field in fields(runtime_catalog.ManagedInstallSurfacePolicy)
    }
    assert set(schema["managed_install_surface_defaults"]) == {
        field.name for field in fields(runtime_catalog.ManagedInstallSurfacePolicy)
    }
    assert set(schema["manifest_metadata_list_value_kinds"]) == {"path_segment", "relpath"}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("hooks/statusline.py", "hooks/statusline.py"),
        ("skills/gpd-help/SKILL.md", "skills/gpd-help/SKILL.md"),
        ("../hooks/statusline.py", None),
        ("hooks//statusline.py", None),
        ("hooks\\statusline.py", None),
        ("/tmp/hooks/statusline.py", None),
        ("C:/tmp/hooks/statusline.py", None),
        ("", None),
        (None, None),
    ],
)
def test_manifest_relpath_validation_lives_in_runtime_catalog(value: object, expected: str | None) -> None:
    assert runtime_catalog.normalize_manifest_relpath(value) == expected


def test_managed_install_glob_helpers_use_catalog_semantics(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    command_path = root / "commands" / "gpd" / "help.md"
    command_path.parent.mkdir(parents=True)
    command_path.write_text("help\n", encoding="utf-8")

    assert runtime_catalog.managed_install_glob_static_root("commands/gpd/**/*.md") == "commands/gpd"
    assert runtime_catalog.managed_install_globs_have_files(
        root,
        ("commands/gpd/**/*.md",),
        on_error=False,
    )
    assert not runtime_catalog.managed_install_globs_have_files(
        root,
        ("agents/gpd-*.md",),
        on_error=False,
    )


def test_runtime_catalog_entries_omit_default_capability_values() -> None:
    catalog_payload = json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8"))
    schema = json.loads(_RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8"))
    capability_defaults = schema["capability_defaults"]

    redundant = []
    for entry in catalog_payload:
        runtime_name = entry["runtime_name"]
        capabilities = entry["capabilities"]
        for key, value in capabilities.items():
            if capability_defaults.get(key) == value:
                redundant.append(f"{runtime_name}.{key}")

    assert redundant == []


def test_runtime_catalog_adapter_registration_aliases_and_public_prefixes() -> None:
    catalog_payload = json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8"))

    assert list_runtime_names() == [entry["runtime_name"] for entry in catalog_payload]
    for entry in catalog_payload:
        runtime_name = entry["runtime_name"]
        descriptor = get_runtime_descriptor(runtime_name)
        for field_name in (
            "display_name",
            "install_flag",
            "launch_command",
            "adapter_module",
            "adapter_class",
            "selection_flags",
            "selection_aliases",
            "command_prefix",
            "validated_command_surface",
            "public_command_surface_prefix",
        ):
            raw_value = entry.get(field_name, getattr(descriptor, field_name))
            expected_value = tuple(raw_value) if isinstance(raw_value, list) else raw_value
            assert getattr(descriptor, field_name) == expected_value

        assert descriptor.runtime_name in descriptor.selection_aliases
        assert descriptor.install_flag in descriptor.selection_flags
        assert normalize_runtime_name(runtime_name) == runtime_name
        assert normalize_runtime_name(descriptor.display_name) == runtime_name
        assert normalize_runtime_name(descriptor.install_flag) == runtime_name
        assert normalize_runtime_name(descriptor.launch_command) == runtime_name
        for selection_flag in descriptor.selection_flags:
            assert normalize_runtime_name(selection_flag) == runtime_name
        for selection_alias in descriptor.selection_aliases:
            assert normalize_runtime_name(selection_alias) == runtime_name


def test_runtime_catalog_records_native_include_support() -> None:
    assert get_runtime_descriptor("claude-code").native_include_support is True
    assert get_runtime_descriptor("codex").native_include_support is False
    assert get_runtime_descriptor("gemini").native_include_support is False
    assert get_runtime_descriptor("opencode").native_include_support is False
    assert get_runtime_descriptor("claude-code").installer_help_example_scope == "global"
    assert get_runtime_descriptor("codex").installer_help_example_scope == "local"
    assert get_runtime_descriptor("claude-code").validated_command_surface == "public_runtime_slash_command"
    assert get_runtime_descriptor("gemini").validated_command_surface == "public_runtime_slash_command"
    assert get_runtime_descriptor("codex").validated_command_surface == "public_runtime_dollar_command"
    assert get_runtime_descriptor("opencode").validated_command_surface == "public_runtime_slash_command"
    assert get_runtime_descriptor("claude-code").public_command_surface_prefix == "/gpd:"
    assert get_runtime_descriptor("gemini").public_command_surface_prefix == "/gpd:"
    assert get_runtime_descriptor("codex").public_command_surface_prefix == "$gpd-"
    assert get_runtime_descriptor("opencode").public_command_surface_prefix == "/gpd-"


def test_runtime_catalog_marks_install_help_example_runtimes() -> None:
    assert get_runtime_help_example_runtime("global") == "claude-code"
    assert get_runtime_help_example_runtime("local") == "codex"


def test_runtime_catalog_rejects_duplicate_global_install_help_example_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    _catalog_entry_by_runtime_name(payload, "codex")["installer_help_example_scope"] = "global"

    with pytest.raises(
        ValueError,
        match=r"runtime catalog contains duplicate installer_help_example_scope 'global'",
    ):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_rejects_duplicate_local_install_help_example_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    _catalog_entry_by_runtime_name(payload, "gemini")["installer_help_example_scope"] = "local"

    with pytest.raises(
        ValueError,
        match=r"runtime catalog contains duplicate installer_help_example_scope 'local'",
    ):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_declares_one_explicit_installer_help_example_per_scope() -> None:
    examples = [
        descriptor.runtime_name for descriptor in iter_runtime_descriptors() if descriptor.installer_help_example_scope
    ]

    assert examples == ["claude-code", "codex"]
    assert get_runtime_descriptor("claude-code").installer_help_example_scope == "global"
    assert get_runtime_descriptor("codex").installer_help_example_scope == "local"


def test_shared_install_metadata_is_centralized_in_runtime_catalog() -> None:
    metadata = get_shared_install_metadata()

    assert metadata.bootstrap_package_name == "get-physics-done"
    assert metadata.bootstrap_command == "npx -y get-physics-done"
    assert metadata.latest_release_url == "https://registry.npmjs.org/get-physics-done/latest"
    assert metadata.releases_api_url == "https://api.github.com/repos/psi-oss/get-physics-done/releases"
    assert metadata.releases_page_url == "https://github.com/psi-oss/get-physics-done/releases"
    assert metadata.install_root_dir_name == "get-physics-done"
    assert metadata.manifest_name == "gpd-file-manifest.json"
    assert metadata.patches_dir_name == "gpd-local-patches"


def test_normalize_runtime_name_is_centralized_in_runtime_catalog() -> None:
    assert normalize_runtime_name("claude-code") == "claude-code"
    assert normalize_runtime_name("Claude Code") == "claude-code"
    assert normalize_runtime_name("claude") == "claude-code"
    assert normalize_runtime_name("open code") == "opencode"
    assert normalize_runtime_name("--claude") == "claude-code"
    assert normalize_runtime_name("--gemini-cli") == "gemini"
    assert normalize_runtime_name("--codex") == "codex"
    assert normalize_runtime_name("--opencode") == "opencode"
    assert normalize_runtime_name("not-a-runtime") is None


def test_normalize_runtime_name_accepts_install_flags_outside_selection_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    codex = _catalog_entry_by_runtime_name(payload, "codex")
    codex["install_flag"] = "--codex-install-only"
    codex["selection_flags"] = ["--codex-selection-only"]

    catalog_path = tmp_path / "runtime_catalog.json"
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(runtime_catalog, "_catalog_path", lambda: catalog_path)
    runtime_catalog._load_catalog.cache_clear()
    try:
        assert normalize_runtime_name("--codex-install-only") == "codex"
        assert normalize_runtime_name("--codex-selection-only") == "codex"
    finally:
        runtime_catalog._load_catalog.cache_clear()


def test_normalize_runtime_name_accepts_launch_command_from_fake_catalog_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    codex = _catalog_entry_by_runtime_name(payload, "codex")
    codex["launch_command"] = "codex-launch"

    catalog_path = tmp_path / "runtime_catalog.json"
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(runtime_catalog, "_catalog_path", lambda: catalog_path)
    runtime_catalog._load_catalog.cache_clear()
    try:
        assert normalize_runtime_name("codex-launch") == "codex"
        assert normalize_runtime_name("CODEX-LAUNCH") == "codex"
    finally:
        runtime_catalog._load_catalog.cache_clear()


def test_managed_install_surface_policy_is_derived_from_runtime_metadata() -> None:
    catalog_payload = json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8"))
    schema = json.loads(_RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8"))
    agent_glob_defaults = tuple(schema["managed_install_surface_defaults"]["managed_agent_globs"])
    claude_entry = _catalog_entry_by_runtime_name(catalog_payload, "claude-code")
    opencode_entry = _catalog_entry_by_runtime_name(catalog_payload, "opencode")
    claude_policy = get_managed_install_surface_policy("claude-code")
    opencode_policy = get_managed_install_surface_policy("opencode")
    codex_policy = get_managed_install_surface_policy("codex")
    merged_policy = get_managed_install_surface_policy()

    assert claude_policy.gpd_content_globs == (f"{get_shared_install_metadata().install_root_dir_name}/**/*",)
    assert claude_policy.nested_command_globs == tuple(claude_entry["managed_install_surface"]["nested_command_globs"])
    assert claude_policy.flat_command_globs == ()
    assert claude_policy.managed_agent_globs == agent_glob_defaults

    assert opencode_policy.nested_command_globs == ()
    assert opencode_policy.flat_command_globs == tuple(opencode_entry["managed_install_surface"]["flat_command_globs"])
    assert codex_policy.nested_command_globs == ()
    assert codex_policy.flat_command_globs == ()
    assert merged_policy.nested_command_globs == claude_policy.nested_command_globs
    assert merged_policy.flat_command_globs == opencode_policy.flat_command_globs


def test_manifest_metadata_list_policies_are_derived_from_runtime_metadata() -> None:
    catalog_payload = json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8"))
    codex_entry = _catalog_entry_by_runtime_name(catalog_payload, "codex")
    gemini_entry = _catalog_entry_by_runtime_name(catalog_payload, "gemini")
    opencode_entry = _catalog_entry_by_runtime_name(catalog_payload, "opencode")

    codex_policy = get_runtime_descriptor("codex").manifest_metadata_list_policies[0]
    gemini_policy = get_runtime_descriptor("gemini").manifest_metadata_list_policies[0]
    opencode_policy = get_runtime_descriptor("opencode").manifest_metadata_list_policies[0]

    assert codex_policy.key == codex_entry["manifest_metadata_list_policies"][0]["key"]
    assert codex_policy.value_kind == "path_segment"
    assert codex_policy.item_prefix == "gpd-"
    assert codex_policy.item_suffix is None
    assert gemini_policy.key == gemini_entry["manifest_metadata_list_policies"][0]["key"]
    assert gemini_policy.value_kind == "relpath"
    assert opencode_policy.key == opencode_entry["manifest_metadata_list_policies"][0]["key"]
    assert opencode_policy.item_prefix == "gpd-"
    assert opencode_policy.item_suffix == ".md"


def test_manifest_metadata_list_policy_key_matches_runtime_descriptor_policy() -> None:
    assert get_manifest_metadata_list_policy_key("codex", value_kind="path_segment", item_prefix="gpd-") == (
        get_runtime_descriptor("codex").manifest_metadata_list_policies[0].key
    )
    assert get_manifest_metadata_list_policy_key("gemini", value_kind="relpath") == (
        get_runtime_descriptor("gemini").manifest_metadata_list_policies[0].key
    )
    assert (
        get_manifest_metadata_list_policy_key(
            "opencode",
            value_kind="path_segment",
            item_prefix="gpd-",
            item_suffix=".md",
        )
        == get_runtime_descriptor("opencode").manifest_metadata_list_policies[0].key
    )


def test_runtime_catalog_source_does_not_hardcode_managed_agent_globs() -> None:
    schema = json.loads(_RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8"))
    source = (Path(__file__).resolve().parents[2] / "src" / "gpd" / "adapters" / "runtime_catalog.py").read_text(
        encoding="utf-8"
    )

    for glob in schema["managed_install_surface_defaults"]["managed_agent_globs"]:
        assert glob not in source


def test_runtime_catalog_runtime_keys_are_unique() -> None:
    descriptors = iter_runtime_descriptors()

    assert len({descriptor.runtime_name for descriptor in descriptors}) == len(descriptors)
    assert len({descriptor.priority for descriptor in descriptors}) == len(descriptors)
    assert len({descriptor.config_dir_name for descriptor in descriptors}) == len(descriptors)
    assert len({descriptor.install_flag for descriptor in descriptors}) == len(descriptors)
    assert len({descriptor.launch_command for descriptor in descriptors}) == len(descriptors)

    selection_flags = [flag for descriptor in descriptors for flag in descriptor.selection_flags]
    selection_aliases = [alias for descriptor in descriptors for alias in descriptor.selection_aliases]
    activation_env_vars = [env_var for descriptor in descriptors for env_var in descriptor.activation_env_vars]

    assert len(set(selection_flags)) == len(selection_flags)
    assert len(set(selection_aliases)) == len(selection_aliases)
    assert len(set(activation_env_vars)) == len(activation_env_vars)


def test_runtime_catalog_rejects_unknown_top_level_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["legacy_note"] = "unexpected"

    with pytest.raises(ValueError, match=r"runtime catalog entry 0 contains unknown key\(s\): legacy_note"):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_rejects_schema_drift_against_fixed_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = deepcopy(json.loads(_RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8")))
    schema["entry_required_keys"] = [*schema["entry_required_keys"], "legacy_required_key"]

    with pytest.raises(ValueError, match=r"runtime catalog entry 0 is missing required key\(s\): legacy_required_key"):
        _iter_runtime_descriptors_from_schema(schema, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_rejects_unknown_capability_enum_schema_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = deepcopy(json.loads(_RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8")))
    schema["capability_enums"]["legacy_surface"] = ["legacy"]

    with pytest.raises(
        ValueError,
        match=r"runtime catalog schema\.capability_enums contains unknown key\(s\): legacy_surface",
    ):
        _iter_runtime_descriptors_from_schema(schema, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_rejects_missing_required_capability_enum_schema_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = deepcopy(json.loads(_RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8")))
    del schema["capability_enums"]["permissions_surface"]

    with pytest.raises(
        ValueError,
        match=r"runtime catalog schema\.capability_enums is missing required key\(s\): permissions_surface",
    ):
        _iter_runtime_descriptors_from_schema(schema, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_required_capability_enum_keys_are_schema_owned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = deepcopy(json.loads(_RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8")))
    schema["capability_enum_required_keys"].remove("permissions_surface")
    del schema["capability_enums"]["permissions_surface"]

    descriptors = _iter_runtime_descriptors_from_schema(schema, tmp_path=tmp_path, monkeypatch=monkeypatch)

    assert descriptors


def test_runtime_catalog_rejects_unknown_required_capability_enum_schema_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = deepcopy(json.loads(_RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8")))
    schema["capability_enum_required_keys"].append("legacy_surface")

    with pytest.raises(
        ValueError,
        match=r"runtime catalog schema\.capability_enum_required_keys contains unknown key\(s\): legacy_surface",
    ):
        _iter_runtime_descriptors_from_schema(schema, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_rejects_blank_selection_aliases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["selection_aliases"] = [payload[0]["selection_aliases"][0], " "]

    with pytest.raises(
        ValueError,
        match=r"runtime catalog entry 0\.selection_aliases\[1\] must be a non-empty string",
    ):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda entry: entry.update(runtime_name="Bad Runtime"),
            r"runtime catalog entry 0\.runtime_name must be a lowercase runtime id",
        ),
        (
            lambda entry: entry.update(config_dir_name="../.codex"),
            r"runtime catalog entry 0\.config_dir_name must be a safe relative path segment without traversal",
        ),
        (
            lambda entry: entry.update(install_flag="--bad flag"),
            r"runtime catalog entry 0\.install_flag must be a --kebab-case flag",
        ),
        (
            lambda entry: entry.update(adapter_module="gpd.adapters;rm"),
            r"runtime catalog entry 0\.adapter_module must be a Python module path",
        ),
        (
            lambda entry: entry.update(adapter_class="Bad-Class"),
            r"runtime catalog entry 0\.adapter_class must be a Python class name",
        ),
        (
            lambda entry: entry.update(activation_env_vars=["BAD=1"]),
            r"runtime catalog entry 0\.activation_env_vars\[0\] must be an environment variable name",
        ),
        (
            lambda entry: entry.update(selection_flags=["--bad flag"]),
            r"runtime catalog entry 0\.selection_flags\[0\] must be a --kebab-case flag",
        ),
        (
            lambda entry: entry["global_config"].update(env_var="BAD=1"),
            r"runtime catalog entry 0\.global_config\.env_var must be an environment variable name",
        ),
        (
            lambda entry: entry["global_config"].update(home_subpath="../.codex"),
            r"runtime catalog entry 0\.global_config\.home_subpath must be a safe relative path without traversal",
        ),
        (
            lambda entry: entry.update(manifest_file_prefixes=["../skills/"]),
            r"runtime catalog entry 0\.manifest_file_prefixes\[0\] must be a safe relative path without traversal",
        ),
    ],
)
def test_runtime_catalog_rejects_unsafe_path_id_and_env_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutator,
    match: str,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    mutator(payload[0])

    with pytest.raises(ValueError, match=match):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_rejects_non_boolean_native_include_support(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["native_include_support"] = "true"

    with pytest.raises(ValueError, match=r"runtime catalog entry 0\.native_include_support must be a boolean"):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_accepts_future_validated_command_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["validated_command_surface"] = "public_runtime_semicolon_command"

    descriptors = _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)

    assert descriptors[0].validated_command_surface == "public_runtime_semicolon_command"


def test_runtime_catalog_defaults_public_command_surface_prefix_to_command_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0].pop("public_command_surface_prefix", None)

    descriptors = _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)

    assert descriptors[0].public_command_surface_prefix == descriptors[0].command_prefix


def test_runtime_catalog_accepts_descriptor_owned_public_command_surface_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["public_command_surface_prefix"] = "/public:"

    descriptors = _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)

    assert descriptors[0].command_prefix == payload[0]["command_prefix"]
    assert descriptors[0].public_command_surface_prefix == "/public:"
    assert descriptors[0].public_command_surface_prefix != descriptors[0].command_prefix


@pytest.mark.parametrize("prefix", [" public:", "public", "/bad space:", "gpd:"])
def test_runtime_catalog_rejects_malformed_command_prefix_even_with_public_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prefix: str,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["command_prefix"] = prefix
    payload[0]["public_command_surface_prefix"] = "/public:"

    with pytest.raises(
        ValueError,
        match=(
            r"runtime catalog entry 0\.command_prefix must be "
            r"(a non-empty string|a slash or dollar command prefix)"
        ),
    ):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


@pytest.mark.parametrize("prefix", [" public:", "public", "/bad space:", "gpd:"])
def test_runtime_catalog_rejects_malformed_public_command_surface_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prefix: str,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["public_command_surface_prefix"] = prefix

    with pytest.raises(
        ValueError,
        match=(
            r"runtime catalog entry 0\.public_command_surface_prefix must be "
            r"(a non-empty string|a slash or dollar command prefix)"
        ),
    ):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_rejects_invalid_delegation_capability_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["capabilities"]["child_artifact_persistence_reliability"] = "unstable"

    with pytest.raises(
        ValueError,
        match=(
            r"runtime catalog entry 0\.capabilities\.child_artifact_persistence_reliability "
            r"must be one of: best-effort, none, reliable"
        ),
    ):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_rejects_invalid_capability_enum_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    schema = json.loads(_RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8"))
    allowed = ", ".join(schema["capability_enums"]["telemetry_source"])
    payload[0]["capabilities"]["telemetry_source"] = "webhook"

    with pytest.raises(
        ValueError,
        match=rf"runtime catalog entry 0\.capabilities\.telemetry_source must be one of: {re.escape(allowed)}",
    ):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_rejects_prompt_free_support_without_mode_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["capabilities"]["supports_prompt_free_mode"] = True
    payload[0]["capabilities"]["prompt_free_mode_value"] = None

    with pytest.raises(
        ValueError,
        match=(
            r"runtime catalog entry 0\.capabilities\.prompt_free_mode_value must be "
            r"a non-empty string when supports_prompt_free_mode=true"
        ),
    ):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


@pytest.mark.parametrize(
    ("runtime_name", "capability_updates", "match"),
    [
        (
            "claude-code",
            {"statusline_config_surface": "none"},
            r'runtime catalog entry \d+\.capabilities\.statusline_config_surface must not be "none" when statusline_surface=explicit',
        ),
        (
            "opencode",
            {"statusline_config_surface": "settings.json:statusLine"},
            r'runtime catalog entry \d+\.capabilities\.statusline_config_surface must be "none" when statusline_surface=none',
        ),
        (
            "codex",
            {"notify_config_surface": "none"},
            r'runtime catalog entry \d+\.capabilities\.notify_config_surface must not be "none" when notify_surface=explicit',
        ),
        (
            "opencode",
            {"notify_config_surface": "config.toml:notify"},
            r'runtime catalog entry \d+\.capabilities\.notify_config_surface must be "none" when notify_surface=none',
        ),
        (
            "codex",
            {"telemetry_completeness": "none"},
            r'runtime catalog entry \d+\.capabilities\.telemetry_source must be "none" when telemetry_completeness=none',
        ),
        (
            "opencode",
            {"telemetry_completeness": "best-effort"},
            r'runtime catalog entry \d+\.capabilities\.telemetry_source must not be "none" when telemetry_completeness is not none',
        ),
    ],
)
def test_runtime_catalog_rejects_incoherent_statusline_notify_and_telemetry_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runtime_name: str,
    capability_updates: dict[str, object],
    match: str,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    entry = _catalog_entry_by_runtime_name(payload, runtime_name)
    entry["capabilities"].update(capability_updates)

    with pytest.raises(ValueError, match=match):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_merges_partial_capabilities_with_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["capabilities"] = {
        "permissions_surface": "unsupported",
    }

    descriptors = _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)

    assert descriptors[0].capabilities.permissions_surface == "unsupported"
    assert descriptors[0].capabilities.permission_surface_kind == "none"
    assert descriptors[0].capabilities.supports_runtime_permission_sync is False
    assert descriptors[0].capabilities.statusline_surface == "none"


def test_runtime_catalog_merges_partial_hook_payload_with_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    opencode = _catalog_entry_by_runtime_name(payload, "opencode")
    opencode["hook_payload"] = {
        "target_path_keys": ["selected_path"],
    }

    descriptors = _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)
    opencode_descriptor = next(descriptor for descriptor in descriptors if descriptor.runtime_name == "opencode")

    assert opencode_descriptor.hook_payload.target_path_keys == ("selected_path",)
    assert opencode_descriptor.hook_payload.target_root_keys == ()
    assert opencode_descriptor.hook_payload.workspace_keys == ()
    assert opencode_descriptor.hook_payload.supports_runtime_session_payload_attribution is False


def test_runtime_catalog_merges_partial_managed_install_surface_with_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    codex = _catalog_entry_by_runtime_name(payload, "codex")
    codex["managed_install_surface"] = {
        "flat_command_globs": ["custom-command/gpd-*.md"],
    }

    descriptors = _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)
    codex_descriptor = next(descriptor for descriptor in descriptors if descriptor.runtime_name == "codex")
    schema = json.loads(_RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert codex_descriptor.managed_install_surface.flat_command_globs == ("custom-command/gpd-*.md",)
    assert codex_descriptor.managed_install_surface.managed_agent_globs == tuple(
        schema["managed_install_surface_defaults"]["managed_agent_globs"]
    )


@pytest.mark.parametrize(
    "bad_pattern",
    ["../tmp/*", "commands/../../tmp/*", "/tmp/gpd-*", "~/gpd-*", "C:/tmp/gpd-*", r"commands\..\tmp\*"],
)
def test_runtime_catalog_rejects_managed_install_surface_glob_escapes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bad_pattern: str,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    codex = _catalog_entry_by_runtime_name(payload, "codex")
    codex["managed_install_surface"] = {
        "flat_command_globs": [bad_pattern],
    }

    with pytest.raises(
        ValueError,
        match=r"runtime catalog entry \d+\.managed_install_surface\.flat_command_globs\.0 "
        r"must be a relative managed install glob without traversal",
    ):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_rejects_manifest_metadata_policy_affix_on_relpaths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    gemini = _catalog_entry_by_runtime_name(payload, "gemini")
    gemini["manifest_metadata_list_policies"] = [
        {
            "key": "managed_runtime_files",
            "value_kind": "relpath",
            "item_prefix": "gpd-",
        }
    ]

    with pytest.raises(
        ValueError,
        match=r"runtime catalog entry \d+\.manifest_metadata_list_policies\[0\]\.item_prefix/item_suffix "
        r"require value_kind=path_segment",
    ):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def _catalog_manifest_policy_entries(
    payload: list[dict[str, object]],
) -> list[tuple[int, dict[str, object], dict[str, object]]]:
    entries: list[tuple[int, dict[str, object], dict[str, object]]] = []
    for index, entry in enumerate(payload):
        policies = entry.get("manifest_metadata_list_policies")
        if isinstance(policies, list) and policies:
            policy = policies[0]
            assert isinstance(policy, dict)
            entries.append((index, entry, policy))
    return entries


def _conflicting_manifest_metadata_policy(policy: dict[str, object]) -> dict[str, object]:
    conflict = deepcopy(policy)
    if conflict.get("value_kind") == "relpath":
        conflict["value_kind"] = "path_segment"
        conflict["item_prefix"] = "managed-"
        conflict.pop("item_suffix", None)
        return conflict

    conflict["item_prefix"] = "alternate-" if conflict.get("item_prefix") != "alternate-" else "managed-"
    return conflict


def test_runtime_catalog_allows_identical_cross_runtime_manifest_metadata_policy_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    policy_entries = _catalog_manifest_policy_entries(payload)
    assert len(policy_entries) >= 2
    _, _source_entry, source_policy = policy_entries[0]
    _target_index, target_entry, _target_policy = policy_entries[1]
    target_entry["manifest_metadata_list_policies"] = [deepcopy(source_policy)]

    descriptors = _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)
    policy_owners = [
        descriptor.runtime_name
        for descriptor in descriptors
        if descriptor.manifest_metadata_list_policies
        and descriptor.manifest_metadata_list_policies[0].key == source_policy["key"]
    ]

    assert len(policy_owners) == 2


def test_runtime_catalog_rejects_conflicting_cross_runtime_manifest_metadata_policy_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    policy_entries = _catalog_manifest_policy_entries(payload)
    assert len(policy_entries) >= 2
    _, _source_entry, source_policy = policy_entries[0]
    _target_index, target_entry, _target_policy = policy_entries[1]
    target_entry["manifest_metadata_list_policies"] = [_conflicting_manifest_metadata_policy(source_policy)]

    with pytest.raises(
        ValueError,
        match=r"runtime catalog contains conflicting manifest_metadata_list_policies\.key",
    ):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


@pytest.mark.parametrize(
    ("field_name", "bad_value", "match"),
    [
        (
            "supports_usage_tokens",
            "true",
            r"runtime catalog schema\.capability_defaults\.supports_usage_tokens must be a boolean",
        ),
        (
            "telemetry_source",
            "webhook",
            r"runtime catalog schema\.capability_defaults\.telemetry_source must be one of: none, notify-hook, runtime-api",
        ),
        (
            "prompt_free_mode_value",
            " ",
            r"runtime catalog schema\.capability_defaults\.prompt_free_mode_value must be a non-empty string",
        ),
        (
            "statusline_config_surface",
            "status-line",
            (
                r"runtime catalog schema\.capability_defaults\.statusline_config_surface must be "
                r'"none" or a config surface label like file:key'
            ),
        ),
    ],
)
def test_runtime_catalog_rejects_invalid_capability_default_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
    bad_value: object,
    match: str,
) -> None:
    schema = deepcopy(json.loads(_RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8")))
    schema["capability_defaults"][field_name] = bad_value

    with pytest.raises(ValueError, match=match):
        _iter_runtime_descriptors_from_schema(schema, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_accepts_future_config_surface_labels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["capabilities"]["permission_surface_kind"] = "future.json:permissions.mode"
    payload[0]["capabilities"]["statusline_config_surface"] = "future.json:statusLine"
    payload[0]["capabilities"]["notify_surface"] = "explicit"
    payload[0]["capabilities"]["notify_config_surface"] = "future.json:notify"
    payload[0]["hook_payload"]["notify_event_types"] = ["future-event"]

    descriptors = _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)

    assert descriptors[0].capabilities.permission_surface_kind == "future.json:permissions.mode"
    assert descriptors[0].capabilities.statusline_config_surface == "future.json:statusLine"
    assert descriptors[0].capabilities.notify_config_surface == "future.json:notify"


def test_runtime_catalog_accepts_non_notify_telemetry_source_with_usage_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    opencode = _catalog_entry_by_runtime_name(payload, "opencode")
    opencode["capabilities"].update(
        {
            "telemetry_source": "runtime-api",
            "telemetry_completeness": "best-effort",
            "supports_usage_tokens": True,
            "supports_cost_usd": True,
        }
    )
    opencode["hook_payload"].update(
        {
            "usage_keys": ["usage"],
            "input_tokens_keys": ["input_tokens"],
            "output_tokens_keys": ["output_tokens"],
            "cost_usd_keys": ["cost_usd"],
        }
    )

    descriptors = _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)
    opencode_descriptor = next(descriptor for descriptor in descriptors if descriptor.runtime_name == "opencode")

    assert opencode_descriptor.capabilities.notify_surface == "none"
    assert opencode_descriptor.capabilities.telemetry_source == "runtime-api"
    assert opencode_descriptor.capabilities.supports_usage_tokens is True
    assert opencode_descriptor.capabilities.supports_cost_usd is True


def test_runtime_catalog_rejects_malformed_config_surface_labels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["capabilities"]["statusline_config_surface"] = "statusLine-toggle"

    with pytest.raises(
        ValueError,
        match=r'runtime catalog entry 0\.capabilities\.statusline_config_surface must be "none" or a config surface label like file:key',
    ):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_rejects_duplicate_runtime_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[1]["runtime_name"] = payload[0]["runtime_name"]

    with pytest.raises(ValueError, match=r"runtime catalog contains duplicate runtime_name"):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_rejects_duplicate_runtime_selection_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[1]["selection_aliases"] = [payload[0]["selection_aliases"][0]]

    with pytest.raises(ValueError, match=r"runtime catalog contains duplicate runtime selection token"):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_rejects_duplicate_install_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[1]["install_flag"] = payload[0]["install_flag"]

    with pytest.raises(ValueError, match=r"runtime catalog contains duplicate install_flag"):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda capabilities: capabilities.update(
                permissions_surface="config-file",
                permission_surface_kind="none",
            ),
            r"runtime catalog entry 0\.capabilities\.permission_surface_kind must be a config surface label when permissions_surface=config-file",
        ),
        (
            lambda capabilities: capabilities.update(
                permissions_surface="unsupported",
                permission_surface_kind="future.json:permissions.mode",
                supports_runtime_permission_sync=True,
                supports_prompt_free_mode=False,
                prompt_free_requires_relaunch=False,
            ),
            r'runtime catalog entry 0\.capabilities\.permission_surface_kind must be "none" when permissions_surface=unsupported',
        ),
    ],
)
def test_runtime_catalog_rejects_incoherent_permission_surface_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutator,
    match: str,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    mutator(payload[0]["capabilities"])

    with pytest.raises(ValueError, match=match):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_runtime_catalog_accepts_catalog_declared_launch_wrapper_special_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = deepcopy(json.loads(_RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8")))
    schema["launch_wrapper_permission_surface_kinds"] = [
        *schema["launch_wrapper_permission_surface_kinds"],
        "future.json:launchWrapper",
    ]
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    _catalog_entry_by_runtime_name(payload, "gemini")["capabilities"]["permission_surface_kind"] = (
        "future.json:launchWrapper"
    )

    catalog_path = tmp_path / "runtime_catalog.json"
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(runtime_catalog, "_catalog_path", lambda: catalog_path)
    descriptors = _iter_runtime_descriptors_from_schema(schema, tmp_path=tmp_path, monkeypatch=monkeypatch)

    gemini = next(descriptor for descriptor in descriptors if descriptor.runtime_name == "gemini")
    assert gemini.capabilities.permission_surface_kind == "future.json:launchWrapper"


def test_runtime_catalog_rejects_config_file_use_of_catalog_declared_launch_wrapper_special_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = deepcopy(json.loads(_RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8")))
    schema["launch_wrapper_permission_surface_kinds"] = [
        *schema["launch_wrapper_permission_surface_kinds"],
        "future.json:launchWrapper",
    ]
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    _catalog_entry_by_runtime_name(payload, "codex")["capabilities"]["permission_surface_kind"] = (
        "future.json:launchWrapper"
    )
    catalog_path = tmp_path / "runtime_catalog.json"
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(runtime_catalog, "_catalog_path", lambda: catalog_path)

    with pytest.raises(
        ValueError,
        match=r"runtime catalog entry \d+\.capabilities\.permission_surface_kind must be a config surface label when permissions_surface=config-file",
    ):
        _iter_runtime_descriptors_from_schema(schema, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_hook_payload_policy_uses_runtime_specific_overrides_and_merged_fallback() -> None:
    codex_policy = get_hook_payload_policy("codex")
    merged_policy = get_hook_payload_policy()

    assert codex_policy.notify_event_types == ("agent-turn-complete",)
    assert "agent-turn-complete" in merged_policy.notify_event_types
    assert "cwd" in merged_policy.workspace_keys
    assert codex_policy.target_path_keys == ("target_path",)
    assert codex_policy.target_root_keys == ("target_root",)
    assert merged_policy.target_path_keys == ("target_path",)
    assert merged_policy.target_root_keys == ("target_root",)
    assert codex_policy.supports_runtime_session_payload_attribution is False
    assert codex_policy.supports_agent_payload_attribution is False
    assert merged_policy.supports_runtime_session_payload_attribution is False
    assert merged_policy.supports_agent_payload_attribution is False
    assert isinstance(codex_policy.runtime_session_id_keys, tuple)
    assert isinstance(codex_policy.agent_id_keys, tuple)
    assert isinstance(codex_policy.agent_name_keys, tuple)
    assert isinstance(codex_policy.agent_scope_keys, tuple)
    assert isinstance(merged_policy.runtime_session_id_keys, tuple)
    assert isinstance(merged_policy.agent_id_keys, tuple)
    assert isinstance(merged_policy.agent_name_keys, tuple)
    assert isinstance(merged_policy.agent_scope_keys, tuple)


def test_runtime_catalog_workspace_payload_keys_use_cwd_as_primary_when_declared() -> None:
    for descriptor in iter_runtime_descriptors():
        workspace_keys = descriptor.hook_payload.workspace_keys
        if not workspace_keys:
            continue

        assert workspace_keys[0] == "cwd", f"{descriptor.runtime_name} must keep cwd as the primary workspace key"


@pytest.mark.parametrize(
    ("capability_key", "capability_value", "hook_payload_updates", "match"),
    [
        (
            "supports_runtime_session_payload_attribution",
            False,
            {"runtime_session_id_keys": ["session_id"]},
            (
                r"runtime catalog entry 0\.capabilities\.supports_runtime_session_payload_attribution "
                r"must match runtime catalog entry 0\.hook_payload\.runtime_session_id_keys"
            ),
        ),
        (
            "supports_runtime_session_payload_attribution",
            True,
            {"runtime_session_id_keys": []},
            (
                r"runtime catalog entry 0\.capabilities\.supports_runtime_session_payload_attribution "
                r"must match runtime catalog entry 0\.hook_payload\.runtime_session_id_keys"
            ),
        ),
        (
            "supports_agent_payload_attribution",
            False,
            {"agent_name_keys": ["agent_name"]},
            (
                r"runtime catalog entry 0\.capabilities\.supports_agent_payload_attribution "
                r"must match runtime catalog entry 0\.hook_payload\.agent_id_keys/agent_name_keys/agent_scope_keys"
            ),
        ),
        (
            "supports_agent_payload_attribution",
            True,
            {"agent_id_keys": [], "agent_name_keys": [], "agent_scope_keys": []},
            (
                r"runtime catalog entry 0\.capabilities\.supports_agent_payload_attribution "
                r"must match runtime catalog entry 0\.hook_payload\.agent_id_keys/agent_name_keys/agent_scope_keys"
            ),
        ),
    ],
)
def test_runtime_catalog_rejects_capability_attribution_drift_from_hook_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capability_key: str,
    capability_value: bool,
    hook_payload_updates: dict[str, list[str]],
    match: str,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    payload[0]["capabilities"][capability_key] = capability_value
    payload[0]["hook_payload"].update(hook_payload_updates)

    with pytest.raises(ValueError, match=match):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


@pytest.mark.parametrize(
    ("runtime_name", "capability_updates", "hook_payload_updates", "match"),
    [
        (
            "codex",
            {},
            {"notify_event_types": []},
            (
                r"runtime catalog entry \d+\.capabilities\.notify_surface requires "
                r"runtime catalog entry \d+\.hook_payload\.notify_event_types"
            ),
        ),
        (
            "codex",
            {},
            {"input_tokens_keys": []},
            (
                r"runtime catalog entry \d+\.capabilities\.supports_usage_tokens requires "
                r"runtime catalog entry \d+\.hook_payload\.input_tokens_keys"
            ),
        ),
        (
            "codex",
            {},
            {"cost_usd_keys": []},
            (
                r"runtime catalog entry \d+\.capabilities\.supports_cost_usd requires "
                r"runtime catalog entry \d+\.hook_payload\.cost_usd_keys"
            ),
        ),
        (
            "claude-code",
            {},
            {"context_remaining_keys": []},
            (
                r"runtime catalog entry \d+\.capabilities\.supports_context_meter requires "
                r"runtime catalog entry \d+\.hook_payload\.context_remaining_keys"
            ),
        ),
        (
            "codex",
            {"notify_surface": "none", "notify_config_surface": "none"},
            {},
            (
                r"runtime catalog entry \d+\.capabilities\.telemetry_source requires "
                r"runtime catalog entry \d+\.capabilities\.notify_surface=explicit"
            ),
        ),
    ],
)
def test_runtime_catalog_rejects_capability_flags_without_required_hook_payload_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runtime_name: str,
    capability_updates: dict[str, object],
    hook_payload_updates: dict[str, list[str]],
    match: str,
) -> None:
    payload = deepcopy(json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8")))
    entry = _catalog_entry_by_runtime_name(payload, runtime_name)
    entry["capabilities"].update(capability_updates)
    entry["hook_payload"].update(hook_payload_updates)

    with pytest.raises(ValueError, match=match):
        _iter_runtime_descriptors_from_payload(payload, tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_hook_payload_policy_rejects_explicit_unknown_runtime() -> None:
    with pytest.raises(KeyError, match=r"Unknown runtime 'not-a-runtime'"):
        get_hook_payload_policy("not-a-runtime")


def test_hook_payload_policy_merges_declared_runtime_session_and_agent_attribution_keys(monkeypatch) -> None:
    descriptors = iter_runtime_descriptors()
    synthetic = (
        replace(
            descriptors[0],
            hook_payload=replace(
                descriptors[0].hook_payload,
                runtime_session_id_keys=("session_id",),
                agent_id_keys=("agent_id",),
                agent_name_keys=("agent_name",),
                agent_scope_keys=("agent_scope",),
            ),
        ),
        *descriptors[1:],
    )
    monkeypatch.setattr(runtime_catalog, "iter_runtime_descriptors", lambda: synthetic)

    runtime_policy = get_hook_payload_policy(synthetic[0].runtime_name)
    merged_policy = get_hook_payload_policy()

    assert runtime_policy.runtime_session_id_keys == ("session_id",)
    assert runtime_policy.agent_id_keys == ("agent_id",)
    assert runtime_policy.agent_name_keys == ("agent_name",)
    assert runtime_policy.agent_scope_keys == ("agent_scope",)
    assert runtime_policy.supports_runtime_session_payload_attribution is True
    assert runtime_policy.supports_agent_payload_attribution is True
    assert merged_policy.runtime_session_id_keys[0] == "session_id"
    assert merged_policy.agent_id_keys[0] == "agent_id"
    assert merged_policy.agent_name_keys[0] == "agent_name"
    assert merged_policy.agent_scope_keys[0] == "agent_scope"
    assert merged_policy.supports_runtime_session_payload_attribution is True
    assert merged_policy.supports_agent_payload_attribution is True


def test_runtime_capabilities_are_explicit_per_runtime() -> None:
    claude = get_runtime_capabilities("claude-code")
    gemini = get_runtime_capabilities("gemini")
    codex = get_runtime_capabilities("codex")
    opencode = get_runtime_capabilities("opencode")

    assert claude.permissions_surface == "config-file"
    assert claude.permission_surface_kind == "settings.json:permissions.defaultMode"
    assert claude.supports_runtime_permission_sync is True
    assert claude.supports_prompt_free_mode is True
    assert claude.prompt_free_requires_relaunch is True
    assert claude.statusline_surface == "explicit"
    assert claude.statusline_config_surface == "settings.json:statusLine"
    assert claude.notify_surface == "none"
    assert claude.notify_config_surface == "none"
    assert claude.supports_context_meter is True
    assert claude.supports_usage_tokens is False
    assert claude.supports_cost_usd is False
    assert claude.child_artifact_persistence_reliability == "best-effort"
    assert claude.supports_structured_child_results is False
    assert claude.continuation_surface == "none"
    assert claude.checkpoint_stop_semantics == "stop"
    assert claude.supports_runtime_session_payload_attribution is False
    assert claude.supports_agent_payload_attribution is False
    assert claude.telemetry_completeness == "none"
    assert get_hook_payload_policy("claude-code").supports_runtime_session_payload_attribution is False
    assert get_hook_payload_policy("claude-code").supports_agent_payload_attribution is False

    assert gemini.permissions_surface == "launch-wrapper"
    assert gemini.permission_surface_kind in _special_permission_surface_kinds()
    assert gemini.supports_runtime_permission_sync is True
    assert gemini.supports_prompt_free_mode is True
    assert gemini.prompt_free_requires_relaunch is True
    assert gemini.statusline_surface == "explicit"
    assert gemini.statusline_config_surface == "settings.json:statusLine"
    assert gemini.notify_surface == "none"
    assert gemini.notify_config_surface == "none"
    assert gemini.supports_context_meter is True
    assert gemini.supports_usage_tokens is False
    assert gemini.supports_cost_usd is False
    assert gemini.child_artifact_persistence_reliability == "best-effort"
    assert gemini.supports_structured_child_results is False
    assert gemini.continuation_surface == "none"
    assert gemini.checkpoint_stop_semantics == "stop"
    assert gemini.supports_runtime_session_payload_attribution is False
    assert gemini.supports_agent_payload_attribution is False
    assert gemini.telemetry_completeness == "none"
    assert get_hook_payload_policy("gemini").supports_runtime_session_payload_attribution is False
    assert get_hook_payload_policy("gemini").supports_agent_payload_attribution is False

    assert codex.permissions_surface == "config-file"
    assert codex.permission_surface_kind == "config.toml:approval_policy+sandbox_mode"
    assert codex.supports_runtime_permission_sync is True
    assert codex.supports_prompt_free_mode is True
    assert codex.prompt_free_requires_relaunch is True
    assert codex.statusline_surface == "none"
    assert codex.statusline_config_surface == "none"
    assert codex.notify_surface == "explicit"
    assert codex.notify_config_surface == "config.toml:notify"
    assert codex.telemetry_source == "notify-hook"
    assert codex.telemetry_completeness == "best-effort"
    assert codex.supports_context_meter is False
    assert codex.supports_usage_tokens is True
    assert codex.supports_cost_usd is True
    assert codex.child_artifact_persistence_reliability == "best-effort"
    assert codex.supports_structured_child_results is True
    assert codex.continuation_surface == "explicit"
    assert codex.checkpoint_stop_semantics == "stop"
    assert codex.supports_runtime_session_payload_attribution is False
    assert codex.supports_agent_payload_attribution is False
    assert get_hook_payload_policy("codex").supports_runtime_session_payload_attribution is False
    assert get_hook_payload_policy("codex").supports_agent_payload_attribution is False

    assert opencode.permissions_surface == "config-file"
    assert opencode.permission_surface_kind == "opencode.json:permission"
    assert opencode.supports_runtime_permission_sync is True
    assert opencode.supports_prompt_free_mode is True
    assert opencode.prompt_free_requires_relaunch is True
    assert opencode.statusline_surface == "none"
    assert opencode.statusline_config_surface == "none"
    assert opencode.notify_surface == "none"
    assert opencode.notify_config_surface == "none"
    assert opencode.telemetry_completeness == "none"
    assert opencode.supports_context_meter is False
    assert opencode.supports_usage_tokens is False
    assert opencode.supports_cost_usd is False
    assert opencode.child_artifact_persistence_reliability == "best-effort"
    assert opencode.supports_structured_child_results is False
    assert opencode.continuation_surface == "none"
    assert opencode.checkpoint_stop_semantics == "stop"
    assert opencode.supports_runtime_session_payload_attribution is False
    assert opencode.supports_agent_payload_attribution is False
    assert get_hook_payload_policy("opencode").supports_runtime_session_payload_attribution is False
    assert get_hook_payload_policy("opencode").supports_agent_payload_attribution is False


def test_runtime_capabilities_and_hook_payload_contract_stay_coherent() -> None:
    schema = json.loads(_RUNTIME_CATALOG_SCHEMA_PATH.read_text(encoding="utf-8"))
    allowed_permissions_surfaces = {"config-file", "launch-wrapper", "unsupported"}
    allowed_hook_surfaces = {"explicit", "none"}
    allowed_telemetry_sources = set(schema["capability_enums"]["telemetry_source"])
    allowed_telemetry_completeness = {"best-effort", "none"}
    allowed_child_artifact_persistence_reliability = {"best-effort", "none", "reliable"}
    allowed_continuation_surfaces = {"explicit", "none"}
    allowed_checkpoint_stop_semantics = {"continue", "none", "stop"}
    special_permission_surface_kinds = _special_permission_surface_kinds()

    for runtime_name in list_runtime_names():
        capabilities = get_runtime_capabilities(runtime_name)
        hook_payload = get_hook_payload_policy(runtime_name)

        assert capabilities.permissions_surface in allowed_permissions_surfaces
        assert (
            capabilities.permission_surface_kind in special_permission_surface_kinds
            or capabilities.permission_surface_kind == "none"
            or _RUNTIME_CONFIG_SURFACE_LABEL_RE.fullmatch(capabilities.permission_surface_kind) is not None
        )
        assert isinstance(capabilities.supports_runtime_permission_sync, bool)
        assert isinstance(capabilities.supports_prompt_free_mode, bool)
        assert isinstance(capabilities.prompt_free_requires_relaunch, bool)
        assert capabilities.statusline_surface in allowed_hook_surfaces
        assert (
            capabilities.statusline_config_surface == "none"
            or _RUNTIME_CONFIG_SURFACE_LABEL_RE.fullmatch(capabilities.statusline_config_surface) is not None
        )
        assert capabilities.notify_surface in allowed_hook_surfaces
        assert (
            capabilities.notify_config_surface == "none"
            or _RUNTIME_CONFIG_SURFACE_LABEL_RE.fullmatch(capabilities.notify_config_surface) is not None
        )
        assert capabilities.telemetry_source in allowed_telemetry_sources
        assert capabilities.telemetry_completeness in allowed_telemetry_completeness
        assert isinstance(capabilities.supports_usage_tokens, bool)
        assert isinstance(capabilities.supports_cost_usd, bool)
        assert isinstance(capabilities.supports_context_meter, bool)
        assert capabilities.child_artifact_persistence_reliability in allowed_child_artifact_persistence_reliability
        assert isinstance(capabilities.supports_structured_child_results, bool)
        assert capabilities.continuation_surface in allowed_continuation_surfaces
        assert capabilities.checkpoint_stop_semantics in allowed_checkpoint_stop_semantics
        assert isinstance(capabilities.supports_runtime_session_payload_attribution, bool)
        assert isinstance(capabilities.supports_agent_payload_attribution, bool)
        assert hook_payload.supports_runtime_session_payload_attribution == bool(hook_payload.runtime_session_id_keys)
        assert hook_payload.supports_agent_payload_attribution == bool(
            hook_payload.agent_id_keys or hook_payload.agent_name_keys or hook_payload.agent_scope_keys
        )
        assert (
            capabilities.supports_runtime_session_payload_attribution
            == hook_payload.supports_runtime_session_payload_attribution
        )
        assert capabilities.supports_agent_payload_attribution == hook_payload.supports_agent_payload_attribution

        if capabilities.statusline_surface == "explicit":
            assert capabilities.statusline_config_surface != "none"
            assert hook_payload.model_keys
            assert hook_payload.context_window_size_keys
            assert hook_payload.context_remaining_keys
            assert capabilities.supports_context_meter is True
        else:
            assert capabilities.statusline_config_surface == "none"
            assert not hook_payload.context_window_size_keys
            assert not hook_payload.context_remaining_keys
            assert capabilities.supports_context_meter is False

        if capabilities.notify_surface == "explicit":
            assert capabilities.notify_config_surface != "none"
            assert hook_payload.notify_event_types
        else:
            assert capabilities.notify_config_surface == "none"
            assert not hook_payload.notify_event_types

        if capabilities.telemetry_completeness == "best-effort":
            assert capabilities.telemetry_source != "none"
            if capabilities.telemetry_source == "notify-hook":
                assert capabilities.notify_surface == "explicit"
            if capabilities.supports_usage_tokens:
                assert hook_payload.usage_keys
                assert hook_payload.input_tokens_keys
                assert hook_payload.output_tokens_keys
            if capabilities.supports_cost_usd:
                assert hook_payload.cost_usd_keys
        else:
            assert capabilities.telemetry_source == "none"
            assert capabilities.supports_usage_tokens is False
            assert capabilities.supports_cost_usd is False
            assert not hook_payload.usage_keys
            assert not hook_payload.input_tokens_keys
            assert not hook_payload.output_tokens_keys
            assert not hook_payload.cost_usd_keys

        if capabilities.supports_structured_child_results:
            assert capabilities.continuation_surface == "explicit"

        if hook_payload.supports_runtime_session_payload_attribution or hook_payload.supports_agent_payload_attribution:
            assert capabilities.notify_surface == "explicit"
            assert capabilities.telemetry_source == "notify-hook"


def test_hook_payload_policy_exposes_usage_alias_fields_for_cost_telemetry() -> None:
    codex_policy = get_hook_payload_policy("codex")
    merged_policy = get_hook_payload_policy()
    merged_aliases = {
        *merged_policy.usage_keys,
        *merged_policy.input_tokens_keys,
        *merged_policy.output_tokens_keys,
        *merged_policy.cached_input_tokens_keys,
        *merged_policy.cache_write_input_tokens_keys,
        *merged_policy.cost_usd_keys,
    }

    assert codex_policy.usage_keys == ("usage", "token_usage", "tokens")
    assert codex_policy.input_tokens_keys == ("input_tokens", "prompt_tokens", "inputTokens", "promptTokens")
    assert codex_policy.output_tokens_keys == (
        "output_tokens",
        "completion_tokens",
        "outputTokens",
        "completionTokens",
    )
    assert codex_policy.cached_input_tokens_keys == (
        "cached_input_tokens",
        "cache_read_input_tokens",
        "cachedInputTokens",
        "cacheReadInputTokens",
    )
    assert codex_policy.cache_write_input_tokens_keys == (
        "cache_write_input_tokens",
        "cache_creation_input_tokens",
        "cacheWriteInputTokens",
        "cacheCreationInputTokens",
    )
    assert codex_policy.cost_usd_keys == ("cost_usd", "costUsd", "usd_cost", "usdCost")

    for alias in (
        "usage",
        "token_usage",
        "tokens",
        "promptTokens",
        "completionTokens",
        "cacheReadInputTokens",
        "cacheCreationInputTokens",
        "usdCost",
    ):
        assert alias in merged_aliases
