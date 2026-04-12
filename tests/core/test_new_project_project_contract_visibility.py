"""Prompt/schema visibility regression for project-contract grounding."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NEW_PROJECT = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "new-project.md"
PROJECT_CONTRACT_SCHEMA = REPO_ROOT / "src" / "gpd" / "specs" / "templates" / "project-contract-schema.md"


def test_new_project_prompt_loads_schema_before_contract_output() -> None:
    new_project_text = NEW_PROJECT.read_text(encoding="utf-8")
    schema_ref = "@{GPD_INSTALL_DIR}/templates/project-contract-schema.md"

    assert schema_ref in new_project_text
    assert f"load `{schema_ref}` and keep its compact Hard-schema capsule visible" in new_project_text
    assert "do not restate or fork the schema text here" in new_project_text
    assert "PROJECT_CONTRACT_JSON" in new_project_text

    schema_load_index = new_project_text.index(f"load `{schema_ref}`")
    contract_output_index = new_project_text.index("PROJECT_CONTRACT_JSON")
    assert schema_load_index < contract_output_index


def test_new_project_prompt_avoids_verbose_schema_capsule() -> None:
    new_project_text = NEW_PROJECT.read_text(encoding="utf-8")

    assert "It lists `schema_version`" not in new_project_text
    assert "critical exponent of the 3D Ising model" not in new_project_text


def test_project_contract_schema_keeps_core_shape_visible() -> None:
    schema_text = PROJECT_CONTRACT_SCHEMA.read_text(encoding="utf-8")

    for token in (
        "project_contract",
        "schema_version",
        "context_intake",
        "uncertainty_markers",
        "references",
        "claims",
        "acceptance_tests",
    ):
        assert token in schema_text
