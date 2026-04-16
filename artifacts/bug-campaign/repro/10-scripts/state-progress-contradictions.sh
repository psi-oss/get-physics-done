#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"

uv run pytest -q -n 0 tests/test_bug_phase_read_model_alignment.py tests/core/test_projection_state.py
