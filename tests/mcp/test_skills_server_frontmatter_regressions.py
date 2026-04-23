"""Assertions for malformed frontmatter in skill-referenced docs."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from gpd.registry import CommandDef, SkillDef


def test_get_skill_surfaces_malformed_reference_frontmatter(tmp_path: Path) -> None:
    from gpd.mcp.servers import skills_server

    reference_path = tmp_path / "peer-review-panel.md"
    reference_path.write_text(
        "---\n"
        "type: peer-review-panel-protocol: [broken\n"
        "---\n"
        "# Peer Review Panel\n"
        "Body.\n",
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
            patch("gpd.mcp.servers.skills_server._portable_reference_path", side_effect=_patched_portable_reference_path),
        ):
            result = skills_server.get_skill("gpd-peer-review")
    finally:
        skills_server._reference_document_metadata.cache_clear()

    contract_documents = {Path(entry["path"]).name: entry for entry in result["contract_documents"]}

    assert "peer-review-panel.md" in contract_documents
    assert contract_documents["peer-review-panel.md"]["kind"] == "reference"
    assert "frontmatter_error" in contract_documents["peer-review-panel.md"]
    assert contract_documents["peer-review-panel.md"]["frontmatter_error"]

