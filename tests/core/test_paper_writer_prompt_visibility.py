from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_PATH = REPO_ROOT / "src" / "gpd" / "agents" / "gpd-paper-writer.md"


def _read_paper_writer() -> str:
    return AGENT_PATH.read_text(encoding="utf-8")


def test_paper_writer_prompt_keeps_contract_evidence_as_writing_block() -> None:
    source = _read_paper_writer()

    assert "required contract-backed outcome evidence" in source
    assert "`plan_contract_ref`, `contract_results`, and any decisive `comparison_verdicts` entry with an evidence path" in source
    assert "the research is not paper-ready. Return WRITING BLOCKED." in source


def test_paper_writer_prompt_treats_missing_confidence_tags_as_calibration_warning() -> None:
    source = _read_paper_writer()

    assert "Missing `CONFIDENCE:` tags are a calibration warning, not a writing block." in source
    assert "Treat them as missing calibration input" in source
    assert "downgrade claim language when confidence is underspecified" in source
    assert "report the missing tags in `gpd_return.issues` or checkpoint notes" in source
    assert "If any contributing phase lacks contract-backed outcome evidence or confidence tags" not in source
