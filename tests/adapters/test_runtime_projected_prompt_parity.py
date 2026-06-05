"""Runtime-projected prompt parity for contract-heavy command and agent surfaces."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

import gpd.adapters.gemini as gemini_module
from gpd.adapters import get_adapter
from gpd.adapters.install_utils import (
    expand_at_includes,
    project_markdown_for_runtime,
)
from gpd.adapters.runtime_catalog import get_runtime_descriptor
from gpd.core.context import init_execute_phase, init_plan_phase, init_quick, init_verify_work
from gpd.core.model_visible_text import (
    agent_visibility_note,
    review_contract_visibility_note,
)
from gpd.core.onboarding_surfaces import beginner_runtime_surface
from gpd.registry import _frontmatter_parts, _load_frontmatter_mapping, _parse_spawn_contracts
from tests.adapters.projection_budget_support import (
    COMPACT_WORKFLOW_REFERENCE_COMMAND_PROJECTION_BUDGETS,
    NATIVE_AGENT_PROJECTION_BUDGETS,
    NON_NATIVE_RUNTIME_PROJECTION_TARGETS,
    RUNTIME_PROJECTION_TARGETS,
    SELECTED_AGENT_PROJECTION_BUDGETS,
    SELECTED_AGENT_PROJECTION_TARGETS,
    STAGED_INIT_TARGET_COMMANDS,
    STAGED_PROJECTED_COMMAND_CHAR_BUDGET,
    TARGET_AGENT_COMBINED_NON_NATIVE_PROJECTION_CHAR_BUDGET,
    TARGET_AGENT_PROJECTION_BUDGETS,
)
from tests.adapters.projection_test_utils import (
    PROTOCOL_BUNDLE_INLINE_CATALOG_MARKERS,
    StagedCommandProjectionCase,
    assert_compact_staged_command_shim,
    assert_compact_workflow_reference_shim,
    assert_no_unresolved_include_markers,
    assert_protocol_bundle_jit_shape,
    assert_runtime_bridge_targets_active_runtime,
    assert_runtime_note_tag_count,
    assert_runtime_note_tags_not_repeated,
    first_runnable_shell_commands,
    has_compact_non_native_shim,
    has_help_bridge_shim_sentinel,
    has_staged_shim_sentinel,
    has_workflow_reference_shim_sentinel,
    iter_staged_command_projection_cases,
    normalized_runtime_bridge_text,
    raw_include_count,
    runtime_bridge_command,
    shell_fence_bodies,
    single_runtime_note_block,
    staged_command_protocol_bundle_fields,
)
from tests.prompt_metrics_support import runtime_command_visibility_note
from tests.runtime_command_prefix_support import assert_no_incompatible_beginner_command_labels
from tests.workflow_authority_support import expanded_workflow_authority_text

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"

RUNTIMES = RUNTIME_PROJECTION_TARGETS
COMPACT_WORKFLOW_COMMANDS = (
    "parameter-sweep",
    "sensitivity-analysis",
    "numerical-convergence",
    "limiting-cases",
    "progress",
    "error-propagation",
    "compare-experiment",
    "dimensional-analysis",
    "discover",
    "start",
    "audit-milestone",
    "debug",
    "review-knowledge",
    "export",
    "explain",
    "list-phase-assumptions",
)
ADDITIONAL_COMPACT_WORKFLOW_REFERENCE_COMMAND_PROJECTION_BUDGETS = {
    "export": {
        "codex": {"chars": 5_400, "lines": 105},
        "copilot-cli": {"chars": 5_100, "lines": 100},
        "gemini": {"chars": 4_900, "lines": 90},
        "opencode": {"chars": 5_200, "lines": 100},
    },
    "explain": {
        "codex": {"chars": 6_200, "lines": 130},
        "copilot-cli": {"chars": 6_600, "lines": 145},
        "gemini": {"chars": 6_950, "lines": 130},
        "opencode": {"chars": 6_550, "lines": 145},
    },
    "list-phase-assumptions": {
        "codex": {"chars": 7_900, "lines": 155},
        "copilot-cli": {"chars": 7_700, "lines": 160},
        "gemini": {"chars": 7_400, "lines": 140},
        "opencode": {"chars": 7_850, "lines": 160},
    },
}
COMPACT_WORKFLOW_REFERENCE_PROJECTION_BUDGETS = {
    **COMPACT_WORKFLOW_REFERENCE_COMMAND_PROJECTION_BUDGETS,
    **ADDITIONAL_COMPACT_WORKFLOW_REFERENCE_COMMAND_PROJECTION_BUDGETS,
}
STAGED_INIT_COMMAND_PROJECTION_RATCHET_BUDGETS = {
    "plan-phase": {
        "claude-code": 4_500,
        "codex": 6_650,
        "copilot-cli": 6_600,
        "gemini": 7_150,
        "opencode": 6_650,
    },
    "execute-phase": {
        "claude-code": 3_450,
        "codex": 5_900,
        "copilot-cli": 5_800,
        "gemini": 6_400,
        "opencode": 5_850,
    },
    "new-project": {
        "claude-code": 7_300,
        "codex": 9_050,
        "copilot-cli": 8_800,
        "gemini": 9_550,
        "opencode": 8_950,
    },
    "write-paper": {
        "claude-code": 12_950,
        "codex": 11_850,
        "copilot-cli": 15_100,
        "gemini": 12_300,
        "opencode": 15_250,
    },
}
COMPACT_WORKFLOW_STALE_WRAPPER_PHRASES = {
    "compare-experiment": ("Follow the included compare-experiment workflow.",),
    "dimensional-analysis": ("Follow the included dimensional-analysis workflow.",),
    "review-knowledge": ("Follow the included review-knowledge workflow exactly.",),
    "export": ("Execute the included export workflow end-to-end.",),
    "explain": ("Follow the included explain workflow end-to-end.",),
    "list-phase-assumptions": ("Follow list-phase-assumptions.md workflow:",),
}
COMPACT_WORKFLOW_WRAPPER_CONSTRAINTS = {
    "export": (
        "Write files to `exports/`.",
        "Do not commit generated exports unless `$ARGUMENTS` includes `--commit`.",
    ),
    "explain": (
        "validate command-context explain",
        "GPD/explanations/",
        "stop and ask the user to rerun with an explicit concept/topic",
    ),
    "list-phase-assumptions": (
        "Conversational output only (no file creation)",
        "Phase number: $ARGUMENTS (required)",
        'Prompt "What do you think?"',
    ),
}
TARGET_FIRST_STAGE_BY_COMMAND = {
    "plan-phase": "phase_bootstrap",
    "execute-phase": "phase_bootstrap",
    "new-project": "scope_intake",
    "verify-work": "session_router",
    "write-paper": "paper_bootstrap",
}
VERIFIER_SCHEMA_INCLUDE_SUFFIXES = (
    "templates/verification-report.md",
    "templates/contract-results-schema.md",
    "references/shared/canonical-schema-discipline.md",
)
VERIFIER_SCHEMA_AUTHORITY_MARKERS = (
    ("templates/verification-report.md", "# Verification Report Template"),
    ("templates/contract-results-schema.md", "# Contract Results Schema"),
    ("references/shared/canonical-schema-discipline.md", "# Canonical Schema Discipline"),
)
VERIFY_WORK_CONCISE_GUIDANCE_FRAGMENTS = (
    "Stage id: `session_router`.",
    "SESSION_ROUTER_INIT=$(gpd --raw init verify-work",
    "Read `active_verification_sessions` from `SESSION_ROUTER_INIT`.",
    "replaces shell loops over `GPD/phases`",
    "Do not assume reference ledgers,",
    'gpd validate review-preflight verify-work "${PHASE_ARG}" --strict',
    "LIFECYCLE_CONTRACT_GATE=$(gpd --raw validate lifecycle-contract-gate verify-work",
)
VERIFY_WORK_LATE_STAGE_FRAGMENTS = (
    "@{GPD_INSTALL_DIR}/references/verification/core/proof-redteam-workflow-gate.md",
    "verification_report_skeleton_bridge",
    "verification_report_finalizer_bridge",
    "verify_work_gap_planner",
    "templates/planner-subagent-prompt.md",
)
VERIFY_WORK_FORBIDDEN_SOURCE_COMMAND_PREFIXES = (
    "$gpd-verify-work",
    "/gpd:verify-work",
    "/gpd-verify-work",
    "gpd-verify-work",
)
PUBLIC_NEXT_UP_PROJECTION_RUNTIMES = RUNTIMES
PUBLIC_NEXT_UP_FORBIDDEN_PROJECTION_FRAGMENTS = (
    "gpd --raw init",
    "--raw init",
    "gpd --raw stage field-access",
    "--raw stage field-access",
    "gpd verify phase",
    "gpd:verify-phase",
)
RUNTIME_BRIDGE_ACCEPTANCE_COMMANDS = tuple(
    dict.fromkeys(
        (
            *STAGED_INIT_TARGET_COMMANDS,
            "health",
            "progress",
            "update",
        )
    )
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _command_names() -> tuple[str, ...]:
    return tuple(path.stem for path in sorted(COMMANDS_DIR.glob("*.md")))


def _command_frontmatter(command_name: str) -> dict[str, object]:
    frontmatter, _body = _frontmatter_parts(_read(COMMANDS_DIR / f"{command_name}.md"))
    assert frontmatter is not None, f"{command_name} is missing command frontmatter"
    return _load_frontmatter_mapping(frontmatter, error_prefix=f"Malformed frontmatter for {command_name}")


def _contract_bearing_command_surfaces() -> dict[str, tuple[str, ...]]:
    surfaces: dict[str, tuple[str, ...]] = {}
    for command_name in _command_names():
        meta = _command_frontmatter(command_name)
        fragments = []
        review_contract = meta.get("review-contract")
        if isinstance(review_contract, dict):
            fragments.append(review_contract_visibility_note())
            if "required_state" in review_contract:
                fragments.append("required_state:")
        if meta.get("agent") or "review-contract" in meta or "allowed-tools" in meta or "requires" in meta:
            surfaces[command_name] = tuple(fragments)
    return surfaces


def _runtime_expected_fragments(fragments: tuple[str, ...], *, runtime: str) -> tuple[str, ...]:
    if runtime == "codex":
        return tuple(fragment.replace("`gpd:suggest-next`", "`$gpd-suggest-next`") for fragment in fragments)
    if runtime == "copilot-cli":
        import re as _re

        def _rewrite(text: str) -> str:
            return _re.sub(r"(?<![A-Za-z0-9_./:$-])/?gpd:([a-z][a-z0-9-]*)\b", r"/gpd-\1", text)

        return tuple(_rewrite(fragment) for fragment in fragments)
    if runtime == "opencode":
        # OpenCode adapter rewrites bare `gpd:X` to `gpd-X` in body text;
        # translate expected fragments accordingly.
        import re as _re

        def _rewrite(text: str) -> str:
            return _re.sub(r"(?<![A-Za-z0-9_./:$-])gpd:([a-z][a-z0-9-]*)\b", r"gpd-\1", text)

        return tuple(_rewrite(fragment) for fragment in fragments)
    return fragments


def _spawn_contract_commands() -> tuple[str, ...]:
    return tuple(
        command_name
        for command_name in _command_names()
        if "<spawn_contract>" in _read(COMMANDS_DIR / f"{command_name}.md")
    )


COMMAND_SURFACES = _contract_bearing_command_surfaces()
SPAWN_CONTRACT_COMMANDS = _spawn_contract_commands()
STAGED_COMMAND_PROJECTION_CASES = iter_staged_command_projection_cases(
    commands_dir=COMMANDS_DIR,
    workflows_dir=WORKFLOWS_DIR,
)
PROJECTED_RUNTIME_NOTE_SURFACES = tuple(
    pytest.param(path, "command", id=f"command:{path.stem}") for path in sorted(COMMANDS_DIR.glob("*.md"))
) + tuple(
    pytest.param(AGENTS_DIR / f"{agent_name}.md", "agent", id=f"agent:{agent_name}")
    for agent_name in SELECTED_AGENT_PROJECTION_TARGETS
)
PLAN_AGENT_SURFACES = {
    "gpd-planner": (
        agent_visibility_note(),
        "tool_requirements",
        "must_surface",
        "validator-accepted tools (`wolfram`, `command`)",
    ),
}
RESULT_AGENT_SURFACES = {
    "gpd-verifier": (
        agent_visibility_note(),
        "templates/contract-results-schema.md",
        "writer_command",
        "skeleton_command",
        "verification_report_skeleton_bridge",
        "gpd frontmatter validate",
        "gpd validate verification-contract",
    ),
    "gpd-executor": (
        agent_visibility_note(),
        "templates/contract-results-schema.md",
        "templates/summary.md",
        "plan_contract_ref",
        "contract_results",
        "comparison_verdicts",
    ),
}
PEER_REVIEW_PUBLICATION_LANE_FRAGMENTS = (
    "Use centralized preflight's selected publication/review roots for GPD-authored review artifacts.",
    "Keep the manuscript and manuscript-local publication manifests rooted at the resolved manuscript directory.",
)


def _write_bundle_projection_project(cwd: Path, *, selected: bool) -> None:
    from gpd.core.state import default_state_dict

    gpd_dir = cwd / "GPD"
    phase_dir = gpd_dir / "phases" / "01-setup"
    phase_dir.mkdir(parents=True, exist_ok=True)
    (phase_dir / "01-PLAN.md").write_text("# Plan\n", encoding="utf-8")
    (phase_dir / "01-CONTEXT.md").write_text("# Context\n", encoding="utf-8")
    (gpd_dir / "config.json").write_text("{}", encoding="utf-8")
    (gpd_dir / "STATE.md").write_text("# State\n", encoding="utf-8")
    (gpd_dir / "REQUIREMENTS.md").write_text("# Requirements\n", encoding="utf-8")
    (gpd_dir / "ROADMAP.md").write_text("## Milestone\n\n### Phase 1: Setup\n", encoding="utf-8")
    (gpd_dir / "PROJECT.md").write_text(
        (
            "# Test Project\n\n"
            "## What This Is\n\n"
            "Monte Carlo study of a statistical mechanics lattice model near criticality.\n\n"
            "## Research Context\n\n"
            "### Theoretical Framework\n\n"
            "Statistical mechanics\n\n"
            "### Known Results\n\n"
            "Binder cumulants, thermalization windows, and finite-size scaling should be benchmarked.\n"
        )
        if selected
        else (
            "# Test Project\n\n"
            "## What This Is\n\n"
            "Quantum-gravity saddle bookkeeping with Page-curve comparisons and entropy arguments.\n"
        ),
        encoding="utf-8",
    )

    state = default_state_dict()
    state["project_contract"] = _stat_mech_contract_payload() if selected else _generic_benchmark_contract_payload()
    state["convention_lock"] = {
        "metric_signature": "(-,+,+,+)",
        "fourier_convention": "physics",
        "natural_units": "SI",
    }
    state["intermediate_results"] = [
        {
            "id": "R-01",
            "equation": "E = mc^2",
            "description": "Rest energy",
            "phase": "01",
            "depends_on": [],
            "verified": True,
        }
    ]
    state["approximations"] = [
        {
            "name": "weak coupling",
            "validity_range": "g << 1",
            "controlling_param": "g",
            "current_value": "0.1",
            "status": "valid",
        }
    ]
    state["propagated_uncertainties"] = [
        {
            "quantity": "m_eff",
            "value": "1.2",
            "uncertainty": "0.1",
            "phase": "01",
            "method": "bootstrap",
        }
    ]
    (gpd_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _stat_mech_contract_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "scope": {
            "question": "What finite-size scaling collapse and benchmark comparison does the simulation recover?",
            "in_scope": ["Recover the decisive finite-size scaling benchmark for the simulation regime"],
        },
        "claims": [
            {
                "id": "claim-critical",
                "statement": "Recover benchmark finite-size scaling behavior",
                "deliverables": ["deliv-data", "deliv-figure"],
                "acceptance_tests": ["test-benchmark"],
                "references": ["ref-benchmark"],
            }
        ],
        "deliverables": [
            {
                "id": "deliv-data",
                "kind": "dataset",
                "path": "results/measurements.csv",
                "description": "Raw Monte Carlo measurements with metadata",
            },
            {
                "id": "deliv-figure",
                "kind": "figure",
                "path": "figures/collapse.png",
                "description": "Finite-size scaling collapse figure",
            },
        ],
        "acceptance_tests": [
            {
                "id": "test-benchmark",
                "subject": "claim-critical",
                "kind": "benchmark",
                "procedure": "Compare Binder cumulants and finite-size scaling against literature benchmarks",
                "pass_condition": "Benchmark agreement is within uncertainty",
            }
        ],
        "references": [
            {
                "id": "ref-benchmark",
                "kind": "paper",
                "locator": "Benchmark Monte Carlo paper",
                "role": "benchmark",
                "why_it_matters": "Decisive comparison for the simulation regime",
                "applies_to": ["claim-critical"],
                "must_surface": True,
                "required_actions": ["read", "compare", "cite"],
            }
        ],
        "context_intake": {
            "must_read_refs": ["ref-benchmark"],
        },
        "forbidden_proxies": [
            {
                "id": "fp-proxy",
                "subject": "claim-critical",
                "proxy": "Qualitative agreement without scaling analysis",
                "reason": "Would not validate the decisive benchmarked observable",
            }
        ],
        "uncertainty_markers": {
            "weakest_anchors": ["Autocorrelation estimate near the critical point"],
            "disconfirming_observations": ["Finite-size crossings drift away from the benchmark window"],
        },
    }


def _generic_benchmark_contract_payload() -> dict[str, object]:
    payload = _stat_mech_contract_payload()
    payload["scope"] = {
        "question": "Does the output match a generic benchmark?",
        "in_scope": ["Compare against the generic benchmark"],
    }
    payload["claims"] = [
        {
            "id": "claim-critical",
            "statement": "Recover a generic benchmark value",
            "deliverables": ["deliv-data", "deliv-figure"],
            "acceptance_tests": ["test-benchmark"],
            "references": ["ref-benchmark"],
        }
    ]
    payload["deliverables"] = [
        {
            "id": "deliv-data",
            "kind": "dataset",
            "path": "results/generic-measurements.csv",
            "description": "Generic benchmark measurements with metadata",
        },
        {
            "id": "deliv-figure",
            "kind": "figure",
            "path": "figures/generic-benchmark.png",
            "description": "Generic benchmark comparison figure",
        },
    ]
    payload["acceptance_tests"] = [
        {
            "id": "test-benchmark",
            "subject": "claim-critical",
            "kind": "benchmark",
            "procedure": "Compare against a benchmark reference",
            "pass_condition": "Benchmark agreement is within uncertainty",
        }
    ]
    payload["references"] = [
        {
            "id": "ref-benchmark",
            "kind": "paper",
            "locator": "Generic benchmark paper",
            "role": "benchmark",
            "why_it_matters": "Comparison target",
            "applies_to": ["claim-critical"],
            "must_surface": True,
            "required_actions": ["read", "compare"],
        }
    ]
    payload["forbidden_proxies"] = [
        {
            "id": "fp-proxy",
            "subject": "claim-critical",
            "proxy": "Qualitative trend agreement without the generic benchmark comparison",
            "reason": "Would not validate the decisive benchmarked observable",
        }
    ]
    payload["uncertainty_markers"] = {
        "weakest_anchors": ["Generic benchmark tolerance"],
        "disconfirming_observations": ["Benchmark agreement disappears under direct comparison"],
    }
    return payload


def _project_markdown(path: Path, runtime: str, *, is_agent: bool) -> str:
    return project_markdown_for_runtime(
        _read(path),
        runtime=runtime,
        path_prefix="/runtime/",
        surface_kind="agent" if is_agent else "command",
        src_root=REPO_ROOT / "src/gpd",
        protect_agent_prompt_body=is_agent,
        command_name=path.stem,
    )


def _project_installed_shared_markdown(path: Path, runtime: str) -> str:
    return get_adapter(runtime).translate_shared_markdown(_read(path), "/runtime/", install_scope="--local")


def _project_fixture_command(
    content: str,
    runtime: str,
    target_dir: Path,
    *,
    command_name: str = "projection-probe",
    src_root: Path | None = None,
) -> str:
    descriptor = get_runtime_descriptor(runtime)
    return project_markdown_for_runtime(
        content,
        runtime=runtime,
        path_prefix=f"./{descriptor.config_dir_name}/",
        surface_kind="command",
        install_scope="--local",
        workflow_target_dir=target_dir,
        src_root=src_root,
        command_name=command_name,
    )


def _project_command_for_runtime(command_name: str, runtime: str, target_dir: Path) -> str:
    descriptor = get_runtime_descriptor(runtime)
    return project_markdown_for_runtime(
        _read(COMMANDS_DIR / f"{command_name}.md"),
        runtime=runtime,
        path_prefix=f"./{descriptor.config_dir_name}/",
        surface_kind="command",
        install_scope="--local",
        src_root=REPO_ROOT / "src/gpd",
        workflow_target_dir=target_dir,
        command_name=command_name,
    )


def _extract_next_up_snippet(text: str) -> str:
    lines = text.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == "## > Next Up")
    except StopIteration as exc:
        raise AssertionError("projected surface is missing a public Next Up block") from exc

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## ") and lines[index].strip() != "## > Next Up":
            end = index
            break
    return "\n".join(lines[start:end])


def _extract_stage_stop_snippet(text: str) -> str:
    lines = text.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == "stage_stop:")
    except StopIteration as exc:
        raise AssertionError("projected surface is missing a stage_stop snippet") from exc

    collected: list[str] = []
    for line in lines[start:]:
        if collected and not line.strip():
            break
        if collected and line[:1] not in {" ", "\t"}:
            break
        collected.append(line)
    return "\n".join(collected)


def _expected_runtime_command_label(runtime: str, command_name: str, suffix: str = "") -> str:
    label = get_adapter(runtime).format_command(command_name)
    public_prefix = get_runtime_descriptor(runtime).public_command_surface_prefix

    assert label.startswith(public_prefix)
    return f"{label}{suffix}"


def _wrong_runtime_command_labels(runtime: str, command_name: str) -> tuple[str, ...]:
    active_label = _expected_runtime_command_label(runtime, command_name)
    return tuple(
        label
        for other_runtime in RUNTIMES
        if (label := get_adapter(other_runtime).format_command(command_name)) != active_label
    )


def _standalone_install_dir_include_lines(text: str) -> tuple[str, ...]:
    return tuple(line for line in text.splitlines() if line.strip().startswith("@{GPD_INSTALL_DIR}/"))


def _workflow_authority_for_shimmed_projection(command_name: str, projected: str, runtime: str) -> str:
    if has_compact_non_native_shim(projected):
        return projected + "\n" + _project_installed_shared_markdown(WORKFLOWS_DIR / f"{command_name}.md", runtime)
    return projected


def _has_line_with_terms(text: str, *terms: str) -> bool:
    folded_terms = tuple(term.casefold() for term in terms)
    return any(all(term in line.casefold() for term in folded_terms) for line in text.splitlines())


def _assert_codex_compact_runtime_note(text: str, bridge: str) -> None:
    block = single_runtime_note_block(text, "codex_runtime_notes")
    assert "runtime-command-snippets.md#runtime-shell-bridge" in block
    assert bridge in block
    assert _has_line_with_terms(block, "bridge")
    assert "Codex shell compatibility:" not in block
    assert "When shell steps call the GPD CLI" not in block


def _assert_codex_inline_freeform_questioning(text: str) -> None:
    block = single_runtime_note_block(text, "codex_questioning")
    assert "runtime-command-snippets.md#runtime-questioning" in block
    assert _has_line_with_terms(block, "ask", "once")
    assert "ask_user" not in text.casefold()
    assert _has_line_with_terms(text, "ask", "inline", "freeform")
    assert (
        _has_line_with_terms(text, "one", "inline", "freeform")
        or _has_line_with_terms(text, "single", "inline", "freeform")
        or _has_line_with_terms(text, "exactly", "inline", "freeform")
    )


def _assert_fragments_visible(text: str, fragments: tuple[str, ...], *, label: str) -> None:
    missing = sorted(fragment for fragment in fragments if fragment not in text)
    assert not missing, f"{label} is missing contract-bearing fragments: {', '.join(missing)}"


def _extract_spawn_contracts(text: str) -> list[dict[str, object]]:
    return list(_parse_spawn_contracts(text, owner_name="runtime-projected"))


def _expected_target_init_command(command_name: str, bridge: str) -> str:
    if command_name in {"plan-phase", "execute-phase", "verify-work"}:
        return f'{bridge} --raw init {command_name} "$ARGUMENTS" --stage {TARGET_FIRST_STAGE_BY_COMMAND[command_name]}'
    if command_name == "new-project":
        return f"{bridge} --raw init new-project --stage scope_intake"
    if command_name == "write-paper":
        return f'{bridge} --raw init write-paper --stage paper_bootstrap -- "$ARGUMENTS"'
    raise AssertionError(f"Unhandled staged init target command: {command_name}")


@pytest.mark.parametrize("agent_name", SELECTED_AGENT_PROJECTION_TARGETS)
@pytest.mark.parametrize("runtime", NON_NATIVE_RUNTIME_PROJECTION_TARGETS)
def test_non_native_projected_selected_agents_stay_budgeted_without_raw_install_dir_placeholders(
    agent_name: str,
    runtime: str,
) -> None:
    projected = _project_markdown(AGENTS_DIR / f"{agent_name}.md", runtime, is_agent=True)
    budget = SELECTED_AGENT_PROJECTION_BUDGETS[agent_name]
    label = f"{runtime} {agent_name}"

    assert_no_unresolved_include_markers(projected, label=label)
    assert_runtime_note_tags_not_repeated(projected, label=label)
    assert _standalone_install_dir_include_lines(projected) == ()
    assert "@{GPD_INSTALL_DIR}" not in projected
    assert "{GPD_INSTALL_DIR}" not in projected
    assert len(projected.splitlines()) <= budget["lines"]
    assert len(projected) <= budget["chars"]


def test_target_agent_non_native_projected_chars_stay_under_combined_close_budget() -> None:
    max_chars_by_agent: dict[str, int] = {}
    for agent_name in TARGET_AGENT_PROJECTION_BUDGETS:
        max_chars_by_agent[agent_name] = max(
            len(_project_markdown(AGENTS_DIR / f"{agent_name}.md", runtime, is_agent=True))
            for runtime in NON_NATIVE_RUNTIME_PROJECTION_TARGETS
        )

    assert sum(max_chars_by_agent.values()) <= TARGET_AGENT_COMBINED_NON_NATIVE_PROJECTION_CHAR_BUDGET


@pytest.mark.parametrize("path, surface_kind", PROJECTED_RUNTIME_NOTE_SURFACES)
@pytest.mark.parametrize("runtime", NON_NATIVE_RUNTIME_PROJECTION_TARGETS)
def test_projected_runtime_note_blocks_are_not_repeated(
    runtime: str,
    path: Path,
    surface_kind: str,
) -> None:
    projected = _project_markdown(path, runtime, is_agent=surface_kind == "agent")

    assert_runtime_note_tags_not_repeated(projected, label=f"{runtime} {surface_kind} {path.stem}")


@pytest.mark.parametrize("command_name", STAGED_INIT_TARGET_COMMANDS)
@pytest.mark.parametrize("runtime", RUNTIMES)
def test_staged_init_target_command_projection_stays_under_baseline_budget(
    command_name: str,
    runtime: str,
) -> None:
    projected = _project_markdown(COMMANDS_DIR / f"{command_name}.md", runtime, is_agent=False)
    budget = STAGED_INIT_COMMAND_PROJECTION_RATCHET_BUDGETS[command_name][runtime]
    normalized_projected = normalized_runtime_bridge_text(projected)

    assert get_adapter(runtime).format_command(command_name) in projected
    assert len(normalized_projected) <= budget
    assert len(projected) <= STAGED_PROJECTED_COMMAND_CHAR_BUDGET


@pytest.mark.parametrize("command_name", STAGED_INIT_TARGET_COMMANDS)
@pytest.mark.parametrize("runtime", NON_NATIVE_RUNTIME_PROJECTION_TARGETS)
def test_staged_init_target_non_native_command_shims_use_exact_runtime_bridge(
    command_name: str,
    runtime: str,
    tmp_path: Path,
) -> None:
    descriptor = get_runtime_descriptor(runtime)
    target_dir = tmp_path / descriptor.config_dir_name
    bridge = runtime_bridge_command(runtime, target_dir)

    projected = _project_command_for_runtime(command_name, runtime, target_dir)

    assert get_adapter(runtime).format_command(command_name) in projected
    assert has_staged_shim_sentinel(projected)
    assert _expected_target_init_command(command_name, bridge) in first_runnable_shell_commands(projected)
    assert f"gpd --raw init {command_name}" not in "\n".join(shell_fence_bodies(projected))


@pytest.mark.parametrize("command_name", RUNTIME_BRIDGE_ACCEPTANCE_COMMANDS)
@pytest.mark.parametrize("runtime", RUNTIMES)
def test_runtime_projected_command_surfaces_only_embed_active_runtime_bridge(
    command_name: str,
    runtime: str,
    tmp_path: Path,
) -> None:
    descriptor = get_runtime_descriptor(runtime)
    target_dir = tmp_path / descriptor.config_dir_name
    projected = _project_command_for_runtime(command_name, runtime, target_dir)
    require_bridge = command_name in STAGED_INIT_TARGET_COMMANDS and not descriptor.native_include_support

    assert_runtime_bridge_targets_active_runtime(
        projected,
        runtime=runtime,
        label=f"{runtime} {command_name}",
        require_bridge=require_bridge,
    )


@pytest.mark.parametrize(
    "case",
    STAGED_COMMAND_PROJECTION_CASES,
    ids=lambda case: case.command_name,
)
@pytest.mark.parametrize("runtime", RUNTIMES)
def test_runtime_projected_staged_commands_use_native_include_or_compact_stage_shim(
    case: StagedCommandProjectionCase,
    runtime: str,
) -> None:
    command_name = case.command_name
    projected = _project_markdown(COMMANDS_DIR / f"{command_name}.md", runtime, is_agent=False)
    descriptor = get_runtime_descriptor(runtime)

    assert_no_unresolved_include_markers(projected, label=f"{runtime} {command_name}")
    assert get_adapter(runtime).format_command(command_name) in projected

    if descriptor.native_include_support:
        for include_path in case.native_include_paths:
            assert raw_include_count(projected, include_path) == 1
        assert raw_include_count(projected, f"workflows/{command_name}-stage-manifest.json") == 0
        assert f"<!-- [included: {command_name}.md] -->" not in projected
        assert not has_staged_shim_sentinel(projected)
        return

    init_lines = tuple(line.strip() for line in projected.splitlines() if f"--raw init {command_name}" in line)

    assert raw_include_count(projected, f"workflows/{command_name}.md") == 0
    assert f"<!-- [included: {command_name}.md] -->" not in projected
    assert not has_help_bridge_shim_sentinel(projected)
    assert any(f"--stage {case.first_stage_id}" in line for line in init_lines)
    assert_compact_staged_command_shim(
        projected,
        command_name=command_name,
        first_stage=case.first_stage_id,
        staged_loading_keys=case.staged_loading_keys,
        command_label=get_adapter(runtime).format_command(command_name),
        stage_count=case.stage_count,
    )
    expanded_workflow = expanded_workflow_authority_text(
        WORKFLOWS_DIR,
        command_name,
        src_root=REPO_ROOT / "src/gpd",
        path_prefix="/runtime/",
        runtime=runtime,
    )
    assert len(projected) <= STAGED_PROJECTED_COMMAND_CHAR_BUDGET
    assert len(projected) <= len(expanded_workflow) * 0.85


@pytest.mark.parametrize("command_name", COMPACT_WORKFLOW_COMMANDS)
@pytest.mark.parametrize("runtime", RUNTIMES)
def test_hotspot_commands_use_native_include_or_compact_workflow_reference_shim(
    command_name: str,
    runtime: str,
) -> None:
    projected = _project_markdown(COMMANDS_DIR / f"{command_name}.md", runtime, is_agent=False)
    descriptor = get_runtime_descriptor(runtime)

    assert_no_unresolved_include_markers(projected, label=f"{runtime} {command_name}")
    assert get_adapter(runtime).format_command(command_name) in projected

    if descriptor.native_include_support:
        assert raw_include_count(projected, f"workflows/{command_name}.md") == 1
        assert f"<!-- [included: {command_name}.md] -->" not in projected
        assert not has_workflow_reference_shim_sentinel(projected)
        return

    workflow_source = _read(WORKFLOWS_DIR / f"{command_name}.md")
    expanded_workflow = expand_at_includes(
        workflow_source,
        REPO_ROOT / "src/gpd",
        "/runtime/",
        runtime=runtime,
    )

    assert raw_include_count(projected, f"workflows/{command_name}.md") == 0
    assert f"<!-- [included: {command_name}.md] -->" not in projected
    assert not has_staged_shim_sentinel(projected)
    assert not has_help_bridge_shim_sentinel(projected)
    assert_compact_workflow_reference_shim(
        projected,
        workflow_id=command_name,
        command_label=get_adapter(runtime).format_command(command_name),
    )
    for fragment in COMPACT_WORKFLOW_WRAPPER_CONSTRAINTS.get(command_name, ()):
        assert fragment in projected
    budget = COMPACT_WORKFLOW_REFERENCE_PROJECTION_BUDGETS.get(command_name, {}).get(runtime)
    if budget is None:
        assert len(projected) <= len(expanded_workflow) * 0.85
    else:
        assert len(projected) <= budget["chars"]
        assert len(projected.splitlines()) <= budget["lines"]
    for phrase in COMPACT_WORKFLOW_STALE_WRAPPER_PHRASES.get(command_name, ()):
        assert phrase not in projected


@pytest.mark.parametrize(
    "case",
    STAGED_COMMAND_PROJECTION_CASES,
    ids=lambda case: case.command_name,
)
@pytest.mark.parametrize("runtime", RUNTIMES)
def test_runtime_projected_staged_commands_keep_protocol_bundle_jit_visible_without_catalog_inline(
    case: StagedCommandProjectionCase,
    runtime: str,
) -> None:
    projected = _project_markdown(COMMANDS_DIR / f"{case.command_name}.md", runtime, is_agent=False)
    bundle_fields = staged_command_protocol_bundle_fields(WORKFLOWS_DIR, case.command_name)

    assert_protocol_bundle_jit_shape(
        projected,
        case=case,
        runtime=runtime,
        expected_bundle_fields=bundle_fields,
    )


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_runtime_projected_help_uses_native_include_or_compact_help_bridge_shim(runtime: str) -> None:
    projected = _project_markdown(COMMANDS_DIR / "help.md", runtime, is_agent=False)

    assert_no_unresolved_include_markers(projected, label=f"{runtime} help")
    assert get_adapter(runtime).format_command("help") in projected

    assert raw_include_count(projected, "workflows/help.md") == 0
    assert "<!-- [included: help.md] -->" not in projected
    assert not has_staged_shim_sentinel(projected)
    assert "<current-help-command>" not in projected
    assert "--raw help" in projected
    assert "--raw help --all" in projected
    assert "--raw help --command <name>" in projected
    assert len(projected) < 10_000

    if not get_runtime_descriptor(runtime).native_include_support:
        assert has_help_bridge_shim_sentinel(projected)


_BEGINNER_ENTRYPOINT_EXPECTED_LABELS = {
    "help": ("help",),
    "start": ("help", "start", "tour", "new-project", "new-project --minimal", "map-research", "resume-work"),
    "tour": ("help", "start", "tour", "new-project", "new-project --minimal", "map-research", "resume-work"),
}


def _expected_beginner_entrypoint_label(runtime: str, command_name: str) -> str:
    if command_name == "new-project --minimal":
        return _expected_runtime_command_label(runtime, "new-project", " --minimal")
    return _expected_runtime_command_label(runtime, command_name)


@pytest.mark.parametrize("command_name", ("help", "start", "tour"))
@pytest.mark.parametrize("runtime", RUNTIMES)
def test_runtime_projected_beginner_entrypoints_keep_active_runtime_prefixes(
    runtime: str,
    command_name: str,
) -> None:
    projected = _project_markdown(COMMANDS_DIR / f"{command_name}.md", runtime, is_agent=False)
    descriptor = get_runtime_descriptor(runtime)
    surface = beginner_runtime_surface(runtime)

    assert get_adapter(runtime).format_command(command_name) in projected
    if not descriptor.native_include_support:
        for expected in _BEGINNER_ENTRYPOINT_EXPECTED_LABELS[command_name]:
            assert _expected_beginner_entrypoint_label(runtime, expected) in projected
    assert_no_incompatible_beginner_command_labels(
        projected,
        surface,
        context=f"{runtime} projected {command_name}",
    )


def _manifest_asset_paths(manifest: dict[str, object]) -> set[str]:
    paths: set[str] = set()
    for bundle in manifest["bundles"]:
        assets = bundle["assets"]
        for role_assets in assets.values():
            paths.update(asset["path"] for asset in role_assets)
    return paths


def _assert_staged_protocol_bundle_payload(payload: dict[str, object], *, selected: bool) -> None:
    assert "selected_protocol_bundles" not in payload
    assert "protocol_bundle_asset_paths" not in payload

    manifest = payload["protocol_bundle_load_manifest"]
    assert manifest["selected_bundle_ids"] == payload["selected_protocol_bundle_ids"]
    assert manifest["bundle_count"] == payload["protocol_bundle_count"]

    if selected:
        assert payload["selected_protocol_bundle_ids"] == ["stat-mech-simulation"]
        assert payload["protocol_bundle_count"] == 1
        assert manifest["bundles"][0]["title"] == "Statistical Mechanics Simulation"
        assert "references/protocols/monte-carlo.md" in _manifest_asset_paths(manifest)
        assert "references/protocols/numerical-relativity.md" not in _manifest_asset_paths(manifest)
        assert manifest["bundles"][0]["estimator_policies"]
        assert manifest["bundles"][0]["decisive_artifact_guidance"]
        assert any(
            extension["bundle_id"] == "stat-mech-simulation"
            for extension in payload["protocol_bundle_verifier_extensions"]
        )
    else:
        assert payload["selected_protocol_bundle_ids"] == []
        assert payload["protocol_bundle_count"] == 0
        assert manifest["bundles"] == []
        assert payload["protocol_bundle_verifier_extensions"] == []

    rendered_context = payload.get("protocol_bundle_context")
    if rendered_context:
        if selected:
            assert "Statistical Mechanics Simulation" in rendered_context
            assert "{GPD_INSTALL_DIR}/references/protocols/monte-carlo.md" in rendered_context
            assert "Numerical Relativity" not in rendered_context
        else:
            assert "None selected from project metadata" in rendered_context
            for marker in PROTOCOL_BUNDLE_INLINE_CATALOG_MARKERS:
                assert marker not in rendered_context


@pytest.mark.parametrize("selected", (True, False), ids=("selected", "absent"))
def test_staged_protocol_bundle_payloads_preserve_selected_vs_absent_context(
    tmp_path: Path,
    selected: bool,
) -> None:
    _write_bundle_projection_project(tmp_path, selected=selected)
    payloads = (
        init_plan_phase(tmp_path, "1", stage="planner_authoring"),
        init_execute_phase(tmp_path, "1", stage="wave_planning"),
        init_verify_work(tmp_path, "1", stage="inventory_build"),
        init_quick(tmp_path, "Benchmark lookup", stage="reference_context"),
    )

    for payload in payloads:
        _assert_staged_protocol_bundle_payload(payload, selected=selected)


@pytest.mark.parametrize("runtime", RUNTIMES)
@pytest.mark.parametrize(("command_name", "expected_fragments"), tuple(COMMAND_SURFACES.items()))
def test_runtime_projected_commands_keep_model_visible_contract_wrappers(
    command_name: str, expected_fragments: tuple[str, ...], runtime: str
) -> None:
    projected = _project_markdown(COMMANDS_DIR / f"{command_name}.md", runtime, is_agent=False)

    assert projected.count("## Command Requirements") == 1
    assert runtime_command_visibility_note(runtime) in projected
    for fragment in _runtime_expected_fragments(expected_fragments, runtime=runtime):
        assert fragment in projected, f"{runtime} {command_name} missing {fragment!r}"


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_runtime_projected_peer_review_keeps_publication_lane_boundary_visible(runtime: str) -> None:
    projected = _project_markdown(COMMANDS_DIR / "peer-review.md", runtime, is_agent=False)
    visible_text = _workflow_authority_for_shimmed_projection("peer-review", projected, runtime)

    _assert_fragments_visible(
        visible_text,
        PEER_REVIEW_PUBLICATION_LANE_FRAGMENTS,
        label=f"{runtime} peer-review",
    )


@pytest.mark.parametrize("runtime", RUNTIMES)
@pytest.mark.parametrize(("agent_name", "expected_fragments"), tuple(PLAN_AGENT_SURFACES.items()))
def test_runtime_projected_planner_agent_keeps_plan_contract_guidance_visible(
    agent_name: str,
    expected_fragments: tuple[str, ...],
    runtime: str,
) -> None:
    projected = _project_markdown(AGENTS_DIR / f"{agent_name}.md", runtime, is_agent=True)

    _assert_fragments_visible(projected, expected_fragments, label=f"{runtime} {agent_name}")


@pytest.mark.parametrize("runtime", RUNTIMES)
@pytest.mark.parametrize(("agent_name", "expected_fragments"), tuple(RESULT_AGENT_SURFACES.items()))
def test_runtime_projected_agents_keep_contract_results_guidance_visible(
    agent_name: str,
    expected_fragments: tuple[str, ...],
    runtime: str,
) -> None:
    projected = _project_markdown(AGENTS_DIR / f"{agent_name}.md", runtime, is_agent=True)
    descriptor = get_runtime_descriptor(runtime)

    _assert_fragments_visible(projected, expected_fragments, label=f"{runtime} {agent_name}")
    if agent_name == "gpd-executor":
        validator_text = (
            _project_installed_shared_markdown(TEMPLATES_DIR / "contract-results-schema.md", runtime)
            if descriptor.native_include_support
            else projected
        )
        assert "gpd validate summary-contract" in validator_text


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_runtime_projected_verifier_surface_keeps_one_wrapper_and_stays_within_budget(runtime: str) -> None:
    projected = _project_markdown(AGENTS_DIR / "gpd-verifier.md", runtime, is_agent=True)
    descriptor = get_runtime_descriptor(runtime)
    budget = (
        NATIVE_AGENT_PROJECTION_BUDGETS["gpd-verifier"]
        if descriptor.native_include_support
        else SELECTED_AGENT_PROJECTION_BUDGETS["gpd-verifier"]
    )

    assert projected.count("## Agent Requirements") == 1
    assert projected.index("## Agent Requirements") < projected.index("## Bootstrap Discipline")
    for include_suffix, expanded_heading in VERIFIER_SCHEMA_AUTHORITY_MARKERS:
        assert include_suffix in projected or expanded_heading in projected
    assert len(projected.splitlines()) <= budget["lines"]
    assert len(projected) <= budget["chars"]


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_runtime_projected_verify_work_surface_keeps_concise_guidance_visible(runtime: str) -> None:
    projected = _project_markdown(COMMANDS_DIR / "verify-work.md", runtime, is_agent=False)
    descriptor = get_runtime_descriptor(runtime)
    visible_text = (
        _project_installed_shared_markdown(WORKFLOWS_DIR / "verify-work" / "session-router.md", runtime)
        if descriptor.native_include_support or has_compact_non_native_shim(projected)
        else projected
    )

    if descriptor.native_include_support:
        assert raw_include_count(projected, "workflows/verify-work/session-router.md") == 1
        assert raw_include_count(projected, "workflows/verify-work.md") == 0
    _assert_fragments_visible(
        visible_text,
        VERIFY_WORK_CONCISE_GUIDANCE_FRAGMENTS,
        label=f"{runtime} verify-work",
    )
    for fragment in VERIFY_WORK_LATE_STAGE_FRAGMENTS:
        assert fragment not in visible_text


def test_verify_work_sources_keep_canonical_command_labels_before_projection() -> None:
    source_text = "\n".join(
        _read(path)
        for path in (
            COMMANDS_DIR / "verify-work.md",
            WORKFLOWS_DIR / "verify-work.md",
            AGENTS_DIR / "gpd-verifier.md",
        )
    )

    for forbidden in VERIFY_WORK_FORBIDDEN_SOURCE_COMMAND_PREFIXES:
        assert forbidden not in source_text


@pytest.mark.parametrize("runtime", PUBLIC_NEXT_UP_PROJECTION_RUNTIMES)
def test_runtime_projected_public_next_up_and_stage_stop_rewrite_canonical_runtime_labels(
    runtime: str,
    tmp_path: Path,
) -> None:
    descriptor = get_runtime_descriptor(runtime)
    target_dir = tmp_path / descriptor.config_dir_name
    source = (
        "---\n"
        "name: gpd:projection-probe\n"
        "description: Projection probe\n"
        "allowed-tools:\n"
        "  - shell\n"
        "---\n"
        "Internal staged loading remains shell-only, not a public route:\n"
        "\n"
        "```bash\n"
        'gpd --raw init verify-work "$PHASE" --stage gap_repair\n'
        "```\n"
        "\n"
        "## > Next Up\n"
        "\n"
        "Primary: `gpd:verify-work 02`\n"
        "\n"
        "Public stage-stop envelope:\n"
        "\n"
        "stage_stop:\n"
        "  status: blocked\n"
        '  next_runtime_command: "gpd:verify-work 02"\n'
        "  also_available:\n"
        '    - "gpd:resume-work"\n'
        '    - "gpd:suggest-next"\n'
    )

    projected = _project_fixture_command(source, runtime, target_dir)
    next_up = _extract_next_up_snippet(projected)
    stage_stop = _extract_stage_stop_snippet(projected)
    projected_public_surface = next_up + "\n" + stage_stop
    expected_verify_work = _expected_runtime_command_label(runtime, "verify-work", " 02")
    expected_resume_work = _expected_runtime_command_label(runtime, "resume-work")
    expected_suggest_next = _expected_runtime_command_label(runtime, "suggest-next")

    assert expected_verify_work in next_up
    assert expected_verify_work in stage_stop
    assert expected_resume_work in stage_stop
    assert expected_suggest_next in stage_stop
    for command_name in ("verify-work", "resume-work", "suggest-next"):
        for forbidden_label in _wrong_runtime_command_labels(runtime, command_name):
            assert forbidden_label not in projected_public_surface
    assert "`gpd:verify-work 02`" not in next_up
    assert '"gpd:verify-work 02"' not in stage_stop
    for snippet in (next_up, stage_stop):
        for forbidden in PUBLIC_NEXT_UP_FORBIDDEN_PROJECTION_FRAGMENTS:
            assert forbidden not in snippet


@pytest.mark.parametrize("runtime", PUBLIC_NEXT_UP_PROJECTION_RUNTIMES)
def test_runtime_projected_after_this_command_uses_native_label_without_meta_instruction(runtime: str) -> None:
    projected = _project_markdown(COMMANDS_DIR / "new-project.md", runtime, is_agent=False)
    after_lines = tuple(line for line in projected.splitlines() if "After this command" in line)
    text = "\n".join(after_lines)
    expected_discuss_phase = _expected_runtime_command_label(runtime, "discuss-phase", " 1")

    assert after_lines
    assert expected_discuss_phase in text
    assert "show native runtime label" not in text.casefold()
    for forbidden_label in _wrong_runtime_command_labels(runtime, "discuss-phase"):
        assert forbidden_label not in text
    for forbidden in PUBLIC_NEXT_UP_FORBIDDEN_PROJECTION_FRAGMENTS:
        assert forbidden not in text


@pytest.mark.parametrize("runtime", PUBLIC_NEXT_UP_PROJECTION_RUNTIMES)
def test_runtime_projected_after_this_completes_rewrites_public_transition_labels(
    runtime: str,
    tmp_path: Path,
) -> None:
    descriptor = get_runtime_descriptor(runtime)
    target_dir = tmp_path / descriptor.config_dir_name
    source = (
        "---\n"
        "name: gpd:projection-probe\n"
        "description: Projection probe\n"
        "allowed-tools:\n"
        "  - shell\n"
        "---\n"
        "Internal staged loading remains shell-only, not a public route:\n"
        "\n"
        "```bash\n"
        'gpd --raw init resume-work "$ARGUMENTS" --stage resume_routing\n'
        "```\n"
        "\n"
        "## > Next Up\n"
        "\n"
        "Primary local transition: `gpd state advance --phase 02`\n"
        "\n"
        "**After this completes:** `gpd:resume-work`\n"
        "\n"
        "Secondary: `gpd:suggest-next`\n"
        "\n"
        "stage_stop:\n"
        "  status: checkpoint\n"
        '  next_runtime_command: "gpd:resume-work"\n'
        "  also_available:\n"
        '    - "gpd:suggest-next"\n'
    )

    projected = _project_fixture_command(source, runtime, target_dir)
    next_up = _extract_next_up_snippet(projected)
    stage_stop = _extract_stage_stop_snippet(projected)
    projected_public_surface = next_up + "\n" + stage_stop
    expected_resume_work = _expected_runtime_command_label(runtime, "resume-work")
    expected_suggest_next = _expected_runtime_command_label(runtime, "suggest-next")

    assert f"**After this completes:** `{expected_resume_work}`" in next_up
    assert expected_suggest_next in next_up
    assert expected_resume_work in stage_stop
    assert expected_suggest_next in stage_stop
    for command_name in ("resume-work", "suggest-next"):
        for forbidden_label in _wrong_runtime_command_labels(runtime, command_name):
            assert forbidden_label not in projected_public_surface
    assert "`gpd:resume-work`" not in next_up
    assert '"gpd:resume-work"' not in stage_stop
    for snippet in (next_up, stage_stop):
        for forbidden in PUBLIC_NEXT_UP_FORBIDDEN_PROJECTION_FRAGMENTS:
            assert forbidden not in snippet


@pytest.mark.parametrize("runtime", NON_NATIVE_RUNTIME_PROJECTION_TARGETS)
def test_compact_shim_public_next_up_and_stage_stop_keep_raw_loader_private(
    runtime: str,
    tmp_path: Path,
) -> None:
    descriptor = get_runtime_descriptor(runtime)
    target_dir = tmp_path / descriptor.config_dir_name
    bridge = runtime_bridge_command(runtime, target_dir)
    source = (
        "---\n"
        "name: gpd:verify-work\n"
        "description: Projection probe\n"
        "allowed-tools:\n"
        "  - shell\n"
        "---\n"
        "\n"
        "<execution_context>\n"
        "@{GPD_INSTALL_DIR}/workflows/verify-work.md\n"
        "</execution_context>\n"
        "\n"
        "## > Next Up\n"
        "\n"
        "Primary: `gpd:verify-work 02`\n"
        "\n"
        "Public stage-stop envelope:\n"
        "\n"
        "stage_stop:\n"
        "  status: blocked\n"
        '  next_runtime_command: "gpd:verify-work 02"\n'
        "  also_available:\n"
        '    - "gpd:resume-work"\n'
        '    - "gpd:suggest-next"\n'
    )

    projected = _project_fixture_command(
        source,
        runtime,
        target_dir,
        command_name="verify-work",
        src_root=REPO_ROOT / "src/gpd",
    )
    next_up = _extract_next_up_snippet(projected)
    stage_stop = _extract_stage_stop_snippet(projected)
    projected_public_surface = next_up + "\n" + stage_stop
    expected_verify_work = _expected_runtime_command_label(runtime, "verify-work", " 02")
    expected_resume_work = _expected_runtime_command_label(runtime, "resume-work")
    expected_suggest_next = _expected_runtime_command_label(runtime, "suggest-next")

    assert has_staged_shim_sentinel(projected)
    assert _expected_target_init_command("verify-work", bridge) in first_runnable_shell_commands(projected)
    assert expected_verify_work in next_up
    assert expected_verify_work in stage_stop
    assert expected_resume_work in stage_stop
    assert expected_suggest_next in stage_stop
    for command_name in ("verify-work", "resume-work", "suggest-next"):
        for forbidden_label in _wrong_runtime_command_labels(runtime, command_name):
            assert forbidden_label not in projected_public_surface
    assert "`gpd:verify-work 02`" not in next_up
    assert '"gpd:verify-work 02"' not in stage_stop
    for snippet in (next_up, stage_stop):
        for forbidden in PUBLIC_NEXT_UP_FORBIDDEN_PROJECTION_FRAGMENTS:
            assert forbidden not in snippet


@pytest.mark.parametrize("runtime", RUNTIMES)
@pytest.mark.parametrize("command_name", SPAWN_CONTRACT_COMMANDS)
def test_runtime_projected_spawn_contract_blocks_match_canonical_command_content(
    command_name: str,
    runtime: str,
) -> None:
    projected = _project_markdown(COMMANDS_DIR / f"{command_name}.md", runtime, is_agent=False)
    descriptor = get_runtime_descriptor(runtime)
    projected_contracts = _extract_spawn_contracts(projected)
    source_text = _read(COMMANDS_DIR / f"{command_name}.md")
    expanded_contracts = _extract_spawn_contracts(
        expand_at_includes(
            source_text,
            REPO_ROOT / "src/gpd",
            "/runtime/",
            runtime=runtime,
        )
    )
    source_contracts = _extract_spawn_contracts(source_text)

    if descriptor.native_include_support:
        assert projected_contracts == source_contracts
        if not source_contracts and expanded_contracts:
            assert "@/runtime/get-physics-done/workflows/" in projected
        return

    if has_staged_shim_sentinel(projected):
        assert projected_contracts == source_contracts
        assert "staged_loading" in projected
        return

    assert projected_contracts == expanded_contracts


def test_codex_projected_command_surface_matches_install_runtime_rewrites(tmp_path: Path) -> None:
    target_dir = tmp_path / ".codex"
    bridge = runtime_bridge_command("codex", target_dir)
    source = (
        "---\n"
        "name: gpd:projection-probe\n"
        "description: Projection probe\n"
        "allowed-tools:\n"
        "  - shell\n"
        "---\n"
        "Ask ONE question inline (freeform, NOT ask_user):\n"
        "\n"
        "```bash\n"
        "gpd --raw init progress --include state,config\n"
        "```\n"
    )

    projected = _project_fixture_command(source, "codex", target_dir)

    _assert_codex_compact_runtime_note(projected, bridge)
    _assert_codex_inline_freeform_questioning(projected)
    assert f"{bridge} --raw init progress --include state,config" in projected


@pytest.mark.parametrize("runtime", ("codex", "opencode", "copilot-cli"))
def test_codex_opencode_and_copilot_projected_commands_downgrade_non_runnable_shell_fences(
    runtime: str,
    tmp_path: Path,
) -> None:
    descriptor = get_runtime_descriptor(runtime)
    target_dir = tmp_path / descriptor.config_dir_name
    bridge = runtime_bridge_command(runtime, target_dir)
    source = (
        "---\n"
        "name: gpd:projection-probe\n"
        "description: Projection probe\n"
        "allowed-tools:\n"
        "  - shell\n"
        "---\n"
        "```bash\n"
        "gpd status\n"
        "```\n"
        "\n"
        "```bash\n"
        "git status --porcelain\n"
        "```\n"
        "\n"
        "```bash\n"
        "CONTEXT=$(gpd --raw init progress --include state,config)\n"
        'echo "$CONTEXT"\n'
        "```\n"
    )

    projected = _project_fixture_command(source, runtime, target_dir)

    assert f"```bash\n{bridge} status\n```" in projected
    assert "```bash\ngit status --porcelain\n```" not in projected
    assert "```text\ngit status --porcelain\n```" in projected
    assert "```bash\nCONTEXT=$(gpd --raw init progress --include state,config)" not in projected
    assert f"```text\nCONTEXT=$({bridge} --raw init progress --include state,config)" in projected
    assert "CONTEXT=$(gpd --raw init progress --include state,config)" not in projected
    assert "Gemini shell compatibility" not in projected


def test_gemini_projected_command_surface_matches_install_runtime_rewrites(tmp_path: Path) -> None:
    target_dir = tmp_path / ".gemini"
    bridge = runtime_bridge_command("gemini", target_dir)
    source = (
        "---\n"
        "name: gpd:projection-probe\n"
        "description: Projection probe\n"
        "allowed-tools:\n"
        "  - shell\n"
        "---\n"
        "```bash\n"
        "gpd config ensure-section\n"
        "INIT=$(gpd --raw init progress --include state,config)\n"
        "if [ $? -ne 0 ]; then\n"
        '  echo "ERROR: gpd initialization failed: $INIT"\n'
        '  echo "$INIT"\n'
        "  # STOP \u2014 display the error to the user and do not proceed.\n"
        "fi\n"
        "```\n"
    )

    projected = _project_fixture_command(source, "gemini", target_dir)

    assert_runtime_note_tag_count(projected, "gemini_runtime_notes", 1)
    assert_runtime_note_tag_count(projected, "gemini_shell_runtime_notes", 1)
    shell_text = "\n".join(shell_fence_bodies(projected))
    assert first_runnable_shell_commands(projected) == (
        f"{bridge} config ensure-section",
        f'{bridge} config set model_profile "$PROFILE"',
    )
    assert f"{bridge} --raw init progress --include state,config" not in shell_text
    assert "INIT=$(gpd --raw init progress --include state,config)" not in projected
    assert 'echo "$INIT"' not in projected


def test_gemini_projected_shell_allowlist_matches_policy_prefixes(tmp_path: Path) -> None:
    target_dir = tmp_path / ".gemini"
    bridge = runtime_bridge_command("gemini", target_dir)
    source = (
        "---\n"
        "name: gpd:projection-probe\n"
        "description: Projection probe\n"
        "allowed-tools:\n"
        "  - shell\n"
        "---\n"
        "Runnable contract persistence must be file-backed in Gemini:\n"
        "\n"
        "```bash\n"
        "printf '%s\\n' \"$PROJECT_CONTRACT_JSON\" | gpd --raw validate project-contract - --mode approved\n"
        "```\n"
        "\n"
        "```bash\n"
        "git init\n"
        "```\n"
        "\n"
        "```bash\n"
        "mkdir -p GPD\n"
        "```\n"
        "\n"
        "Non-runnable contract-variable shorthand, for explanation only:\n"
        "\n"
        "```text\n"
        "PROJECT_CONTRACT_JSON={...}\n"
        "printf '%s\\n' \"$PROJECT_CONTRACT_JSON\"\n"
        "```\n"
    )

    projected = _project_fixture_command(source, "gemini", target_dir)
    policy_prefixes = tuple(tomllib.loads(gemini_module._render_gemini_policy_toml(bridge))["rule"][0]["commandPrefix"])

    assert policy_prefixes == gemini_module._gemini_policy_command_prefixes(bridge)
    for prefix in policy_prefixes:
        assert f"  - `{prefix}`" in projected
    assert all("PROJECT_CONTRACT_JSON" not in prefix for prefix in policy_prefixes)
    assert all(not prefix.startswith("printf") for prefix in policy_prefixes)

    shell_bodies = shell_fence_bodies(projected)
    assert shell_bodies
    first_commands = first_runnable_shell_commands(projected)
    assert first_commands == (
        f"{bridge} --raw validate project-contract GPD/.approved-project-contract.json --mode approved",
        "git init",
        "mkdir -p GPD",
    )
    assert all(command.startswith(policy_prefixes) for command in first_commands)
    assert "PROJECT_CONTRACT_JSON" not in "\n".join(shell_bodies)
    assert "printf '%s\\n'" not in "\n".join(shell_bodies)
    assert "```text\nPROJECT_CONTRACT_JSON={...}" in projected


def test_gemini_real_command_shell_fences_start_with_policy_prefixes(tmp_path: Path) -> None:
    target_dir = tmp_path / ".gemini"
    bridge = runtime_bridge_command("gemini", target_dir)
    policy_prefixes = gemini_module._gemini_policy_command_prefixes(bridge)
    offenders: list[str] = []

    for command_name in _command_names():
        projected = project_markdown_for_runtime(
            _read(COMMANDS_DIR / f"{command_name}.md"),
            runtime="gemini",
            path_prefix="./.gemini/",
            surface_kind="command",
            install_scope="--local",
            workflow_target_dir=target_dir,
            command_name=command_name,
        )
        for body in shell_fence_bodies(projected):
            classification = gemini_module.classify_gemini_shell_fence_body(body, bridge_command=bridge)
            first_command = classification.first_runnable_command
            if classification.kind not in {"runnable-bridge", "policy-static"}:
                detail = first_command or "no runnable command"
                reasons = ", ".join(classification.reasons)
                offenders.append(f"{command_name}: {classification.kind}: {detail} ({reasons})")
            elif first_command is None or not first_command.startswith(policy_prefixes):
                offenders.append(f"{command_name}: {classification.kind}: {first_command or 'no runnable command'}")

    assert offenders == []


@pytest.mark.parametrize("runtime", ("claude-code", "opencode"))
def test_projected_command_surfaces_rewrite_fenced_cli_invocations_to_runtime_bridge(
    runtime: str,
    tmp_path: Path,
) -> None:
    descriptor = get_runtime_descriptor(runtime)
    target_dir = tmp_path / descriptor.config_dir_name
    bridge = runtime_bridge_command(runtime, target_dir)
    source = (
        "---\n"
        "name: gpd:projection-probe\n"
        "description: Projection probe\n"
        "allowed-tools:\n"
        "  - shell\n"
        "---\n"
        "Inline `gpd --raw init progress` stays prose.\n"
        "\n"
        "```bash\n"
        "gpd --raw init progress --include state,config\n"
        "```\n"
    )

    projected = _project_fixture_command(source, runtime, target_dir)

    assert f"{bridge} --raw init progress --include state,config" in projected
    assert "Inline `gpd --raw init progress` stays prose." in projected


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_projected_command_surfaces_rewrite_tilde_fenced_cli_invocations_to_runtime_bridge(
    runtime: str,
    tmp_path: Path,
) -> None:
    descriptor = get_runtime_descriptor(runtime)
    target_dir = tmp_path / descriptor.config_dir_name
    bridge = runtime_bridge_command(runtime, target_dir)
    source = (
        "---\n"
        "name: gpd:projection-probe\n"
        "description: Projection probe\n"
        "allowed-tools:\n"
        "  - shell\n"
        "---\n"
        "Inline `gpd status` stays prose.\n"
        "\n"
        "~~~bash\n"
        "gpd --raw init progress --include state,config\n"
        "~~~\n"
    )

    projected = _project_fixture_command(source, runtime, target_dir)

    assert f"{bridge} --raw init progress --include state,config" in projected
    assert "Inline `gpd status` stays prose." in projected
