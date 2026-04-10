"""Shared helpers for the Phase 16 projection oracle tests.

The module keeps Phase 16 test-only: it loads the handoff-bundle manifest,
builds a canonical case registry, copies fixture workspaces for isolated
test runs, normalizes projection payloads, and provides a deterministic
diff/allowlist discipline for the oracle modules.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[1]
HANDOFF_BUNDLE_ROOT = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle"
HANDOFF_BUNDLE_MANIFEST_PATH = HANDOFF_BUNDLE_ROOT / "manifest.json"

PHASE16_EXPECTED_CASE_KEYS: tuple[str, ...] = (
    "completed-phase/positive",
    "plan-only/positive",
    "plan-only/mutation",
    "empty-phase/positive",
    "empty-phase/mutation",
    "query-registry-drift/positive",
    "context-indexing/positive",
    "bridge-vs-cli/positive",
    "bridge-vs-cli/mutation",
    "summary-missing-return/positive",
    "summary-missing-return/mutation",
    "mutation-ordering/positive",
    "mutation-ordering/mutation",
    "resume-handoff/positive",
    "resume-handoff/mutation",
    "resume-recent-noise/positive",
    "resume-recent-noise/mutation",
    "config-readback/positive",
    "placeholder-conventions/positive",
    "placeholder-conventions/mutation",
)

PHASE16_FAMILY_TO_MODULE: dict[str, str] = {
    "state": "tests/core/test_projection_state.py",
    "query-result": "tests/core/test_projection_query_result.py",
    "phase-verify": "tests/core/test_projection_phase_verify.py",
    "resume-observe": "tests/core/test_projection_resume_observe.py",
    "config-contract": "tests/core/test_projection_config_contract.py",
}

PHASE16_SLUG_TO_FAMILY: dict[str, str] = {
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

PHASE16_FAMILY_TO_CASE_KEYS: dict[str, tuple[str, ...]] = {
    "state": (
        "completed-phase/positive",
        "plan-only/positive",
        "plan-only/mutation",
        "empty-phase/positive",
        "empty-phase/mutation",
    ),
    "query-result": (
        "query-registry-drift/positive",
        "context-indexing/positive",
        "bridge-vs-cli/positive",
        "bridge-vs-cli/mutation",
    ),
    "phase-verify": (
        "summary-missing-return/positive",
        "summary-missing-return/mutation",
        "mutation-ordering/positive",
        "mutation-ordering/mutation",
    ),
    "resume-observe": (
        "resume-handoff/positive",
        "resume-handoff/mutation",
        "resume-recent-noise/positive",
        "resume-recent-noise/mutation",
    ),
    "config-contract": (
        "config-readback/positive",
        "placeholder-conventions/positive",
        "placeholder-conventions/mutation",
    ),
}

_NULLISH_TEXT = {"", "none", "null", "undefined", "not set"}
_IGNORE = object()
_ANY = object()
_PHASE_NUMBER_RE = re.compile(r"\d+")
_NON_ALNUM_RE = re.compile(r"[^0-9A-Za-z]+")


@dataclass(frozen=True, slots=True)
class ProjectionOracleAllowance:
    """One explicit allowlist rule for a projection diff."""

    path_pattern: str
    reason: str = ""
    kind: str | None = None
    expected: object = _ANY
    actual: object = _ANY

    def matches(self, diff: ProjectionOracleDiff) -> bool:
        if not fnmatchcase(diff.path_text, self.path_pattern):
            return False
        if self.kind is not None and diff.kind != self.kind:
            return False
        if self.expected is not _ANY and diff.expected != self.expected:
            return False
        if self.actual is not _ANY and diff.actual != self.actual:
            return False
        return True


@dataclass(frozen=True, slots=True)
class ProjectionOracleCase:
    """One handoff-bundle fixture variant tracked by the Phase 16 oracle."""

    case_key: str
    fixture_slug: str
    variant: str
    fixture_id: str
    fixture_kind: str
    status: str
    order: int
    family: str
    owner_module: str
    fixture_path: Path
    workspace_path: Path
    mutation_axis: str | None
    paired_fixture_id: str | None
    primary_interface_class: str | None
    fixture_manifest: Mapping[str, object] = field(repr=False, compare=False)
    allowlist: tuple[ProjectionOracleAllowance, ...] = ()

    @property
    def fixture_json_path(self) -> Path:
        return self.fixture_path / "fixture.json"


@dataclass(frozen=True, slots=True)
class ProjectionOracleDiff:
    """A single normalized diff emitted by the projection comparator."""

    path: tuple[str, ...]
    kind: str
    expected: object
    actual: object

    @property
    def path_text(self) -> str:
        return ".".join(self.path)


def _manifest_path(path: Path | None = None) -> Path:
    return HANDOFF_BUNDLE_MANIFEST_PATH if path is None else Path(path)


@cache
def load_handoff_bundle_manifest(path: Path | None = None) -> dict[str, object]:
    """Load the Phase 16 handoff-bundle manifest from disk."""

    manifest_path = _manifest_path(path)
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _coerce_path_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, Path):
        text = value.as_posix()
    else:
        text = str(value).strip()
    return text or None


def normalize_optional_text(value: object) -> str | None:
    """Normalize placeholder text values to ``None`` and trim whitespace."""

    text = _coerce_path_text(value)
    if text is None:
        return None
    if text.casefold() in _NULLISH_TEXT:
        return None
    return text


def normalize_identifier_token(value: object) -> str | None:
    """Normalize identifier-like text to a case-folded token."""

    text = normalize_optional_text(value)
    if text is None:
        return None
    normalized = _NON_ALNUM_RE.sub(" ", text).strip().casefold()
    return normalized or None


def normalize_phase_token(value: object) -> str | None:
    """Normalize phase identifiers to the canonical padded token."""

    text = normalize_optional_text(value)
    if text is None:
        return None
    matches = _PHASE_NUMBER_RE.findall(text)
    if not matches:
        return text
    if len(matches) == 1:
        return matches[0].zfill(2)
    return "-".join(match.zfill(2) for match in matches)


def normalize_path_value(value: object, *, base: Path | None = None) -> str | None:
    """Normalize a path-like value to a POSIX string."""

    text = normalize_optional_text(value)
    if text is None:
        return None
    path = Path(text)
    if base is not None and not path.is_absolute():
        path = base / path
    if path.is_absolute():
        path = path.resolve(strict=False)
    return path.as_posix()


def _freeze_sequence(values: Sequence[object]) -> tuple[object, ...]:
    return tuple(values)


def _canonical_sort_key(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _path_text(path: tuple[str, ...]) -> str:
    return ".".join(path)


def _path_matches(path: tuple[str, ...], patterns: tuple[str, ...]) -> bool:
    if not patterns:
        return False
    path_text = _path_text(path)
    return any(fnmatchcase(path_text, pattern) for pattern in patterns)


def _normalize_recursive(
    value: object,
    *,
    path: tuple[str, ...],
    text_paths: tuple[str, ...],
    identifier_paths: tuple[str, ...],
    phase_paths: tuple[str, ...],
    path_paths: tuple[str, ...],
    unordered_paths: tuple[str, ...],
    ignore_paths: tuple[str, ...],
) -> object:
    if _path_matches(path, ignore_paths):
        return _IGNORE

    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            normalized_value = _normalize_recursive(
                raw_value,
                path=path + (key,),
                text_paths=text_paths,
                identifier_paths=identifier_paths,
                phase_paths=phase_paths,
                path_paths=path_paths,
                unordered_paths=unordered_paths,
                ignore_paths=ignore_paths,
            )
            if normalized_value is not _IGNORE:
                normalized[key] = normalized_value
        return normalized

    if isinstance(value, (list, tuple, set, frozenset)):
        normalized_items = [
            item
            for item in (
                _normalize_recursive(
                    raw_item,
                    path=path + (str(index),),
                    text_paths=text_paths,
                    identifier_paths=identifier_paths,
                    phase_paths=phase_paths,
                    path_paths=path_paths,
                    unordered_paths=unordered_paths,
                    ignore_paths=ignore_paths,
                )
                for index, raw_item in enumerate(value)
            )
            if item is not _IGNORE
        ]
        if isinstance(value, (set, frozenset)) or _path_matches(path, unordered_paths):
            normalized_items = sorted(normalized_items, key=_canonical_sort_key)
            deduped: list[object] = []
            seen: set[str] = set()
            for item in normalized_items:
                key = _canonical_sort_key(item)
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(item)
            normalized_items = deduped
        return _freeze_sequence(normalized_items)

    if isinstance(value, Path):
        return normalize_path_value(value)

    if isinstance(value, str):
        if _path_matches(path, phase_paths):
            return normalize_phase_token(value)
        if _path_matches(path, identifier_paths):
            return normalize_identifier_token(value)
        if _path_matches(path, path_paths):
            return normalize_path_value(value)
        if _path_matches(path, text_paths):
            return normalize_optional_text(value)
        return normalize_optional_text(value)

    return value


def normalize_projection_payload(
    value: object,
    *,
    text_paths: tuple[str, ...] = (),
    identifier_paths: tuple[str, ...] = (),
    phase_paths: tuple[str, ...] = (),
    path_paths: tuple[str, ...] = (),
    unordered_paths: tuple[str, ...] = (),
    ignore_paths: tuple[str, ...] = (),
) -> object:
    """Recursively normalize a projection payload for comparison."""

    return _normalize_recursive(
        value,
        path=(),
        text_paths=text_paths,
        identifier_paths=identifier_paths,
        phase_paths=phase_paths,
        path_paths=path_paths,
        unordered_paths=unordered_paths,
        ignore_paths=ignore_paths,
    )


def _manifest_fixture_key(row: Mapping[str, object]) -> str:
    slug = str(row["fixture_slug"])
    variant = str(row["fixture_kind"])
    return f"{slug}/{variant}"


def _build_case(row: Mapping[str, object]) -> ProjectionOracleCase:
    fixture_slug = str(row["fixture_slug"])
    variant = str(row["fixture_kind"])
    family = PHASE16_SLUG_TO_FAMILY[fixture_slug]
    fixture_path = (REPO_ROOT / str(row["fixture_path"])).resolve(strict=False)
    workspace_path = (REPO_ROOT / str(row["workspace_path"])).resolve(strict=False)
    manifest = MappingProxyType(dict(row))
    return ProjectionOracleCase(
        case_key=_manifest_fixture_key(row),
        fixture_slug=fixture_slug,
        variant=variant,
        fixture_id=str(row["fixture_id"]),
        fixture_kind=variant,
        status=str(row["status"]),
        order=int(row["order"]),
        family=family,
        owner_module=PHASE16_FAMILY_TO_MODULE[family],
        fixture_path=fixture_path,
        workspace_path=workspace_path,
        mutation_axis=(str(row["mutation_axis"]) if row.get("mutation_axis") is not None else None),
        paired_fixture_id=(
            str(row["paired_fixture_id"]) if row.get("paired_fixture_id") is not None else None
        ),
        primary_interface_class=(
            str(row["primary_interface_class"]) if row.get("primary_interface_class") is not None else None
        ),
        fixture_manifest=manifest,
    )


@cache
def phase16_case_registry(path: Path | None = None) -> tuple[ProjectionOracleCase, ...]:
    """Return the canonical Phase 16 case registry in execution order."""

    manifest = load_handoff_bundle_manifest(path)
    if int(manifest.get("schema_version", 0)) != 1:
        raise ValueError("handoff-bundle manifest has unexpected schema version")
    if int(manifest.get("fixture_count", 0)) != 20:
        raise ValueError("handoff-bundle manifest must expose exactly 20 fixtures")
    fixtures = manifest.get("fixtures")
    if not isinstance(fixtures, list):
        raise TypeError("handoff-bundle manifest missing fixture list")

    row_by_key = {
        _manifest_fixture_key(row): row
        for row in fixtures
        if isinstance(row, Mapping)
    }
    expected_keys = set(PHASE16_EXPECTED_CASE_KEYS)
    actual_keys = set(row_by_key)
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        raise ValueError(f"handoff-bundle manifest mismatch: missing={missing}, extra={extra}")

    cases = tuple(_build_case(row_by_key[key]) for key in PHASE16_EXPECTED_CASE_KEYS)
    if len(cases) != 20:
        raise AssertionError(f"expected 20 Phase 16 cases, found {len(cases)}")

    for case in cases:
        if case.status != "live":
            raise AssertionError(f"unexpected non-live case in Phase 16 registry: {case.case_key}")
        if not case.fixture_path.exists():
            raise FileNotFoundError(case.fixture_path)
        if not case.workspace_path.exists():
            raise FileNotFoundError(case.workspace_path)
        if not case.fixture_json_path.exists():
            raise FileNotFoundError(case.fixture_json_path)

    return cases


PHASE16_CASE_REGISTRY: tuple[ProjectionOracleCase, ...] = phase16_case_registry()
PHASE16_CASE_BY_KEY: dict[str, ProjectionOracleCase] = {
    case.case_key: case for case in PHASE16_CASE_REGISTRY
}
PHASE16_CASES_BY_FAMILY: dict[str, tuple[ProjectionOracleCase, ...]] = {
    family: tuple(PHASE16_CASE_BY_KEY[key] for key in keys)
    for family, keys in PHASE16_FAMILY_TO_CASE_KEYS.items()
}


def phase16_case_keys(*, family: str | None = None) -> tuple[str, ...]:
    """Return case keys in registry order, optionally filtered by family."""

    if family is None:
        return PHASE16_EXPECTED_CASE_KEYS
    return PHASE16_FAMILY_TO_CASE_KEYS[family]


def phase16_cases(*, family: str | None = None) -> tuple[ProjectionOracleCase, ...]:
    """Return the canonical case objects, optionally filtered by family."""

    if family is None:
        return PHASE16_CASE_REGISTRY
    return PHASE16_CASES_BY_FAMILY[family]


def get_projection_oracle_case(
    fixture_slug: str,
    variant: str = "positive",
) -> ProjectionOracleCase:
    """Look up one canonical case by its fixture slug and variant."""

    case_key = f"{fixture_slug}/{variant}"
    try:
        return PHASE16_CASE_BY_KEY[case_key]
    except KeyError as exc:  # pragma: no cover - defensive helper path
        raise KeyError(f"unknown Phase 16 case: {case_key}") from exc


def load_fixture_metadata(case: ProjectionOracleCase | str, variant: str | None = None) -> dict[str, object]:
    """Load the raw ``fixture.json`` metadata for a case."""

    if isinstance(case, str):
        if variant is None:
            raise ValueError("variant is required when looking up a case by slug")
        case = get_projection_oracle_case(case, variant)
    return json.loads(case.fixture_json_path.read_text(encoding="utf-8"))


def copy_fixture_workspace(
    tmp_path: Path,
    fixture_slug: str,
    variant: str = "positive",
    *,
    suffix: str = "",
) -> Path:
    """Copy one fixture workspace into a temporary location."""

    case = get_projection_oracle_case(fixture_slug, variant)
    return copy_case_workspace(case, tmp_path, suffix=suffix)


def copy_case_workspace(
    case: ProjectionOracleCase,
    tmp_path: Path,
    *,
    suffix: str = "",
) -> Path:
    """Copy a case workspace into a temporary destination."""

    destination = tmp_path / f"{case.fixture_slug}-{case.variant}{suffix}"
    shutil.copytree(case.workspace_path, destination)
    return destination


def build_case_record(case: ProjectionOracleCase) -> dict[str, object]:
    """Build a normalized metadata record for a registry case."""

    return {
        "case_key": case.case_key,
        "family": case.family,
        "owner_module": case.owner_module,
        "fixture_id": case.fixture_id,
        "fixture_slug": case.fixture_slug,
        "variant": case.variant,
        "fixture_kind": case.fixture_kind,
        "status": case.status,
        "order": case.order,
        "fixture_path": case.fixture_path.as_posix(),
        "workspace_path": case.workspace_path.as_posix(),
        "mutation_axis": case.mutation_axis,
        "paired_fixture_id": case.paired_fixture_id,
        "primary_interface_class": case.primary_interface_class,
        "allowlist": [
            {
                "path_pattern": allowance.path_pattern,
                "reason": allowance.reason,
                "kind": allowance.kind,
            }
            for allowance in case.allowlist
        ],
    }


def build_projection_record(
    case: ProjectionOracleCase,
    surface: str,
    projection: object,
    *,
    metadata: object | None = None,
    text_paths: tuple[str, ...] = (),
    identifier_paths: tuple[str, ...] = (),
    phase_paths: tuple[str, ...] = (),
    path_paths: tuple[str, ...] = (),
    unordered_paths: tuple[str, ...] = (),
    ignore_paths: tuple[str, ...] = (),
) -> dict[str, object]:
    """Build a normalized projection record with case provenance attached."""

    record: dict[str, object] = {
        "case_key": case.case_key,
        "family": case.family,
        "surface": surface,
        "workspace_root": case.workspace_path.resolve(strict=False).as_posix(),
        "fixture_root": case.fixture_path.resolve(strict=False).as_posix(),
        "projection": normalize_projection_payload(
            projection,
            text_paths=text_paths,
            identifier_paths=identifier_paths,
            phase_paths=phase_paths,
            path_paths=path_paths,
            unordered_paths=unordered_paths,
            ignore_paths=ignore_paths,
        ),
    }
    if metadata is not None:
        record["metadata"] = normalize_projection_payload(
            metadata,
            text_paths=text_paths,
            identifier_paths=identifier_paths,
            phase_paths=phase_paths,
            path_paths=path_paths,
            unordered_paths=unordered_paths,
            ignore_paths=ignore_paths,
        )
    return record


def normalize_case_record(case: ProjectionOracleCase) -> dict[str, object]:
    """Normalize a case object to a JSON-friendly comparison record."""

    return cast(
        dict[str, object],
        normalize_projection_payload(
            build_case_record(case),
            path_paths=("fixture_path", "workspace_path"),
            unordered_paths=("allowlist",),
        ),
    )


def diff_projection_records(
    expected: object,
    actual: object,
    *,
    text_paths: tuple[str, ...] = (),
    identifier_paths: tuple[str, ...] = (),
    phase_paths: tuple[str, ...] = (),
    path_paths: tuple[str, ...] = (),
    unordered_paths: tuple[str, ...] = (),
    ignore_paths: tuple[str, ...] = (),
) -> tuple[ProjectionOracleDiff, ...]:
    """Compute a deterministic recursive diff between two normalized records."""

    expected_normalized = normalize_projection_payload(
        expected,
        text_paths=text_paths,
        identifier_paths=identifier_paths,
        phase_paths=phase_paths,
        path_paths=path_paths,
        unordered_paths=unordered_paths,
        ignore_paths=ignore_paths,
    )
    actual_normalized = normalize_projection_payload(
        actual,
        text_paths=text_paths,
        identifier_paths=identifier_paths,
        phase_paths=phase_paths,
        path_paths=path_paths,
        unordered_paths=unordered_paths,
        ignore_paths=ignore_paths,
    )
    diffs: list[ProjectionOracleDiff] = []

    def walk(left: object, right: object, path: tuple[str, ...]) -> None:
        if left is _IGNORE or right is _IGNORE:
            return
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            left_keys = set(left)
            right_keys = set(right)
            for key in sorted(left_keys - right_keys):
                diffs.append(
                    ProjectionOracleDiff(path + (key,), "missing", left[key], _IGNORE)
                )
            for key in sorted(right_keys - left_keys):
                diffs.append(ProjectionOracleDiff(path + (key,), "extra", _IGNORE, right[key]))
            for key in sorted(left_keys & right_keys):
                walk(left[key], right[key], path + (key,))
            return
        if isinstance(left, Sequence) and isinstance(right, Sequence) and not isinstance(
            left, (str, bytes)
        ) and not isinstance(right, (str, bytes)):
            max_len = max(len(left), len(right))
            for index in range(max_len):
                if index >= len(left):
                    diffs.append(
                        ProjectionOracleDiff(path + (str(index),), "extra", _IGNORE, right[index])
                    )
                elif index >= len(right):
                    diffs.append(
                        ProjectionOracleDiff(path + (str(index),), "missing", left[index], _IGNORE)
                    )
                else:
                    walk(left[index], right[index], path + (str(index),))
            return
        if left != right:
            diff_kind = "value"
            if type(left) is not type(right):
                diff_kind = "type"
            diffs.append(ProjectionOracleDiff(path, diff_kind, left, right))

    walk(expected_normalized, actual_normalized, ())
    return tuple(diffs)


def split_projection_diffs(
    diffs: Sequence[ProjectionOracleDiff],
    allowlist: Sequence[ProjectionOracleAllowance] = (),
) -> tuple[tuple[ProjectionOracleDiff, ...], tuple[ProjectionOracleDiff, ...]]:
    """Split diffs into explicit allowlisted and unexpected buckets."""

    allowed: list[ProjectionOracleDiff] = []
    unexpected: list[ProjectionOracleDiff] = []
    for diff in diffs:
        if any(allowance.matches(diff) for allowance in allowlist):
            allowed.append(diff)
        else:
            unexpected.append(diff)
    return tuple(allowed), tuple(unexpected)


def format_projection_diffs(
    diffs: Sequence[ProjectionOracleDiff],
    *,
    title: str = "Projection diffs",
) -> str:
    """Render a deterministic diff summary for assertion failures."""

    lines = [title]
    for diff in diffs:
        expected = "<missing>" if diff.expected is _IGNORE else repr(diff.expected)
        actual = "<missing>" if diff.actual is _IGNORE else repr(diff.actual)
        lines.append(
            f"- {diff.path_text}: {diff.kind} expected={expected} actual={actual}"
        )
    return "\n".join(lines)


def assert_projection_records_match(
    expected: object,
    actual: object,
    *,
    allowlist: Sequence[ProjectionOracleAllowance] = (),
    text_paths: tuple[str, ...] = (),
    identifier_paths: tuple[str, ...] = (),
    phase_paths: tuple[str, ...] = (),
    path_paths: tuple[str, ...] = (),
    unordered_paths: tuple[str, ...] = (),
    ignore_paths: tuple[str, ...] = (),
) -> None:
    """Assert that two projection records match after allowlist filtering."""

    diffs = diff_projection_records(
        expected,
        actual,
        text_paths=text_paths,
        identifier_paths=identifier_paths,
        phase_paths=phase_paths,
        path_paths=path_paths,
        unordered_paths=unordered_paths,
        ignore_paths=ignore_paths,
    )
    _, unexpected = split_projection_diffs(diffs, allowlist)
    if unexpected:
        raise AssertionError(format_projection_diffs(unexpected))


__all__ = [
    "HANDOFF_BUNDLE_MANIFEST_PATH",
    "HANDOFF_BUNDLE_ROOT",
    "PHASE16_CASE_BY_KEY",
    "PHASE16_CASE_REGISTRY",
    "PHASE16_CASES_BY_FAMILY",
    "PHASE16_EXPECTED_CASE_KEYS",
    "PHASE16_FAMILY_TO_CASE_KEYS",
    "PHASE16_FAMILY_TO_MODULE",
    "PHASE16_SLUG_TO_FAMILY",
    "ProjectionOracleAllowance",
    "ProjectionOracleCase",
    "ProjectionOracleDiff",
    "assert_projection_records_match",
    "build_case_record",
    "build_projection_record",
    "copy_case_workspace",
    "copy_fixture_workspace",
    "diff_projection_records",
    "format_projection_diffs",
    "get_projection_oracle_case",
    "load_fixture_metadata",
    "load_handoff_bundle_manifest",
    "normalize_case_record",
    "normalize_identifier_token",
    "normalize_optional_text",
    "normalize_path_value",
    "normalize_phase_token",
    "normalize_projection_payload",
    "phase16_case_keys",
    "phase16_case_registry",
    "phase16_cases",
    "split_projection_diffs",
]
