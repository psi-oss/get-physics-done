"""Tests for adapter registry and tool_names module."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import gpd.adapters as adapters_module
from gpd.adapters import get_adapter, list_runtimes
from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.runtime_catalog import (
    GlobalConfigPolicy,
    HookPayloadPolicy,
    RuntimeDescriptor,
    iter_runtime_descriptors,
    list_runtime_names,
)
from gpd.adapters.tool_names import (
    CANONICAL_TOOL_NAMES,
    CONTEXTUAL_TOOL_REFERENCE_NAMES,
    build_canonical_alias_map,
    canonical,
    reference_translation_map,
    translate,
    translate_for_runtime,
)


def _runtime_tool_maps() -> dict[str, dict[str, str]]:
    return {runtime: get_adapter(runtime).tool_name_map for runtime in list_runtimes()}


def _canonical_alias_map() -> dict[str, str]:
    return build_canonical_alias_map(_runtime_tool_maps().values())


RUNTIME_NAMES = list_runtime_names()


class TestRegistry:
    """Tests for the adapter registry (get_adapter / list_runtimes)."""

    def test_list_runtimes_returns_all_catalog_entries(self) -> None:
        runtimes = list_runtimes()
        assert set(runtimes) == set(RUNTIME_NAMES)

    def test_list_runtimes_matches_runtime_catalog_order(self) -> None:
        assert list_runtimes() == list_runtime_names()

    def test_list_runtimes_follows_priority_order(self) -> None:
        runtimes = list_runtimes()
        assert runtimes == [descriptor.runtime_name for descriptor in iter_runtime_descriptors()]

    @pytest.mark.parametrize("runtime", RUNTIME_NAMES)
    def test_get_adapter_returns_instance(self, runtime: str) -> None:
        adapter = get_adapter(runtime)
        assert isinstance(adapter, RuntimeAdapter)
        assert adapter.runtime_name == runtime

    def test_get_adapter_unknown_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="Unknown runtime"):
            get_adapter("nonexistent")

    def test_get_adapter_returns_new_instance_each_call(self) -> None:
        a = get_adapter("claude-code")
        b = get_adapter("claude-code")
        assert a is not b

    @pytest.mark.parametrize("runtime", RUNTIME_NAMES)
    def test_update_command_is_adapter_owned(self, runtime: str) -> None:
        adapter = get_adapter(runtime)
        assert adapter.update_command == f"npx -y get-physics-done {adapter.runtime_descriptor.install_flag}"

    def test_loader_uses_runtime_descriptors_to_import_modules(self, monkeypatch: pytest.MonkeyPatch) -> None:
        alpha_descriptor = RuntimeDescriptor(
            runtime_name="alpha-runtime",
            display_name="Alpha Runtime",
            priority=20,
            config_dir_name=".alpha",
            install_flag="--alpha",
            launch_command="alpha",
            command_prefix="/gpd:",
            activation_env_vars=(),
            selection_flags=("--alpha",),
            selection_aliases=("alpha-runtime",),
            global_config=GlobalConfigPolicy(strategy="env_or_home", home_subpath=".alpha"),
            hook_payload=HookPayloadPolicy(),
        )
        beta_descriptor = RuntimeDescriptor(
            runtime_name="beta-runtime",
            display_name="Beta Runtime",
            priority=10,
            config_dir_name=".beta",
            install_flag="--beta",
            launch_command="beta",
            command_prefix="/gpd:",
            activation_env_vars=(),
            selection_flags=("--beta",),
            selection_aliases=("beta-runtime",),
            global_config=GlobalConfigPolicy(strategy="env_or_home", home_subpath=".beta"),
            hook_payload=HookPayloadPolicy(),
        )

        class AlphaAdapter(RuntimeAdapter):
            @property
            def runtime_name(self) -> str:
                return "alpha-runtime"

        class BetaAdapter(RuntimeAdapter):
            @property
            def runtime_name(self) -> str:
                return "beta-runtime"

        imported_modules: list[str] = []

        def fake_import_module(name: str) -> object:
            imported_modules.append(name)
            return {
                "gpd.adapters.alpha_runtime": SimpleNamespace(AlphaAdapter=AlphaAdapter),
                "gpd.adapters.beta_runtime": SimpleNamespace(BetaAdapter=BetaAdapter),
            }[name]

        monkeypatch.setattr(adapters_module, "iter_runtime_descriptors", lambda: (beta_descriptor, alpha_descriptor))
        monkeypatch.setattr(adapters_module, "import_module", fake_import_module)
        monkeypatch.setattr(adapters_module, "_REGISTRY", {})
        monkeypatch.setattr(adapters_module, "_LOADED", False)

        adapters_module._ensure_loaded()

        assert imported_modules == ["gpd.adapters.beta_runtime", "gpd.adapters.alpha_runtime"]
        assert adapters_module.list_runtimes() == ["beta-runtime", "alpha-runtime"]
        assert adapters_module.get_adapter("alpha-runtime").runtime_name == "alpha-runtime"

    def test_loader_rejects_duplicate_runtime_names(self, monkeypatch: pytest.MonkeyPatch) -> None:
        duplicate_descriptor = RuntimeDescriptor(
            runtime_name="duplicate-runtime",
            display_name="Duplicate Runtime",
            priority=10,
            config_dir_name=".duplicate",
            install_flag="--duplicate",
            launch_command="duplicate",
            command_prefix="/gpd:",
            activation_env_vars=(),
            selection_flags=("--duplicate",),
            selection_aliases=("duplicate-runtime",),
            global_config=GlobalConfigPolicy(strategy="env_or_home", home_subpath=".duplicate"),
            hook_payload=HookPayloadPolicy(),
        )

        class DuplicateAdapter(RuntimeAdapter):
            @property
            def runtime_name(self) -> str:
                return "duplicate-runtime"

        monkeypatch.setattr(
            adapters_module,
            "iter_runtime_descriptors",
            lambda: (duplicate_descriptor, duplicate_descriptor),
        )
        monkeypatch.setattr(
            adapters_module,
            "import_module",
            lambda name: SimpleNamespace(DuplicateAdapter=DuplicateAdapter),
        )
        monkeypatch.setattr(adapters_module, "_REGISTRY", {})
        monkeypatch.setattr(adapters_module, "_LOADED", False)

        with pytest.raises(RuntimeError, match="Duplicate runtime name in runtime catalog"):
            adapters_module._ensure_loaded()


class TestToolNames:
    """Tests for tool_names canonical/translate functions."""

    def test_canonical_identity_for_canonical_names(self) -> None:
        for name in ("file_read", "file_write", "shell", "search_files"):
            assert canonical(name) == name

    @pytest.mark.parametrize(
        ("runtime_alias", "expected"),
        [
            ("Read", "file_read"),
            ("read_file", "file_read"),
            ("Write", "file_write"),
            ("apply_patch", "file_edit"),
            ("Edit", "file_edit"),
            ("Bash", "shell"),
            ("run_shell_command", "shell"),
            ("Grep", "search_files"),
            ("Glob", "find_files"),
            ("WebSearch", "web_search"),
            ("websearch", "web_search"),
            ("WebFetch", "web_fetch"),
            ("AskUserQuestion", "ask_user"),
            ("question", "ask_user"),
            ("skill", "slash_command"),
        ],
    )
    def test_canonical_runtime_aliases(self, runtime_alias: str, expected: str) -> None:
        assert canonical(runtime_alias, _canonical_alias_map()) == expected

    def test_canonical_unknown_passthrough(self) -> None:
        assert canonical("custom_tool", _canonical_alias_map()) == "custom_tool"

    @pytest.mark.parametrize(
        ("canon", "runtime", "expected"),
        [
            ("file_read", "claude-code", "Read"),
            ("file_read", "codex", "read_file"),
            ("file_read", "gemini", "read_file"),
            ("file_read", "opencode", "read_file"),
            ("shell", "claude-code", "Bash"),
            ("shell", "gemini", "run_shell_command"),
            ("search_files", "gemini", "search_file_content"),
            ("web_search", "gemini", "google_web_search"),
            ("ask_user", "opencode", "question"),
            ("slash_command", "opencode", "skill"),
        ],
    )
    def test_translate_canonical_to_runtime(self, canon: str, runtime: str, expected: str) -> None:
        assert translate(canon, _runtime_tool_maps()[runtime], alias_map=_canonical_alias_map()) == expected

    def test_translate_runtime_alias_auto_canonicalized(self) -> None:
        runtime_maps = _runtime_tool_maps()
        alias_map = _canonical_alias_map()
        assert translate("Read", runtime_maps["codex"], alias_map=alias_map) == "read_file"
        assert translate("Bash", runtime_maps["gemini"], alias_map=alias_map) == "run_shell_command"

    def test_translate_runtime_native_name_auto_canonicalized(self) -> None:
        runtime_maps = _runtime_tool_maps()
        alias_map = _canonical_alias_map()
        assert translate("apply_patch", runtime_maps["claude-code"], alias_map=alias_map) == "Edit"
        assert translate("question", runtime_maps["codex"], alias_map=alias_map) == "ask_user"
        assert translate("run_shell_command", runtime_maps["opencode"], alias_map=alias_map) == "shell"

    def test_translate_unknown_runtime_fallback(self) -> None:
        assert translate("file_read", {}, alias_map=_canonical_alias_map()) == "file_read"

    def test_translate_unknown_tool_fallback(self) -> None:
        assert translate("custom_tool", _runtime_tool_maps()["claude-code"], alias_map=_canonical_alias_map()) == "custom_tool"

    def test_translate_for_runtime_drops_auto_discovered_tools(self) -> None:
        runtime_maps = _runtime_tool_maps()
        alias_map = _canonical_alias_map()
        assert translate_for_runtime(
            "task",
            runtime_maps["codex"],
            alias_map=alias_map,
            auto_discovered_tools=get_adapter("codex").auto_discovered_tools,
        ) is None
        assert translate_for_runtime(
            "Task",
            runtime_maps["gemini"],
            alias_map=alias_map,
            auto_discovered_tools=get_adapter("gemini").auto_discovered_tools,
            drop_mcp_frontmatter_tools=get_adapter("gemini").drop_mcp_frontmatter_tools,
        ) is None

    def test_translate_for_runtime_handles_mcp_policy(self) -> None:
        runtime_maps = _runtime_tool_maps()
        alias_map = _canonical_alias_map()
        assert translate_for_runtime(
            "mcp__physics",
            runtime_maps["gemini"],
            alias_map=alias_map,
            auto_discovered_tools=get_adapter("gemini").auto_discovered_tools,
            drop_mcp_frontmatter_tools=get_adapter("gemini").drop_mcp_frontmatter_tools,
        ) is None
        assert translate_for_runtime(
            "mcp__physics",
            runtime_maps["codex"],
            alias_map=alias_map,
            auto_discovered_tools=get_adapter("codex").auto_discovered_tools,
        ) == "mcp__physics"

    def test_reference_translation_map_uses_only_canonical_source_names(self) -> None:
        mapping = reference_translation_map(_runtime_tool_maps()["opencode"], alias_map=_canonical_alias_map())
        assert mapping["ask_user"] == "question"
        assert "AskUserQuestion" not in mapping
        assert "read_file" not in mapping  # identical names are omitted

    def test_contextual_reference_names_cover_common_english_tools(self) -> None:
        assert {"Read", "Write", "Edit", "shell", "task", "agent"} <= CONTEXTUAL_TOOL_REFERENCE_NAMES

    def test_canonical_tool_names_match_runtime_table_keys(self) -> None:
        assert set(CANONICAL_TOOL_NAMES) == set(_runtime_tool_maps()[RUNTIME_NAMES[0]])

    def test_all_runtime_tables_present(self) -> None:
        assert set(_runtime_tool_maps()) == set(RUNTIME_NAMES)

    def test_all_tables_have_same_canonical_keys(self) -> None:
        runtime_maps = _runtime_tool_maps()
        keys = set(runtime_maps[RUNTIME_NAMES[0]].keys())
        for runtime, table in runtime_maps.items():
            assert set(table.keys()) == keys, f"{runtime} has different canonical keys than {RUNTIME_NAMES[0]}"
