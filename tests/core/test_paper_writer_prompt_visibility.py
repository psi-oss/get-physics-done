from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_PATH = REPO_ROOT / "src" / "gpd" / "agents" / "gpd-paper-writer.md"


def _read_paper_writer() -> str:
    return AGENT_PATH.read_text(encoding="utf-8")


def test_paper_writer_prompt_keeps_contract_evidence_as_writing_block() -> None:
    source = _read_paper_writer()

    assert "required contract-backed outcome evidence" in source
    assert "plan_contract_ref" in source
    assert "contract_results" in source
    assert "comparison_verdicts" in source
    assert "any decisive `comparison_verdicts` entry with an evidence path" not in source
    assert "any decisive `comparison_verdicts` entry when the manuscript claim depends on that comparison" in source
    assert "the research is not paper-ready. Return WRITING BLOCKED." in source


def test_paper_writer_prompt_treats_missing_confidence_tags_as_calibration_warning() -> None:
    source = _read_paper_writer()

    assert "Missing `CONFIDENCE:` tags are a calibration warning, not a writing block." in source
    assert "Treat them as missing calibration input" in source
    assert "downgrade claim language" in source
    assert "gpd_return.issues" in source
    assert "If any contributing phase lacks contract-backed outcome evidence or confidence tags" not in source


def test_paper_writer_prompt_surfaces_builder_journal_boundary() -> None:
    source = _read_paper_writer()

    assert "Builder-backed journal keys for `PAPER-CONFIG.json` and `ARTIFACT-MANIFEST.json` are only" in source
    assert "`prl`, `apj`, `mnras`, `nature`, `jhep`, and `jfm`" in source
    assert "style-only calibration for prose and structure" in source
    assert "Do not write unsupported journal labels into machine-readable builder artifacts." in source


def test_paper_writer_prompt_keeps_required_gpd_acknowledgment_visible() -> None:
    source = _read_paper_writer()

    assert "This research made use of Get Physics Done (GPD)" in source
    assert "GPD Research Grant from Physical Superintelligence PBC (PSI)." in source
