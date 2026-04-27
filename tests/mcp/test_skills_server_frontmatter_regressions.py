"""Assertions for malformed frontmatter in skill-referenced docs."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from gpd.registry import CommandDef, SkillDef


def test_get_skill_surfaces_malformed_reference_frontmatter(tmp_path: Path) -> None:
    from gpd.mcp.servers import skills_server

    reference_path = tmp_path / "peer-review-panel.md"
    reference_path.write_text(
        "---\ntype: peer-review-panel-protocol: [broken\n---\n# Peer Review Panel\nBody.\n",
        encoding="utf-8",
    )

    command = CommandDef(
        name="gpd:peer-review",
        description="Review.",
        argument_hint="",
        requires={},
        allowed_tools=["file_read"],
        content="Command body.",
        path=str(tmp_path / "gpd-peer-review.md"),
        source="commands",
    )
    skill = SkillDef(
        name="gpd-peer-review",
        description="Review.",
        content="See @{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md\n",
        category="review",
        path=str(tmp_path / "gpd-peer-review.md"),
        source_kind="command",
        registry_name="peer-review",
    )

    original_portable_reference_path = skills_server._portable_reference_path

    def _patched_portable_reference_path(raw_path: str, *, base_path: Path | None = None):
        if raw_path == "@{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md":
            return raw_path, reference_path
        return original_portable_reference_path(raw_path, base_path=base_path)

    skills_server._reference_document_metadata.cache_clear()
    try:
        with (
            patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
            patch("gpd.mcp.servers.skills_server.content_registry.get_command", return_value=command),
            patch(
                "gpd.mcp.servers.skills_server._portable_reference_path", side_effect=_patched_portable_reference_path
            ),
        ):
            result = skills_server.get_skill("gpd-peer-review")
    finally:
        skills_server._reference_document_metadata.cache_clear()

    contract_documents = {Path(entry["path"]).name: entry for entry in result["contract_documents"]}

    assert "peer-review-panel.md" in contract_documents
    assert contract_documents["peer-review-panel.md"]["kind"] == "reference"
    assert "content" not in contract_documents["peer-review-panel.md"]
    assert "# Peer Review Panel" in contract_documents["peer-review-panel.md"]["body"]
    assert "frontmatter_error" in contract_documents["peer-review-panel.md"]
    assert contract_documents["peer-review-panel.md"]["frontmatter_error"]


def test_get_skill_transitive_schema_documents_are_metadata_only_by_default(tmp_path: Path) -> None:
    from gpd.mcp.servers import skills_server

    workflow_path = tmp_path / "wrapper.md"
    workflow_path.write_text(
        "See @{GPD_INSTALL_DIR}/templates/nested-schema.md for the schema.\n",
        encoding="utf-8",
    )
    schema_path = tmp_path / "nested-schema.md"
    schema_path.write_text(
        "---\ntype: schema\n---\n# Nested Schema\nTransitive body.\n",
        encoding="utf-8",
    )

    command = CommandDef(
        name="gpd:debug",
        description="Debug.",
        argument_hint="",
        requires={},
        allowed_tools=["file_read"],
        content="Command body.",
        path=str(tmp_path / "gpd-debug.md"),
        source="commands",
    )
    skill = SkillDef(
        name="gpd-debug",
        description="Debug.",
        content="Read @{GPD_INSTALL_DIR}/workflows/wrapper.md first.\n",
        category="debugging",
        path=str(tmp_path / "gpd-debug.md"),
        source_kind="command",
        registry_name="debug",
    )

    portable_paths = {
        "@{GPD_INSTALL_DIR}/workflows/wrapper.md": workflow_path,
        "@{GPD_INSTALL_DIR}/templates/nested-schema.md": schema_path,
    }
    original_portable_reference_path = skills_server._portable_reference_path

    def _patched_portable_reference_path(raw_path: str, *, base_path: Path | None = None):
        if raw_path in portable_paths:
            return raw_path, portable_paths[raw_path]
        return original_portable_reference_path(raw_path, base_path=base_path)

    skills_server._reference_document_metadata.cache_clear()
    try:
        with (
            patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
            patch("gpd.mcp.servers.skills_server.content_registry.get_command", return_value=command),
            patch(
                "gpd.mcp.servers.skills_server._portable_reference_path", side_effect=_patched_portable_reference_path
            ),
        ):
            result = skills_server.get_skill("gpd-debug")
            opt_in_result = skills_server.get_skill("gpd-debug", include_transitive_reference_bodies=True)
    finally:
        skills_server._reference_document_metadata.cache_clear()

    assert result["schema_documents"] == []
    assert any(path.endswith("nested-schema.md") for path in result["transitive_schema_references"])
    assert any(entry["name"] == "nested-schema.md" for entry in result["transitive_schema_documents"])
    nested_doc = next(entry for entry in result["transitive_schema_documents"] if entry["name"] == "nested-schema.md")
    assert "content" not in nested_doc
    assert nested_doc["frontmatter"] == {"type": "schema"}
    assert "body" not in nested_doc
    assert "transitive_schema_documents" not in result["loading_hint"]
    assert "metadata-only by default" in result["loading_hint"]
    assert "include_transitive_reference_bodies=true" in result["loading_hint"]
    assert "See `referenced_files` for external markdown dependencies." in result["loading_hint"]

    opt_in_nested_doc = next(
        entry for entry in opt_in_result["transitive_schema_documents"] if entry["name"] == "nested-schema.md"
    )
    assert opt_in_nested_doc["frontmatter"] == {"type": "schema"}
    assert "# Nested Schema" in opt_in_nested_doc["body"]
    assert "metadata-only by default" not in opt_in_result["loading_hint"]


def test_get_skill_default_payload_budget_excludes_transitive_reference_bodies(tmp_path: Path) -> None:
    from gpd.mcp.servers import skills_server

    workflow_path = tmp_path / "wrapper.md"
    workflow_path.write_text(
        "See @{GPD_INSTALL_DIR}/templates/large-schema.md for the schema.\n" + ("workflow detail\n" * 2000),
        encoding="utf-8",
    )
    schema_path = tmp_path / "large-schema.md"
    schema_body = "# Large Schema\n" + ("transitive schema body that should not ship by default\n" * 2500)
    schema_path.write_text(
        f"---\ntype: schema\n---\n{schema_body}",
        encoding="utf-8",
    )

    command = CommandDef(
        name="gpd:debug",
        description="Debug.",
        argument_hint="",
        requires={},
        allowed_tools=["file_read"],
        content="Command body.",
        path=str(tmp_path / "gpd-debug.md"),
        source="commands",
    )
    skill = SkillDef(
        name="gpd-debug",
        description="Debug.",
        content="Read @{GPD_INSTALL_DIR}/workflows/wrapper.md first.\n",
        category="debugging",
        path=str(tmp_path / "gpd-debug.md"),
        source_kind="command",
        registry_name="debug",
    )

    portable_paths = {
        "@{GPD_INSTALL_DIR}/workflows/wrapper.md": workflow_path,
        "@{GPD_INSTALL_DIR}/templates/large-schema.md": schema_path,
    }
    original_portable_reference_path = skills_server._portable_reference_path

    def _patched_portable_reference_path(raw_path: str, *, base_path: Path | None = None):
        if raw_path in portable_paths:
            return raw_path, portable_paths[raw_path]
        return original_portable_reference_path(raw_path, base_path=base_path)

    skills_server._reference_document_metadata.cache_clear()
    try:
        with (
            patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
            patch("gpd.mcp.servers.skills_server.content_registry.get_command", return_value=command),
            patch(
                "gpd.mcp.servers.skills_server._portable_reference_path", side_effect=_patched_portable_reference_path
            ),
        ):
            default_result = skills_server.get_skill("gpd-debug")
            opt_in_result = skills_server.get_skill("gpd-debug", include_transitive_reference_bodies=True)
    finally:
        skills_server._reference_document_metadata.cache_clear()

    default_payload = json.dumps(default_result)
    opt_in_payload = json.dumps(opt_in_result)
    default_doc = next(
        entry for entry in default_result["transitive_schema_documents"] if entry["name"] == "large-schema.md"
    )
    opt_in_doc = next(
        entry for entry in opt_in_result["transitive_schema_documents"] if entry["name"] == "large-schema.md"
    )

    assert "body" not in default_doc
    assert "transitive schema body that should not ship by default" not in default_payload
    assert "transitive schema body that should not ship by default" in opt_in_doc["body"]
    assert len(opt_in_payload) > len(default_payload) + 100_000
