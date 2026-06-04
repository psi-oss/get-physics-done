"""Shared helpers for CLI tests."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path

from typer.testing import CliRunner, Result

from gpd.core.constants import STATE_JSON_BACKUP_FILENAME
from gpd.core.costs import (
    CostBudgetThresholdSummary,
    CostProjectSummary,
    CostSessionSummary,
    CostSummary,
    _profile_tier_mix,
)
from gpd.core.reproducibility import compute_sha256
from gpd.core.resume_surface import RESUME_BACKEND_ONLY_FIELDS
from gpd.core.state import default_state_dict, generate_state_markdown, save_state_json, save_state_markdown
from tests.manuscript_test_support import CANONICAL_MANUSCRIPT_STEM
from tests.manuscript_test_support import manuscript_path as canonical_manuscript_path
from tests.runtime_test_support import PRIMARY_RUNTIME, runtime_display_name


class StableCliRunner(CliRunner):
    def invoke(self, *args, **kwargs):
        kwargs.setdefault("color", False)
        return super().invoke(*args, **kwargs)


_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def normalize_cli_output(text: str) -> str:
    return " ".join(_ANSI_ESCAPE_RE.sub("", text).split())


def _safe_stderr(result: Result) -> str:
    try:
        return result.stderr
    except ValueError:
        return ""


def _result_failure_message(result: Result, expected_exit: int) -> str:
    details = [
        f"expected exit code {expected_exit}, got {result.exit_code}",
        f"stdout:\n{result.output}",
    ]
    stderr = _safe_stderr(result)
    if stderr:
        details.append(f"stderr:\n{stderr}")
    if result.exception is not None:
        details.append(f"exception: {result.exception!r}")
    return "\n\n".join(details)


def assert_result_exit(result: Result, expected_exit: int = 0) -> None:
    assert result.exit_code == expected_exit, _result_failure_message(result, expected_exit)


def assert_cli_success(result: Result, expected_exit: int = 0) -> Result:
    """Assert a CLI result exited successfully and return it for chaining."""

    assert_result_exit(result, expected_exit)
    return result


def cli_text(result: Result, *, normalized: bool = True, expect_exit: int | None = None) -> str:
    """Return CLI output with optional exit validation and normalization."""

    if expect_exit is not None:
        assert_result_exit(result, expect_exit)
    text = _ANSI_ESCAPE_RE.sub("", result.output)
    return normalize_cli_output(text) if normalized else text


def assert_cli_human_contract(
    result_or_text: Result | str,
    *,
    required_all: Sequence[str] = (),
    required_any: Sequence[str] = (),
    forbidden: Sequence[str] = (),
    normalize: bool = True,
    expect_exit: int | None = 0,
) -> str:
    """Assert normalized human CLI text contains required fragments and excludes stale ones."""

    text = _text_from_result_or_text(result_or_text, normalize=normalize, expect_exit=expect_exit)
    required_all_pairs = _contract_fragment_pairs(required_all, normalize=normalize)
    required_any_pairs = _contract_fragment_pairs(required_any, normalize=normalize)
    forbidden_pairs = _contract_fragment_pairs(forbidden, normalize=normalize)

    failures: list[str] = []
    missing_all = [fragment for fragment, needle in required_all_pairs if needle not in text]
    if missing_all:
        failures.append(f"missing required fragments: {missing_all!r}")
    if required_any_pairs and not any(needle in text for _fragment, needle in required_any_pairs):
        failures.append(f"missing any required fragment from: {[fragment for fragment, _needle in required_any_pairs]!r}")
    unexpected = [fragment for fragment, needle in forbidden_pairs if needle in text]
    if unexpected:
        failures.append(f"unexpected forbidden fragments: {unexpected!r}")
    if failures:
        raise AssertionError("CLI human contract failed:\n" + "\n".join(failures) + f"\n\noutput:\n{text}")
    return text


def assert_cli_json_subset(
    result_or_payload: Result | object,
    expected_subset: object,
    *,
    expected_exit: int | None = 0,
) -> object:
    """Assert a CLI JSON payload contains ``expected_subset`` recursively."""

    payload = _json_from_result_or_payload(result_or_payload, expected_exit=expected_exit)
    _assert_json_subset(payload, expected_subset, path="$")
    return payload


def assert_cli_json_contract(
    result_or_payload: Result | object,
    *,
    expected_subset: object | None = None,
    required_keys: Sequence[str] = (),
    forbidden_keys: Sequence[str] = (),
    expected_exit: int | None = 0,
) -> dict[str, object]:
    """Assert top-level JSON object shape without relaxing exact contracts by default."""

    payload = _json_from_result_or_payload(result_or_payload, expected_exit=expected_exit)
    if not isinstance(payload, dict):
        raise AssertionError(f"expected JSON object payload, got {type(payload).__name__}: {payload!r}")

    if expected_subset is not None:
        _assert_json_subset(payload, expected_subset, path="$")
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise AssertionError(f"missing required JSON keys: {missing!r}\n\npayload:\n{payload!r}")
    unexpected = [key for key in forbidden_keys if key in payload]
    if unexpected:
        raise AssertionError(f"unexpected forbidden JSON keys: {unexpected!r}\n\npayload:\n{payload!r}")
    return payload


def assert_cli_help_contract(
    text_or_result: Result | str,
    *,
    commands: Sequence[str] = (),
    options: Sequence[str] = (),
    sections: Sequence[str] = (),
    forbidden: Sequence[str] = (),
    normalize: bool = True,
    expect_exit: int | None = 0,
) -> str:
    """Assert common CLI help surface fragments with grouped diagnostics."""

    text = _text_from_result_or_text(text_or_result, normalize=normalize, expect_exit=expect_exit)
    failures: list[str] = []
    for label, fragments in (
        ("commands", commands),
        ("options", options),
        ("sections", sections),
    ):
        missing = [
            fragment
            for fragment, needle in _contract_fragment_pairs(fragments, normalize=normalize)
            if needle not in text
        ]
        if missing:
            failures.append(f"missing help {label}: {missing!r}")
    unexpected = [
        fragment
        for fragment, needle in _contract_fragment_pairs(forbidden, normalize=normalize)
        if needle in text
    ]
    if unexpected:
        failures.append(f"unexpected help fragments: {unexpected!r}")
    if failures:
        raise AssertionError("CLI help contract failed:\n" + "\n".join(failures) + f"\n\noutput:\n{text}")
    return text


def assert_no_traceback(result: Result) -> Result:
    """Assert a CLI result did not print a Python traceback."""

    combined = f"{result.output}\n{_safe_stderr(result)}"
    assert "Traceback" not in combined, f"unexpected traceback in CLI output:\n{combined}"
    return result


def invoke_cli(
    runner: CliRunner,
    app: object,
    args: Sequence[str],
    *,
    expect_exit: int | None = 0,
    **kwargs: object,
) -> Result:
    result = runner.invoke(app, list(args), **kwargs)
    if expect_exit is not None:
        assert_result_exit(result, expect_exit)
    return result


def json_output_from_result(result: Result, *, expect_exit: int = 0) -> object:
    assert_result_exit(result, expect_exit)
    return json.loads(result.output)


def invoke_json(
    runner: CliRunner,
    app: object,
    args: Sequence[str],
    *,
    expect_exit: int = 0,
    **kwargs: object,
) -> object:
    return json_output_from_result(invoke_cli(runner, app, args, expect_exit=None, **kwargs), expect_exit=expect_exit)


def invoke_raw_json(
    runner: CliRunner,
    app: object,
    args: Sequence[str],
    *,
    expect_exit: int = 0,
    **kwargs: object,
) -> dict[str, object]:
    payload = invoke_json(runner, app, args, expect_exit=expect_exit, **kwargs)
    assert isinstance(payload, dict)
    return payload


def invoke_help_text(
    runner: CliRunner,
    app: object,
    args: Sequence[str],
    *,
    expect_exit: int = 0,
    **kwargs: object,
) -> str:
    result = invoke_cli(runner, app, [*args, "--help"], expect_exit=expect_exit, **kwargs)
    return normalize_cli_output(result.output)


def _text_from_result_or_text(
    result_or_text: Result | str,
    *,
    normalize: bool,
    expect_exit: int | None,
) -> str:
    if isinstance(result_or_text, Result):
        return cli_text(result_or_text, normalized=normalize, expect_exit=expect_exit)
    text = _ANSI_ESCAPE_RE.sub("", result_or_text)
    return normalize_cli_output(text) if normalize else text


def _contract_fragment_pairs(fragments: Sequence[str], *, normalize: bool) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for fragment in fragments:
        needle = normalize_cli_output(fragment) if normalize else _ANSI_ESCAPE_RE.sub("", fragment)
        if needle == "":
            raise AssertionError("CLI contract fragments must be non-empty after normalization")
        pairs.append((fragment, needle))
    return tuple(pairs)


def _json_from_result_or_payload(result_or_payload: Result | object, *, expected_exit: int | None) -> object:
    if not isinstance(result_or_payload, Result):
        return result_or_payload
    if expected_exit is not None:
        assert_result_exit(result_or_payload, expected_exit)
    candidates = [result_or_payload.output]
    stderr = _safe_stderr(result_or_payload)
    if stderr:
        candidates.append(stderr)
    for candidate in candidates:
        text = candidate.strip()
        if not text:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue
    raise AssertionError(f"result did not contain JSON:\n{result_or_payload.output}")


def _assert_json_subset(actual: object, expected: object, *, path: str) -> None:
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping):
            raise AssertionError(f"{path}: expected JSON object subset, got {type(actual).__name__}: {actual!r}")
        for key, expected_value in expected.items():
            if key not in actual:
                raise AssertionError(f"{_json_child_path(path, key)}: missing key; available keys: {list(actual)!r}")
            _assert_json_subset(actual[key], expected_value, path=_json_child_path(path, key))
        return

    if isinstance(expected, list):
        if not isinstance(actual, list):
            raise AssertionError(f"{path}: expected JSON list subset, got {type(actual).__name__}: {actual!r}")
        if len(actual) < len(expected):
            raise AssertionError(f"{path}: expected at least {len(expected)} list item(s), got {len(actual)}")
        for index, expected_item in enumerate(expected):
            _assert_json_subset(actual[index], expected_item, path=f"{path}[{index}]")
        return

    if actual != expected:
        raise AssertionError(f"{path}: expected {expected!r}, got {actual!r}")


def _json_child_path(path: str, key: object) -> str:
    key_text = str(key)
    if key_text.isidentifier():
        return f"{path}.{key_text}"
    return f"{path}[{key_text!r}]"


def checks_by_name(payload: dict[str, object], *, key: str = "checks") -> dict[str, dict[str, object]]:
    checks = payload[key]
    assert isinstance(checks, list)
    return {str(check["name"]): check for check in checks if isinstance(check, dict)}


def assert_check(
    payload: dict[str, object],
    name: str,
    *,
    passed: bool | None = None,
    blocking: bool | None = None,
    detail: str | None = None,
    detail_contains: str | Sequence[str] = (),
    detail_startswith: str | None = None,
) -> dict[str, object]:
    check = checks_by_name(payload)[name]
    if passed is not None:
        assert check["passed"] is passed
    if blocking is not None:
        assert check["blocking"] is blocking
    check_detail = str(check.get("detail", ""))
    if detail is not None:
        assert check_detail == detail
    if detail_startswith is not None:
        assert check_detail.startswith(detail_startswith)
    fragments = (detail_contains,) if isinstance(detail_contains, str) else detail_contains
    for fragment in fragments:
        assert fragment in check_detail
    return check


def assert_checks_pass(payload: dict[str, object], *names: str) -> None:
    for name in names:
        assert_check(payload, name, passed=True)


def assert_checks_fail(payload: dict[str, object], *names: str) -> None:
    for name in names:
        assert_check(payload, name, passed=False)


def assert_no_checks(payload: dict[str, object], *names: str) -> None:
    checks = checks_by_name(payload)
    for name in names:
        assert name not in checks


def artifact_manifest_payload(
    manuscript: Path,
    *,
    title: str = "Curvature Flow Bounds",
    journal: str = "prl",
    artifact_id: str = "tex-paper",
    artifact_path: str | None = None,
    produced_by: str = "test",
) -> dict[str, object]:
    digest = compute_sha256(manuscript)
    return {
        "version": 1,
        "paper_title": title,
        "journal": journal,
        "created_at": "2026-04-02T00:00:00+00:00",
        "manuscript_sha256": digest,
        "manuscript_mtime_ns": manuscript.stat().st_mtime_ns,
        "artifacts": [
            {
                "artifact_id": artifact_id,
                "category": "tex",
                "path": artifact_path or manuscript.name,
                "sha256": digest,
                "produced_by": produced_by,
                "sources": [],
                "metadata": {},
            }
        ],
    }


def write_managed_publication_manuscript(
    project_root: Path,
    *,
    subject_slug: str = "curvature-flow",
    stem: str = "managed_manuscript",
    body: str = "Managed manuscript.",
    produced_by: str = "tests.test_cli_commands",
) -> Path:
    manuscript_dir = project_root / "GPD" / "publication" / subject_slug / "manuscript"
    manuscript_dir.mkdir(parents=True, exist_ok=True)
    manuscript = manuscript_dir / f"{stem}.tex"
    manuscript.write_text(
        f"\\documentclass{{article}}\n\\begin{{document}}\n{body}\n\\end{{document}}\n",
        encoding="utf-8",
    )
    compiled_manuscript = manuscript.with_suffix(".pdf")
    compiled_manuscript.write_bytes(b"%PDF-1.4\n% fake managed arxiv submission pdf\n")
    (manuscript_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Managed Manuscript",
                "output_filename": stem,
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Introduction", "content": body}],
            }
        ),
        encoding="utf-8",
    )
    (manuscript_dir / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(
            {
                "version": 1,
                "paper_title": "Managed Manuscript",
                "journal": "prl",
                "created_at": "2026-03-10T00:00:00+00:00",
                "manuscript_sha256": compute_sha256(manuscript),
                "manuscript_mtime_ns": manuscript.stat().st_mtime_ns,
                "artifacts": [
                    {
                        "artifact_id": "managed-manuscript",
                        "category": "tex",
                        "path": f"{stem}.tex",
                        "sha256": compute_sha256(manuscript),
                        "produced_by": produced_by,
                        "sources": [],
                        "metadata": {"role": "manuscript"},
                    },
                    {
                        "artifact_id": "managed-compiled-manuscript",
                        "category": "pdf",
                        "path": f"{stem}.pdf",
                        "sha256": compute_sha256(compiled_manuscript),
                        "produced_by": produced_by,
                        "sources": [{"path": f"{stem}.tex", "role": "compiled_from"}],
                        "metadata": {"role": "compiled_manuscript"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (manuscript_dir / "BIBLIOGRAPHY-AUDIT.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-03-10T00:00:00+00:00",
                "total_sources": 0,
                "resolved_sources": 0,
                "partial_sources": 0,
                "unverified_sources": 0,
                "failed_sources": 0,
                "entries": [],
            }
        ),
        encoding="utf-8",
    )
    (manuscript_dir / "reproducibility-manifest.json").write_text(
        json.dumps(
            {
                "paper_title": "Managed Manuscript",
                "date": "2026-03-10",
                "environment": {
                    "python_version": "3.12.1",
                    "package_manager": "uv",
                    "required_packages": [{"package": "numpy", "version": "1.26.4"}],
                    "lock_file": "pyproject.toml",
                    "system_requirements": {},
                },
                "execution_steps": [{"name": "run", "command": "python scripts/run.py"}],
                "expected_results": [
                    {"quantity": "x", "expected_value": "1", "tolerance": "0.1", "script": "scripts/run.py"}
                ],
                "output_files": [{"path": "results/out.json", "checksum_sha256": "a" * 64}],
                "resource_requirements": [{"step": "run", "cpu_cores": 1, "memory_gb": 1.0}],
                "verification_steps": ["rerun", "compare", "inspect"],
                "minimum_viable": "1 core",
                "recommended": "2 cores",
                "last_verified": "2026-03-10T00:00:00+00:00",
                "last_verified_platform": "macOS-15-arm64",
                "random_seeds": [],
                "seeding_strategy": "",
            }
        ),
        encoding="utf-8",
    )
    return manuscript


def bootstrap_publication_project(project_root: Path) -> None:
    planning = project_root / "GPD"
    planning.mkdir(parents=True, exist_ok=True)
    state = default_state_dict()
    save_state_json(project_root, state)
    save_state_markdown(project_root, generate_state_markdown(state))
    (planning / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    (planning / "CONVENTIONS.md").write_text("# Conventions\n", encoding="utf-8")


def mark_verified_project_root(project_root: Path) -> None:
    planning = project_root / "GPD"
    planning.mkdir(parents=True, exist_ok=True)
    save_state_json(project_root, default_state_dict())
    (planning / "PROJECT.md").write_text("# Project\n", encoding="utf-8")


def write_write_paper_authoring_input(
    workspace: Path,
    *,
    file_name: str = "write-paper-authoring-input.json",
    subject_slug: str = "external-authoring-test",
) -> Path:
    intake_path = workspace / file_name
    intake_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "title": "External Authoring Bounds",
                "authors": [{"name": "A. Researcher", "affiliation": "Example University"}],
                "target_journal": "prl",
                "subject_slug": subject_slug,
                "central_claim": "The controlled benchmark supports a stable external-authoring draft.",
                "claims": [
                    {
                        "id": "CLM-main",
                        "statement": "The benchmarked bound is stable across the resolved regime.",
                        "evidence": {
                            "source_note_ids": ["NOTE-main"],
                            "result_ids": ["RES-main"],
                            "figure_ids": ["FIG-main"],
                            "citation_source_ids": ["cite-main"],
                        },
                    }
                ],
                "source_notes": [
                    {
                        "id": "NOTE-main",
                        "path": "notes/main-result.md",
                        "summary": "Summarizes the decisive benchmark and fit stability.",
                    }
                ],
                "results": [
                    {
                        "id": "RES-main",
                        "summary": "Main fitted bound with uncertainty band.",
                        "source_note_ids": ["NOTE-main"],
                    }
                ],
                "figures": [
                    {
                        "id": "FIG-main",
                        "path": "figures/main-bound.pdf",
                        "caption": "Benchmark comparison supporting the main bound.",
                        "source_note_ids": ["NOTE-main"],
                    }
                ],
                "citation_sources": [
                    {
                        "source_type": "paper",
                        "reference_id": "cite-main",
                        "title": "Benchmark Recovery in a Controlled Regime",
                        "authors": ["A. Author", "B. Author"],
                        "year": "2024",
                        "arxiv_id": "2401.12345",
                    }
                ],
                "notation_note": "Use c = hbar = 1 throughout the draft.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return intake_path


def make_checkout(tmp_path: Path, version: str = "9.9.9") -> Path:
    """Create a minimal GPD source checkout for CLI version tests."""
    repo_root = tmp_path / "checkout"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "package.json").write_text(
        json.dumps(
            {
                "name": "get-physics-done",
                "version": version,
                "gpdPythonVersion": version,
            }
        ),
        encoding="utf-8",
    )
    (repo_root / "pyproject.toml").write_text(
        f'[project]\nname = "get-physics-done"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    gpd_root = repo_root / "src" / "gpd"
    for subdir in ("commands", "agents", "hooks", "specs"):
        (gpd_root / subdir).mkdir(parents=True, exist_ok=True)
    return repo_root


def sample_cost_summary(
    workspace: Path,
    *,
    runtime: str = "runtime-under-test",
    model: str = "model-under-test",
) -> CostSummary:
    workspace_text = str(workspace)
    project = CostProjectSummary(
        project_root=workspace_text,
        record_count=2,
        usage_status="measured",
        cost_status="unavailable",
        interpretation="tokens measured; USD unavailable",
        input_tokens=1200,
        output_tokens=300,
        total_tokens=1500,
        cost_usd=None,
        last_recorded_at="2026-03-27T00:00:00+00:00",
        runtimes=[runtime],
        models=[model],
    )
    current_session = CostSessionSummary(
        session_id="session-123",
        project_root=workspace_text,
        record_count=1,
        usage_status="measured",
        cost_status="unavailable",
        interpretation="tokens measured; USD unavailable",
        input_tokens=800,
        output_tokens=200,
        total_tokens=1000,
        cost_usd=None,
        last_recorded_at="2026-03-27T00:00:00+00:00",
        runtimes=[runtime],
        models=[model],
    )
    return CostSummary(
        project_root=workspace_text,
        active_runtime=runtime,
        active_runtime_capabilities={
            "permissions_surface": "config-file",
            "statusline_surface": "none",
            "notify_surface": "explicit",
            "telemetry_source": "notify-hook",
            "telemetry_completeness": "best-effort",
        },
        model_profile="review",
        runtime_model_selection="runtime defaults",
        profile_tier_mix=_profile_tier_mix("review"),
        current_session_id="session-123",
        project=project,
        current_session=current_session,
        recent_sessions=[current_session],
        budget_thresholds=[
            CostBudgetThresholdSummary(
                scope="project",
                config_key="project_usd_budget",
                budget_usd=1.0,
                spent_usd=0.85,
                remaining_usd=0.15,
                percent_used=85.0,
                cost_status="measured",
                comparison_exact=True,
                state="near_budget",
                message=(
                    "Configured project USD budget is nearing budget based on measured local USD telemetry; "
                    "it stays advisory only and never stops work automatically."
                ),
            )
        ],
        guidance=[
            f"Current model posture: profile `review` with {runtime} runtime defaults. Use `gpd:set-tier-models` to pin explicit tier-1, tier-2, and tier-3 model IDs.",
        ],
    )


def write_install_manifest(
    config_dir: Path, *, runtime: str, install_scope: str = "local", raw: str | None = None
) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = config_dir / "gpd-file-manifest.json"
    if raw is not None:
        manifest_path.write_text(raw, encoding="utf-8")
        return
    manifest_path.write_text(
        json.dumps(
            {
                "runtime": runtime,
                "install_scope": install_scope,
                "explicit_target": False,
            }
        ),
        encoding="utf-8",
    )


class PermissionsTargetAdapter:
    def __init__(
        self,
        *,
        local_target: Path,
        global_target: Path,
        missing_install_artifacts: tuple[str, ...] = (),
    ) -> None:
        self.runtime_name = PRIMARY_RUNTIME
        self.display_name = runtime_display_name(PRIMARY_RUNTIME)
        self._local_target = local_target
        self._global_target = global_target
        self._missing_install_artifacts = missing_install_artifacts

    def resolve_target_dir(self, is_global: bool, cwd: Path) -> Path:
        return self._global_target if is_global else self._local_target

    def validate_target_runtime(self, target_dir: Path, *, action: str) -> None:
        return None

    def missing_install_artifacts(self, target_dir: Path) -> tuple[str, ...]:
        if target_dir == self._local_target:
            return self._missing_install_artifacts
        return ()

    def runtime_permissions_status(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
        return {
            "runtime": self.runtime_name,
            "desired_mode": autonomy,
            "configured_mode": "default",
            "config_aligned": True,
            "requires_relaunch": False,
            "managed_by_gpd": False,
            "message": "configured",
        }

    def sync_runtime_permissions(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
        return self.runtime_permissions_status(target_dir, autonomy=autonomy)


def compact_plan_with_missing_must_surface_benchmark() -> str:
    return (
        "---\n"
        "phase: 01-baseline\n"
        "plan: 01\n"
        "type: execute\n"
        "wave: 1\n"
        "depends_on: []\n"
        "files_modified: []\n"
        "interactive: false\n"
        "conventions:\n"
        "  units: natural\n"
        "contract:\n"
        "  schema_version: 1\n"
        "  scope:\n"
        "    question: Verify the fresh result against the decisive benchmark.\n"
        "    in_scope: [stale verification refresh]\n"
        "  context_intake:\n"
        "    must_read_refs: [ref-stale-verification-benchmark]\n"
        "    must_include_prior_outputs: [GPD/phases/00-baseline/00-SUMMARY.md]\n"
        "    context_gaps: [The decisive benchmark artifact is intentionally absent.]\n"
        "  claims:\n"
        "    - id: claim-stale-verification\n"
        "      statement: Current result agrees with the decisive benchmark.\n"
        "      deliverables: [deliv-stale-verification-data]\n"
        "      acceptance_tests: [test-stale-verification-decisive]\n"
        "      references: [ref-stale-verification-benchmark]\n"
        "  deliverables:\n"
        "    - id: deliv-stale-verification-data\n"
        "      kind: data\n"
        "      path: artifacts/phase4/result.json\n"
        "      description: Fresh numerical result to compare against the benchmark.\n"
        "  references:\n"
        "    - id: ref-stale-verification-benchmark\n"
        "      kind: dataset\n"
        "      locator: artifacts/benchmark/reference.json\n"
        "      role: benchmark\n"
        "      why_it_matters: Decisive benchmark for stale verification detection.\n"
        "      applies_to: [claim-stale-verification]\n"
        "      must_surface: true\n"
        "      required_actions: [read, compare]\n"
        "  acceptance_tests:\n"
        "    - id: test-stale-verification-decisive\n"
        "      subject: claim-stale-verification\n"
        "      kind: benchmark\n"
        "      procedure: Read and compare the decisive benchmark reference.\n"
        "      pass_condition: Current result matches the benchmark within tolerance.\n"
        "      evidence_required: [deliv-stale-verification-data, ref-stale-verification-benchmark]\n"
        "  forbidden_proxies:\n"
        "    - id: fp-stale-verification-prose-only\n"
        "      subject: claim-stale-verification\n"
        "      proxy: Prose-only pass without reading the decisive benchmark.\n"
        "      reason: Would miss stale or absent benchmark evidence.\n"
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Missing benchmark reference]\n"
        "    disconfirming_observations: [Benchmark file is absent]\n"
        "---\n\n"
        "Plan body.\n"
    )


def assert_forbidden_verification_fields_absent(value: object) -> None:
    forbidden_fields = {"runtime", "computational_oracle", "gpd_return"}
    if isinstance(value, dict):
        assert not forbidden_fields.intersection(value)
        for child in value.values():
            assert_forbidden_verification_fields_absent(child)
    elif isinstance(value, list):
        for child in value:
            assert_forbidden_verification_fields_absent(child)


def write_stale_refresh_skeleton_plan(project_root: Path) -> Path:
    phase_dir = project_root / "GPD" / "phases" / "01-baseline"
    phase_dir.mkdir(parents=True)
    baseline_dir = project_root / "GPD" / "phases" / "00-baseline"
    baseline_dir.mkdir(parents=True)
    (baseline_dir / "00-SUMMARY.md").write_text("prior baseline", encoding="utf-8")
    plan_path = phase_dir / "01-PLAN.md"
    plan_path.write_text(compact_plan_with_missing_must_surface_benchmark(), encoding="utf-8")
    return plan_path


def write_verification_body_file(tmp_path: Path, body: str, *, name: str = "verification-body.md") -> Path:
    body_path = tmp_path / name
    body_path.write_text(body, encoding="utf-8")
    return body_path


def raw_payload_from_result(result: Result) -> dict[str, object]:
    candidates = [result.output]
    stderr = _safe_stderr(result)
    if stderr:
        candidates.append(stderr)
    for candidate in candidates:
        text = candidate.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        assert isinstance(payload, dict)
        return payload
    raise AssertionError(f"result did not contain a JSON object:\n{result.output}")


def proof_redteam_markdown(*, claim_id: str, claim_text: str, status: str) -> str:
    return (
        "---\n"
        f"status: {status}\n"
        "reviewer: proof-redteam\n"
        "claim_ids:\n"
        f"  - {claim_id}\n"
        "proof_artifact_paths:\n"
        "  - paper/main.tex\n"
        "missing_parameter_symbols: []\n"
        "missing_hypothesis_ids: []\n"
        "coverage_gaps:\n"
        "  - unresolved coverage pending human review\n"
        "scope_status: unclear\n"
        "quantifier_status: unclear\n"
        "counterexample_status: not_attempted\n"
        "---\n\n"
        "# Proof Redteam\n\n"
        "## Proof Inventory\n\n"
        f"- Exact claim / theorem text: {claim_text}\n\n"
        "## Coverage Ledger\n\n"
        "### Named-Parameter Coverage\n\n"
        "| Parameter | Role / Domain | Proof Location | Status | Notes |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| `r_0` | target radius | paper/main.tex:1 | human_needed | Needs audit. |\n\n"
        "### Hypothesis Coverage\n\n"
        "| Hypothesis | Proof Location | Status | Notes |\n"
        "| --- | --- | --- | --- |\n"
        "| `H1` | paper/main.tex:1 | human_needed | Needs audit. |\n\n"
        "### Quantifier / Domain Coverage\n\n"
        "| Obligation | Proof Location | Status | Notes |\n"
        "| --- | --- | --- | --- |\n"
        "| for every r_0 > 0 | paper/main.tex:1 | human_needed | Needs audit. |\n\n"
        "### Conclusion-Clause Coverage\n\n"
        "| Clause | Proof Location | Status | Notes |\n"
        "| --- | --- | --- | --- |\n"
        "| target annulus is reached | paper/main.tex:1 | human_needed | Needs audit. |\n\n"
        "## Adversarial Probe\n\n"
        "- Probe type: dropped-parameter test\n"
        "- Result: Human audit still required.\n\n"
        "## Verdict\n\n"
        "- Scope status: `unclear`\n"
        "- Quantifier status: `unclear`\n"
        "- Counterexample status: `not_attempted`\n\n"
        "## Required Follow-Up\n\n"
        "- Complete the proof-redteam audit.\n"
    )


def write_recoverable_result_state(tmp_path: Path, state: dict[str, object]) -> None:
    planning = tmp_path / "GPD"
    planning.mkdir(parents=True, exist_ok=True)
    (planning / "state.json").write_text("{not valid json", encoding="utf-8")
    (planning / STATE_JSON_BACKUP_FILENAME).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def write_markdown_recoverable_result_state(tmp_path: Path, state: dict[str, object]) -> None:
    save_state_json(tmp_path, state)
    save_state_markdown(tmp_path, generate_state_markdown(state))
    planning = tmp_path / "GPD"
    (planning / "state.json").write_text("{not valid json", encoding="utf-8")
    (planning / STATE_JSON_BACKUP_FILENAME).write_text("{also not valid json", encoding="utf-8")


def return_skeleton_error_payload(result: Result) -> dict[str, object]:
    text = result.output.strip() or _safe_stderr(result).strip()
    return json.loads(text)


def valid_checkpoint_return_markdown() -> str:
    return (
        "# Summary\n\n```yaml\ngpd_return:\n"
        "  status: checkpoint\n"
        "  files_written: []\n"
        "  issues: []\n"
        "  next_actions: [gpd resume-work]\n"
        "```\n"
    )


def refresh_artifact_manifest_for_manuscript(
    project_root: Path,
    manuscript: Path | None = None,
    *,
    produced_by: str = "tests.test_cli_commands",
) -> None:
    """Keep the publication manifest fresh after tests rewrite the active manuscript."""
    manuscript = manuscript or canonical_manuscript_path(project_root)
    manifest_path = manuscript.parent / "ARTIFACT-MANIFEST.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {
            "version": 1,
            "paper_title": "Test",
            "journal": "prl",
            "created_at": "2026-03-10T00:00:00+00:00",
            "artifacts": [],
        }
    )
    manuscript_sha256 = compute_sha256(manuscript)
    manifest["manuscript_sha256"] = manuscript_sha256
    manifest["manuscript_mtime_ns"] = manuscript.stat().st_mtime_ns
    tex_artifacts = [
        artifact
        for artifact in manifest.get("artifacts", [])
        if isinstance(artifact, dict) and artifact.get("category") == "tex"
    ]
    if not tex_artifacts:
        tex_artifacts = [
            {
                "artifact_id": "manuscript",
                "category": "tex",
                "produced_by": produced_by,
                "sources": [],
                "metadata": {"role": "manuscript"},
            }
        ]
        manifest.setdefault("artifacts", []).extend(tex_artifacts)
    for artifact in tex_artifacts:
        artifact["path"] = manuscript.name
        artifact["sha256"] = manuscript_sha256
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def write_binary_pdf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"2 0 obj\n<< /Length 5 >>\nstream\n\x80\x81\xff\x00\xfe\nendstream\nendobj\n"
        b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"
    )
    return path


def write_minimal_docx(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Override PartName="/word/document.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                "</Types>"
            ),
        )
        archive.writestr(
            "word/document.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body><w:p><w:r><w:t>Theorem. Standalone OOXML intake.</w:t></w:r></w:p></w:body>"
                "</w:document>"
            ),
        )
    return path


def write_minimal_xlsx(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Override PartName="/xl/workbook.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/worksheets/sheet1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                "</Types>"
            ),
        )
        archive.writestr(
            "xl/workbook.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
                "</workbook>"
            ),
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                'Target="worksheets/sheet1.xml"/>'
                "</Relationships>"
            ),
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                "<sheetData>"
                '<row r="1"><c r="A1" t="inlineStr"><is><t>claim</t></is></c>'
                '<c r="B1" t="inlineStr"><is><t>evidence</t></is></c></row>'
                '<row r="2"><c r="A2" t="inlineStr"><is><t>main</t></is></c>'
                '<c r="B2" t="inlineStr"><is><t>table</t></is></c></row>'
                "</sheetData>"
                "</worksheet>"
            ),
        )
    return path


def fake_pypdf_module(extracted_text: str):
    """Return a fake pypdf module whose PdfReader yields one page with extracted_text."""
    import types

    class _FakePage:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class _FakeReader:
        def __init__(self, _path: object) -> None:
            self.pages = [_FakePage(extracted_text)]

    fake = types.ModuleType("pypdf")
    fake.PdfReader = _FakeReader  # type: ignore[attr-defined]

    def _install() -> None:
        sys.modules["pypdf"] = fake

    def _uninstall() -> None:
        sys.modules.pop("pypdf", None)

    return fake, _install, _uninstall


def fake_pypdf_failure_module(error_message: str):
    """Return a fake pypdf module whose PdfReader raises error_message."""
    import types

    class _FailingReader:
        def __init__(self, _path: object) -> None:
            raise RuntimeError(error_message)

    fake = types.ModuleType("pypdf")
    fake.PdfReader = _FailingReader  # type: ignore[attr-defined]

    def _install() -> None:
        sys.modules["pypdf"] = fake

    def _uninstall() -> None:
        sys.modules.pop("pypdf", None)

    return fake, _install, _uninstall


def fake_pdftotext_run(extracted_text: str):
    def _run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
        assert Path(command[0]).name == "pdftotext"

        output_arg = next(
            (
                Path(str(argument))
                for argument in command[1:]
                if isinstance(argument, str) and argument not in {"-"} and str(argument).endswith(".txt")
            ),
            None,
        )
        if output_arg is not None:
            output_arg.parent.mkdir(parents=True, exist_ok=True)
            output_arg.write_text(extracted_text, encoding="utf-8")

        text_mode = bool(kwargs.get("text"))
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=extracted_text if text_mode else extracted_text.encode("utf-8"),
            stderr="" if text_mode else b"",
        )

    return _run


def fake_pdftotext_failure_run(stderr_text: str, *, returncode: int = 1):
    def _run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
        assert Path(command[0]).name == "pdftotext"

        text_mode = bool(kwargs.get("text"))
        return subprocess.CompletedProcess(
            args=command,
            returncode=returncode,
            stdout="" if text_mode else b"",
            stderr=stderr_text if text_mode else stderr_text.encode("utf-8"),
        )

    return _run


def write_internal_publication_artifacts(project_root: Path, artifact_names: tuple[str, ...]) -> None:
    """Mirror publication review artifacts into the removed internal planning location."""
    internal_dir = project_root / "GPD" / "paper"
    internal_dir.mkdir(parents=True, exist_ok=True)
    paper_dir = project_root / "paper"
    for artifact_name in artifact_names:
        source = paper_dir / artifact_name
        (internal_dir / artifact_name).write_bytes(source.read_bytes())


def write_secondary_manuscript_root(project_root: Path, *, root_name: str = "manuscript") -> Path:
    manuscript_dir = project_root / root_name
    manuscript_dir.mkdir(parents=True, exist_ok=True)
    basename = f"{CANONICAL_MANUSCRIPT_STEM}.tex"
    manuscript = manuscript_dir / basename
    manuscript.write_text(
        "\\documentclass{article}\n\\begin{document}\nSecondary manuscript.\n\\end{document}\n",
        encoding="utf-8",
    )
    (manuscript_dir / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(
            artifact_manifest_payload(
                manuscript,
                artifact_id=f"manuscript-{root_name}",
                produced_by="tests.test_cli_commands",
            )
        ),
        encoding="utf-8",
    )
    return manuscript


def assert_no_top_level_resume_aliases(payload: dict[str, object]) -> None:
    for key in RESUME_BACKEND_ONLY_FIELDS:
        assert key not in payload
