from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gpd.cli import app

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "stage0" / "plan_with_contract.md"

runner = CliRunner()


def _plan_contract_with_omitted_defaultable_fields() -> str:
    content = PLAN_FIXTURE.read_text(encoding="utf-8")
    content = content.replace("      kind: figure\n", "", 1)
    content = content.replace("      kind: paper\n", "", 1)
    content = content.replace("      role: benchmark\n", "", 1)
    content = content.replace("      kind: benchmark\n", "", 1)
    content = content.replace(
        "  forbidden_proxies:\n",
        "  observables:\n"
        "    - id: obs-benchmark\n"
        "      name: Benchmark observable\n"
        "      definition: Decisive benchmark observable\n"
        "  links:\n"
        "    - id: link-benchmark\n"
        "      source: claim-benchmark\n"
        "      target: deliv-figure\n"
        "      verified_by: [test-benchmark]\n"
        "  forbidden_proxies:\n",
        1,
    )
    return content


def test_validate_plan_contract_command_accepts_omitted_defaultable_fields(tmp_path: Path) -> None:
    plan_path = tmp_path / "01-PLAN.md"
    plan_path.write_text(_plan_contract_with_omitted_defaultable_fields(), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--raw", "validate", "plan-contract", str(plan_path)],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is True
    assert payload["errors"] == []
