"""Integration tests for Warp container examples.

Builds and runs each example in Docker, verifies metrics.json structure,
gradient checks, and optimization direction. Requires Docker.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "src" / "gpd" / "specs" / "templates" / "compute" / "warp"


def _docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False


requires_docker = pytest.mark.skipif(not _docker_available(), reason="Docker not available")


_WORKDIR = Path.home() / ".gpd-test-workdir"


def _run_example(example_name: str) -> tuple[dict, Path]:
    """Build and run one example, return (metrics, output_dir)."""
    _WORKDIR.mkdir(exist_ok=True)
    project = _WORKDIR / example_name
    if project.exists():
        shutil.rmtree(project)
    project.mkdir(parents=True)
    (project / "output").mkdir()
    (project / "src").mkdir()

    for f in ["Dockerfile.cpu", "requirements.txt"]:
        shutil.copy2(TEMPLATE_DIR / f, project / f)
    shutil.copy2(TEMPLATE_DIR / example_name / "main.py", project / "src" / "main.py")

    image = f"gpd-integ-{example_name}"
    build = subprocess.run(
        ["docker", "build", "-t", image, "-f", str(project / "Dockerfile.cpu"), str(project)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert build.returncode == 0, f"Build failed: {build.stderr[-300:]}"

    run = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{project / 'output'}:/app/output", image],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert run.returncode == 0, f"Run failed: {run.stderr[-300:]}\nstdout: {run.stdout[-300:]}"

    metrics = json.loads((project / "output" / "metrics.json").read_text())
    return metrics, project / "output"


def _cleanup(example_name: str) -> None:
    p = Path.home() / ".gpd-test-workdir" / example_name
    shutil.rmtree(p, ignore_errors=True)


@requires_docker
class TestHeatSourceExample:
    @pytest.fixture(autouse=True, scope="class")
    def run_example(self):
        self.__class__._metrics, self.__class__._outdir = _run_example("example")
        yield
        _cleanup("example")

    def test_has_answer(self) -> None:
        assert "answer" in self._metrics

    def test_gradient_check_passes(self) -> None:
        assert self._metrics["gradient_check_pass"] is True

    def test_optimizes_toward_center(self) -> None:
        assert self._metrics["answer"] > 0.3, f"Expected >0.3, got {self._metrics['answer']}"


@requires_docker
class TestOscillatorExample:
    @pytest.fixture(autouse=True, scope="class")
    def run_example(self):
        self.__class__._metrics, self.__class__._outdir = _run_example("example-oscillator")
        yield
        _cleanup("example-oscillator")

    def test_has_recovered_params(self) -> None:
        assert "recovered" in self._metrics
        assert "k" in self._metrics["recovered"]
        assert "c" in self._metrics["recovered"]

    def test_gradient_check_passes(self) -> None:
        assert self._metrics["gradient_check_pass"] is True

    def test_recovers_toward_true_k(self) -> None:
        assert self._metrics["recovered"]["k"] > 30, f"k={self._metrics['recovered']['k']}"


@requires_docker
class TestBarrierExample:
    @pytest.fixture(autouse=True, scope="class")
    def run_example(self):
        self.__class__._metrics, self.__class__._outdir = _run_example("example-barrier")
        yield
        _cleanup("example-barrier")

    def test_has_barrier_position(self) -> None:
        assert "barrier_y" in self._metrics

    def test_gradient_check_passes(self) -> None:
        assert self._metrics["gradient_check_pass"] is True

    def test_produces_figure_pdf(self) -> None:
        pdf = self._outdir / "barrier-optimization.pdf"
        assert pdf.exists(), "PDF figure not produced"
        assert pdf.stat().st_size > 1000

    def test_probe_temperature_decreases(self) -> None:
        assert self._metrics["T_probe_final"] < self._metrics["T_probe_initial"]
