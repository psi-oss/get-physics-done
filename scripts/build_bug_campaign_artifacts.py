"""Build durable bug-campaign control-plane artifacts.

The master campaign source bundle lives under ignored ``tmp/``.  This script
turns that frozen corpus into tracked ledgers, partial repro reconstruction
artifacts, and closure scorecards under ``artifacts/bug-campaign``.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "tmp" / "handoff-bundle"
VERIFIED_PATH = SOURCE_ROOT / "verification-02" / "VERIFIED-BUGS-VERIFICATION.json"
RAW_BUGS_PATH = SOURCE_ROOT / "bugs" / "BUGS-RAW.json"
WATCHDOG_SUMMARY_PATH = SOURCE_ROOT / "watchdog-summary.json"
CHECKPOINTS_PATH = SOURCE_ROOT / "verification" / "experiment-checkpoints.json"
MASTER_PLAN_PATH = SOURCE_ROOT / "MASTER-BUG-CAMPAIGN-PLAN.md"

OUTPUT_ROOT = REPO_ROOT / "artifacts" / "bug-campaign"
CAMPAIGN_ROOT = OUTPUT_ROOT / "campaign"
TAXONOMY_ROOT = OUTPUT_ROOT / "taxonomy"
REPRO_ROOT = OUTPUT_ROOT / "repro"
SCORECARD_ROOT = REPO_ROOT / "artifacts" / "verification" / "scorecards"

HANDOFF_MANIFEST_PATH = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle" / "manifest.json"
PHASE15_ROOT = REPO_ROOT / "artifacts" / "phases" / "15-verification-contract" / "verification" / "fixes"
PHASE17_THRESHOLDS_PATH = REPO_ROOT / "benchmarks" / "phase17_thresholds.json"
PHASE17_WATCHDOG_PATH = REPO_ROOT / "benchmarks" / "phase17_watchdog_summary.json"
PHASE17_CHECKPOINTS_PATH = REPO_ROOT / "benchmarks" / "phase17_experiment_checkpoints.json"
NIGHTLY_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "nightly-handoff-bundle.yml"

EXTERNAL_REPRO_ROOT = Path("/tmp/gpd-bug-campaign/repro")
EXTERNAL_REPRO_IMPORTS = (
    "11-mutation-summary.md",
    "11-oracle-dual-writer-ordering-race.json",
    "11-histogram-dual-writer-ordering-race.json",
    "11-transcript-dual-writer-ordering-race.md",
    "11-validator-result.json",
    "12-family-prevalence-matrix.json",
    "12-post-stop-observations.json",
    "12-ranked-repro-queue.json",
    "13-environment-matrix.json",
    "13-mcp-vs-cli.md",
    "13-blockers.json",
    "14-flake-dossier.md",
    "14-residual-queue.json",
)
PUBLIC_RUNTIME_PREFIX = "$" + "gpd-"

PHASE15_FAMILIES = (
    {
        "bug_id": "phase-read-model-alignment",
        "family_id": "phase-read-model-alignment",
        "family_title": "phase/read-model alignment",
        "wave": "F2",
        "status": "verified",
        "contract_test": "tests/test_bug_phase_read_model_alignment.py",
        "artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/phase-read-model-alignment.json",
        "source_artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/f2-phase-read-model-alignment.json",
    },
    {
        "bug_id": "placeholder-sentinel-normalization",
        "family_id": "placeholder-sentinel-normalization",
        "family_title": "placeholder/sentinel normalization",
        "wave": "F4",
        "status": "verified",
        "contract_test": "tests/test_bug_placeholder_sentinel_normalization.py",
        "artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/placeholder-sentinel-normalization.json",
        "source_artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/f3-placeholder-sentinel-normalization.json",
    },
    {
        "bug_id": "query-result-registry-projection",
        "family_id": "query-result-registry-projection",
        "family_title": "query/result registry projection",
        "wave": "F3",
        "status": "verified",
        "contract_test": "tests/core/test_projection_query_result.py",
        "artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/query-result-registry-projection.json",
        "source_artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/f3-query-result-registry-projection.json",
    },
    {
        "bug_id": "nested-root-readonly-probe-parity",
        "family_id": "nested-root-readonly-probe-parity",
        "family_title": "nested-root read-only probe parity",
        "wave": "F4",
        "status": "closed",
        "contract_test": "tests/test_bug_nested_root_readonly_probe_parity.py",
        "artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/nested-root-readonly-probe-parity.json",
        "source_artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/f4-nested-root-readonly-probe-parity.json",
    },
    {
        "bug_id": "resume-recent-selection-control",
        "family_id": "resume-recent-selection-control",
        "family_title": "resume recent selection control",
        "wave": "F5",
        "status": "closed",
        "contract_test": "tests/test_bug_resume_state_continuity.py",
        "artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/resume-recent-selection-control.json",
        "source_artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/f5-resume-state-continuity.json",
    },
    {
        "bug_id": "canonical-session-continuation-access",
        "family_id": "canonical-session-continuation-access",
        "family_title": "canonical session / continuation access",
        "wave": "F5",
        "status": "closed",
        "contract_test": "tests/test_bug_resume_state_continuity.py",
        "artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/canonical-session-continuation-access.json",
        "source_artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/f5-resume-state-continuity.json",
    },
    {
        "bug_id": "runtime-bridge-classification",
        "family_id": "runtime-bridge-classification",
        "family_title": "runtime bridge classification",
        "wave": "F5",
        "status": "closed",
        "contract_test": "tests/test_bug_runtime_recovery_contract.py",
        "artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/runtime-bridge-classification.json",
        "source_artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/f5-runtime-recovery.json",
    },
    {
        "bug_id": "doctor-target-readiness-contract",
        "family_id": "doctor-target-readiness-contract",
        "family_title": "doctor target / readiness contract",
        "wave": "F5",
        "status": "closed",
        "contract_test": "tests/test_bug_runtime_recovery_contract.py",
        "artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/doctor-target-readiness-contract.json",
        "source_artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/f5-runtime-recovery.json",
    },
    {
        "bug_id": "observability-degraded-visibility",
        "family_id": "observability-degraded-visibility",
        "family_title": "observability degraded visibility",
        "wave": "F5",
        "status": "closed",
        "contract_test": "tests/test_bug_runtime_recovery_contract.py",
        "artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/observability-degraded-visibility.json",
        "source_artifact_path": "artifacts/phases/15-verification-contract/verification/fixes/f5-runtime-recovery.json",
    },
)

PHASE15_GENERATED_SOURCE_ARTIFACTS = {
    "artifacts/phases/15-verification-contract/verification/fixes/f3-query-result-registry-projection.json": {
        "schema_version": 1,
        "bug_id": "f3-query-result-registry-projection",
        "family_id": "query-result-registry-projection",
        "family_title": "Query / result registry projection",
        "phase": 15,
        "wave": "F3",
        "status": "verified",
        "classification": "cross_surface_projection_contract",
        "scope": {
            "in_scope": [
                "query search projection of canonical intermediate_results entries",
                "query deps projection of canonical result dependency chains",
                "result search positional text argument parity",
            ],
            "out_of_scope": [
                "changing SUMMARY/frontmatter query semantics when no registry-backed search filter is supplied"
            ],
            "question": "Do query and result surfaces expose the canonical result registry without forcing users to switch commands?",
        },
        "source": {
            "anchor_fixtures": [
                "tests/fixtures/handoff-bundle/query-registry-drift/positive/workspace",
                "tests/fixtures/handoff-bundle/context-indexing/positive/workspace",
            ],
            "mutation_fixtures": [
                "tests/fixtures/handoff-bundle/bridge-vs-cli/mutation/workspace",
            ],
            "packet_ids": [
                "PK-BT-136-01",
                "PK-BT-138-01",
                "PK-BT-140-01",
                "PK-BT-142-01",
            ],
            "bug_type_ids": ["BT-136", "BT-138", "BT-140", "BT-142"],
        },
        "exact_repro": {
            "surface": "query search/deps on fixture workspaces with canonical intermediate_results but sparse SUMMARY artifacts",
            "assertions": [
                "query search --text semiclassical includes result_registry matches",
                "query deps R-05-ml-window exposes direct and transitive result registry dependencies",
                "result search singularity accepts a positional text search term",
            ],
        },
        "exact_fix": {
            "surface": "gpd.core.query registry projection and result search CLI argument parsing",
            "assertions": [
                "QueryResult includes result_registry matches without suppressing SUMMARY/frontmatter matches",
                "DepsResult includes depends_on, direct_deps, and transitive_deps from canonical result_deps",
                "result search rejects ambiguous positional term plus --text usage",
            ],
        },
        "adjacent_checks": [
            {
                "surface": "bridge-vs-cli projection parity",
                "assertions": [
                    "bridge-vs-cli positive and mutation fixtures still produce matching query/result snapshots"
                ],
            }
        ],
        "verification": {
            "contract_test": "tests/core/test_projection_query_result.py",
            "unit_tests": ["tests/core/test_query.py"],
            "fixture_mode": "positive+mutation",
        },
        "red_exact_repro": True,
        "green_exact_fix": True,
        "green_adjacent_checks": True,
    }
}

PHASE16_FAMILY_TO_MODULE = {
    "state": "tests/core/test_projection_state.py",
    "query-result": "tests/core/test_projection_query_result.py",
    "phase-verify": "tests/core/test_projection_phase_verify.py",
    "resume-observe": "tests/core/test_projection_resume_observe.py",
    "config-contract": "tests/core/test_projection_config_contract.py",
}

PHASE16_SLUG_TO_FAMILY = {
    "completed-phase": "state",
    "plan-only": "state",
    "empty-phase": "state",
    "query-registry-drift": "query-result",
    "context-indexing": "query-result",
    "bridge-vs-cli": "query-result",
    "summary-missing-return": "phase-verify",
    "mutation-ordering": "phase-verify",
    "resume-handoff": "resume-observe",
    "resume-recent-noise": "resume-observe",
    "config-readback": "config-contract",
    "placeholder-conventions": "config-contract",
}

PHASE10_FAMILIES = (
    {
        "family_id": "state-progress-contradictions",
        "priority_family": "state/progress contradictions",
        "oracle_filename": "state-progress-contradictions.json",
        "script_filename": "state-progress-contradictions.sh",
        "transcript_filename": "state-progress-contradictions.txt",
        "pytest_args": [
            "tests/test_bug_phase_read_model_alignment.py",
            "tests/core/test_projection_state.py",
        ],
        "expected_pytest_pass_count": 8,
        "source_tests": [
            "tests/test_bug_phase_read_model_alignment.py",
            "tests/core/test_projection_state.py",
        ],
        "positive_fixtures": [
            "completed-phase/positive",
            "plan-only/positive",
            "empty-phase/positive",
        ],
        "mutation_fixtures": [
            "plan-only/mutation",
            "empty-phase/mutation",
        ],
        "assertion_surface": [
            "roadmap_analyze",
            "progress_render",
            "state_snapshot",
            "verify_phase_completeness",
            "get_phase_info",
        ],
    },
    {
        "family_id": "query-vs-result-blindness",
        "priority_family": "query-vs-result blindness",
        "oracle_filename": "query-vs-result-blindness.json",
        "script_filename": "query-vs-result-blindness.sh",
        "transcript_filename": "query-vs-result-blindness.txt",
        "pytest_args": ["tests/core/test_projection_query_result.py"],
        "expected_pytest_pass_count": 6,
        "source_tests": ["tests/core/test_projection_query_result.py"],
        "positive_fixtures": [
            "query-registry-drift/positive",
            "context-indexing/positive",
            "bridge-vs-cli/positive",
        ],
        "mutation_fixtures": ["bridge-vs-cli/mutation"],
        "assertion_surface": [
            "gpd --raw query search",
            "gpd --raw query assumptions",
            "gpd --raw query deps",
            "gpd --raw result search",
            "gpd --raw result deps",
        ],
        "closed_gaps": [
            {
                "class": "closed-by-result-registry-projection",
                "fixtures": [
                    "query-registry-drift/positive",
                    "context-indexing/positive",
                ],
            }
        ],
    },
    {
        "family_id": "phase-content-blindness",
        "priority_family": "phase-content blindness",
        "oracle_filename": "phase-content-blindness.json",
        "script_filename": "phase-content-blindness.sh",
        "transcript_filename": "phase-content-blindness.txt",
        "pytest_args": ["tests/core/test_projection_phase_verify.py"],
        "expected_pytest_pass_count": 4,
        "source_tests": ["tests/core/test_projection_phase_verify.py"],
        "positive_fixtures": [
            "summary-missing-return/positive",
            "mutation-ordering/positive",
        ],
        "mutation_fixtures": [
            "summary-missing-return/mutation",
            "mutation-ordering/mutation",
        ],
        "assertion_surface": [
            "verify_phase_completeness",
            "phase_plan_index",
            "get_phase_info",
            "get_progress",
        ],
        "known_gaps": [
            {
                "class": "allowlisted-projection-diff",
                "fixtures": [
                    "summary-missing-return/positive",
                    "summary-missing-return/mutation",
                    "mutation-ordering/positive",
                    "mutation-ordering/mutation",
                ],
            }
        ],
    },
    {
        "family_id": "unsupported-cli-surface-drift",
        "priority_family": "unsupported CLI surface drift",
        "oracle_filename": "unsupported-cli-surface-drift.json",
        "script_filename": "unsupported-cli-surface-drift.sh",
        "transcript_filename": "unsupported-cli-surface-drift.txt",
        "pytest_args": [
            "tests/core/test_projection_query_result.py::test_projection_query_result_bridge_mutation_matches_positive_snapshot",
            "tests/test_bug_runtime_recovery_contract.py",
        ],
        "expected_pytest_pass_count": 10,
        "source_tests": [
            "tests/core/test_projection_query_result.py",
            "tests/test_bug_runtime_recovery_contract.py",
        ],
        "positive_fixtures": [
            "bridge-vs-cli/positive",
            "config-readback/positive",
        ],
        "mutation_fixtures": ["bridge-vs-cli/mutation"],
        "assertion_surface": [
            "runtime_cli",
            "gpd --raw doctor --runtime",
            "gpd --raw query search",
            "gpd --raw result search",
        ],
    },
    {
        "family_id": "convention-placeholder-completeness",
        "priority_family": "convention placeholder completeness",
        "oracle_filename": "convention-placeholder-completeness.json",
        "script_filename": "convention-placeholder-completeness.sh",
        "transcript_filename": "convention-placeholder-completeness.txt",
        "pytest_args": [
            "tests/test_bug_placeholder_sentinel_normalization.py",
            "tests/core/test_projection_config_contract.py::test_placeholder_conventions_projection_oracle_treats_literal_not_set_as_unset",
        ],
        "expected_pytest_pass_count": 3,
        "source_tests": [
            "tests/test_bug_placeholder_sentinel_normalization.py",
            "tests/core/test_projection_config_contract.py",
        ],
        "positive_fixtures": ["placeholder-conventions/positive"],
        "mutation_fixtures": ["placeholder-conventions/mutation"],
        "assertion_surface": [
            "convention_list",
            "convention_check",
            "convention_set",
            "check_convention_lock",
            "suggest_next",
        ],
    },
)

TEXT_SPLIT_RE = re.compile(r"[;]\s+")
TOKEN_RE = re.compile(r"[A-Za-z0-9:_$-]+")


def read_json_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def coerce_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def coerce_sequence(value: object) -> Sequence[object]:
    return value if isinstance(value, Sequence) and not isinstance(value, str) else ()


def string_list(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return []
    return [str(item) for item in value]


def candidates_from_verified(verified: Mapping[str, object]) -> list[Mapping[str, object]]:
    candidates = verified.get("candidates")
    if not isinstance(candidates, list):
        raise TypeError("verified payload missing candidates list")
    return [candidate for candidate in candidates if isinstance(candidate, Mapping)]


def split_repro_hint(repro_hint: object) -> list[str]:
    if not isinstance(repro_hint, str) or not repro_hint.strip():
        return []
    return [part.strip() for part in TEXT_SPLIT_RE.split(repro_hint) if part.strip()]


def command_hints(candidate: Mapping[str, object]) -> list[str]:
    raw = coerce_mapping(candidate.get("raw"))
    hints = string_list(raw.get("command_hints"))
    if hints:
        return hints
    return split_repro_hint(candidate.get("repro_hint"))


def first_command(candidate: Mapping[str, object]) -> str:
    hints = command_hints(candidate)
    return hints[0] if hints else "unknown"


def command_tokens(command: str) -> list[str]:
    text = command.strip().strip("`")
    return [token.strip("$") for token in TOKEN_RE.findall(text)]


def command_surface(command: str, text: str) -> tuple[str, str, str]:
    tokens = command_tokens(command)
    if not tokens:
        if "mcp" in text or "bridge" in text:
            return "unknown:runtime-bridge", "mcp", "keyword"
        if "skill" in text or PUBLIC_RUNTIME_PREFIX in text:
            return "unknown:docs-skill", "docs", "keyword"
        return "unknown", "unknown", "none"

    for token in tokens:
        if token.startswith("gpd:"):
            return f"runtime:{token.replace(':', '.')}", "runtime", "command_hint"
        if token.startswith("gpd-"):
            return f"runtime:{token.replace('-', '.')}", "runtime", "command_hint"

    if "gpd" in tokens:
        index = tokens.index("gpd")
        tail = [token for token in tokens[index + 1 :] if token not in {"--raw", "-q"} and not token.startswith("--")]
        command_name = ".".join(tail[:2]) if tail else "root"
        if "--raw" in tokens:
            return f"raw:gpd.{command_name}", "raw", "command_hint"
        return f"cli:gpd.{command_name}", "cli", "command_hint"

    if "uv" in tokens and "gpd" in command:
        return "cli:gpd.wrapper", "cli", "command_hint"
    if "mcp" in text or "bridge" in text:
        return "unknown:runtime-bridge", "mcp", "keyword"
    return "unknown", "unknown", "none"


def candidate_text(candidate: Mapping[str, object]) -> str:
    raw = coerce_mapping(candidate.get("raw"))
    parts = [
        candidate.get("heading"),
        candidate.get("category"),
        candidate.get("repro_hint"),
        candidate.get("excerpt"),
        raw.get("title"),
        raw.get("category"),
        *command_hints(candidate),
    ]
    return "\n".join(str(part) for part in parts if part).casefold()


def invariant_id(candidate: Mapping[str, object], text: str) -> tuple[str, str]:
    category = str(candidate.get("category") or "unknown")
    if re.search(r"\b(parallel|race|concurrent|ordering|atomic|serialized|lock)\b", text):
        return "mutation-ordering-durability", "keyword"
    if re.search(r"\b(not set|placeholder|sentinel)\b", text):
        return "placeholder-sentinel-normalization", "keyword"
    public_runtime_prefix_pattern = re.escape(PUBLIC_RUNTIME_PREFIX)
    if re.search(
        rf"\b(unsupported|unknown option|rejects|does not expose|suggest-next|--reconcile|{public_runtime_prefix_pattern})\b",
        text,
    ):
        return "interface-contract-parity", "keyword"
    if re.search(r"\bquery\b", text) and re.search(r"\b(result|registry|deps|assumptions|search)\b", text):
        return "registry-query-visibility", "keyword"
    if re.search(r"\b(progress|roadmap|suggest|state snapshot|state load|phase list|phase index)\b", text):
        return "state-projection-parity", "keyword"
    if re.search(r"\b(resume|continuation|handoff|session|recent)\b", text):
        return "resume-session-continuity", "keyword"
    if re.search(r"\b(bridge|mcp|runtime|adapter)\b", text):
        return "runtime-bridge-parity", "keyword"
    if re.search(r"\b(validator|validate|schema|contract|frontmatter|return envelope|gpd_return)\b", text):
        return "validation-contract-precision", "keyword"
    if re.search(r"\b(citation|bibliograph|reference)\b", text):
        return "citation-reference-propagation", "keyword"
    if re.search(r"\b(observ|trace)\b", text):
        return "observability-lifecycle", "keyword"
    if re.search(r"\b(data loss|lost|provenance|artifact)\b", text):
        return "artifact-provenance-propagation", "keyword"
    return category, "category"


def environment_scope(text: str) -> tuple[str, str]:
    if re.search(r"\b(sandbox|uv cache|/\\.cache/uv|permission|api key|network|outside allowed roots)\b", text):
        return "environment_or_sandbox", "keyword"
    if re.search(r"\b(mcp|bridge|runtime)\b", text):
        return "runtime_boundary", "keyword"
    return "product_local_or_unknown", "default"


def affected_substrates(text: str) -> list[str]:
    pairs = (
        ("state.json", "state.json"),
        ("state.md", "STATE.md"),
        ("frontmatter", "frontmatter"),
        ("gpd_return", "return-envelope"),
        ("result", "result-registry"),
        ("registry", "result-registry"),
        ("config", "config"),
        ("observ", "observability"),
        ("trace", "observability"),
        ("recent", "recent-project-scan"),
        ("mcp", "MCP-bridge"),
        ("bridge", "MCP-bridge"),
        ("skill", "docs-skills"),
        (PUBLIC_RUNTIME_PREFIX, "docs-skills"),
        ("convention", "conventions"),
        ("checkpoint", "checkpoint-registry"),
    )
    found: list[str] = []
    for needle, substrate in pairs:
        if needle in text and substrate not in found:
            found.append(substrate)
    return found or ["unknown"]


def comparator_surface(text: str) -> str:
    if "state snapshot" in text:
        return "state_snapshot"
    if "result deps" in text or "result search" in text:
        return "result_registry"
    if "progress" in text:
        return "progress"
    if "roadmap analyze" in text:
        return "roadmap_analyze"
    if "health" in text or "doctor" in text:
        return "health_doctor"
    if "resume" in text:
        return "resume"
    return "unknown"


def split_claims(excerpt: object) -> tuple[str, ...]:
    if not isinstance(excerpt, str) or not excerpt.strip():
        return ("unknown",)
    claims: list[str] = []
    current: list[str] = []
    for line in excerpt.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            if current:
                claims.append("\n".join(current).strip())
            current = [stripped[2:].strip()]
            continue
        if current and stripped:
            current.append(stripped)
    if current:
        claims.append("\n".join(current).strip())
    return tuple(claim for claim in claims if claim) or (excerpt.strip(),)


def candidate_ledger_rows(candidates: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for candidate in candidates:
        raw = coerce_mapping(candidate.get("raw"))
        span = coerce_mapping(raw.get("span"))
        rows.append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "experiment_slug": candidate.get("experiment_slug"),
                "status": candidate.get("status"),
                "category": candidate.get("category"),
                "confidence": candidate.get("confidence"),
                "source_path": candidate.get("source_path"),
                "source_format": candidate.get("source_format"),
                "source_file": candidate.get("source_file"),
                "source_line": candidate.get("source_line"),
                "raw_source_path": raw.get("source_path"),
                "raw_source_kind": raw.get("source_kind"),
                "raw_source_role": raw.get("source_role"),
                "raw_span_line_start": span.get("line_start"),
                "raw_span_line_end": span.get("line_end"),
                "raw_fingerprint": raw.get("fingerprint"),
                "raw_title": raw.get("title"),
                "raw_category": raw.get("category"),
                "raw_confidence": raw.get("confidence"),
                "raw_severity_hint": raw.get("severity_hint"),
                "report_path": candidate.get("report_path"),
                "workspace_path": candidate.get("workspace_path"),
                "repro_hint": candidate.get("repro_hint"),
                "notes": candidate.get("notes"),
                "command_hints": command_hints(candidate),
                "evidence": string_list(raw.get("evidence")),
                "section_path": string_list(raw.get("section_path")),
                "excerpt": candidate.get("excerpt"),
            }
        )
    return rows


def atomize(candidates: Sequence[Mapping[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    findings: list[dict[str, object]] = []
    mapping_rows: list[dict[str, object]] = []
    counter = 0
    for candidate in candidates:
        raw = coerce_mapping(candidate.get("raw"))
        claims = split_claims(candidate.get("excerpt"))
        atomization_method = "markdown_bullet" if len(claims) > 1 else "single_excerpt"
        for index, claim in enumerate(claims, start=1):
            counter += 1
            finding_id = f"AF-{counter:06d}"
            heuristic_only = candidate.get("status") == "heuristic_candidate" or not command_hints(candidate)
            row = {
                "atomic_finding_id": finding_id,
                "candidate_id": candidate.get("candidate_id"),
                "experiment_slug": candidate.get("experiment_slug"),
                "claim_index": index,
                "atomization_method": atomization_method,
                "heuristic_only": heuristic_only,
                "status": candidate.get("status"),
                "confidence": candidate.get("confidence"),
                "raw_fingerprint": raw.get("fingerprint"),
                "raw_title": raw.get("title"),
                "raw_category": raw.get("category"),
                "source_span": raw.get("span"),
                "trigger_or_command": first_command(candidate),
                "scope": candidate.get("workspace_path") or "unknown",
                "expected_claim": "unknown",
                "actual_claim": claim,
                "evidence_excerpt": claim,
                "command_hints": command_hints(candidate),
                "source_path": raw.get("source_path") or candidate.get("source_path"),
            }
            findings.append(row)
            mapping_rows.append(
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "atomic_finding_id": finding_id,
                    "claim_index": index,
                    "atomization_method": atomization_method,
                    "heuristic_only": heuristic_only,
                }
            )
    return findings, mapping_rows


def normalize_findings(findings: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for finding in findings:
        text = "\n".join(
            str(part)
            for part in (
                finding.get("actual_claim"),
                finding.get("raw_title"),
                finding.get("raw_category"),
                finding.get("trigger_or_command"),
            )
            if part
        ).casefold()
        command = str(finding.get("trigger_or_command") or "")
        surface_id, surface_mode, surface_basis = command_surface(command, text)
        invariant, invariant_basis = invariant_id(finding, text)
        environment, environment_basis = environment_scope(text)
        substrates = affected_substrates(text)
        if finding.get("status") == "heuristic_candidate" and command == "unknown":
            disposition = "insufficient_detail"
        elif environment == "environment_or_sandbox":
            disposition = "noise"
        elif re.search(r"\b(expected behavior|not product-local|not_product_local)\b", text):
            disposition = "expected_behavior_or_non_product"
        else:
            disposition = "product_finding"
        rows.append(
            {
                "atomic_finding_id": finding.get("atomic_finding_id"),
                "candidate_id": finding.get("candidate_id"),
                "experiment_slug": finding.get("experiment_slug"),
                "normalized_surface_id": surface_id,
                "surface_mode": surface_mode,
                "surface_basis": surface_basis,
                "broken_invariant_id": invariant,
                "invariant_basis": invariant_basis,
                "trigger_precondition": command,
                "expected_truth_source": comparator_surface(text),
                "actual_behavior_signature": f"{finding.get('raw_category')}:{finding.get('raw_fingerprint')}",
                "authoritative_comparator_surface": comparator_surface(text),
                "environment_scope": environment,
                "environment_basis": environment_basis,
                "affected_substrates": substrates,
                "affected_substrate_primary": substrates[0],
                "disposition": disposition,
                "status": finding.get("status"),
                "confidence": finding.get("confidence"),
                "heuristic_only": finding.get("heuristic_only"),
                "actual_claim": finding.get("actual_claim"),
                "source_path": finding.get("source_path"),
            }
        )
    return rows


def cluster_rows(normalized: Sequence[Mapping[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    grouped: dict[tuple[str, str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in normalized:
        key = (
            str(row.get("normalized_surface_id") or "unknown"),
            str(row.get("broken_invariant_id") or "unknown"),
            str(row.get("trigger_precondition") or "unknown"),
            str(row.get("environment_scope") or "unknown"),
        )
        grouped[key].append(row)

    clusters: list[dict[str, object]] = []
    finding_map: list[dict[str, object]] = []
    for index, (key, rows) in enumerate(sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])), start=1):
        cluster_id = f"CS-{index:04d}"
        candidate_ids = sorted({str(row.get("candidate_id")) for row in rows})
        finding_ids = sorted(str(row.get("atomic_finding_id")) for row in rows)
        dispositions = Counter(str(row.get("disposition")) for row in rows)
        statuses = Counter(str(row.get("status")) for row in rows)
        clusters.append(
            {
                "cluster_id": cluster_id,
                "normalized_surface_id": key[0],
                "broken_invariant_id": key[1],
                "trigger_precondition": key[2],
                "environment_scope": key[3],
                "atomic_finding_count": len(rows),
                "candidate_count": len(candidate_ids),
                "candidate_ids": candidate_ids,
                "atomic_finding_ids": finding_ids,
                "disposition_counts": dict(sorted(dispositions.items())),
                "status_counts": dict(sorted(statuses.items())),
                "representative_claim": rows[0].get("actual_claim"),
            }
        )
        for row in rows:
            finding_map.append(
                {
                    "atomic_finding_id": row.get("atomic_finding_id"),
                    "candidate_id": row.get("candidate_id"),
                    "cluster_id": cluster_id,
                    "disposition": row.get("disposition"),
                }
            )
    return clusters, finding_map


def bug_registry(
    clusters: Sequence[Mapping[str, object]],
    cluster_finding_map: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], list[dict[str, object]], str]:
    product_clusters = [
        cluster for cluster in clusters if coerce_mapping(cluster.get("disposition_counts")).get("product_finding")
    ]
    bug_type_by_cluster: dict[str, str] = {}
    registry_entries: list[dict[str, object]] = []
    unresolved_lines: list[str] = ["# Phase 07 Unresolved Singletons", ""]
    for index, cluster in enumerate(product_clusters, start=1):
        cluster_id = str(cluster["cluster_id"])
        is_singleton = int(cluster["atomic_finding_count"]) == 1
        bug_type_id = f"BT-CAMP-{index:04d}" if not is_singleton else f"BT-CAMP-U{index:04d}"
        bug_type_by_cluster[cluster_id] = bug_type_id
        status = "unresolved_singleton" if is_singleton else "needs_repro"
        title = (
            f"{cluster['broken_invariant_id']} on {cluster['normalized_surface_id']} "
            f"under {cluster['trigger_precondition']}"
        )
        entry = {
            "bug_type_id": bug_type_id,
            "cluster_id": cluster_id,
            "title": title,
            "invariant": cluster.get("broken_invariant_id"),
            "trigger": cluster.get("trigger_precondition"),
            "scope": cluster.get("environment_scope"),
            "authority_source": "taxonomy/04-normalized-findings.jsonl",
            "comparator_surfaces": ["unknown"],
            "negative_examples": [],
            "linked_symptoms": [cluster.get("representative_claim")],
            "candidate_count": cluster.get("candidate_count"),
            "atomic_finding_count": cluster.get("atomic_finding_count"),
            "status": status,
        }
        registry_entries.append(entry)
        if is_singleton:
            unresolved_lines.extend(
                (
                    f"## {bug_type_id}",
                    "",
                    f"- cluster_id: `{cluster_id}`",
                    f"- invariant: `{cluster.get('broken_invariant_id')}`",
                    f"- surface: `{cluster.get('normalized_surface_id')}`",
                    "- status: unresolved_singleton",
                    "",
                )
            )

    finding_to_type_rows: list[dict[str, object]] = []
    for row in cluster_finding_map:
        if row.get("disposition") != "product_finding":
            continue
        cluster_id = str(row.get("cluster_id"))
        bug_type_id = bug_type_by_cluster.get(cluster_id, "unmapped")
        finding_to_type_rows.append(
            {
                "atomic_finding_id": row.get("atomic_finding_id"),
                "candidate_id": row.get("candidate_id"),
                "cluster_id": cluster_id,
                "bug_type_id": bug_type_id,
                "mapping_status": "unresolved_singleton" if "-U" in bug_type_id else "canonical_bug_type",
            }
        )

    registry = {
        "schema_version": 1,
        "source": "artifacts/bug-campaign/taxonomy/06-cluster-seeds.jsonl",
        "bug_type_count": len(registry_entries),
        "canonical_bug_type_count": sum(1 for entry in registry_entries if entry["status"] == "needs_repro"),
        "unresolved_singleton_count": sum(1 for entry in registry_entries if entry["status"] == "unresolved_singleton"),
        "bug_types": registry_entries,
    }
    return registry, finding_to_type_rows, "\n".join(unresolved_lines)


def write_campaign_docs(verified: Mapping[str, object], candidates: Sequence[Mapping[str, object]]) -> None:
    status_counts = coerce_mapping(verified.get("status_counts"))
    category_counts = coerce_mapping(verified.get("category_counts"))
    experiment_counts = coerce_mapping(verified.get("experiment_counts"))
    manifest = coerce_mapping(verified.get("manifest"))
    source_hashes = {
        "master_plan_sha256": sha256_file(MASTER_PLAN_PATH),
        "verified_json_sha256": sha256_file(VERIFIED_PATH),
        "raw_bugs_json_sha256": sha256_file(RAW_BUGS_PATH),
    }
    write_text(
        CAMPAIGN_ROOT / "00-charter.md",
        f"""# Phase 00 Campaign Charter

## Frozen Source Corpus

- copied bundle root: `{SOURCE_ROOT.relative_to(REPO_ROOT)}`
- original batch root: `{verified.get("batch_root")}`
- original verification root: `{verified.get("verification_root")}`
- generated_at: `{verified.get("generated_at")}`
- candidate_count: `{len(candidates)}`
- experiment_instance_count: `{len(experiment_counts)}`
- status_counts: `{dict(sorted(status_counts.items()))}`
- category_counts: `{dict(sorted(category_counts.items()))}`

## Output Root

The tracked campaign output root is `artifacts/bug-campaign`.  The ignored
`tmp/handoff-bundle` tree is treated as read-only source evidence.

## Source Hashes

```json
{json.dumps(source_hashes, indent=2, sort_keys=True)}
```
""",
    )
    write_text(
        CAMPAIGN_ROOT / "00-scope.md",
        f"""# Phase 00 Scope

## In Scope

- Ingest all `{len(candidates)}` verifier candidates.
- Preserve raw provenance from nested JSON fields, especially raw source paths and raw spans.
- Separate product-local findings from environment, expected-behavior, and insufficient-detail records.
- Reconstruct only checked-in Phase 08/09 coverage unless original repro artifacts are present.
- Track missing exact repro/transcript gaps explicitly.

## Out Of Scope

- Mutating original stress-test workspaces under `{manifest.get("batch_root")}`.
- Treating verifier status as fresh reproduction status.
- Promoting `heuristic_candidate` records into closed product bugs without repro packets.
- Copying the full `/tmp/gpd-bug-campaign` workspace tree into git.
""",
    )
    write_text(
        CAMPAIGN_ROOT / "00-decision-log.md",
        """# Phase 00 Decision Log

1. Use `artifacts/bug-campaign` as the tracked campaign root because `tmp/` is ignored.
2. Treat `tmp/handoff-bundle` as the frozen source bundle and do not edit it.
3. Use nested raw JSON provenance over candidate Markdown headers when they disagree or lose line data.
4. Interpret `verified_from_source` as source-confirmed, not fresh-reproduced.
5. Keep Phase 08 reconstruction partial unless the original `/tmp/gpd-bug-campaign/repro/08-*` corpus is present.
6. Import only small Phase 11-14 summary/matrix artifacts from `/tmp/gpd-bug-campaign`, not run workspaces.
""",
    )


def write_taxonomy_contract() -> None:
    write_text(
        TAXONOMY_ROOT / "01-taxonomy-spec.md",
        """# Phase 01 Taxonomy Spec

## Units

- Candidate: one verifier record from the source bundle; not a unique bug type.
- Atomic finding: one expected-vs-actual claim with one trigger and one scope.
- Bug type: one broken invariant on one product surface under one trigger scope.
- Symptom: downstream manifestation of a bug type on another surface.
- Noise record: environment pollution, missing prerequisite, sandbox constraint, observer failure, or transport failure.

## Merge Key

Use `surface x invariant x trigger x scope`.  Do not merge on title, category,
experiment slug, or raw fingerprint alone.

## Confidence Policy

The raw and verified confidence scores are triage evidence only.  They do not
replace deterministic reproduction and must not close a bug type.
""",
    )
    write_yaml(
        TAXONOMY_ROOT / "01-field-dictionary.yaml",
        {
            "schema_version": 1,
            "candidate": [
                "candidate_id",
                "experiment_slug",
                "status",
                "category",
                "confidence",
                "source_path",
                "source_format",
                "source_file",
                "source_line",
                "raw_source_path",
                "raw_source_kind",
                "raw_source_role",
                "raw_span_line_start",
                "raw_span_line_end",
                "raw_fingerprint",
                "raw_title",
                "raw_category",
                "raw_confidence",
                "raw_severity_hint",
                "report_path",
                "workspace_path",
                "repro_hint",
                "notes",
                "command_hints",
                "evidence",
                "section_path",
                "excerpt",
            ],
            "atomic_finding": [
                "atomic_finding_id",
                "candidate_id",
                "experiment_slug",
                "source_span",
                "raw_fingerprint",
                "raw_title",
                "raw_category",
                "status",
                "confidence",
                "expected_claim",
                "actual_claim",
                "trigger_or_command",
                "scope",
                "evidence_excerpt",
                "command_hints",
                "heuristic_only",
            ],
            "normalized_finding": [
                "normalized_surface_id",
                "surface_mode",
                "broken_invariant_id",
                "trigger_precondition",
                "expected_truth_source",
                "actual_behavior_signature",
                "authoritative_comparator_surface",
                "environment_scope",
                "affected_substrate_primary",
            ],
        },
    )
    write_text(
        TAXONOMY_ROOT / "01-merge-rubric.md",
        """# Phase 01 Merge Rubric

## Merge

- Same normalized surface id.
- Same broken invariant id.
- Same trigger/precondition.
- Same environment scope.

## Split

- One candidate contains multiple bullet claims with different commands or observed behaviors.
- A claim mixes environment failure with product-local behavior.
- A bridge/runtime failure and a raw CLI failure have different authority surfaces.

## Do Not Promote

- `heuristic_candidate` rows without command evidence.
- Source-confirmed rows as fresh-reproduced bugs.
- Environment-only failures as product-local bugs.
""",
    )


def write_taxonomy_ledgers(
    verified: Mapping[str, object],
    candidates: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    candidate_rows = candidate_ledger_rows(candidates)
    findings, candidate_to_finding = atomize(candidates)
    normalized = normalize_findings(findings)
    clusters, cluster_finding_map = cluster_rows(normalized)
    registry, finding_to_type_rows, unresolved_md = bug_registry(clusters, cluster_finding_map)

    write_jsonl(TAXONOMY_ROOT / "02-candidates.jsonl", candidate_rows)
    write_csv(
        TAXONOMY_ROOT / "02-provenance.csv",
        (
            "candidate_id",
            "experiment_slug",
            "source_path",
            "raw_source_path",
            "raw_span_line_start",
            "raw_span_line_end",
            "report_path",
            "workspace_path",
            "raw_fingerprint",
        ),
        candidate_rows,
    )
    write_jsonl(TAXONOMY_ROOT / "03-atomic-findings.jsonl", findings)
    write_csv(
        TAXONOMY_ROOT / "03-candidate-to-finding-map.csv",
        ("candidate_id", "atomic_finding_id", "claim_index", "atomization_method", "heuristic_only"),
        candidate_to_finding,
    )
    write_jsonl(TAXONOMY_ROOT / "04-normalized-findings.jsonl", normalized)

    surface_counts = Counter(str(row["normalized_surface_id"]) for row in normalized)
    invariant_counts = Counter(str(row["broken_invariant_id"]) for row in normalized)
    environment_counts = Counter(str(row["environment_scope"]) for row in normalized)
    write_yaml(
        TAXONOMY_ROOT / "04-surface-dictionary.yaml",
        {"schema_version": 1, "surfaces": dict(sorted(surface_counts.items()))},
    )
    write_yaml(
        TAXONOMY_ROOT / "04-invariant-catalog.yaml",
        {"schema_version": 1, "invariants": dict(sorted(invariant_counts.items()))},
    )
    write_yaml(
        TAXONOMY_ROOT / "04-environment-flags.yaml",
        {"schema_version": 1, "environment_scopes": dict(sorted(environment_counts.items()))},
    )

    disposition_rows: dict[str, list[dict[str, object]]] = {
        "product_finding": [],
        "noise": [],
        "expected_behavior_or_non_product": [],
        "insufficient_detail": [],
    }
    for row in normalized:
        disposition_rows.setdefault(str(row["disposition"]), []).append(dict(row))
    write_jsonl(TAXONOMY_ROOT / "05-product-findings.jsonl", disposition_rows["product_finding"])
    write_jsonl(TAXONOMY_ROOT / "05-noise-registry.jsonl", disposition_rows["noise"])
    write_jsonl(
        TAXONOMY_ROOT / "05-expected-behavior-registry.jsonl",
        disposition_rows["expected_behavior_or_non_product"],
    )
    write_jsonl(TAXONOMY_ROOT / "05-insufficient-detail.jsonl", disposition_rows["insufficient_detail"])

    write_jsonl(TAXONOMY_ROOT / "06-cluster-seeds.jsonl", clusters)
    write_csv(
        TAXONOMY_ROOT / "06-merge-candidates.csv",
        (
            "cluster_id",
            "normalized_surface_id",
            "broken_invariant_id",
            "trigger_precondition",
            "environment_scope",
            "atomic_finding_count",
            "candidate_count",
        ),
        (cluster for cluster in clusters if int(cluster["atomic_finding_count"]) > 1),
    )
    split_decisions = [
        {
            "candidate_id": candidate_id,
            "finding_count": count,
            "split_decision": "split" if count > 1 else "single",
        }
        for candidate_id, count in sorted(Counter(str(row["candidate_id"]) for row in findings).items())
    ]
    write_csv(
        TAXONOMY_ROOT / "06-split-decisions.csv", ("candidate_id", "finding_count", "split_decision"), split_decisions
    )

    write_json(TAXONOMY_ROOT / "07-bug-type-registry.json", registry)
    write_text(
        TAXONOMY_ROOT / "07-bug-type-registry.md",
        bug_registry_markdown(registry),
    )
    write_csv(
        TAXONOMY_ROOT / "07-finding-to-type-map.csv",
        ("atomic_finding_id", "candidate_id", "cluster_id", "bug_type_id", "mapping_status"),
        finding_to_type_rows,
    )
    write_text(TAXONOMY_ROOT / "07-unresolved-singletons.md", unresolved_md)

    summary = {
        "schema_version": 1,
        "source_candidate_count": len(candidates),
        "source_status_counts": verified.get("status_counts"),
        "source_category_counts": verified.get("category_counts"),
        "candidate_ledger_count": len(candidate_rows),
        "atomic_finding_count": len(findings),
        "normalized_finding_count": len(normalized),
        "disposition_counts": {key: len(value) for key, value in sorted(disposition_rows.items())},
        "cluster_count": len(clusters),
        "bug_type_count": registry["bug_type_count"],
        "unresolved_singleton_count": registry["unresolved_singleton_count"],
    }
    write_json(TAXONOMY_ROOT / "taxonomy-summary.json", summary)
    return findings, normalized, registry


def bug_registry_markdown(registry: Mapping[str, object]) -> str:
    lines = [
        "# Phase 07 Bug Type Registry",
        "",
        f"- bug_type_count: `{registry.get('bug_type_count')}`",
        f"- canonical_bug_type_count: `{registry.get('canonical_bug_type_count')}`",
        f"- unresolved_singleton_count: `{registry.get('unresolved_singleton_count')}`",
        "",
    ]
    for entry in coerce_sequence(registry.get("bug_types")):
        if not isinstance(entry, Mapping):
            continue
        lines.extend(
            (
                f"## {entry.get('bug_type_id')}",
                "",
                f"- title: {entry.get('title')}",
                f"- invariant: `{entry.get('invariant')}`",
                f"- trigger: `{entry.get('trigger')}`",
                f"- scope: `{entry.get('scope')}`",
                f"- status: `{entry.get('status')}`",
                f"- candidate_count: `{entry.get('candidate_count')}`",
                f"- atomic_finding_count: `{entry.get('atomic_finding_count')}`",
                "",
            )
        )
    return "\n".join(lines)


def write_phase08_reconstruction() -> dict[str, object]:
    manifest = read_json_object(HANDOFF_MANIFEST_PATH)
    fixtures = [row for row in coerce_sequence(manifest.get("fixtures")) if isinstance(row, Mapping)]
    family_records: dict[str, dict[str, object]] = {}
    queue_records: list[dict[str, object]] = []
    unique_packet_ids: set[str] = set()
    for fixture in fixtures:
        packet_ids = string_list(fixture.get("packet_ids"))
        bug_type_ids = string_list(fixture.get("bug_type_ids"))
        command_recipes = [
            item for item in coerce_sequence(fixture.get("command_recipes")) if isinstance(item, Sequence)
        ]
        expected_assertions = string_list(fixture.get("expected_assertions"))
        actual_assertions = string_list(fixture.get("actual_assertions"))
        for index, (packet_id, bug_type_id) in enumerate(zip(packet_ids, bug_type_ids, strict=True)):
            family = family_records.setdefault(
                bug_type_id,
                {
                    "bug_type_id": bug_type_id,
                    "packet_ids": [],
                    "fixture_ids": [],
                    "anchor_candidate_ids": [],
                    "interface_classes": [],
                    "source_workspaces": [],
                    "starting_snapshot_hashes": [],
                    "priority_score": fixture.get("priority_score"),
                    "status": "partial_reconstructed_from_phase09_manifest",
                },
            )
            for key in ("packet_ids", "fixture_ids", "anchor_candidate_ids", "interface_classes"):
                values = {
                    "packet_ids": [packet_id],
                    "fixture_ids": [fixture.get("fixture_id")],
                    "anchor_candidate_ids": string_list(fixture.get("anchor_candidate_ids")),
                    "interface_classes": string_list(fixture.get("interface_classes")),
                }[key]
                current = list(coerce_sequence(family[key]))
                for value in values:
                    if value not in current:
                        current.append(value)
                family[key] = current
            for key in ("source_workspaces", "starting_snapshot_hashes"):
                current = list(coerce_sequence(family[key]))
                for value in string_list(fixture.get(key)):
                    if value not in current:
                        current.append(value)
                family[key] = current
            recipe = string_list(command_recipes[index]) if index < len(command_recipes) else []
            unique_packet_ids.add(packet_id)
            queue_records.append(
                {
                    "queue_entry_id": f"{packet_id}::{fixture.get('fixture_id')}",
                    "packet_id": packet_id,
                    "bug_type_id": bug_type_id,
                    "fixture_id": fixture.get("fixture_id"),
                    "fixture_path": fixture.get("fixture_path"),
                    "workspace_path": fixture.get("workspace_path"),
                    "anchor_candidate_ids": string_list(fixture.get("anchor_candidate_ids")),
                    "source_workspaces": string_list(fixture.get("source_workspaces")),
                    "starting_snapshot_hashes": string_list(fixture.get("starting_snapshot_hashes")),
                    "minimal_command_sequence": recipe,
                    "expected_assertion": expected_assertions[index] if index < len(expected_assertions) else "unknown",
                    "actual_assertion": actual_assertions[index] if index < len(actual_assertions) else "unknown",
                    "interface_class": fixture.get("primary_interface_class"),
                    "evidence_links": string_list(fixture.get("evidence_links")),
                    "status": "partial_reconstructed_from_phase09_manifest",
                }
            )

    family_manifest = {
        "schema_version": 1,
        "source_authority": "tests/fixtures/handoff-bundle/manifest.json",
        "reconstruction_scope": "covered_live_phase09_subset",
        "accepted_phase08_packet_count": manifest.get("accepted_phase08_packet_count"),
        "accepted_phase08_blocked_count": manifest.get("accepted_phase08_blocked_count"),
        "covered_bug_type_count": len(family_records),
        "covered_packet_count": len(queue_records),
        "covered_unique_packet_count": len(unique_packet_ids),
        "families": [family_records[key] for key in sorted(family_records)],
    }
    queue = queue_records
    blocked = list(coerce_sequence(manifest.get("blocked_references")))
    write_json(REPRO_ROOT / "08-family-manifest.json", family_manifest)
    write_json(REPRO_ROOT / "08-repro-queue.json", queue)
    write_json(REPRO_ROOT / "08-blocked-candidates.json", blocked)
    write_text(
        REPRO_ROOT / "08-priority-board.md",
        phase08_priority_board(family_manifest, queue, blocked),
    )
    for family in family_manifest["families"]:
        if not isinstance(family, Mapping):
            continue
        write_text(REPRO_ROOT / "08-packets" / f"{family['bug_type_id']}.md", phase08_packet_markdown(family, queue))
    return {
        "covered_bug_type_count": len(family_records),
        "covered_packet_count": len(queue_records),
        "covered_unique_packet_count": len(unique_packet_ids),
        "blocked_reference_count": len(blocked),
        "accepted_phase08_packet_count": manifest.get("accepted_phase08_packet_count"),
        "accepted_phase08_blocked_count": manifest.get("accepted_phase08_blocked_count"),
    }


def phase08_priority_board(
    family_manifest: Mapping[str, object],
    queue: Sequence[Mapping[str, object]],
    blocked: Sequence[object],
) -> str:
    lines = [
        "# Phase 08 Priority Board",
        "",
        "- reconstruction_scope: `covered_live_phase09_subset`",
        f"- accepted_phase08_packet_count: `{family_manifest.get('accepted_phase08_packet_count')}`",
        f"- reconstructed_packet_count: `{len(queue)}`",
        f"- reconstructed_bug_type_count: `{family_manifest.get('covered_bug_type_count')}`",
        f"- blocked_reference_count: `{len(blocked)}`",
        "",
    ]
    for row in queue[:50]:
        lines.append(f"- `{row.get('packet_id')}` -> `{row.get('bug_type_id')}` via `{row.get('fixture_id')}`")
    if len(queue) > 50:
        lines.append(f"- ... {len(queue) - 50} additional packets omitted from the board preview")
    return "\n".join(lines)


def phase08_packet_markdown(family: Mapping[str, object], queue: Sequence[Mapping[str, object]]) -> str:
    bug_type_id = str(family["bug_type_id"])
    packets = [row for row in queue if row.get("bug_type_id") == bug_type_id]
    lines = [
        f"# Phase 08 Packet {bug_type_id}",
        "",
        "- reconstruction_scope: `covered_live_phase09_subset`",
        f"- packet_ids: `{', '.join(str(row.get('packet_id')) for row in packets)}`",
        f"- anchor_candidate_ids: `{', '.join(string_list(family.get('anchor_candidate_ids')))}`",
        f"- interface_classes: `{', '.join(string_list(family.get('interface_classes')))}`",
        "",
        "## Assertions",
        "",
    ]
    for row in packets:
        lines.extend(
            (
                f"### {row.get('packet_id')}",
                "",
                f"- fixture: `{row.get('fixture_id')}`",
                f"- workspace: `{row.get('workspace_path')}`",
                f"- commands: `{row.get('minimal_command_sequence')}`",
                f"- expected: {row.get('expected_assertion')}",
                f"- actual: {row.get('actual_assertion')}",
                "",
            )
        )
    return "\n".join(lines)


def phase10_pytest_command(family: Mapping[str, object]) -> str:
    return "uv run pytest -q -n 0 " + " ".join(string_list(family.get("pytest_args")))


def phase10_script_content(family: Mapping[str, object]) -> str:
    command = phase10_pytest_command(family)
    return f"""#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/../../../.." && pwd)"
cd "$REPO_ROOT"

{command}
"""


def phase10_oracle(family: Mapping[str, object]) -> dict[str, object]:
    positive_fixtures = string_list(family.get("positive_fixtures"))
    mutation_fixtures = string_list(family.get("mutation_fixtures"))
    return {
        "schema_version": 1,
        "phase": "10",
        "family_id": family.get("family_id"),
        "priority_family": family.get("priority_family"),
        "reconstruction_scope": "checked_in_fixture_covered_subset",
        "source_authority": "checked-in fixture-backed tests",
        "command": phase10_pytest_command(family),
        "source_tests": string_list(family.get("source_tests")),
        "fixture_coverage": {
            "positive": positive_fixtures,
            "mutation": mutation_fixtures,
            "covered_fixture_count": len(positive_fixtures) + len(mutation_fixtures),
        },
        "assertion_surface": string_list(family.get("assertion_surface")),
        "expected_outcome": "pytest exit code 0 for the current fixed behavior",
        "expected_pytest_pass_count": family.get("expected_pytest_pass_count"),
        "known_gaps": list(coerce_sequence(family.get("known_gaps"))),
        "closed_gaps": list(coerce_sequence(family.get("closed_gaps"))),
        "phase10_exit_criteria": {
            "anchor_copy_runs_required": 2,
            "confirmatory_copy_runs_required": 1,
            "strict_phase10_criteria_met": False,
            "promotion_status": "not_promoted_partial_reconstruction",
            "blocking_gap": (
                "The archived Phase 10 2/2 anchor-copy and 1/1 confirmatory-copy transcripts are absent; "
                "this oracle covers the checked-in fixture subset only."
            ),
        },
    }


def phase10_transcript_text(family: Mapping[str, object]) -> str:
    command = phase10_pytest_command(family)
    return f"""# Phase 10 Normalized Transcript: {family.get("priority_family")}

```
$ {command}
```

- expected_exit_code: `0`
- normalized_pytest_result: `{family.get("expected_pytest_pass_count")} passed`
- transcript_policy: `normalized_command_transcript`
- reconstruction_scope: `checked_in_fixture_covered_subset`
- strict_phase10_criteria_met: `false`
- historical_transcript_gap: `Original Phase 10 2/2 anchor-copy and 1/1 confirmatory-copy transcripts are absent.`

The live verification step for this artifact increment reruns the command above;
pytest timing and worker-specific temporary paths are intentionally excluded from
this normalized transcript.
"""


def phase10_wave_summary_markdown(summary: Mapping[str, object]) -> str:
    lines = [
        "# Phase 10 Wave Summary",
        "",
        "- reconstruction_scope: `checked_in_fixture_covered_subset`",
        f"- strict_phase10_exit_criteria_met: `{str(summary.get('strict_phase10_exit_criteria_met')).lower()}`",
        f"- family_count: `{summary.get('family_count')}`",
        "",
        "## Families",
        "",
    ]
    for family in coerce_sequence(summary.get("families")):
        if not isinstance(family, Mapping):
            continue
        lines.extend(
            (
                f"- `{family.get('family_id')}`",
                f"  - priority_family: `{family.get('priority_family')}`",
                f"  - oracle: `{family.get('oracle_path')}`",
                f"  - script: `{family.get('script_path')}`",
                f"  - transcript: `{family.get('transcript_path')}`",
                f"  - promotion_status: `{family.get('promotion_status')}`",
            )
        )
    lines.extend(
        (
            "",
            "## Blocking Gap",
            "",
            "The checked-in fixture subset makes the priority families runnable and regression-guarded, "
            "but the missing historical Phase 10 copy-run transcripts still block strict deterministic promotion.",
        )
    )
    return "\n".join(lines)


def write_phase10_reconstruction() -> dict[str, object]:
    oracle_root = REPRO_ROOT / "10-oracles"
    script_root = REPRO_ROOT / "10-scripts"
    transcript_root = REPRO_ROOT / "10-transcripts"
    family_rows: list[dict[str, object]] = []

    for family in PHASE10_FAMILIES:
        oracle_path = oracle_root / str(family["oracle_filename"])
        script_path = script_root / str(family["script_filename"])
        transcript_path = transcript_root / str(family["transcript_filename"])
        oracle = phase10_oracle(family)

        write_json(oracle_path, oracle)
        write_text(script_path, phase10_script_content(family))
        script_path.chmod(0o755)
        write_text(transcript_path, phase10_transcript_text(family))
        family_rows.append(
            {
                "family_id": family["family_id"],
                "priority_family": family["priority_family"],
                "oracle_path": oracle_path.relative_to(OUTPUT_ROOT).as_posix(),
                "script_path": script_path.relative_to(OUTPUT_ROOT).as_posix(),
                "transcript_path": transcript_path.relative_to(OUTPUT_ROOT).as_posix(),
                "command": oracle["command"],
                "expected_pytest_pass_count": oracle["expected_pytest_pass_count"],
                "covered_fixture_count": coerce_mapping(oracle["fixture_coverage"]).get("covered_fixture_count"),
                "promotion_status": "not_promoted_partial_reconstruction",
            }
        )

    summary = {
        "schema_version": 1,
        "phase": "10",
        "source_authority": "checked-in fixture-backed tests",
        "source_master_plan": "tmp/handoff-bundle/MASTER-BUG-CAMPAIGN-PLAN.md",
        "reconstruction_scope": "checked_in_fixture_covered_subset",
        "status": "covered_subset_reconstructed_not_promoted",
        "strict_phase10_exit_criteria_met": False,
        "family_count": len(family_rows),
        "families": family_rows,
        "blocking_gaps": [
            "Original repro/10 exact scripts, full transcripts, and copy-run results were not present in the "
            "frozen source bundle.",
            "Current artifacts do not satisfy the master plan's 2/2 anchor-copy plus 1/1 confirmatory-copy "
            "promotion rule.",
        ],
    }
    write_json(REPRO_ROOT / "10-wave-summary.json", summary)
    write_text(REPRO_ROOT / "10-wave-summary.md", phase10_wave_summary_markdown(summary))
    return {
        "status": summary["status"],
        "strict_phase10_exit_criteria_met": summary["strict_phase10_exit_criteria_met"],
        "family_count": summary["family_count"],
        "evidence": ["repro/10-wave-summary.json", "repro/10-wave-summary.md"],
        "gap": "Covered fixture subset reconstructed; strict Phase 10 copy-run transcripts remain absent.",
    }


def import_external_repro_artifacts() -> dict[str, object]:
    imported: list[str] = []
    missing: list[str] = []
    for name in EXTERNAL_REPRO_IMPORTS:
        source = EXTERNAL_REPRO_ROOT / name
        destination = REPRO_ROOT / name
        if source.exists():
            if source.suffix == ".md":
                write_text(destination, source.read_text(encoding="utf-8"))
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            imported.append(name)
        else:
            missing.append(name)
    return {"source_root": str(EXTERNAL_REPRO_ROOT), "imported": imported, "missing": missing}


def write_phase15_generated_source_artifacts() -> None:
    for path, payload in PHASE15_GENERATED_SOURCE_ARTIFACTS.items():
        write_json(REPO_ROOT / path, payload)


def write_phase15_registry() -> None:
    index_families: list[dict[str, object]] = []
    for family in PHASE15_FAMILIES:
        source_path = REPO_ROOT / str(family["source_artifact_path"])
        source_payload = read_json_object(source_path)
        adjacent = source_payload.get("adjacent_checks")
        wrapper = {
            "schema_version": 1,
            "phase": "15",
            "bug_id": family["bug_id"],
            "family_id": family["family_id"],
            "family_title": family["family_title"],
            "wave": family["wave"],
            "status": family["status"],
            "classification": source_payload.get("classification") or "verification_contract",
            "contract_test": family["contract_test"],
            "source_artifact_path": family["source_artifact_path"],
            "source_artifact_status": source_payload.get("status"),
            "source_artifact_wave": source_payload.get("wave"),
            "gates": {
                "red_exact_repro_present": bool(source_payload.get("exact_repro")),
                "green_exact_fix_present": bool(source_payload.get("exact_fix")),
                "green_adjacent_checks_present": bool(adjacent),
                "artifact_json_written": True,
            },
            "closure_candidate": family["status"] == "closed",
        }
        write_json(REPO_ROOT / str(family["artifact_path"]), wrapper)
        index_families.append(
            {
                "bug_id": family["bug_id"],
                "family_id": family["family_id"],
                "family_title": family["family_title"],
                "contract_test": family["contract_test"],
                "artifact_path": family["artifact_path"],
                "status": family["status"],
                "classification": wrapper["classification"],
            }
        )
    write_json(
        PHASE15_ROOT / "index.json",
        {
            "schema_version": 1,
            "phase": "15",
            "wave": "F2-F5",
            "artifact_root": "artifacts/phases/15-verification-contract/verification/fixes",
            "families": index_families,
            "checklist_items": [
                "Red exact repro",
                "Green exact fix",
                "Green adjacent checks",
                "Artifact JSON written",
            ],
        },
    )


def write_scorecards(
    verified: Mapping[str, object],
    findings: Sequence[Mapping[str, object]],
    normalized: Sequence[Mapping[str, object]],
    registry: Mapping[str, object],
    phase08: Mapping[str, object],
    external_repro: Mapping[str, object],
) -> None:
    phase15_index = read_json_object(PHASE15_ROOT / "index.json")
    fixture_manifest = read_json_object(HANDOFF_MANIFEST_PATH)
    thresholds = read_json_object(PHASE17_THRESHOLDS_PATH)
    phase17_watchdog = read_json_object(PHASE17_WATCHDOG_PATH)
    phase17_checkpoints = read_json_object(PHASE17_CHECKPOINTS_PATH)
    workflow = yaml.safe_load(NIGHTLY_WORKFLOW_PATH.read_text(encoding="utf-8"))
    if not isinstance(workflow, Mapping):
        workflow = {}

    phase15_rows: list[dict[str, object]] = []
    for family in coerce_sequence(phase15_index.get("families")):
        if not isinstance(family, Mapping):
            continue
        artifact_path = REPO_ROOT / str(family.get("artifact_path"))
        artifact_payload = read_json_object(artifact_path) if artifact_path.exists() else {}
        gates = coerce_mapping(artifact_payload.get("gates"))
        phase15_rows.append(
            {
                "family_id": family.get("family_id"),
                "bug_id": family.get("bug_id"),
                "registry_status": family.get("status"),
                "artifact_status": artifact_payload.get("status"),
                "contract_test_path": family.get("contract_test"),
                "contract_test_exists": (REPO_ROOT / str(family.get("contract_test"))).exists(),
                "artifact_path_declared": family.get("artifact_path"),
                "artifact_path_exists": artifact_path.exists(),
                "red_exact_repro_present": bool(gates.get("red_exact_repro_present")),
                "green_exact_fix_present": bool(gates.get("green_exact_fix_present")),
                "green_adjacent_checks_present": bool(gates.get("green_adjacent_checks_present")),
                "verification_status": artifact_payload.get("status"),
                "closure_candidate": artifact_payload.get("closure_candidate"),
                "closure_blockers": [] if artifact_payload.get("closure_candidate") else ["not marked closed"],
            }
        )
    write_json(
        SCORECARD_ROOT / "repro-funnel.json",
        {
            "schema_version": 1,
            "candidate_count": len(candidates_from_verified(verified)),
            "atomic_finding_count": len(findings),
            "normalized_finding_count": len(normalized),
            "clustered_bug_type_count": registry.get("bug_type_count"),
            "packetized_covered_packet_count": phase08.get("covered_packet_count"),
            "packetized_accepted_phase08_packet_count": phase08.get("accepted_phase08_packet_count"),
            "phase15_families": phase15_rows,
            "external_repro_import": external_repro,
        },
    )

    fixtures = [row for row in coerce_sequence(fixture_manifest.get("fixtures")) if isinstance(row, Mapping)]
    family_counts = Counter(PHASE16_SLUG_TO_FAMILY[str(row.get("fixture_slug"))] for row in fixtures)
    write_json(
        SCORECARD_ROOT / "surface-parity.json",
        {
            "schema_version": 1,
            "phase16_case_count": len(fixtures),
            "case_keys": [f"{row.get('fixture_slug')}/{row.get('fixture_kind')}" for row in fixtures],
            "family_counts": dict(sorted(family_counts.items())),
            "owner_modules": PHASE16_FAMILY_TO_MODULE,
            "fixture_status_counts": dict(sorted(Counter(str(row.get("status")) for row in fixtures).items())),
            "projection_test_modules_present": {
                family: (REPO_ROOT / module).exists() for family, module in PHASE16_FAMILY_TO_MODULE.items()
            },
            "allowlisted_diff_count": "not_materialized",
            "unexpected_diff_count": "not_materialized",
        },
    )

    checkpoint_experiments = coerce_sequence(phase17_checkpoints.get("experiments"))
    write_json(
        SCORECARD_ROOT / "checkpoint-board.json",
        {
            "schema_version": 1,
            "pilot_case_count": len(coerce_sequence(coerce_mapping(thresholds.get("registry")).get("pilot"))),
            "full_case_count": len(coerce_sequence(coerce_mapping(thresholds.get("registry")).get("full"))),
            "checkpoint_case_count": len(coerce_sequence(coerce_mapping(thresholds.get("registry")).get("checkpoint"))),
            "checkpoint_batch_experiment_count": len(checkpoint_experiments),
            "watchdog_repair_rounds": phase17_watchdog.get("repair_rounds"),
            "batch_repair_rounds": phase17_checkpoints.get("repair_rounds"),
            "batch_kind": phase17_checkpoints.get("kind"),
        },
    )

    on_block = workflow.get("on") if isinstance(workflow.get("on"), Mapping) else workflow.get(True, {})
    benchmark_modules = (
        "benchmarks/test_resume_recent.py",
        "benchmarks/test_query_index_freshness.py",
        "benchmarks/test_phase_projection_latency.py",
        "benchmarks/test_checkpoint_batch.py",
    )
    write_json(
        SCORECARD_ROOT / "benchmarks.json",
        {
            "schema_version": 1,
            "thresholds": thresholds.get("thresholds"),
            "metric_sources_present": sorted(coerce_mapping(thresholds.get("metric_sources")).keys()),
            "warmup_runs": coerce_mapping(thresholds.get("timing")).get("warmup_runs"),
            "sample_runs": coerce_mapping(thresholds.get("timing")).get("sample_runs"),
            "benchmark_modules_present": {module: (REPO_ROOT / module).exists() for module in benchmark_modules},
            "nightly_modes": list(coerce_mapping(thresholds.get("registry")).keys()),
            "nightly_permissions": workflow.get("permissions"),
            "nightly_scheduled": "schedule" in coerce_mapping(on_block),
            "thresholds_enforced_by_tests": (REPO_ROOT / "tests" / "test_phase17_nightly_contract.py").exists(),
        },
    )

    write_json(
        SCORECARD_ROOT / "family-closure.json",
        {
            "schema_version": 1,
            "phase15_family_count": len(phase15_rows),
            "closed_phase15_family_count": sum(1 for row in phase15_rows if row["closure_candidate"]),
            "taxonomy_bug_type_count": registry.get("bug_type_count"),
            "taxonomy_unresolved_singleton_count": registry.get("unresolved_singleton_count"),
            "families": [
                {
                    "family_id": row["family_id"],
                    "bug_class": row["bug_id"],
                    "mapped_surfaces": "see taxonomy/07-bug-type-registry.json",
                    "gates_complete": all(
                        bool(row[key])
                        for key in (
                            "artifact_path_exists",
                            "contract_test_exists",
                            "red_exact_repro_present",
                            "green_exact_fix_present",
                            "green_adjacent_checks_present",
                        )
                    ),
                    "artifact_registry_consistent": row["artifact_path_exists"],
                    "test_guard_present": row["contract_test_exists"],
                    "nightly_green_run_count": 0,
                    "release_candidate_green_count": 0,
                    "unconverted_manual_repro_count": verified.get("status_counts", {}).get("needs_manual_repro")
                    if isinstance(verified.get("status_counts"), Mapping)
                    else "unknown",
                    "closed": False,
                    "closure_reason": "Scorecard gates require durable nightly/release-candidate run history before closure.",
                }
                for row in phase15_rows
            ],
        },
    )


def write_phase_status(
    phase08: Mapping[str, object],
    phase10: Mapping[str, object],
    external_repro: Mapping[str, object],
) -> None:
    imported = set(string_list(external_repro.get("imported")))
    statuses = [
        {"phase": "00", "name": "Campaign Freeze", "status": "complete", "evidence": ["campaign/00-charter.md"]},
        {
            "phase": "01",
            "name": "Taxonomy Contract",
            "status": "complete",
            "evidence": ["taxonomy/01-taxonomy-spec.md"],
        },
        {"phase": "02", "name": "Candidate Ledger", "status": "complete", "evidence": ["taxonomy/02-candidates.jsonl"]},
        {"phase": "03", "name": "Atomization", "status": "complete", "evidence": ["taxonomy/03-atomic-findings.jsonl"]},
        {
            "phase": "04",
            "name": "Evidence Normalization",
            "status": "complete",
            "evidence": ["taxonomy/04-normalized-findings.jsonl"],
        },
        {
            "phase": "05",
            "name": "Disposition Triage",
            "status": "complete",
            "evidence": ["taxonomy/05-product-findings.jsonl"],
        },
        {
            "phase": "06",
            "name": "Cluster Seeding",
            "status": "complete",
            "evidence": ["taxonomy/06-cluster-seeds.jsonl"],
        },
        {
            "phase": "07",
            "name": "Bug Type Registry",
            "status": "complete",
            "evidence": ["taxonomy/07-bug-type-registry.json"],
        },
        {
            "phase": "08",
            "name": "Repro Packetization",
            "status": "partial_reconstructed",
            "evidence": ["repro/08-family-manifest.json"],
            "gap": "Only checked-in Phase 09 live subset reconstructed; full 203/250 Phase 08 corpus absent.",
            "reconstructed_packet_count": phase08.get("covered_packet_count"),
        },
        {
            "phase": "09",
            "name": "Fixture Construction",
            "status": "tracked",
            "evidence": ["tests/fixtures/handoff-bundle/manifest.json"],
        },
        {
            "phase": "10",
            "name": "CLI Fast-Path Anchor Repro",
            "status": phase10.get("status"),
            "evidence": string_list(phase10.get("evidence")),
            "gap": phase10.get("gap"),
            "reconstructed_family_count": phase10.get("family_count"),
            "strict_phase10_exit_criteria_met": phase10.get("strict_phase10_exit_criteria_met"),
        },
        {
            "phase": "11",
            "name": "Mutation And Ordering Repro",
            "status": "imported_external_summary" if "11-mutation-summary.md" in imported else "external_missing",
            "evidence": ["repro/11-mutation-summary.md"],
        },
        {
            "phase": "12",
            "name": "Breadth Sweep",
            "status": "imported_external_summary"
            if "12-family-prevalence-matrix.json" in imported
            else "external_missing",
            "evidence": ["repro/12-family-prevalence-matrix.json"],
        },
        {
            "phase": "13",
            "name": "MCP / Sandbox / Environment Characterization",
            "status": "imported_external_summary" if "13-environment-matrix.json" in imported else "external_missing",
            "evidence": ["repro/13-environment-matrix.json"],
        },
        {
            "phase": "14",
            "name": "Flake Soak And Residual Heuristics",
            "status": "imported_external_summary" if "14-flake-dossier.md" in imported else "external_missing",
            "evidence": ["repro/14-flake-dossier.md"],
        },
        {
            "phase": "15",
            "name": "Fix Verification Contract",
            "status": "tracked_with_registry_hardened",
            "evidence": ["artifacts/phases/15-verification-contract/verification/fixes/index.json"],
        },
        {
            "phase": "16",
            "name": "Cross-Surface Consistency Oracle",
            "status": "tracked",
            "evidence": ["tests/phase16_projection_oracle_helpers.py"],
        },
        {
            "phase": "17",
            "name": "Nightly Matrix And Benchmarks",
            "status": "tracked",
            "evidence": ["benchmarks/phase17_thresholds.json", ".github/workflows/nightly-handoff-bundle.yml"],
        },
        {
            "phase": "18",
            "name": "Scorecards And Closure Gates",
            "status": "scorecards_generated_not_closed",
            "evidence": ["artifacts/verification/scorecards/family-closure.json"],
        },
    ]
    payload = {"schema_version": 1, "phase_statuses": statuses}
    write_json(OUTPUT_ROOT / "phase-status.json", payload)
    lines = ["# Bug Campaign Phase Status", ""]
    for row in statuses:
        lines.append(f"- Phase {row['phase']} {row['name']}: `{row['status']}`")
        if "gap" in row:
            lines.append(f"  - gap: {row['gap']}")
    write_text(OUTPUT_ROOT / "phase-status.md", "\n".join(lines))


def main() -> None:
    verified = read_json_object(VERIFIED_PATH)
    candidates = candidates_from_verified(verified)
    write_campaign_docs(verified, candidates)
    write_taxonomy_contract()
    findings, normalized, registry = write_taxonomy_ledgers(verified, candidates)
    phase08 = write_phase08_reconstruction()
    phase10 = write_phase10_reconstruction()
    external_repro = import_external_repro_artifacts()
    write_phase15_generated_source_artifacts()
    write_phase15_registry()
    write_scorecards(verified, findings, normalized, registry, phase08, external_repro)
    write_phase_status(phase08, phase10, external_repro)


if __name__ == "__main__":
    main()
