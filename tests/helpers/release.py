from __future__ import annotations

EXPECTED_SETUP_UV_VERSION = "0.9.12"

ISOLATED_UV_BUILD_ENV_LINES = (
    'UV_CACHE_DIR="$(mktemp -d)"',
    "export UV_CACHE_DIR",
    "export UV_NO_CONFIG=1",
    "export UV_PYTHON_DOWNLOADS=never",
)


def assert_setup_uv_step_pins_expected_version(step: dict[str, object], *, context: str) -> None:
    assert step.get("uses") == "astral-sh/setup-uv@v7", context
    step_with = step.get("with")
    assert isinstance(step_with, dict), context
    assert step_with.get("version") == EXPECTED_SETUP_UV_VERSION, context


def assert_run_step_uses_isolated_uv_build_env(step: dict[str, object], *, context: str) -> None:
    run = step.get("run")
    assert isinstance(run, str), context

    lines = [line.strip() for line in run.splitlines() if line.strip() and not line.strip().startswith("#")]
    build_line_index = next((index for index, line in enumerate(lines) if line.startswith("uv build")), None)
    assert build_line_index is not None, context
    setup_lines = lines[:build_line_index]
    for line in ISOLATED_UV_BUILD_ENV_LINES:
        assert line in setup_lines, f"{context} must set `{line}` before `uv build`"
