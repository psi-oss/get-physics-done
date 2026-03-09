"""Error path tests for the GPD bundle loading system.

Tests:
1. YAML parse errors — actions, skills, config (manifest covered in test_edge_cases)
2. Missing specs — empty/absent actors, actions, skills, config directories
3. Placeholder resolution failures — strict mode raises, non-strict leaves intact
4. Merge conflicts — actor prompt concatenation, action deep merge, skill union
5. Invalid schemas — bad field types, extra fields, non-dict YAML values
6. File not found — BundleNotFoundError, OSError on manifest read
7. Deep merge edge cases — nested dicts, list concatenation, type mismatches
8. BundleLoader state — get_* before load, singleton lifecycle, discovery
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd.strategy.bundle_loader import (
    ActionSpec,
    ActorSpec,
    Bundle,
    BundleLoader,
    BundleManifest,
    BundleManifestError,
    BundleNotFoundError,
    PlaceholderError,
    SkillEntry,
    _load_actions,
    _load_actors,
    _load_config,
    _load_skills,
    _load_yaml_dir,
    _load_yaml_file,
    _merge_action,
    _merge_actor,
    deep_merge,
    get_bundle_loader,
    init_bundle_loader,
    load_bundle,
    load_bundle_manifest,
    merge_bundles,
    reset_bundle_loader,
    resolve_placeholders,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    """Write text to path, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_bundle_dir(tmp_path: Path, name: str = "test") -> Path:
    """Create a minimal valid bundle directory."""
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _make_full_bundle(
    tmp_path: Path,
    name: str = "test",
    *,
    manifest: str | None = None,
    actors: dict[str, str] | None = None,
    actions: dict[str, str] | None = None,
    skills: dict[str, str] | None = None,
    config: str | None = None,
) -> Path:
    """Create a bundle directory with optional YAML content."""
    d = _make_bundle_dir(tmp_path, name)
    if manifest is not None:
        _write(d / "bundle.yaml", manifest)
    if actors:
        actors_dir = d / "actors"
        actors_dir.mkdir(exist_ok=True)
        for actor_name, yaml_text in actors.items():
            _write(actors_dir / f"{actor_name}.yaml", yaml_text)
    if actions:
        actions_dir = d / "actions"
        actions_dir.mkdir(exist_ok=True)
        for action_name, yaml_text in actions.items():
            _write(actions_dir / f"{action_name}.yaml", yaml_text)
    if skills:
        skills_dir = d / "skills"
        skills_dir.mkdir(exist_ok=True)
        for skill_name, yaml_text in skills.items():
            _write(skills_dir / f"{skill_name}.yaml", yaml_text)
    if config is not None:
        _write(d / "config" / "default.yaml", config)
    return d


# ===========================================================================
# 1. YAML Parse Errors
# ===========================================================================


class TestYAMLParseErrors:
    """Malformed YAML in various spec files should not crash the loader."""

    def test_malformed_action_yaml_skipped(self, tmp_path):
        """Invalid action YAML is silently skipped by _load_yaml_file."""
        d = _make_full_bundle(
            tmp_path,
            actions={"broken": ":::invalid yaml{{{"},
        )
        actions = _load_actions(d)
        assert "broken" not in actions

    def test_malformed_skill_yaml_creates_empty_entry(self, tmp_path):
        """Invalid skill YAML creates a skill entry with empty fields (name defaults to stem)."""
        d = _make_full_bundle(
            tmp_path,
            skills={"broken_skill": ":::not valid yaml{{{"},
        )
        skills = _load_skills(d)
        # _load_yaml_file returns {} for bad YAML, but _load_skills still creates
        # a SkillEntry with defaults (name=stem, description="")
        assert "broken_skill" in skills
        assert skills["broken_skill"].description == ""

    def test_malformed_config_yaml_returns_empty(self, tmp_path):
        """Invalid config YAML returns empty dict."""
        d = _make_full_bundle(tmp_path, config=":::bad yaml{{{")
        config = _load_config(d)
        assert config == {}

    def test_load_yaml_file_returns_empty_for_non_dict(self, tmp_path):
        """_load_yaml_file returns {} when YAML parses to a non-dict (e.g. list)."""
        path = tmp_path / "list.yaml"
        _write(path, "- item1\n- item2")
        assert _load_yaml_file(path) == {}

    def test_load_yaml_file_returns_empty_for_scalar(self, tmp_path):
        """_load_yaml_file returns {} when YAML parses to a scalar."""
        path = tmp_path / "scalar.yaml"
        _write(path, "just a string")
        assert _load_yaml_file(path) == {}

    def test_load_yaml_file_returns_empty_for_null(self, tmp_path):
        """_load_yaml_file returns {} for empty YAML."""
        path = tmp_path / "empty.yaml"
        _write(path, "")
        assert _load_yaml_file(path) == {}

    def test_load_yaml_dir_skips_malformed_files(self, tmp_path):
        """_load_yaml_dir skips files that fail to parse and returns the rest."""
        d = tmp_path / "yamls"
        d.mkdir()
        _write(d / "good.yaml", "key: value")
        _write(d / "bad.yaml", ":::broken{{{")
        _write(d / "also_good.yml", "other: data")
        result = _load_yaml_dir(d)
        assert "good" in result
        assert "also_good" in result
        assert "bad" not in result

    def test_load_yaml_dir_nonexistent_returns_empty(self, tmp_path):
        """_load_yaml_dir on a nonexistent directory returns empty dict."""
        result = _load_yaml_dir(tmp_path / "nope")
        assert result == {}


# ===========================================================================
# 2. Missing Specs
# ===========================================================================


class TestMissingSpecs:
    """Loading from directories with missing subdirectories/files."""

    def test_no_actors_dir_or_file(self, tmp_path):
        """Bundle with no actors/ dir and no actors.yaml returns empty actors."""
        d = _make_bundle_dir(tmp_path)
        actors = _load_actors(d)
        assert actors == {}

    def test_no_actions_dir_or_file(self, tmp_path):
        """Bundle with no actions/ dir and no actions.yaml returns empty actions."""
        d = _make_bundle_dir(tmp_path)
        actions = _load_actions(d)
        assert actions == {}

    def test_no_skills_dir(self, tmp_path):
        """Bundle with no skills/ dir returns empty skills."""
        d = _make_bundle_dir(tmp_path)
        skills = _load_skills(d)
        assert skills == {}

    def test_no_config_dir(self, tmp_path):
        """Bundle with no config/ dir returns empty config."""
        d = _make_bundle_dir(tmp_path)
        config = _load_config(d)
        assert config == {}

    def test_empty_actors_dir(self, tmp_path):
        """Empty actors/ directory returns empty dict."""
        d = _make_bundle_dir(tmp_path)
        (d / "actors").mkdir()
        actors = _load_actors(d)
        assert actors == {}

    def test_empty_actions_dir(self, tmp_path):
        """Empty actions/ directory returns empty dict."""
        d = _make_bundle_dir(tmp_path)
        (d / "actions").mkdir()
        actions = _load_actions(d)
        assert actions == {}

    def test_empty_skills_dir(self, tmp_path):
        """Empty skills/ directory returns empty dict."""
        d = _make_bundle_dir(tmp_path)
        (d / "skills").mkdir()
        skills = _load_skills(d)
        assert skills == {}

    def test_load_bundle_no_manifest_uses_default(self, tmp_path):
        """Bundle dir without bundle.yaml gets a default manifest."""
        d = _make_bundle_dir(tmp_path, "my_bundle")
        bundle = load_bundle(d)
        assert bundle.manifest.name == "my_bundle"
        assert bundle.manifest.version == "0.0.0"

    def test_load_bundle_completely_empty_dir(self, tmp_path):
        """Completely empty bundle directory loads as empty bundle."""
        d = _make_bundle_dir(tmp_path)
        bundle = load_bundle(d)
        assert bundle.actors == {}
        assert bundle.actions == {}
        assert bundle.skills == {}
        assert bundle.config == {}


# ===========================================================================
# 3. Placeholder Resolution Failures
# ===========================================================================


class TestPlaceholderResolution:
    """resolve_placeholders strict/non-strict modes and edge cases."""

    def test_strict_mode_raises_for_known_placeholder(self):
        """Strict mode raises PlaceholderError for unresolved known placeholders."""
        with pytest.raises(PlaceholderError, match="skills_index"):
            resolve_placeholders("Use {skills_index} here", {}, strict=True)

    def test_strict_mode_raises_for_each_known_placeholder(self):
        """Each known placeholder triggers PlaceholderError in strict mode."""
        from gpd.strategy.bundle_loader import KNOWN_PLACEHOLDERS

        for placeholder in sorted(KNOWN_PLACEHOLDERS):
            with pytest.raises(PlaceholderError, match=placeholder):
                resolve_placeholders(f"{{{placeholder}}}", {}, strict=True)

    def test_strict_mode_ignores_unknown_placeholders(self):
        """Strict mode leaves unknown placeholders untouched (no error)."""
        result = resolve_placeholders("{custom_thing}", {}, strict=True)
        assert result == "{custom_thing}"

    def test_non_strict_mode_leaves_unresolved(self):
        """Non-strict mode leaves all unresolved placeholders in place."""
        result = resolve_placeholders("Hello {skills_index} and {unknown}", {})
        assert result == "Hello {skills_index} and {unknown}"

    def test_resolved_placeholders_are_substituted(self):
        """Resolved placeholders are correctly replaced."""
        ctx = {"skills_index": "- skill_a\n- skill_b", "custom_thing": "hello"}
        result = resolve_placeholders("{skills_index} {custom_thing} {unknown}", ctx)
        assert "- skill_a" in result
        assert "hello" in result
        assert "{unknown}" in result

    def test_empty_text_returns_empty(self):
        """Empty input returns empty output."""
        assert resolve_placeholders("", {}) == ""

    def test_no_placeholders_returns_unchanged(self):
        """Text without placeholders is returned unchanged."""
        text = "No placeholders here, just {braces in backtick `{x}`} context."
        # Note: the regex matches {x} even inside backticks — this is expected behavior
        result = resolve_placeholders(text, {"x": "replaced"})
        assert "replaced" in result

    def test_placeholder_error_has_placeholder_attr(self):
        """PlaceholderError stores the placeholder name."""
        try:
            resolve_placeholders("{skills_index}", {}, strict=True)
        except PlaceholderError as e:
            assert e.placeholder == "skills_index"

    def test_partial_context_resolves_only_provided(self):
        """Only placeholders in context are resolved; others remain."""
        ctx = {"skills_index": "SKILLS"}
        result = resolve_placeholders("{skills_index} {error_awareness}", ctx, strict=False)
        assert result == "SKILLS {error_awareness}"


# ===========================================================================
# 4. Merge Conflicts
# ===========================================================================


class TestMergeConflicts:
    """Actor and action merging with overlapping fields."""

    def test_merge_actor_system_prompt_concatenation(self):
        """Overlay system prompt is appended after the separator."""
        base = ActorSpec(actor_id="r", system="Base system prompt.")
        overlay = ActorSpec(actor_id="r", system="Physics extension.")
        merged = _merge_actor(base, overlay)
        assert "Base system prompt." in merged.system
        assert "Physics extension." in merged.system
        assert "## Physics Extensions" in merged.system

    def test_merge_actor_overlay_empty_system(self):
        """Empty overlay system prompt leaves base system unchanged."""
        base = ActorSpec(actor_id="r", system="Base only.")
        overlay = ActorSpec(actor_id="r", system="")
        merged = _merge_actor(base, overlay)
        assert merged.system == "Base only."

    def test_merge_actor_base_empty_system(self):
        """Empty base system prompt uses overlay system directly."""
        base = ActorSpec(actor_id="r", system="")
        overlay = ActorSpec(actor_id="r", system="Overlay only.")
        merged = _merge_actor(base, overlay)
        assert merged.system == "Overlay only."

    def test_merge_actor_schema_version_takes_higher(self):
        """Merged schema_version is max of base and overlay."""
        base = ActorSpec(actor_id="r", schema_version=2)
        overlay = ActorSpec(actor_id="r", schema_version=5)
        merged = _merge_actor(base, overlay)
        assert merged.schema_version == 5

        base2 = ActorSpec(actor_id="r", schema_version=7)
        overlay2 = ActorSpec(actor_id="r", schema_version=3)
        merged2 = _merge_actor(base2, overlay2)
        assert merged2.schema_version == 7

    def test_merge_actor_overlay_string_fields_win(self):
        """Non-empty overlay string fields override base."""
        base = ActorSpec(actor_id="r", description="Base desc", model_id="model-a")
        overlay = ActorSpec(actor_id="r", description="Overlay desc", model_id="")
        merged = _merge_actor(base, overlay)
        assert merged.description == "Overlay desc"
        assert merged.model_id == "model-a"  # Empty overlay doesn't clobber

    def test_merge_actor_audit_spec_deep_merged(self):
        """audit_spec dict fields are deep-merged."""
        base = ActorSpec(actor_id="r", audit_spec={"check_a": True, "nested": {"x": 1}})
        overlay = ActorSpec(actor_id="r", audit_spec={"check_b": True, "nested": {"y": 2}})
        merged = _merge_actor(base, overlay)
        assert merged.audit_spec["check_a"] is True
        assert merged.audit_spec["check_b"] is True
        assert merged.audit_spec["nested"] == {"x": 1, "y": 2}

    def test_merge_action_deep_merge(self):
        """Action merge deep-merges dict fields."""
        base = ActionSpec(
            action_id="work",
            write_set={"path_a": "rw"},
            parameters={"param1": "val1"},
        )
        overlay = ActionSpec(
            action_id="work",
            write_set={"path_b": "r"},
            parameters={"param2": "val2"},
        )
        merged = _merge_action(base, overlay)
        assert merged.write_set["path_a"] == "rw"
        assert merged.write_set["path_b"] == "r"
        assert merged.parameters["param1"] == "val1"
        assert merged.parameters["param2"] == "val2"

    def test_merge_action_overlay_title_wins(self):
        """Non-default overlay title overrides base."""
        base = ActionSpec(action_id="a", title="Base Title")
        overlay = ActionSpec(action_id="a", title="Overlay Title")
        merged = _merge_action(base, overlay)
        assert merged.title == "Overlay Title"

    def test_merge_action_empty_overlay_preserves_base(self):
        """Empty overlay fields don't clobber base values."""
        base = ActionSpec(action_id="a", title="Base Title", summary="Base Summary")
        overlay = ActionSpec(action_id="a")  # All defaults
        merged = _merge_action(base, overlay)
        assert merged.title == "Base Title"
        assert merged.summary == "Base Summary"

    def test_merge_bundles_actor_only_in_base(self, tmp_path):
        """Actor in base but not overlay passes through unchanged."""
        base = Bundle(
            manifest=BundleManifest(name="base"),
            actors={"solver": ActorSpec(actor_id="solver", system="Solve things.")},
        )
        overlay = Bundle(
            manifest=BundleManifest(name="physics"),
            actors={},
        )
        merged = merge_bundles(base, overlay)
        assert "solver" in merged.actors
        assert merged.actors["solver"].system == "Solve things."

    def test_merge_bundles_actor_only_in_overlay(self):
        """Actor in overlay but not base is added."""
        base = Bundle(manifest=BundleManifest(name="base"))
        overlay = Bundle(
            manifest=BundleManifest(name="physics"),
            actors={"physics_expert": ActorSpec(actor_id="physics_expert", system="Physics!")},
        )
        merged = merge_bundles(base, overlay)
        assert "physics_expert" in merged.actors

    def test_merge_bundles_skills_union(self):
        """Skills are unioned — overlay additions appear alongside base."""
        base = Bundle(
            manifest=BundleManifest(name="base"),
            skills={"calc": SkillEntry(name="calc", description="Calculator")},
        )
        overlay = Bundle(
            manifest=BundleManifest(name="physics"),
            skills={"sympy": SkillEntry(name="sympy", description="SymPy CAS")},
        )
        merged = merge_bundles(base, overlay)
        assert "calc" in merged.skills
        assert "sympy" in merged.skills

    def test_merge_bundles_skill_overlay_overrides_base(self):
        """Overlay skill with same name overrides base skill."""
        base = Bundle(
            manifest=BundleManifest(name="base"),
            skills={"calc": SkillEntry(name="calc", description="Basic calc")},
        )
        overlay = Bundle(
            manifest=BundleManifest(name="physics"),
            skills={"calc": SkillEntry(name="calc", description="Physics-aware calc")},
        )
        merged = merge_bundles(base, overlay)
        assert merged.skills["calc"].description == "Physics-aware calc"

    def test_merge_bundles_config_overlay_overrides(self):
        """Config values from overlay override base values."""
        base = Bundle(
            manifest=BundleManifest(name="base"),
            config={"budget": 100, "model": "gpt-4o"},
        )
        overlay = Bundle(
            manifest=BundleManifest(name="physics"),
            config={"budget": 200, "physics_mode": True},
        )
        merged = merge_bundles(base, overlay)
        assert merged.config["budget"] == 200
        assert merged.config["model"] == "gpt-4o"
        assert merged.config["physics_mode"] is True


# ===========================================================================
# 5. Invalid Schemas / Bad Data
# ===========================================================================


class TestInvalidSchemas:
    """Loading specs with wrong types or unexpected structures."""

    def test_actors_yaml_with_non_dict_actor_entries(self, tmp_path):
        """actors.yaml where actor entries are strings (not dicts) are skipped."""
        d = _make_bundle_dir(tmp_path)
        _write(d / "actors.yaml", "actors:\n  bad_actor: just_a_string\n  good_actor:\n    system: hi\n")
        actors = _load_actors(d)
        # bad_actor is a string, not a dict — should be skipped
        assert "bad_actor" not in actors
        assert "good_actor" in actors

    def test_actions_yaml_with_non_dict_action_entries(self, tmp_path):
        """actions.yaml where action entries are not dicts are skipped."""
        d = _make_bundle_dir(tmp_path)
        _write(d / "actions.yaml", "actions:\n  bad_action: 42\n  good_action:\n    title: Do stuff\n")
        actions = _load_actions(d)
        assert "bad_action" not in actions
        assert "good_action" in actions

    def test_actors_yaml_single_format_with_prompt_id(self, tmp_path):
        """actors.yaml with prompt_id field loads as single actor."""
        d = _make_bundle_dir(tmp_path)
        _write(d / "actors.yaml", "prompt_id: my_actor\nsystem: Hello world\n")
        actors = _load_actors(d)
        assert "my_actor" in actors
        assert actors["my_actor"].system == "Hello world"

    def test_actions_yaml_single_format_with_action_id(self, tmp_path):
        """actions.yaml with action_id field loads as single action."""
        d = _make_bundle_dir(tmp_path)
        _write(d / "actions.yaml", "action_id: my_action\ntitle: Do thing\n")
        actions = _load_actions(d)
        assert "my_action" in actions
        assert actions["my_action"].title == "Do thing"

    def test_actor_dir_overrides_single_file(self, tmp_path):
        """actors/ directory takes precedence over actors.yaml for same IDs."""
        d = _make_bundle_dir(tmp_path)
        _write(d / "actors.yaml", "actors:\n  solver:\n    system: From file\n")
        actors_dir = d / "actors"
        actors_dir.mkdir()
        _write(actors_dir / "solver.yaml", "system: From directory\n")
        actors = _load_actors(d)
        assert actors["solver"].system == "From directory"

    def test_skills_markdown_file_loaded(self, tmp_path):
        """Markdown skill files extract description from first non-heading line."""
        d = _make_bundle_dir(tmp_path)
        skills_dir = d / "skills"
        skills_dir.mkdir()
        _write(skills_dir / "my_skill.md", "# My Skill\n\nThis skill does things.\n\nMore details.")
        skills = _load_skills(d)
        assert "my_skill" in skills
        assert skills["my_skill"].description == "This skill does things."

    def test_skills_non_yaml_non_md_ignored(self, tmp_path):
        """Non-YAML, non-Markdown files in skills/ are ignored."""
        d = _make_bundle_dir(tmp_path)
        skills_dir = d / "skills"
        skills_dir.mkdir()
        _write(skills_dir / "readme.txt", "Not a skill.")
        _write(skills_dir / "tool.py", "print('hello')")
        skills = _load_skills(d)
        assert skills == {}

    def test_skills_subdirectories_ignored(self, tmp_path):
        """Subdirectories within skills/ are ignored."""
        d = _make_bundle_dir(tmp_path)
        skills_dir = d / "skills"
        skills_dir.mkdir()
        sub = skills_dir / "subdir"
        sub.mkdir()
        _write(sub / "nested.yaml", "name: nested\ndescription: Should be ignored")
        skills = _load_skills(d)
        assert skills == {}


# ===========================================================================
# 6. File Not Found / Read Errors
# ===========================================================================


class TestFileNotFound:
    """File system errors during loading."""

    def test_load_bundle_nonexistent_raises(self, tmp_path):
        """load_bundle on nonexistent path raises BundleNotFoundError."""
        with pytest.raises(BundleNotFoundError) as exc_info:
            load_bundle(tmp_path / "does_not_exist")
        assert exc_info.value.bundle_dir == tmp_path / "does_not_exist"

    def test_load_bundle_file_not_dir_raises(self, tmp_path):
        """load_bundle on a file (not dir) raises BundleNotFoundError."""
        f = tmp_path / "not_a_dir.yaml"
        f.write_text("key: val")
        with pytest.raises(BundleNotFoundError):
            load_bundle(f)

    def test_load_yaml_file_nonexistent(self, tmp_path):
        """_load_yaml_file on nonexistent path returns {}."""
        assert _load_yaml_file(tmp_path / "nope.yaml") == {}

    def test_manifest_os_error(self, tmp_path):
        """OSError reading bundle.yaml raises BundleManifestError."""
        d = _make_bundle_dir(tmp_path)
        manifest = d / "bundle.yaml"
        manifest.mkdir()  # Create a dir where a file is expected — triggers OSError
        with pytest.raises(BundleManifestError, match="Read error"):
            load_bundle_manifest(d)

    def test_bundle_not_found_error_message(self, tmp_path):
        """BundleNotFoundError message includes the path."""
        path = tmp_path / "missing"
        err = BundleNotFoundError(path)
        assert str(path) in str(err)

    def test_bundle_manifest_error_message(self, tmp_path):
        """BundleManifestError message includes dir and reason."""
        err = BundleManifestError(tmp_path, "test reason")
        assert str(tmp_path) in str(err)
        assert "test reason" in str(err)


# ===========================================================================
# 7. Deep Merge Edge Cases
# ===========================================================================


class TestDeepMerge:
    """Edge cases for the deep_merge utility."""

    def test_empty_base(self):
        assert deep_merge({}, {"a": 1}) == {"a": 1}

    def test_empty_overlay(self):
        assert deep_merge({"a": 1}, {}) == {"a": 1}

    def test_both_empty(self):
        assert deep_merge({}, {}) == {}

    def test_nested_dict_merge(self):
        base = {"a": {"x": 1, "y": 2}}
        overlay = {"a": {"y": 3, "z": 4}}
        result = deep_merge(base, overlay)
        assert result == {"a": {"x": 1, "y": 3, "z": 4}}

    def test_list_concatenation(self):
        base = {"items": [1, 2]}
        overlay = {"items": [3, 4]}
        result = deep_merge(base, overlay)
        assert result == {"items": [1, 2, 3, 4]}

    def test_type_mismatch_overlay_wins(self):
        """When types differ (e.g. dict vs string), overlay wins."""
        base = {"a": "string"}
        overlay = {"a": {"nested": True}}
        result = deep_merge(base, overlay)
        assert result == {"a": {"nested": True}}

    def test_type_mismatch_scalar_over_dict(self):
        """Scalar overlay replaces dict base."""
        base = {"a": {"nested": True}}
        overlay = {"a": "replaced"}
        result = deep_merge(base, overlay)
        assert result == {"a": "replaced"}

    def test_deeply_nested(self):
        """Three levels deep merge."""
        base = {"a": {"b": {"c": 1, "d": 2}}}
        overlay = {"a": {"b": {"d": 3, "e": 4}}}
        result = deep_merge(base, overlay)
        assert result == {"a": {"b": {"c": 1, "d": 3, "e": 4}}}

    def test_does_not_mutate_inputs(self):
        """deep_merge should not modify its input dicts."""
        base = {"a": {"x": 1}, "items": [1]}
        overlay = {"a": {"y": 2}, "items": [2]}
        base_copy = {"a": {"x": 1}, "items": [1]}
        overlay_copy = {"a": {"y": 2}, "items": [2]}
        deep_merge(base, overlay)
        assert base == base_copy
        assert overlay == overlay_copy


# ===========================================================================
# 8. BundleLoader State
# ===========================================================================


class TestBundleLoaderState:
    """BundleLoader before load, after load, and singleton lifecycle."""

    def test_not_loaded_initially(self, tmp_path):
        loader = BundleLoader(specs_dir=tmp_path)
        assert not loader.is_loaded
        assert loader.merged is None

    def test_get_actor_prompt_before_load(self, tmp_path):
        loader = BundleLoader(specs_dir=tmp_path)
        assert loader.get_actor_prompt("anything") is None

    def test_get_actor_spec_before_load(self, tmp_path):
        loader = BundleLoader(specs_dir=tmp_path)
        assert loader.get_actor_spec("anything") is None

    def test_get_action_spec_before_load(self, tmp_path):
        loader = BundleLoader(specs_dir=tmp_path)
        assert loader.get_action_spec("anything") is None

    def test_get_action_spec_dict_before_load(self, tmp_path):
        loader = BundleLoader(specs_dir=tmp_path)
        assert loader.get_action_spec_dict("anything") is None

    def test_get_skills_index_before_load(self, tmp_path):
        loader = BundleLoader(specs_dir=tmp_path)
        assert loader.get_skills_index() == ""

    def test_get_actor_ids_before_load(self, tmp_path):
        loader = BundleLoader(specs_dir=tmp_path)
        assert loader.get_actor_ids() == []

    def test_get_action_ids_before_load(self, tmp_path):
        loader = BundleLoader(specs_dir=tmp_path)
        assert loader.get_action_ids() == []

    def test_get_skill_names_before_load(self, tmp_path):
        loader = BundleLoader(specs_dir=tmp_path)
        assert loader.get_skill_names() == []

    def test_get_bundle_dirs_before_load(self, tmp_path):
        loader = BundleLoader(specs_dir=tmp_path)
        assert loader.get_bundle_dirs() == []

    def test_load_sets_is_loaded(self, tmp_path):
        _make_bundle_dir(tmp_path, "base")
        loader = BundleLoader(specs_dir=tmp_path)
        loader.load(base_name="base")
        assert loader.is_loaded
        assert loader.merged is not None

    def test_get_actor_prompt_nonexistent_actor(self, tmp_path):
        """After load, requesting a non-existent actor returns None."""
        _make_bundle_dir(tmp_path, "base")
        loader = BundleLoader(specs_dir=tmp_path)
        loader.load(base_name="base")
        assert loader.get_actor_prompt("nonexistent") is None

    def test_get_action_spec_nonexistent_action(self, tmp_path):
        _make_bundle_dir(tmp_path, "base")
        loader = BundleLoader(specs_dir=tmp_path)
        loader.load(base_name="base")
        assert loader.get_action_spec("nonexistent") is None

    def test_get_action_spec_dict_nonexistent(self, tmp_path):
        _make_bundle_dir(tmp_path, "base")
        loader = BundleLoader(specs_dir=tmp_path)
        loader.load(base_name="base")
        assert loader.get_action_spec_dict("nonexistent") is None


class TestBundleLoaderWithContent:
    """BundleLoader end-to-end with actual spec content."""

    def test_load_with_actors_and_actions(self, tmp_path):
        _make_full_bundle(
            tmp_path,
            "base",
            manifest="name: base\nversion: '1.0.0'\n",
            actors={"solver": "system: Solve the problem.\ndescription: Main solver\n"},
            actions={"work": "title: Do work\nsummary: Execute work step\n"},
        )
        loader = BundleLoader(specs_dir=tmp_path)
        result = loader.load(base_name="base")
        assert "solver" in result.actors
        assert result.actors["solver"].system == "Solve the problem."
        assert "work" in result.actions
        assert result.actions["work"].title == "Do work"

    def test_load_with_overlay(self, tmp_path):
        _make_full_bundle(
            tmp_path,
            "base",
            actors={"solver": "system: Base solver.\n"},
        )
        _make_full_bundle(
            tmp_path,
            "physics",
            actors={"solver": "system: Physics extension.\n"},
        )
        loader = BundleLoader(specs_dir=tmp_path)
        result = loader.load(base_name="base", overlay_names=["physics"])
        assert "Physics extension." in result.actors["solver"].system
        assert "Base solver." in result.actors["solver"].system

    def test_get_actor_prompt_with_context(self, tmp_path):
        _make_full_bundle(
            tmp_path,
            "base",
            actors={"solver": "system: Use {skills_index} for tools.\n"},
        )
        loader = BundleLoader(specs_dir=tmp_path)
        loader.load(base_name="base")
        prompt = loader.get_actor_prompt("solver", {"skills_index": "- calc\n- sympy"})
        assert "- calc" in prompt
        assert "- sympy" in prompt
        assert "{skills_index}" not in prompt

    def test_get_skills_index_formatted(self, tmp_path):
        _make_full_bundle(
            tmp_path,
            "base",
            skills={
                "calc": "name: Calculator\ndescription: Basic math\n",
                "sympy": "name: SymPy\ndescription: Computer algebra\n",
            },
        )
        loader = BundleLoader(specs_dir=tmp_path)
        loader.load(base_name="base")
        index = loader.get_skills_index()
        assert "Calculator" in index
        assert "SymPy" in index

    def test_get_action_spec_dict_returns_dict(self, tmp_path):
        _make_full_bundle(
            tmp_path,
            "base",
            actions={"work": "title: Do work\nsummary: Execute\n"},
        )
        loader = BundleLoader(specs_dir=tmp_path)
        loader.load(base_name="base")
        d = loader.get_action_spec_dict("work")
        assert isinstance(d, dict)
        assert d["title"] == "Do work"

    def test_build_context(self, tmp_path):
        _make_full_bundle(
            tmp_path,
            "base",
            skills={"calc": "name: calc\ndescription: Math\n"},
        )
        loader = BundleLoader(specs_dir=tmp_path)
        loader.load(base_name="base")
        ctx = loader.build_context(
            convention_context="Use SI units",
            error_awareness="Watch for sign errors",
            extra={"custom_key": "custom_val"},
        )
        assert "calc" in ctx["skills_index"]
        assert ctx["convention_context"] == "Use SI units"
        assert ctx["error_awareness"] == "Watch for sign errors"
        assert ctx["custom_key"] == "custom_val"

    def test_list_available_bundles(self, tmp_path):
        _make_full_bundle(tmp_path, "base", manifest="name: base\n")
        _make_full_bundle(tmp_path, "physics", manifest="name: physics\ndomain: physics\n")
        loader = BundleLoader(specs_dir=tmp_path)
        manifests = loader.list_available_bundles()
        names = [m.name for m in manifests]
        assert "base" in names
        assert "physics" in names

    def test_list_available_bundles_empty_dir(self, tmp_path):
        loader = BundleLoader(specs_dir=tmp_path)
        assert loader.list_available_bundles() == []

    def test_list_available_bundles_nonexistent_dir(self, tmp_path):
        loader = BundleLoader(specs_dir=tmp_path / "nope")
        assert loader.list_available_bundles() == []

    def test_get_bundle_dirs_after_load(self, tmp_path):
        _make_full_bundle(tmp_path, "base")
        _make_full_bundle(tmp_path, "physics")
        loader = BundleLoader(specs_dir=tmp_path)
        loader.load(base_name="base", overlay_names=["physics"])
        dirs = loader.get_bundle_dirs()
        assert len(dirs) == 2
        assert dirs[0].name == "base"
        assert dirs[1].name == "physics"


# ===========================================================================
# 9. Singleton Lifecycle
# ===========================================================================


class TestSingleton:
    """Module-level singleton init/get/reset."""

    def setup_method(self):
        reset_bundle_loader()

    def teardown_method(self):
        reset_bundle_loader()

    def test_get_before_init_returns_none(self):
        assert get_bundle_loader() is None

    def test_init_returns_loader(self, tmp_path):
        _make_bundle_dir(tmp_path, "base")
        loader = init_bundle_loader(specs_dir=tmp_path, base_name="base")
        assert loader is not None
        assert loader.is_loaded

    def test_get_after_init_returns_same(self, tmp_path):
        _make_bundle_dir(tmp_path, "base")
        loader = init_bundle_loader(specs_dir=tmp_path, base_name="base")
        assert get_bundle_loader() is loader

    def test_reset_clears_singleton(self, tmp_path):
        _make_bundle_dir(tmp_path, "base")
        init_bundle_loader(specs_dir=tmp_path, base_name="base")
        reset_bundle_loader()
        assert get_bundle_loader() is None

    def test_init_with_overlays(self, tmp_path):
        _make_full_bundle(tmp_path, "base")
        _make_full_bundle(tmp_path, "physics")
        loader = init_bundle_loader(
            specs_dir=tmp_path,
            base_name="base",
            overlay_names=["physics"],
        )
        assert loader.is_loaded
        assert len(loader.merged.overlay_manifests) == 1


# ===========================================================================
# 10. Skills edge cases
# ===========================================================================


class TestSkillsEdgeCases:
    """Edge cases for skill loading."""

    def test_markdown_skill_heading_only(self, tmp_path):
        """Markdown with only headings gets empty description."""
        d = _make_bundle_dir(tmp_path)
        skills_dir = d / "skills"
        skills_dir.mkdir()
        _write(skills_dir / "empty_skill.md", "# Title\n## Subtitle\n---\n")
        skills = _load_skills(d)
        assert "empty_skill" in skills
        assert skills["empty_skill"].description == ""

    def test_yaml_skill_with_domain(self, tmp_path):
        """YAML skill with domain field is captured."""
        d = _make_bundle_dir(tmp_path)
        skills_dir = d / "skills"
        skills_dir.mkdir()
        _write(skills_dir / "phys.yaml", "name: Physics Tool\ndescription: Physics stuff\ndomain: physics\n")
        skills = _load_skills(d)
        assert skills["phys"].domain == "physics"

    def test_multiple_skill_types_mixed(self, tmp_path):
        """Mix of .yaml, .yml, and .md skill files all load."""
        d = _make_bundle_dir(tmp_path)
        skills_dir = d / "skills"
        skills_dir.mkdir()
        _write(skills_dir / "a.yaml", "name: a\ndescription: A\n")
        _write(skills_dir / "b.yml", "name: b\ndescription: B\n")
        _write(skills_dir / "c.md", "# C\n\nC skill description.")
        skills = _load_skills(d)
        assert len(skills) == 3
        assert skills["a"].name == "a"
        assert skills["b"].name == "b"
        assert skills["c"].description == "C skill description."
