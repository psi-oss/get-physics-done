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
    get_runtime_descriptor,
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


def _patch_catalog_descriptors(monkeypatch: pytest.MonkeyPatch, descriptors: tuple[RuntimeDescriptor, ...]) -> None:
    monkeypatch.setattr(adapters_module, "iter_runtime_descriptors", lambda: descriptors)
    monkeypatch.setattr("gpd.adapters.base.iter_runtime_descriptors", lambda: descriptors)


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

    @pytest.mark.parametrize("runtime", RUNTIME_NAMES)
    def test_adapter_runtime_name_is_catalog_derived(self, runtime: str) -> None:
        adapter = get_adapter(runtime)
        descriptor = get_runtime_descriptor(runtime)

        assert adapter.runtime_name == descriptor.runtime_name
        assert adapter.__class__.__module__.rsplit(".", 1)[-1] == descriptor.adapter_module

    def test_adapter_runtime_descriptor_is_cached_catalog_source(self, monkeypatch: pytest.MonkeyPatch) -> None:
        descriptor = RuntimeDescriptor(
            runtime_name="catalog-runtime",
            adapter_module="catalog_adapter",
            display_name="Catalog Runtime",
            priority=10,
            config_dir_name=".catalog",
            install_flag="--catalog",
            launch_command="catalog",
            command_prefix="/gpd:",
            activation_env_vars=(),
            selection_flags=("--catalog",),
            selection_aliases=("catalog-runtime",),
            global_config=GlobalConfigPolicy(strategy="env_or_home", home_subpath=".catalog"),
            hook_payload=HookPayloadPolicy(),
        )

        class CatalogAdapter(RuntimeAdapter):
            pass

        CatalogAdapter.__module__ = "gpd.adapters.catalog_adapter"
        _patch_catalog_descriptors(monkeypatch, (descriptor,))

        adapter = CatalogAdapter()

        assert adapter.runtime_descriptor is descriptor
        assert adapter.runtime_name == "catalog-runtime"

        monkeypatch.setattr("gpd.adapters.base.iter_runtime_descriptors", lambda: pytest.fail("descriptor lookup repeated"))

        assert adapter.runtime_descriptor is descriptor
        assert adapter.runtime_name == "catalog-runtime"

    @pytest.mark.parametrize("descriptor", iter_runtime_descriptors(), ids=lambda descriptor: descriptor.runtime_name)
    def test_get_adapter_accepts_catalog_aliases(self, descriptor) -> None:
        values = {descriptor.display_name, descriptor.install_flag, *descriptor.selection_flags, *descriptor.selection_aliases}
        for value in values:
            adapter = get_adapter(value)
            assert adapter.runtime_name == descriptor.runtime_name

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

    def test_get_adapter_loads_only_requested_runtime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        alpha_descriptor = RuntimeDescriptor(
            runtime_name="alpha-runtime",
            adapter_module="alpha_adapter",
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
            adapter_module="beta_adapter",
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
            pass

        class BetaAdapter(RuntimeAdapter):
            pass

        AlphaAdapter.__module__ = "gpd.adapters.alpha_adapter"
        BetaAdapter.__module__ = "gpd.adapters.beta_adapter"

        imported_modules: list[str] = []

        def fake_import_module(name: str) -> object:
            imported_modules.append(name)
            return {
                "gpd.adapters.alpha_adapter": SimpleNamespace(AlphaAdapter=AlphaAdapter),
                "gpd.adapters.beta_adapter": SimpleNamespace(BetaAdapter=BetaAdapter),
            }[name]

        _patch_catalog_descriptors(monkeypatch, (beta_descriptor, alpha_descriptor))
        monkeypatch.setattr(adapters_module, "import_module", fake_import_module)
        monkeypatch.setattr(adapters_module, "_REGISTRY", {})

        assert adapters_module.list_runtimes() == ["beta-runtime", "alpha-runtime"]
        assert imported_modules == []
        assert adapters_module.get_adapter("alpha-runtime").runtime_name == "alpha-runtime"
        assert imported_modules == ["gpd.adapters.alpha_adapter"]

    def test_loader_rejects_adapter_runtime_name_mismatch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        descriptor = RuntimeDescriptor(
            runtime_name="catalog-runtime",
            adapter_module="mismatch_adapter",
            display_name="Catalog Runtime",
            priority=10,
            config_dir_name=".catalog",
            install_flag="--catalog",
            launch_command="catalog",
            command_prefix="/gpd:",
            activation_env_vars=(),
            selection_flags=("--catalog",),
            selection_aliases=("catalog-runtime",),
            global_config=GlobalConfigPolicy(strategy="env_or_home", home_subpath=".catalog"),
            hook_payload=HookPayloadPolicy(),
        )

        class MismatchAdapter(RuntimeAdapter):
            pass

        MismatchAdapter.__module__ = "gpd.adapters.mismatch_adapter"
        MismatchAdapter.runtime_name = "other-runtime"

        _patch_catalog_descriptors(monkeypatch, (descriptor,))
        monkeypatch.setattr(adapters_module, "import_module", lambda name: SimpleNamespace(MismatchAdapter=MismatchAdapter))
        monkeypatch.setattr(adapters_module, "_REGISTRY", {})

        with pytest.raises(RuntimeError, match="Adapter runtime_name mismatch"):
            adapters_module.get_adapter("catalog-runtime")

    def test_list_runtimes_does_not_import_adapters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(adapters_module, "import_module", lambda name: pytest.fail(f"imported {name}"))
        monkeypatch.setattr(adapters_module, "_REGISTRY", {})

        assert adapters_module.list_runtimes() == list_runtime_names()

    def test_get_adapter_imports_declared_adapter_module_for_each_runtime(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        descriptors = tuple(iter_runtime_descriptors())
        expected_modules = {f"gpd.adapters.{descriptor.adapter_module}" for descriptor in descriptors}
        imported_modules: list[str] = []

        original_import = adapters_module.import_module

        def tracking_import(name: str) -> object:
            imported_modules.append(name)
            return original_import(name)

        monkeypatch.setattr(adapters_module, "import_module", tracking_import)
        monkeypatch.setattr(adapters_module, "_REGISTRY", {})

        for descriptor in descriptors:
            get_adapter(descriptor.runtime_name)

        assert expected_modules <= set(imported_modules)


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
