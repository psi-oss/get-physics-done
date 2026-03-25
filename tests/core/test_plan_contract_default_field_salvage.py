from __future__ import annotations

import pytest

from gpd.core.frontmatter import FrontmatterValidationError, parse_contract_block, validate_frontmatter
from tests.core.test_frontmatter import _plan_contract_frontmatter_with_explicit_semantic_sections


def _plan_contract_missing_defaultable_field(missing_line: str) -> str:
    return _plan_contract_frontmatter_with_explicit_semantic_sections().replace(missing_line, "", 1) + "Body.\n"


def _plan_contract_with_defaultable_fields() -> str:
    return _plan_contract_frontmatter_with_explicit_semantic_sections() + "Body.\n"


@pytest.mark.parametrize(
    ("missing_line", "collection_name", "field_name"),
    [
        ("      kind: scalar\n", "observables", "kind"),
        ("      kind: figure\n", "deliverables", "kind"),
        ("      kind: benchmark\n", "acceptance_tests", "kind"),
        ("      kind: paper\n", "references", "kind"),
        ("      role: benchmark\n", "references", "role"),
        ("      relation: supports\n", "links", "relation"),
    ],
)
def test_plan_contract_missing_defaultable_semantic_fields_validate_and_default_to_other(
    missing_line: str,
    collection_name: str,
    field_name: str,
) -> None:
    content = _plan_contract_missing_defaultable_field(missing_line)

    validation = validate_frontmatter(content, "plan")
    contract = parse_contract_block(content)

    assert validation.valid is True
    assert getattr(getattr(contract, collection_name)[0], field_name) == "other"


@pytest.mark.parametrize(
    ("explicit_line", "invalid_line", "collection_name", "field_name"),
    [
        ("      kind: scalar\n", "      kind: invalid\n", "observables", "kind"),
        ("      kind: figure\n", "      kind: invalid\n", "deliverables", "kind"),
        ("      kind: benchmark\n", "      kind: invalid\n", "acceptance_tests", "kind"),
        ("      kind: paper\n", "      kind: invalid\n", "references", "kind"),
        ("      role: benchmark\n", "      role: invalid\n", "references", "role"),
        ("      relation: supports\n", "      relation: invalid\n", "links", "relation"),
    ],
)
def test_plan_contract_invalid_defaultable_semantic_fields_are_still_rejected(
    explicit_line: str,
    invalid_line: str,
    collection_name: str,
    field_name: str,
) -> None:
    content = _plan_contract_with_defaultable_fields().replace(explicit_line, invalid_line, 1)

    validation = validate_frontmatter(content, "plan")

    assert validation.valid is False
    assert any(
        f"contract: {collection_name}.0.{field_name}:" in error for error in validation.errors
    )
    with pytest.raises(
        FrontmatterValidationError,
        match=rf"Invalid contract frontmatter: {collection_name}\.0\.{field_name}:",
    ):
        parse_contract_block(content)
