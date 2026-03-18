"""Research verification kernel for GPD.

A domain-independent verification core that evaluates executable predicates
over structured evidence registries and produces content-addressed verdicts.

The kernel provides:
- Result type: the universal output of every predicate
- RegistryBase: generic JSON loader with content hashing
- run(): load registry, run predicates, produce verdict
- Verdict format: content-addressed with SHA-256

Domain-specific code (provided per-project) supplies:
- Record types (dataclasses or Pydantic models loaded from registry JSON)
- Predicates (pure functions: registry -> Result)
- Registry subclass (typed query methods for domain records)

Usage from a GPD project::

    from gpd.core.kernel import run, RegistryBase, Result, Pass, Fail

    class MyRegistry(RegistryBase):
        ...

    def my_predicate(registry: MyRegistry) -> Result:
        ...

    verdict = run(registry, {"my_check": my_predicate})
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "KERNEL_VERSION",
    "Result",
    "Pass",
    "Fail",
    "RegistryBase",
    "run",
    "print_verdict",
]

KERNEL_VERSION = "0.1.0"


def _content_address(payload: object) -> str:
    """Return a stable SHA-256 address for a JSON-serializable payload."""
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


# -----------------------------------------------------------------------
# Result type — the universal output of every predicate
# -----------------------------------------------------------------------

@dataclass
class Result:
    """The output of a predicate check."""
    passed: bool
    reason: str

    def __bool__(self) -> bool:
        return self.passed


def Pass(reason: str = "") -> Result:
    """Create a passing result."""
    return Result(passed=True, reason=reason)


def Fail(reason: str) -> Result:
    """Create a failing result."""
    return Result(passed=False, reason=reason)


# -----------------------------------------------------------------------
# Registry base — generic JSON loader with content hashing
# -----------------------------------------------------------------------

class RegistryBase:
    """Base class for domain-specific registries.

    Handles:
    - Loading JSON files from subdirectories
    - Content hashing for verdict integrity
    - Stats reporting

    Subclasses add typed record lists and domain-specific query methods.
    """

    def __init__(self, raw_bytes: bytes = b"") -> None:
        self._raw_bytes = raw_bytes

    @staticmethod
    def load_records(
        directory: Path,
        factory: Callable[[dict[str, object]], object],
    ) -> list[object]:
        """Load JSON records from a directory using a factory function."""
        records: list[object] = []
        if not directory.exists():
            return records
        for f in sorted(directory.glob("*.json")):
            if f.name.startswith("."):
                continue
            data = json.loads(f.read_text())
            if isinstance(data, list):
                records.extend(factory(d) for d in data)
            else:
                records.append(factory(data))
        return records

    @staticmethod
    def collect_raw_bytes(registry_dir: Path, subdirs: list[str]) -> bytes:
        """Collect raw bytes from all JSON files for content hashing."""
        parts: list[bytes] = []
        for subdir in subdirs:
            d = registry_dir / subdir
            if d.exists():
                for f in sorted(d.glob("*.json")):
                    if not f.name.startswith("."):
                        parts.append(f.read_bytes())
        return b"".join(parts)

    def content_hash(self) -> str:
        """SHA-256 hash of the raw registry bytes."""
        return "sha256:" + hashlib.sha256(self._raw_bytes).hexdigest()

    def stats(self) -> dict[str, int]:
        """Override in subclass to report record counts."""
        return {}


# -----------------------------------------------------------------------
# Kernel runner
# -----------------------------------------------------------------------

#: Type alias for a predicate catalog.
PredicateMap = Mapping[str, Callable[[RegistryBase], Result]]


def run(
    registry: RegistryBase,
    predicates: PredicateMap,
    *,
    predicates_source: Path | None = None,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Run all predicates against the registry and return a verdict dict.

    Parameters
    ----------
    registry : RegistryBase
        A domain-specific registry instance.
    predicates : PredicateMap
        Mapping of predicate names to pure functions.
    predicates_source : Path, optional
        Path to the predicates source file for content addressing.

    Returns
    -------
    dict
        A content-addressed verdict with pass/fail per predicate.
    """
    results: dict[str, dict[str, object]] = {}
    for name, pred in predicates.items():
        try:
            result = pred(registry)
            results[name] = {
                "passed": result.passed,
                "reason": result.reason,
            }
        except Exception as exc:
            results[name] = {
                "passed": False,
                "reason": f"predicate raised {type(exc).__name__}: {exc}",
            }

    overall = "PASS" if all(r["passed"] for r in results.values()) else "FAIL"

    pred_hash = ""
    if predicates_source and predicates_source.exists():
        pred_hash = _content_address(predicates_source.read_text(encoding="utf-8"))

    timestamp = (generated_at or datetime.now(UTC)).isoformat()

    verdict: dict[str, object] = {
        "kernel_version": KERNEL_VERSION,
        "timestamp": timestamp,
        "registry_hash": registry.content_hash(),
        "predicates_hash": pred_hash,
        "registry_stats": registry.stats(),
        "results": results,
        "passed": sum(1 for r in results.values() if r["passed"]),
        "failed": sum(1 for r in results.values() if not r["passed"]),
        "total": len(results),
        "overall": overall,
    }

    # Keep the generation timestamp visible while hashing only the stable content.
    verdict["verdict_hash"] = _content_address(
        {key: value for key, value in verdict.items() if key != "timestamp"}
    )

    return verdict


def print_verdict(
    verdict: dict,
    *,
    domain: str = "Research",
    as_json: bool = False,
) -> None:
    """Print a verdict in human-readable or JSON format."""
    if as_json:
        print(json.dumps(verdict, indent=2))
        return

    overall = verdict["overall"]
    stats = verdict["registry_stats"]
    stats_str = ", ".join(f"{v} {k}" for k, v in stats.items())
    print(f"{domain} Kernel v{verdict['kernel_version']}")
    print(f"Registry: {stats_str}")
    print(f"Registry hash: {verdict['registry_hash'][:20]}...")
    print()

    for name, result in verdict["results"].items():
        status = "PASS" if result["passed"] else "FAIL"
        print(f"  {status:4s}  {name}: {result['reason']}")

    print()
    print(f"Result: {verdict['passed']}/{verdict['total']} passed — {overall}")

    if overall == "FAIL":
        failed = [n for n, r in verdict["results"].items() if not r["passed"]]
        print(f"Failed: {', '.join(failed)}")
