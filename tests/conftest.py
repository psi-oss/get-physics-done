from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from tests.ci_sharding import CI_CATEGORY_SHARD_COUNTS


def _is_default_full_suite_invocation(args: list[str]) -> bool:
    normalized = tuple(arg.rstrip("/") for arg in args)
    return normalized in {(), ("tests",)}


def _has_pytest_selection_filter(config: pytest.Config) -> bool:
    option = getattr(config, "option", None)
    if option is None:
        return False
    if getattr(option, "keyword", None):
        return True
    if getattr(option, "markexpr", None):
        return True
    return any(bool(getattr(option, name, False)) for name in ("lastfailed", "failedfirst", "collectonly"))


def _is_default_full_suite_config(config: pytest.Config) -> bool:
    return _is_default_full_suite_invocation([str(arg) for arg in config.args]) and not _has_pytest_selection_filter(
        config
    )


def _full_suite_auto_worker_count(*, cpu_count: int, ci_shard_total: int) -> int:
    cpu_count = max(cpu_count, 1)
    return min(max(cpu_count, ci_shard_total), cpu_count * 2)


def pytest_xdist_auto_num_workers(config: pytest.Config) -> int | None:
    """Keep local full-suite auto parallelism in the same range as CI fanout."""

    if os.environ.get("PYTEST_XDIST_AUTO_NUM_WORKERS"):
        return None

    numprocesses = getattr(config.option, "numprocesses", None)
    if numprocesses not in {"auto", "logical"}:
        return None
    if not _is_default_full_suite_config(config):
        return None

    worker_count = _full_suite_auto_worker_count(
        cpu_count=os.cpu_count() or 1,
        ci_shard_total=sum(CI_CATEGORY_SHARD_COUNTS.values()),
    )
    maxprocesses = getattr(config.option, "maxprocesses", None)
    if maxprocesses is not None:
        worker_count = min(worker_count, maxprocesses)
    return worker_count


@pytest.fixture(scope="session", autouse=True)
def _isolate_machine_local_gpd_data(tmp_path_factory) -> Iterator[None]:
    """Give each pytest worker its own machine-local data root.

    Many state and CLI paths project advisory data into the machine-local
    recent-project cache. Under xdist, sharing one cache root across workers
    creates avoidable lock contention that dominates suite wall time without
    adding coverage value.
    """

    previous = os.environ.get("GPD_DATA_DIR")
    data_root = tmp_path_factory.getbasetemp() / "gpd-data"
    data_root.mkdir(parents=True, exist_ok=True)
    os.environ["GPD_DATA_DIR"] = str(data_root)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("GPD_DATA_DIR", None)
        else:
            os.environ["GPD_DATA_DIR"] = previous


def pytest_report_header(config) -> str:
    if _is_default_full_suite_config(config):
        return "test suite mode: full default suite"
    return "test suite mode: targeted/sharded args"
