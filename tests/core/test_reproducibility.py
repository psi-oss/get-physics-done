from __future__ import annotations

from pathlib import Path

from gpd.core.reproducibility import (
    EnvironmentSpecification,
    ExecutionStep,
    ExpectedNumericalResult,
    GeneratedDataset,
    InputDataset,
    OutputFileExpectation,
    RandomSeedRecord,
    ReproducibilityManifest,
    RequiredPackage,
    ResourceRequirement,
    SystemRequirements,
    compute_sha256,
    validate_reproducibility_manifest,
    verify_output_checksum,
)


def _manifest() -> ReproducibilityManifest:
    return ReproducibilityManifest(
        paper_title="Reproducible Paper",
        date="2026-03-10",
        contact="author@example.com",
        environment=EnvironmentSpecification(
            python_version="3.12.1",
            package_manager="uv",
            virtual_environment=".venv",
            required_packages=[
                RequiredPackage(package="numpy", version="1.26.4", purpose="linear algebra"),
                RequiredPackage(package="scipy", version="1.12.0", purpose="special functions"),
            ],
            lock_file="pyproject.toml",
            system_requirements=SystemRequirements(
                operating_systems=["macOS 14", "Ubuntu 22.04"],
                architectures=["arm64", "x86_64"],
                compiler="clang 15",
            ),
        ),
        input_data=[
            InputDataset(
                name="benchmark",
                source="NIST",
                version_or_date="2026-03-01",
                download_url="https://example.com/data.csv",
                checksum_sha256="a" * 64,
            )
        ],
        generated_data=[
            GeneratedDataset(
                name="spectrum",
                script="scripts/02_compute.py",
                parameters={"grid": "256"},
                checksum_sha256="b" * 64,
            )
        ],
        execution_steps=[
            ExecutionStep(name="prepare", command="python scripts/01_prepare.py"),
            ExecutionStep(name="sample", command="python scripts/02_compute.py", stochastic=True),
            ExecutionStep(name="plot", command="python scripts/03_plot.py"),
        ],
        expected_results=[
            ExpectedNumericalResult(
                quantity="T_c",
                expected_value="4.5115",
                tolerance="+/- 0.01",
                script="scripts/02_compute.py",
                figure_or_table="Table I",
            )
        ],
        output_files=[
            OutputFileExpectation(
                path="results/spectrum.json",
                description="computed spectrum",
                checksum_sha256="c" * 64,
            )
        ],
        resource_requirements=[
            ResourceRequirement(step="prepare", cpu_cores=1, memory_gb=2.0),
            ResourceRequirement(step="sample", cpu_cores=4, memory_gb=8.0),
            ResourceRequirement(step="plot", cpu_cores=1, memory_gb=2.0),
        ],
        minimum_viable="4 cores, 8 GB RAM",
        recommended="8 cores, 16 GB RAM",
        random_seeds=[RandomSeedRecord(computation="sample", seed="42", purpose="reproducible sampling")],
        seeding_strategy="Fixed master seed with derived worker seeds",
        verification_steps=[
            "Run the pipeline",
            "Compare numerical outputs",
            "Inspect generated figures",
        ],
        manifest_created="2026-03-10",
        last_verified="2026-03-10",
        last_verified_platform="macOS 14 arm64",
    )


def test_validate_reproducibility_manifest_valid():
    result = validate_reproducibility_manifest(_manifest())

    assert result.valid is True
    assert result.ready_for_review is True
    assert result.checksum_coverage_percent == 100.0
    assert result.stochastic_seed_coverage_percent == 100.0
    assert result.issues == []


def test_validate_reproducibility_manifest_reports_schema_errors_without_raising():
    result = validate_reproducibility_manifest({"paper_title": "Demo", "environment": []})

    assert result.valid is False
    assert any(issue.field == "date" and "required" in issue.message.lower() for issue in result.issues)
    assert any(issue.field == "environment" and "object" in issue.message.lower() for issue in result.issues)


def test_validate_reproducibility_manifest_flags_missing_requirements():
    manifest = _manifest().model_copy(
        update={
            "environment": _manifest().environment.model_copy(
                update={
                    "required_packages": [RequiredPackage(package="numpy", version=">=1.26", purpose="bad pin")],
                    "lock_file": "",
                }
            ),
            "random_seeds": [],
            "seeding_strategy": "",
            "output_files": [
                OutputFileExpectation(
                    path="results/spectrum.json",
                    description="computed spectrum",
                    checksum_sha256="not-a-checksum",
                )
            ],
        }
    )

    result = validate_reproducibility_manifest(manifest)

    assert result.valid is False
    fields = {issue.field for issue in result.issues}
    assert "environment.lock_file" in fields
    assert "random_seeds" in fields
    assert "seeding_strategy" in fields
    assert "output_files[0].checksum_sha256" in fields


def test_validate_reproducibility_manifest_warns_on_incomplete_review_metadata():
    manifest = _manifest().model_copy(
        update={
            "resource_requirements": [],
            "minimum_viable": "",
            "recommended": "",
            "verification_steps": ["Run pipeline"],
            "last_verified": "",
            "last_verified_platform": "",
        }
    )

    result = validate_reproducibility_manifest(manifest)

    assert result.valid is True
    assert result.ready_for_review is False
    warning_fields = {warning.field for warning in result.warnings}
    assert "resource_requirements" in warning_fields
    assert "minimum_viable" in warning_fields
    assert "recommended" in warning_fields
    assert "verification_steps" in warning_fields
    assert "last_verified" in warning_fields


def test_compute_and_verify_output_checksum(tmp_path: Path):
    target = tmp_path / "artifact.txt"
    target.write_text("physics", encoding="utf-8")

    checksum = compute_sha256(target)

    assert len(checksum) == 64
    assert verify_output_checksum(target, checksum) is True


# ─── Issue 1: whitespace-only last_verified should not trigger platform warning ──


def test_whitespace_last_verified_no_contradictory_platform_warning():
    """Whitespace-only last_verified must NOT trigger last_verified_platform warning.

    Before the fix, line 403 used raw truthiness (``if manifest_obj.last_verified``)
    which is True for ``"  "``, while line 395 used ``.strip()`` which treats it as
    empty.  This produced two contradictory warnings: "no last verified timestamp"
    AND "platform should be recorded when last_verified is set".
    """
    manifest = _manifest().model_copy(
        update={
            "last_verified": "   ",  # whitespace-only
            "last_verified_platform": "",
        }
    )

    result = validate_reproducibility_manifest(manifest)

    warning_fields = [w.field for w in result.warnings]
    # Should warn about missing last_verified
    assert "last_verified" in warning_fields
    # Should NOT warn about missing platform — there is nothing to pair it with
    assert "last_verified_platform" not in warning_fields


def test_nonempty_last_verified_without_platform_warns():
    """Non-whitespace last_verified without platform should trigger platform warning."""
    manifest = _manifest().model_copy(
        update={
            "last_verified": "2026-03-10",
            "last_verified_platform": "  ",  # whitespace-only
        }
    )

    result = validate_reproducibility_manifest(manifest)

    warning_fields = [w.field for w in result.warnings]
    assert "last_verified" not in warning_fields
    assert "last_verified_platform" in warning_fields


# ─── Issue 2: approximate checksum should count toward coverage ──


def test_approximate_checksum_counts_toward_coverage():
    """An output file with approximate_checksum=True and a non-empty checksum
    should count as covered, yielding 100% checksum_coverage_percent.

    Before the fix, the elif branch for approximate checksums appended a
    warning but did not increment checksum_ok, dragging down coverage and
    potentially blocking ready_for_review.
    """
    manifest = _manifest().model_copy(
        update={
            "output_files": [
                OutputFileExpectation(
                    path="results/spectrum.json",
                    description="stochastic output",
                    checksum_sha256="approx:" + "d" * 58,
                    approximate_checksum=True,
                )
            ],
        }
    )

    result = validate_reproducibility_manifest(manifest)

    assert result.checksum_coverage_percent == 100.0
    # The informational warning should still be emitted
    approx_warnings = [
        w for w in result.warnings if "approximate checksum" in w.message
    ]
    assert len(approx_warnings) == 1
