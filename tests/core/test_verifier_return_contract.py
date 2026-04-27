"""Focused assertions for the verifier return-contract surface."""

from __future__ import annotations

from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parents[2] / "src" / "gpd" / "agents"


def _read_verifier_prompt() -> str:
    return (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")


def test_verifier_prompt_keeps_the_canonical_return_contract_visible() -> None:
    verifier = _read_verifier_prompt()

    assert "Return with status `completed | checkpoint | blocked | failed`:" in verifier
    assert "Use only status names: `completed` | `checkpoint` | `blocked` | `failed`." in verifier
    assert "Return changed paths in `gpd_return.files_written`." in verifier
    assert "`gpd_return.files_written` is fail-closed:" in verifier
    assert "list only files that genuinely landed on disk in this run" in verifier
    assert "`checkpoint`, `blocked`, and `failed` may use `[]`" in verifier


def test_verifier_prompt_surfaces_schema_sources_before_the_machine_readable_return_envelope() -> None:
    verifier = _read_verifier_prompt()
    envelope_index = verifier.index("### Machine-Readable Return Envelope")

    assert verifier.index("templates/verification-report.md") < envelope_index
    assert verifier.index("templates/contract-results-schema.md") < envelope_index
    assert verifier.index("references/shared/canonical-schema-discipline.md") < envelope_index
    assert verifier.index("## Create VERIFICATION.md") < envelope_index
