#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"

uv run pytest -q -n 0 tests/test_bug_placeholder_sentinel_normalization.py tests/core/test_projection_config_contract.py::test_placeholder_conventions_projection_oracle_treats_literal_not_set_as_unset
