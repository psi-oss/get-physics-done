"""Ensure repair flows keep the project-contract schema visible without duplication."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_REF = "@{GPD_INSTALL_DIR}/templates/project-contract-schema.md"
GUARD_TEXT = (
    "Before repairing or re-emitting any `project_contract`, load "
    "`@{GPD_INSTALL_DIR}/templates/project-contract-schema.md` and keep its compact Hard-schema capsule "
    "visible; do not restate or fork the schema text here."
)

SCHEMA_GUARD_WORKFLOWS = (
    "src/gpd/specs/workflows/audit-milestone.md",
    "src/gpd/specs/workflows/execute-plan.md",
    "src/gpd/specs/workflows/new-milestone.md",
    "src/gpd/specs/workflows/peer-review.md",
    "src/gpd/specs/workflows/plan-phase.md",
    "src/gpd/specs/workflows/resume-work.md",
    "src/gpd/specs/workflows/verify-work.md",
)


def test_repair_workflows_reference_single_contract_schema() -> None:
    for relative_path in SCHEMA_GUARD_WORKFLOWS:
        workflow_text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert GUARD_TEXT in workflow_text
        assert workflow_text.count(SCHEMA_REF) == 1
