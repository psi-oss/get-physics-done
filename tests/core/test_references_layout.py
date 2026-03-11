"""Regression tests for the reorganized specs/references tree."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"

ROOT_MARKDOWN_FILES = {
    "README.md",
    "physics-subfields.md",
}

EXPECTED_REFERENCE_DIRS = {
    "architecture",
    "conventions",
    "examples",
    "execution",
    "methods",
    "orchestration",
    "planning",
    "protocols",
    "publication",
    "research",
    "shared",
    "subfields",
    "templates",
    "tooling",
    "ui",
    "verification",
}

EXPECTED_TEMPLATE_DIRS = {
    "research-mapper",
}

EXPECTED_VERIFICATION_DIRS = {
    "audits",
    "core",
    "domains",
    "errors",
    "examples",
    "meta",
}

REFERENCE_TOKEN_RE = re.compile(r"references/[A-Za-z0-9_./-]+\.md")
INLINE_DOC_TOKEN_RE = re.compile(r"`((?:references/|\.{1,2}/)[A-Za-z0-9_./-]+\.md(?:#[^`]+)?)`")
NON_SPEC_REFERENCE_TOKENS = {
    "references/references-pending.md",
}

MOVED_REFERENCE_FILES = [
    ("agent-delegation.md", "orchestration/agent-delegation.md"),
    ("agent-infrastructure.md", "orchestration/agent-infrastructure.md"),
    ("approximation-selection.md", "methods/approximation-selection.md"),
    ("artifact-review-architecture.md", "architecture/artifact-review-architecture.md"),
    ("bibtex-standards.md", "publication/bibtex-standards.md"),
    ("checkpoints.md", "orchestration/checkpoints.md"),
    ("code-testing-physics.md", "verification/core/code-testing-physics.md"),
    (
        "computational-verification-templates.md",
        "verification/core/computational-verification-templates.md",
    ),
    ("context-budget.md", "orchestration/context-budget.md"),
    ("context-pressure-thresholds.md", "orchestration/context-pressure-thresholds.md"),
    ("continuation-format.md", "orchestration/continuation-format.md"),
    ("contradiction-resolution-example.md", "examples/contradiction-resolution-example.md"),
    ("conventions-quick-reference.md", "conventions/conventions-quick-reference.md"),
    ("cross-project-patterns.md", "shared/cross-project-patterns.md"),
    ("error-propagation-protocol.md", "protocols/error-propagation-protocol.md"),
    ("execute-plan-checkpoints.md", "execution/execute-plan-checkpoints.md"),
    ("execute-plan-recovery.md", "execution/execute-plan-recovery.md"),
    ("execute-plan-validation.md", "execution/execute-plan-validation.md"),
    ("executor-completion.md", "execution/executor-completion.md"),
    ("executor-deviation-rules.md", "execution/executor-deviation-rules.md"),
    ("executor-index.md", "execution/executor-index.md"),
    ("executor-subfield-guide.md", "execution/executor-subfield-guide.md"),
    ("executor-task-checkpoints.md", "execution/executor-task-checkpoints.md"),
    ("executor-verification-flows.md", "execution/executor-verification-flows.md"),
    ("executor-worked-example.md", "execution/executor-worked-example.md"),
    ("figure-generation-templates.md", "publication/figure-generation-templates.md"),
    ("git-integration.md", "execution/git-integration.md"),
    ("hypothesis-driven-research.md", "protocols/hypothesis-driven-research.md"),
    ("ising-experiment-design-example.md", "examples/ising-experiment-design-example.md"),
    ("llm-errors-core.md", "verification/errors/llm-errors-core.md"),
    ("llm-errors-deep.md", "verification/errors/llm-errors-deep.md"),
    ("llm-errors-extended.md", "verification/errors/llm-errors-extended.md"),
    ("llm-errors-field-theory.md", "verification/errors/llm-errors-field-theory.md"),
    ("llm-errors-traceability.md", "verification/errors/llm-errors-traceability.md"),
    ("llm-physics-errors.md", "verification/errors/llm-physics-errors.md"),
    ("meta-orchestration.md", "orchestration/meta-orchestration.md"),
    ("model-profile-resolution.md", "orchestration/model-profile-resolution.md"),
    ("model-profiles.md", "orchestration/model-profiles.md"),
    ("paper-quality-scoring.md", "publication/paper-quality-scoring.md"),
    ("planner-approximations.md", "planning/planner-approximations.md"),
    ("planner-conventions.md", "planning/planner-conventions.md"),
    ("planner-iterative.md", "planning/planner-iterative.md"),
    ("planner-scope-examples.md", "planning/planner-scope-examples.md"),
    ("planner-tdd.md", "planning/planner-tdd.md"),
    ("planning-config.md", "planning/planning-config.md"),
    ("publication-pipeline-modes.md", "publication/publication-pipeline-modes.md"),
    ("questioning.md", "research/questioning.md"),
    ("reproducibility.md", "protocols/reproducibility.md"),
    ("research-modes.md", "research/research-modes.md"),
    ("researcher-shared.md", "research/researcher-shared.md"),
    ("shared-protocols.md", "shared/shared-protocols.md"),
    ("subfield-convention-defaults.md", "conventions/subfield-convention-defaults.md"),
    ("tool-integration.md", "tooling/tool-integration.md"),
    ("ui-brand.md", "ui/ui-brand.md"),
    ("verification-core.md", "verification/core/verification-core.md"),
    (
        "verification-domain-algebraic-qft.md",
        "verification/domains/verification-domain-algebraic-qft.md",
    ),
    ("verification-domain-amo.md", "verification/domains/verification-domain-amo.md"),
    ("verification-domain-astrophysics.md", "verification/domains/verification-domain-astrophysics.md"),
    ("verification-domain-condmat.md", "verification/domains/verification-domain-condmat.md"),
    (
        "verification-domain-fluid-plasma.md",
        "verification/domains/verification-domain-fluid-plasma.md",
    ),
    (
        "verification-domain-gr-cosmology.md",
        "verification/domains/verification-domain-gr-cosmology.md",
    ),
    (
        "verification-domain-mathematical-physics.md",
        "verification/domains/verification-domain-mathematical-physics.md",
    ),
    (
        "verification-domain-nuclear-particle.md",
        "verification/domains/verification-domain-nuclear-particle.md",
    ),
    ("verification-domain-qft.md", "verification/domains/verification-domain-qft.md"),
    (
        "verification-domain-quantum-info.md",
        "verification/domains/verification-domain-quantum-info.md",
    ),
    (
        "verification-domain-soft-matter.md",
        "verification/domains/verification-domain-soft-matter.md",
    ),
    (
        "verification-domain-statmech.md",
        "verification/domains/verification-domain-statmech.md",
    ),
    (
        "verification-domain-string-field-theory.md",
        "verification/domains/verification-domain-string-field-theory.md",
    ),
    ("verification-gap-analysis.md", "verification/audits/verification-gap-analysis.md"),
    ("verification-gap-summary.md", "verification/audits/verification-gap-summary.md"),
    ("verification-hierarchy-mapping.md", "verification/meta/verification-hierarchy-mapping.md"),
    ("verification-independence.md", "verification/meta/verification-independence.md"),
    ("verification-numerical.md", "verification/core/verification-numerical.md"),
    ("verification-patterns.md", "verification/core/verification-patterns.md"),
    ("verification-quick-reference.md", "verification/core/verification-quick-reference.md"),
    ("verifier-profile-checks.md", "verification/meta/verifier-profile-checks.md"),
    ("verifier-worked-examples.md", "verification/examples/verifier-worked-examples.md"),
]


def test_references_root_only_keeps_index_markdown_files() -> None:
    root_markdown = {path.name for path in REFERENCES_DIR.glob("*.md")}
    assert root_markdown == ROOT_MARKDOWN_FILES


def test_references_top_level_directories_exist() -> None:
    actual_dirs = {path.name for path in REFERENCES_DIR.iterdir() if path.is_dir()}
    assert EXPECTED_REFERENCE_DIRS <= actual_dirs


def test_references_nested_directories_exist() -> None:
    template_dirs = {path.name for path in (REFERENCES_DIR / "templates").iterdir() if path.is_dir()}
    verification_dirs = {path.name for path in (REFERENCES_DIR / "verification").iterdir() if path.is_dir()}

    assert template_dirs == EXPECTED_TEMPLATE_DIRS
    assert EXPECTED_VERIFICATION_DIRS <= verification_dirs


@pytest.mark.parametrize(("old_rel", "new_rel"), MOVED_REFERENCE_FILES)
def test_all_moved_reference_files_exist_only_in_new_home(old_rel: str, new_rel: str) -> None:
    assert not (REFERENCES_DIR / old_rel).exists(), old_rel
    assert (REFERENCES_DIR / new_rel).exists(), new_rel


def test_deleted_decimal_phase_reference_is_gone() -> None:
    assert not (REFERENCES_DIR / "decimal-phase-calculation.md").exists()


def test_insert_phase_workflow_points_to_merged_decimal_phase_section() -> None:
    content = (REPO_ROOT / "src/gpd/specs/workflows/insert-phase.md").read_text(encoding="utf-8")
    assert "references/decimal-phase-calculation.md" not in content
    assert "references/orchestration/agent-infrastructure.md" in content
    assert "Decimal Phase Calculation" in content


def test_research_mapper_references_use_renamed_template_tree() -> None:
    agent = (REPO_ROOT / "src/gpd/agents/gpd-research-mapper.md").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / "src/gpd/specs/workflows/map-research.md").read_text(encoding="utf-8")

    expected_paths = [
        "references/templates/research-mapper/FORMALISM.md",
        "references/templates/research-mapper/REFERENCES.md",
        "references/templates/research-mapper/ARCHITECTURE.md",
        "references/templates/research-mapper/STRUCTURE.md",
        "references/templates/research-mapper/CONVENTIONS.md",
        "references/templates/research-mapper/VALIDATION.md",
        "references/templates/research-mapper/CONCERNS.md",
    ]
    for token in expected_paths:
        assert token in agent
    assert "references/templates/research-mapper/" in workflow


def test_source_files_only_reference_existing_reference_markdown_files() -> None:
    referenced_paths: set[str] = set()

    for path in (REPO_ROOT / "src/gpd").rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".py"} or REFERENCES_DIR in path.parents:
            continue
        content = path.read_text(encoding="utf-8")
        referenced_paths.update(REFERENCE_TOKEN_RE.findall(content))

    referenced_paths -= NON_SPEC_REFERENCE_TOKENS
    assert referenced_paths

    for token in sorted(referenced_paths):
        resolved = REFERENCES_DIR / token.removeprefix("references/")
        assert resolved.is_file(), token


def test_reference_docs_inline_markdown_targets_resolve() -> None:
    found_tokens: set[str] = set()

    for path in REFERENCES_DIR.rglob("*.md"):
        content = path.read_text(encoding="utf-8")
        for token in INLINE_DOC_TOKEN_RE.findall(content):
            found_tokens.add(token)
            without_anchor = token.split("#", 1)[0]
            if without_anchor.startswith("references/"):
                resolved = REFERENCES_DIR / without_anchor.removeprefix("references/")
            else:
                resolved = (path.parent / without_anchor).resolve()
            assert resolved.is_file(), f"{path.relative_to(REPO_ROOT)} -> {token}"

    assert found_tokens


def test_no_stale_root_reference_paths_remain_in_prompt_sources() -> None:
    source_roots = [
        REPO_ROOT / "src/gpd/agents",
        REPO_ROOT / "src/gpd/commands",
        REPO_ROOT / "src/gpd/specs/templates",
        REPO_ROOT / "src/gpd/specs/workflows",
    ]
    stale_tokens = [
        "references/decimal-phase-calculation.md",
        "references/agent-delegation.md",
        "references/verification-core.md",
        "references/publication-pipeline-modes.md",
        "references/model-profiles.md",
    ]

    for root in source_roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".md", ".py"}:
                continue
            content = path.read_text(encoding="utf-8")
            for token in stale_tokens:
                assert token not in content, f"{path.relative_to(REPO_ROOT)} still contains {token}"
