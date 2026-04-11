from __future__ import annotations

from pathlib import Path

import yaml

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "src" / "gpd" / "specs" / "templates"
_CONTRACT_TEMPLATES: dict[str, dict[str, str]] = {
    "project-contract-schema.md": {},
    "plan-contract-schema.md": {"type": "plan-contract-schema"},
    "contract-results-schema.md": {"type": "contract-results-schema"},
    "proof-redteam-schema.md": {"type": "proof-redteam-schema"},
}


def _load_frontmatter(path: Path) -> dict[str, object]:
    contents = path.read_text(encoding="utf-8")
    assert contents.startswith("---"), f"{path} is missing front matter"
    parts = contents.split("---", 2)
    assert len(parts) == 3, f"{path} has malformed front matter"
    frontmatter = parts[1].strip()
    return yaml.safe_load(frontmatter) or {}


def test_contract_schema_templates_keep_template_version_and_type() -> None:
    for relpath, expectations in _CONTRACT_TEMPLATES.items():
        template_path = _TEMPLATES_DIR / relpath
        assert template_path.is_file(), f"{relpath} disappeared"

        frontmatter = _load_frontmatter(template_path)
        assert frontmatter.get("template_version") == 1

        expected_type = expectations.get("type")
        if expected_type is not None:
            assert frontmatter.get("type") == expected_type
