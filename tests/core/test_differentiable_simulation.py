"""Tests for the differentiable simulation protocol, competitive synthesis workflow, and related patterns.

Validates that the new specs are discoverable by the registry, that the
bootstrap patterns use valid domains/categories, and that the command
and workflow form a matched same-stem pair.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd.core.patterns import (
    _BOOTSTRAP_PATTERNS,
    VALID_CATEGORIES,
    VALID_DOMAINS,
    VALID_SEVERITIES,
    pattern_init,
    pattern_search,
    pattern_seed,
)
from gpd.registry import _parse_command_file

# ─── Registry discovery ───────────────────────────────────────────────────────

SPECS_DIR = Path(__file__).resolve().parents[2] / "src" / "gpd" / "specs"
COMMANDS_DIR = Path(__file__).resolve().parents[2] / "src" / "gpd" / "commands"


class TestSynthesizeImplementationsCommand:
    """The synthesize-implementations command is discovered and well-formed."""

    def test_command_parses_successfully(self) -> None:
        cmd_path = COMMANDS_DIR / "synthesize-implementations.md"
        cmd = _parse_command_file(cmd_path, "commands")
        assert cmd is not None
        assert cmd.name == "gpd:synthesize-implementations"

    def test_command_has_required_tools(self) -> None:
        cmd_path = COMMANDS_DIR / "synthesize-implementations.md"
        cmd = _parse_command_file(cmd_path, "commands")
        assert cmd is not None
        assert "file_read" in cmd.allowed_tools
        assert "shell" in cmd.allowed_tools

    def test_command_has_matching_workflow(self) -> None:
        cmd_path = SPECS_DIR.parent / "commands" / "synthesize-implementations.md"
        workflow_path = SPECS_DIR / "workflows" / "synthesize-implementations.md"
        assert cmd_path.is_file(), "command file must exist"
        assert workflow_path.is_file(), "matching workflow file must exist"


# ─── Reference protocol ──────────────────────────────────────────────────────


class TestDifferentiableSimulationReference:
    """The differentiable simulation reference loads with correct metadata."""

    def test_reference_file_exists(self) -> None:
        ref_path = SPECS_DIR / "references" / "methods" / "differentiable-simulation.md"
        assert ref_path.is_file()

    def test_reference_has_load_when_triggers(self) -> None:
        ref_path = SPECS_DIR / "references" / "methods" / "differentiable-simulation.md"
        content = ref_path.read_text(encoding="utf-8")
        assert "load_when:" in content
        assert "differentiable simulation" in content
        assert "autodiff through solver" in content

    def test_reference_covers_key_topics(self) -> None:
        ref_path = SPECS_DIR / "references" / "methods" / "differentiable-simulation.md"
        content = ref_path.read_text(encoding="utf-8")
        assert "<gradient_methods>" in content
        assert "<warp_kernel_rules>" in content
        assert "<verification_protocol>" in content
        assert "<tools_landscape>" in content


# ─── Container template ──────────────────────────────────────────────────────


class TestWarpContainerTemplate:
    """The Warp container template provides ready-to-copy artifacts."""

    def test_template_files_exist(self) -> None:
        template_dir = SPECS_DIR / "templates" / "compute" / "warp"
        assert (template_dir / "Dockerfile.cpu").is_file()
        assert (template_dir / "Dockerfile.gpu").is_file()
        assert (template_dir / "requirements.txt").is_file()
        assert (template_dir / "run.sh").is_file()

    def test_cpu_dockerfile_uses_slim_base(self) -> None:
        content = (SPECS_DIR / "templates" / "compute" / "warp" / "Dockerfile.cpu").read_text()
        assert "python:3.11-slim" in content

    def test_gpu_dockerfile_uses_nvidia_base(self) -> None:
        content = (SPECS_DIR / "templates" / "compute" / "warp" / "Dockerfile.gpu").read_text()
        assert "nvcr.io/nvidia" in content

    def test_requirements_includes_warp(self) -> None:
        content = (SPECS_DIR / "templates" / "compute" / "warp" / "requirements.txt").read_text()
        assert "warp-lang" in content

    def test_run_script_is_executable(self) -> None:
        import os
        run_sh = SPECS_DIR / "templates" / "compute" / "warp" / "run.sh"
        assert os.access(run_sh, os.X_OK)

    def test_run_script_detects_gpu(self) -> None:
        content = (SPECS_DIR / "templates" / "compute" / "warp" / "run.sh").read_text()
        assert "nvidia-smi" in content
        assert "Dockerfile.gpu" in content
        assert "Dockerfile.cpu" in content


# ─── Bootstrap patterns ──────────────────────────────────────────────────────


_DIFF_SIM_SLUGS = {
    "forward-gradient-iteration-mismatch",
    "uniform-properties-heterogeneous-domain",
    "fd-gradients-when-autodiff-available",
}


class TestDifferentiableSimulationPatterns:
    """The differentiable simulation bootstrap patterns are well-formed and searchable."""

    def test_patterns_exist_in_bootstrap_list(self) -> None:
        slugs = {str(bp["slug"]) for bp in _BOOTSTRAP_PATTERNS}
        for expected in _DIFF_SIM_SLUGS:
            assert expected in slugs, f"missing bootstrap pattern: {expected}"

    def test_patterns_use_valid_domains(self) -> None:
        for bp in _BOOTSTRAP_PATTERNS:
            if bp["slug"] in _DIFF_SIM_SLUGS:
                assert bp["domain"] in VALID_DOMAINS
                assert bp["category"] in VALID_CATEGORIES
                assert bp["severity"] in VALID_SEVERITIES

    def test_patterns_have_required_fields(self) -> None:
        for bp in _BOOTSTRAP_PATTERNS:
            if bp["slug"] in _DIFF_SIM_SLUGS:
                assert "description" in bp and len(str(bp["description"])) > 10
                assert "detection" in bp and len(str(bp["detection"])) > 10
                assert "prevention" in bp and len(str(bp["prevention"])) > 10
                assert "tags" in bp and len(bp["tags"]) >= 3

    def test_patterns_are_searchable_by_autodiff(self, tmp_path: Path) -> None:
        lib_root = tmp_path / "patterns"
        pattern_init(root=lib_root)
        pattern_seed(root=lib_root)
        result = pattern_search("autodiff", root=lib_root)
        assert result.count >= 2, "at least 2 differentiable-sim patterns should match 'autodiff'"

    def test_patterns_are_searchable_by_gradient(self, tmp_path: Path) -> None:
        lib_root = tmp_path / "patterns"
        pattern_init(root=lib_root)
        pattern_seed(root=lib_root)
        result = pattern_search("gradient iteration", root=lib_root)
        assert result.count >= 1
