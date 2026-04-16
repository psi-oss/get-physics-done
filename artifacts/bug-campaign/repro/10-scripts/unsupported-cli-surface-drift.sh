#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"

uv run pytest -q -n 0 tests/core/test_projection_query_result.py::test_projection_query_result_bridge_mutation_matches_positive_snapshot tests/test_bug_runtime_recovery_contract.py
