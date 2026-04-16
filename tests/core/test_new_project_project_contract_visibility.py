"""Prompt/schema visibility regression for approved-mode project-contract grounding."""

from __future__ import annotations

from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes

REPO_ROOT = Path(__file__).resolve().parents[2]
NEW_PROJECT = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "new-project.md"
PROJECT_CONTRACT_SCHEMA = REPO_ROOT / "src" / "gpd" / "specs" / "templates" / "project-contract-schema.md"
STATE_SCHEMA = REPO_ROOT / "src" / "gpd" / "specs" / "templates" / "state-json-schema.md"
QUESTIONING = REPO_ROOT / "src" / "gpd" / "specs" / "references" / "research" / "questioning.md"


def _expanded(path: Path) -> str:
    return expand_at_includes(path.read_text(encoding="utf-8"), REPO_ROOT / "src/gpd/specs", "/runtime/")


def _extract_contract_rule_block_lines(text: str, start_marker: str) -> tuple[str, ...]:
    lines = text.splitlines()
    start = lines.index(start_marker)
    end = next(
        idx
        for idx in range(start + 1, len(lines))
        if lines[idx].startswith("Then present a concise scoping summary")
        or lines[idx].startswith("Present a concise scoping summary")
    )
    return tuple(line.strip() for line in lines[start:end] if line.lstrip().startswith("- "))


def test_new_project_prompt_surfaces_the_canonical_contract_schema_for_project_contract_grounding() -> None:
    new_project_text = NEW_PROJECT.read_text(encoding="utf-8")
    parse_line = next(
        line for line in new_project_text.splitlines() if line.startswith("Parse JSON for:")
    )

    assert "templates/project-contract-schema.md" in new_project_text
    assert (
        "Before you ask for approval, keep the contract as a literal JSON object for the "
        "`project_contract` subsection of `templates/project-contract-schema.md`, and use that "
        "schema as the canonical source of truth for the object rules. Do not restate the full "
        "contract rules here; keep only the approval-critical reminders below."
        in new_project_text
    )
    assert "Do not approve a scoping contract that strips decisive outputs, anchors, prior outputs, or review/stop triggers down to generic placeholders." in new_project_text
    assert "Before you show the approval gate, build the raw contract as a literal JSON object for the `project_contract` subsection of `templates/project-contract-schema.md`:" in new_project_text
    assert "author only the JSON object that will be stored in `project_contract`, not the surrounding `state.json` envelope" in new_project_text
    assert "follow the `project_contract` object rules in `templates/project-contract-schema.md` exactly" in new_project_text
    assert "do not paraphrase the schema here; reuse its exact keys, enum values, list/object shapes, ID-linkage rules, and proof-bearing claim requirements" in new_project_text
    assert "do not invent near-miss enum values, extra keys, or scalar shortcuts for list fields" in new_project_text
    assert "fix them to the schema before approval" in new_project_text
    assert "`context_intake`, `approach_policy`, and `uncertainty_markers` must each stay as objects, not strings or lists." in new_project_text
    assert "`schema_version` must be the integer `1`, `references[].must_surface` must stay a boolean `true` or `false`, and `context_intake`, `uncertainty_markers`, and `references[]` must stay visible in the approval gate so the contract still reflects the real inputs" in new_project_text
    assert "the contract schema is closed: do not add invented top-level or nested keys" not in new_project_text
    assert "list fields must stay lists even for single-item values" not in new_project_text
    assert "blank or duplicate list entries are invalid after trimming whitespace" not in new_project_text
    assert "project_contract_load_info" in new_project_text
    assert "project_contract_validation" in new_project_text
    assert "`context_intake`, `approach_policy`, and `uncertainty_markers` must each stay as objects, not strings or lists." in new_project_text
    assert (
        "`schema_version` must be the integer `1`, `references[].must_surface` must stay a boolean `true` or "
        "`false`, and `context_intake`, `uncertainty_markers`, and `references[]` must stay visible in the approval gate"
        in new_project_text
    )
    for field in (
        "researcher_model",
        "synthesizer_model",
        "commit_docs",
        "autonomy",
        "research_mode",
        "project_exists",
        "has_research_map",
        "planning_exists",
        "has_research_files",
        "has_project_manifest",
        "needs_research_map",
        "has_git",
        "project_contract",
        "project_contract_gate",
        "project_contract_load_info",
        "project_contract_validation",
    ):
        assert f"`{field}`" in parse_line
    assert "POST_SCOPE_INIT=$(gpd --raw init new-project --stage post_scope)" in new_project_text
    assert "`roadmapper_model`" in new_project_text
    assert "If the init JSON already contains `project_contract`, `project_contract_load_info`, or `project_contract_validation`, preserve that state in the approval gate and continuation decision." in new_project_text
    assert "preserve any init-surfaced `project_contract`, `project_contract_load_info`, and `project_contract_validation` state while deciding whether this is fresh work or a continuation" not in new_project_text


def test_new_project_contract_rule_block_is_not_duplicated() -> None:
    new_project_text = NEW_PROJECT.read_text(encoding="utf-8")
    show_block = _extract_contract_rule_block_lines(
        new_project_text,
        "Before you show the approval gate, build the raw contract as a literal JSON object for the `project_contract` subsection of `templates/project-contract-schema.md`:",
    )
    step4_block = new_project_text.split(
        "## 4. Synthesize The Approved Project Contract And Write PROJECT.md",
        1,
    )[1].split("Then synthesize all context into `GPD/PROJECT.md`", 1)[0]

    assert new_project_text.count("Before you show the approval gate, build the raw contract as a literal JSON object") == 1
    assert new_project_text.count("Before you ask for approval, keep the contract as a literal JSON object") == 1
    assert "Use the scoping-contract procedure from Step M1.5 for every flow before writing `PROJECT.md`." in step4_block
    assert "Do not define a second scoping-contract variant here." in step4_block
    assert "`scope.question`" not in step4_block
    assert "`context_intake.must_read_refs`" not in step4_block
    assert 'header: "Scope"' not in step4_block
    assert any("context_intake" in line and "uncertainty_markers" in line for line in show_block)
    assert any("schema_version" in line and "must_surface" in line for line in show_block)


def test_project_contract_schema_slice_keeps_contract_critical_rules_visible() -> None:
    contract_schema_text = _expanded(PROJECT_CONTRACT_SCHEMA)

    assert "Canonical schema for the `project_contract` object inside `GPD/state.json`." in contract_schema_text
    assert "model-facing contract setup should see only the `project_contract` shape and rules" in contract_schema_text
    assert "`context_intake`, `approach_policy`, and `uncertainty_markers` are JSON objects when present; do not collapse them to strings or lists." in contract_schema_text
    assert "`schema_version` must be the integer `1`." in contract_schema_text
    assert "`must_surface` is a boolean scalar. Use the JSON literals `true` and `false`;" in contract_schema_text


def test_state_schema_surfaces_the_exact_approved_mode_grounding_rule() -> None:
    state_schema_text = _expanded(STATE_SCHEMA)

    assert (
        "approved project contract requires at least one concrete anchor/reference/prior-output/baseline; "
        "explicit missing-anchor notes preserve uncertainty but do not satisfy approval on their own"
        in state_schema_text
    )
    assert (
        "`must_include_prior_outputs[]` entries should be explicit project-artifact paths or filenames that already exist inside the current project root."
        in state_schema_text
    )
    assert "If `project_root` is unavailable, treat them as non-grounding until the file can be resolved against a concrete root." in state_schema_text
    assert '"must_include_prior_outputs": ["GPD/phases/00-baseline/00-01-SUMMARY.md"]' in state_schema_text
    assert "`GPD/phases/.../*-SUMMARY.md` or `paper/main.tex`" not in state_schema_text
    assert "`GPD/phases/.../SUMMARY.md`" not in state_schema_text
    assert (
        "`user_asserted_anchors[]` and `known_good_baselines[]` must name a concrete, re-findable handle such as a citation, DOI, arXiv ID, durable URL, or project-local artifact path."
        in state_schema_text
    )
    assert "Multi-word prose alone does not count." in state_schema_text
    assert "should use at least three words and name a concrete benchmark" not in state_schema_text
    assert "gpd --raw validate project-contract - --mode approved" in state_schema_text
    assert "`context_intake`, `approach_policy`, and `uncertainty_markers` are JSON objects when present; do not collapse them to strings or lists." in state_schema_text
    assert "`schema_version` must be the integer `1`." in state_schema_text
    assert "`must_surface` is a boolean scalar. Use the JSON literals `true` and `false`;" in state_schema_text
    assert "`context_intake` must not be empty." in state_schema_text
    assert '`claims[]` — `{ "id", "statement", "claim_kind", "observables[]", "deliverables[]", "acceptance_tests[]", "references[]", "parameters[]", "hypotheses[]", "quantifiers[]", "conclusion_clauses[]", "proof_deliverables[]" }`' in state_schema_text
    assert "Treat a claim as proof-bearing whenever any of these is true" in state_schema_text
    assert "`claim_kind` is `theorem`, `lemma`, `corollary`, `proposition`, or `claim`" in state_schema_text
    assert "the statement is theorem-like (`prove/show that`, explicit `for all` / `exists`, or uniqueness language)" in state_schema_text
    assert "any proof field is already populated (`parameters`, `hypotheses`, `quantifiers`, `conclusion_clauses`, or `proof_deliverables`)" in state_schema_text
    assert "`observables[]` references a `proof_obligation` target" in state_schema_text
    assert "claims[].proof_deliverables[]" in state_schema_text
    assert "`claims[].parameters[]`, `claims[].hypotheses[]`, and `claims[].conclusion_clauses[]` must each be non-empty." in state_schema_text
    assert "`claims[].acceptance_tests[]` must include at least one proof-specific test kind" in state_schema_text
    assert "already exists inside the current project root" in state_schema_text
    assert "Placeholder or `TBD` text does not count as concrete grounding." in state_schema_text
    assert "they do not satisfy approved-mode grounding on their own" in state_schema_text


def test_new_project_and_questioning_gate_do_not_treat_missing_anchor_notes_as_approval_ready_grounding() -> None:
    new_project_text = NEW_PROJECT.read_text(encoding="utf-8")
    questioning_text = QUESTIONING.read_text(encoding="utf-8")

    assert "At least one concrete anchor, reference, prior-output constraint, or baseline" in new_project_text
    assert "If the decisive anchor is still unknown, keep that blocker explicit" in new_project_text
    assert "Missing-anchor notes preserve uncertainty, but they do not satisfy approval on their own." in new_project_text
    assert "do not offer approval yet" in new_project_text
    assert "must ground approval or be carried forward" in new_project_text
    assert "gpd --raw validate project-contract - --mode approved" in new_project_text
    assert "do not invent extra keys or collapse list fields into scalars" in questioning_text
    assert "Array fields stay arrays, even for singletons" in questioning_text
    assert "blank or duplicate list items are invalid after trimming whitespace" in questioning_text
    assert "at least one concrete anchor, reference, prior output, or baseline" in questioning_text
    assert "if the decisive anchor is still unknown, an explicit missing-anchor note" in questioning_text
    assert "do not replace the requirement for at least one concrete reference, prior output, baseline" in questioning_text
