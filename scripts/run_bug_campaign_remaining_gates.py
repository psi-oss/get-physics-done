"""Run local evidence gates that remain after the bug-campaign fix waves.

This script intentionally records *local* evidence.  It does not claim durable
GitHub nightly or release-candidate history, because those gates require CI
history outside the repository checkout.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PHASE10_EVIDENCE_JSON = REPO_ROOT / "artifacts" / "bug-campaign" / "repro" / "10-copy-run-evidence.json"
PHASE10_EVIDENCE_MD = REPO_ROOT / "artifacts" / "bug-campaign" / "repro" / "10-copy-run-evidence.md"
LOCAL_CLOSURE_JSON = REPO_ROOT / "artifacts" / "verification" / "scorecards" / "local-closure-runs.json"
LOCAL_CLOSURE_MD = REPO_ROOT / "artifacts" / "verification" / "scorecards" / "local-closure-runs.md"

PHASE10_COMMANDS: tuple[tuple[str, list[str]], ...] = (
    (
        "state-progress-contradictions",
        [
            "uv",
            "run",
            "pytest",
            "-q",
            "-n",
            "0",
            "tests/test_bug_phase_read_model_alignment.py",
            "tests/core/test_projection_state.py",
        ],
    ),
    (
        "query-vs-result-blindness",
        ["uv", "run", "pytest", "-q", "-n", "0", "tests/core/test_projection_query_result.py"],
    ),
    (
        "phase-content-blindness",
        ["uv", "run", "pytest", "-q", "-n", "0", "tests/core/test_projection_phase_verify.py"],
    ),
    (
        "unsupported-cli-surface-drift",
        [
            "uv",
            "run",
            "pytest",
            "-q",
            "-n",
            "0",
            "tests/core/test_projection_query_result.py::test_projection_query_result_bridge_mutation_matches_positive_snapshot",
            "tests/test_bug_runtime_recovery_contract.py",
        ],
    ),
    (
        "convention-placeholder-completeness",
        [
            "uv",
            "run",
            "pytest",
            "-q",
            "-n",
            "0",
            "tests/core/test_projection_config_contract.py",
            "tests/test_bug_placeholder_sentinel_normalization.py",
        ],
    ),
)

NIGHTLY_LOCAL_COMMAND = [
    "uv",
    "run",
    "pytest",
    "-q",
    "-n",
    "0",
    "tests/core/test_projection_state.py",
    "tests/core/test_projection_query_result.py",
    "tests/core/test_projection_phase_verify.py",
    "tests/core/test_projection_resume_observe.py",
    "tests/core/test_projection_config_contract.py",
    "tests/test_phase17_nightly_contract.py",
    "benchmarks/test_resume_recent.py",
    "benchmarks/test_query_index_freshness.py",
    "benchmarks/test_phase_projection_latency.py",
    "benchmarks/test_checkpoint_batch.py",
]

RELEASE_CANDIDATE_LOCAL_COMMAND = ["uv", "run", "pytest", "-q"]

_PYTEST_SUMMARY_RE = re.compile(
    r"(?P<passed>\d+) passed(?:, (?P<skipped>\d+) skipped)?(?: in (?P<duration>[0-9.]+)s)?"
)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _pytest_summary(output: str) -> dict[str, object]:
    match = None
    for candidate in _PYTEST_SUMMARY_RE.finditer(output):
        match = candidate
    if match is None:
        return {"raw": output.splitlines()[-1] if output.splitlines() else ""}
    return {
        "passed": int(match.group("passed")),
        "skipped": int(match.group("skipped") or 0),
        "pytest_duration_s": None if match.group("duration") is None else float(match.group("duration")),
        "raw": match.group(0),
    }


def _run(label: str, command: list[str]) -> dict[str, object]:
    start = time.perf_counter()
    result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    elapsed = time.perf_counter() - start
    combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
    tail = combined.splitlines()[-20:]
    return {
        "label": label,
        "command": command,
        "returncode": result.returncode,
        "passed": result.returncode == 0,
        "elapsed_s": round(elapsed, 3),
        "pytest_summary": _pytest_summary(combined),
        "output_tail": tail,
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _phase10_evidence(git_head: str) -> dict[str, object]:
    run_kinds = ("anchor_copy_1", "anchor_copy_2", "confirmatory_copy_1")
    family_runs: list[dict[str, object]] = []
    for family_id, command in PHASE10_COMMANDS:
        runs = [_run(f"{family_id}:{run_kind}", command) for run_kind in run_kinds]
        family_runs.append(
            {
                "family_id": family_id,
                "runs": runs,
                "green_run_count": sum(1 for run in runs if run["passed"]),
                "required_green_run_count": len(run_kinds),
                "post_fix_copy_run_criteria_met": all(run["passed"] for run in runs),
            }
        )
    return {
        "schema_version": 1,
        "generated_at": _utc_now(),
        "git_head": git_head,
        "scope": "local_post_fix_copy_runs",
        "historical_failure_repro_note": (
            "Original Phase 10 failure transcripts remain absent; these runs verify current fixed behavior "
            "through fresh isolated pytest fixture copies."
        ),
        "run_kinds": list(run_kinds),
        "families": family_runs,
        "post_fix_copy_run_criteria_met": all(family["post_fix_copy_run_criteria_met"] for family in family_runs),
    }


def _local_closure_evidence(git_head: str) -> dict[str, object]:
    nightly_runs = [
        _run(f"local_nightly_equivalent_{index:02d}", NIGHTLY_LOCAL_COMMAND)
        for index in range(1, 11)
    ]
    release_candidate_runs = [
        _run(f"local_release_candidate_{index:02d}", RELEASE_CANDIDATE_LOCAL_COMMAND)
        for index in range(1, 3)
    ]
    return {
        "schema_version": 1,
        "generated_at": _utc_now(),
        "git_head": git_head,
        "scope": "local_evidence_not_durable_ci_history",
        "nightly_equivalent": {
            "required_green_run_count": 10,
            "green_run_count": sum(1 for run in nightly_runs if run["passed"]),
            "all_green": all(run["passed"] for run in nightly_runs),
            "command": NIGHTLY_LOCAL_COMMAND,
            "runs": nightly_runs,
        },
        "release_candidate_equivalent": {
            "required_green_run_count": 2,
            "green_run_count": sum(1 for run in release_candidate_runs if run["passed"]),
            "all_green": all(run["passed"] for run in release_candidate_runs),
            "command": RELEASE_CANDIDATE_LOCAL_COMMAND,
            "runs": release_candidate_runs,
        },
        "durable_ci_closure_note": (
            "These runs are local substitutes only. Official closure still requires durable nightly/release "
            "history and conversion of remaining high-confidence manual-repro items."
        ),
    }


def _phase10_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Phase 10 Local Copy-Run Evidence",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- git_head: `{payload['git_head']}`",
        f"- scope: `{payload['scope']}`",
        f"- post_fix_copy_run_criteria_met: `{str(payload['post_fix_copy_run_criteria_met']).lower()}`",
        "",
        "## Families",
        "",
    ]
    for family in payload["families"]:
        lines.append(f"- `{family['family_id']}`: `{family['green_run_count']}/{family['required_green_run_count']}` green")
        for run in family["runs"]:
            lines.append(f"  - `{run['label']}`: `{run['pytest_summary']['raw']}`")
    lines.extend(("", "## Note", "", str(payload["historical_failure_repro_note"])))
    return "\n".join(lines) + "\n"


def _local_closure_markdown(payload: dict[str, object]) -> str:
    nightly = payload["nightly_equivalent"]
    release = payload["release_candidate_equivalent"]
    lines = [
        "# Local Closure Run Evidence",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- git_head: `{payload['git_head']}`",
        f"- scope: `{payload['scope']}`",
        f"- nightly_equivalent_green: `{nightly['green_run_count']}/{nightly['required_green_run_count']}`",
        f"- release_candidate_equivalent_green: `{release['green_run_count']}/{release['required_green_run_count']}`",
        "",
        "## Nightly Equivalent Runs",
        "",
    ]
    for run in nightly["runs"]:
        lines.append(f"- `{run['label']}`: `{run['pytest_summary']['raw']}`")
    lines.extend(("", "## Release Candidate Equivalent Runs", ""))
    for run in release["runs"]:
        lines.append(f"- `{run['label']}`: `{run['pytest_summary']['raw']}`")
    lines.extend(("", "## Note", "", str(payload["durable_ci_closure_note"])))
    return "\n".join(lines) + "\n"


def main() -> int:
    git_head = _git_head()
    phase10 = _phase10_evidence(git_head)
    closure = _local_closure_evidence(git_head)
    _write_json(PHASE10_EVIDENCE_JSON, phase10)
    _write_text(PHASE10_EVIDENCE_MD, _phase10_markdown(phase10))
    _write_json(LOCAL_CLOSURE_JSON, closure)
    _write_text(LOCAL_CLOSURE_MD, _local_closure_markdown(closure))
    return 0 if phase10["post_fix_copy_run_criteria_met"] and closure["nightly_equivalent"]["all_green"] and closure["release_candidate_equivalent"]["all_green"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
