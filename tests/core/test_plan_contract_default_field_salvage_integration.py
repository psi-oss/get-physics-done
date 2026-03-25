from __future__ import annotations

from pathlib import Path

from gpd.core.frontmatter import parse_contract_block, verify_plan_structure

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "stage0" / "plan_with_contract.md"


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


def test_parse_contract_block_salvages_defaultable_enum_and_relation_fields() -> None:
    contract = parse_contract_block(_plan_contract_with_omitted_defaultable_fields())

    assert contract is not None
    assert contract.observables[0].kind == "other"
    assert contract.deliverables[0].kind == "other"
    assert contract.references[0].kind == "other"
    assert contract.references[0].role == "other"
    assert contract.acceptance_tests[0].kind == "other"
    assert contract.links[0].relation == "other"


def test_verify_plan_structure_accepts_omitted_defaultable_fields(tmp_path: Path) -> None:
    plan_content = _plan_contract_with_omitted_defaultable_fields()
    plan_path = tmp_path / "plan-default-field-salvage.md"
    plan_path.write_text(plan_content, encoding="utf-8")

    result = verify_plan_structure(tmp_path, plan_path)

    assert result.valid is True
    assert result.errors == []
