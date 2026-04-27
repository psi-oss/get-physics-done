"""Import-boundary regressions for private core helpers."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_knowledge_review_hash_is_import_order_independent() -> None:
    env = os.environ.copy()
    repo_src = str(REPO_ROOT / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = repo_src if not existing_pythonpath else os.pathsep.join((repo_src, existing_pythonpath))

    script = r"""
from gpd.core import knowledge_docs

content = '''---
knowledge_schema_version: 1
knowledge_id: K-import-order
title: Import Order
topic: import-order
status: stable
created_at: 2026-04-07T12:00:00Z
updated_at: 2026-04-07T12:00:00Z
sources:
  - source_id: source-main
    kind: paper
    locator: Doe et al., 2024
    title: Import Order
    why_it_matters: Trusted source
coverage_summary:
  covered_topics: [imports]
  excluded_topics: [runtime mutation]
  open_gaps: [none]
---

Trusted body.
'''

before = knowledge_docs.compute_knowledge_reviewed_content_sha256(content)
from gpd.core import frontmatter
after = knowledge_docs.compute_knowledge_reviewed_content_sha256(content)
frontmatter_hash = frontmatter.compute_knowledge_reviewed_content_sha256(content)
assert before == after == frontmatter_hash
assert knowledge_docs.compute_knowledge_reviewed_content_sha256 is frontmatter.compute_knowledge_reviewed_content_sha256
print("ok")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.strip() == "ok"


def test_knowledge_review_hash_matches_typed_and_raw_inputs() -> None:
    from gpd.core.frontmatter import extract_frontmatter
    from gpd.core.knowledge_docs import (
        compute_knowledge_reviewed_content_sha256,
        parse_knowledge_doc_data_strict,
    )

    content = """---
knowledge_schema_version: 1
knowledge_id: K-typed-parity
title: Typed Parity
topic: typed-parity
status: in_review
created_at: 2026-04-07T12:00:00Z
updated_at: 2026-04-07T12:00:00Z
sources:
  - source_id: source-main
    kind: paper
    locator: Doe et al., 2024
    title: Typed Parity
    why_it_matters: Trusted source
coverage_summary:
  covered_topics: [typed]
  excluded_topics: [none]
  open_gaps: [none]
---

Trusted body.
"""

    meta, body = extract_frontmatter(content)
    parsed = parse_knowledge_doc_data_strict(meta)

    assert compute_knowledge_reviewed_content_sha256(content) == compute_knowledge_reviewed_content_sha256(
        parsed,
        body_text=body,
    )
