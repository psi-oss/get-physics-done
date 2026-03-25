---
template_version: 1
type: reproducibility-manifest
---

# Reproducibility Manifest Template

Template for `paper/reproducibility-manifest.json` — the machine-readable manifest consumed by `gpd validate reproducibility-manifest` and strict review preflight checks.

---

## File Template

```json
{
  "paper_title": "[Title]",
  "date": "[YYYY-MM-DD]",
  "contact": "[corresponding author email]",
  "environment": {
    "python_version": "3.12.1",
    "package_manager": "uv",
    "virtual_environment": ".venv",
    "required_packages": [
      {
        "package": "numpy",
        "version": "1.26.4",
        "purpose": "Array operations and linear algebra"
      },
      {
        "package": "scipy",
        "version": "1.12.0",
        "purpose": "Optimization, integration, special functions"
      }
    ],
    "lock_file": "uv.lock",
    "system_requirements": {
      "operating_systems": ["Ubuntu 22.04", "macOS 15"],
      "architectures": ["x86_64", "arm64"],
      "compiler": "gcc 13",
      "gpu": "CUDA 12.x (optional)"
    }
  },
  "input_data": [
    {
      "name": "benchmark-dataset",
      "source": "NIST",
      "version_or_date": "2026-03-15",
      "download_url": "https://example.org/data",
      "checksum_sha256": "[64-char sha256]",
      "license": "CC-BY-4.0",
      "transformations": "None"
    }
  ],
  "generated_data": [
    {
      "name": "spectrum",
      "script": "scripts/run.py",
      "parameters": {
        "grid_size": "256",
        "temperature": "0.85"
      },
      "size": "24 MB",
      "checksum_sha256": "[64-char sha256]"
    }
  ],
  "external_dependencies": [
    {
      "resource": "LHAPDF grid files",
      "access_method": "https://lhapdfsets.web.cern.ch/",
      "restrictions": "open"
    }
  ],
  "execution_steps": [
    {
      "name": "prepare-data",
      "command": "python scripts/01_prepare_data.py --config config/main.yaml",
      "outputs": ["data/prepared/inputs.json"],
      "stochastic": false,
      "expected_wall_time": "5 min",
      "parallel_group": ""
    },
    {
      "name": "run-main",
      "command": "python scripts/02_compute.py --input data/prepared/ --output results/",
      "outputs": ["results/spectrum.json"],
      "stochastic": true,
      "expected_wall_time": "90 min",
      "parallel_group": "compute"
    }
  ],
  "expected_results": [
    {
      "quantity": "T_c",
      "expected_value": "0.893",
      "tolerance": "+/- 0.005",
      "script": "scripts/02_compute.py",
      "figure_or_table": "Table I"
    }
  ],
  "output_files": [
    {
      "path": "results/spectrum.json",
      "description": "Energy eigenvalues",
      "approximate_size": "420 KB",
      "checksum_sha256": "[64-char sha256]",
      "approximate_checksum": false
    },
    {
      "path": "figures/fig1.pdf",
      "description": "Main result figure",
      "approximate_size": "180 KB",
      "checksum_sha256": "approx:[64-char sha256]",
      "approximate_checksum": true
    }
  ],
  "resource_requirements": [
    {
      "step": "prepare-data",
      "cpu_cores": 2,
      "memory_gb": 4.0,
      "gpu": "",
      "wall_time": "5 min",
      "notes": "Light preprocessing"
    },
    {
      "step": "run-main",
      "cpu_cores": 8,
      "memory_gb": 16.0,
      "gpu": "",
      "wall_time": "90 min",
      "notes": "Scales linearly with cores"
    }
  ],
  "minimum_viable": "4 cores, 8 GB RAM, ~3 hours",
  "recommended": "8+ cores, 16 GB RAM, ~90 minutes",
  "random_seeds": [
    {
      "computation": "run-main",
      "seed": "42",
      "purpose": "Reproducible disorder realizations"
    }
  ],
  "seeding_strategy": "Base seed in config; per-sample seeds derived deterministically.",
  "known_platform_differences": [
    {
      "platform": "macOS arm64",
      "issue": "LAPACK may order degenerate eigenvalues differently.",
      "workaround": "Sort eigenvalues before comparison."
    }
  ],
  "verification_steps": [
    "Rerun the full pipeline.",
    "Compare key numerical results against expected tolerances.",
    "Inspect emitted artifacts against the paper."
  ],
  "manifest_created": "[YYYY-MM-DDTHH:MM:SSZ]",
  "last_verified": "[YYYY-MM-DDTHH:MM:SSZ]",
  "last_verified_platform": "[platform string]"
}
```

---

## Guidelines

**Strict review-ready requirements (`gpd validate reproducibility-manifest ... --strict` and strict review preflight):**
- The manifest must be schema-valid and warning-free. Strict validation fails on warnings, not only on hard errors.
- `environment.required_packages` must be non-empty, and every package `version` must be pinned to an exact version string.
- `environment.lock_file` must name the real lock file used to pin the environment.
- Every `input_data`, `generated_data`, and `output_files` entry must carry a valid SHA-256 checksum. Draft-only approximate output checksums still emit warnings and therefore block strict review.
- `execution_steps` are required, and the manifest must declare `expected_results` or `output_files` so a reviewer knows what success looks like.
- Every `execution_steps[].name` should appear in `resource_requirements[].step`; missing per-step coverage emits warnings that block strict review.
- Every stochastic `execution_steps[].name` must have a matching `random_seeds[].computation`, and `seeding_strategy` must be non-empty.
- `verification_steps` should include at least three concrete steps: rerun the pipeline, compare key numbers, and inspect emitted artifacts.
- `minimum_viable`, `recommended`, `last_verified`, and `last_verified_platform` must all be populated before strict review. If `last_verified` is set, `last_verified_platform` must also be set.

**What must be pinned:**
- All Python packages with exact versions (not ranges)
- System libraries if compilation is involved
- Data file versions and checksums
- Random seeds for stochastic computations

**Current artifact path and validator:**
- Store this file as `paper/reproducibility-manifest.json`
- Validate with `gpd validate reproducibility-manifest paper/reproducibility-manifest.json --strict`
- Use this template as the schema source of truth for manual manifests

**Field linkage rules:**
- `random_seeds[].computation` must exactly match the `execution_steps[].name` of each stochastic step
- `resource_requirements[].step` should cover every execution step, not only the expensive ones
- `environment.lock_file` may be `uv.lock`, `poetry.lock`, or another real lock file path, but it must name the file actually used to pin the environment

**What can be approximate:**
- Figure checksums may be recorded temporarily as `approx:[64-char sha256]` or with `approximate_checksum: true` while drafting, but those warnings still fail `--strict`; replace them with exact SHA-256 values before strict review
- Wall time estimates (hardware-dependent)
- Memory requirements (OS overhead varies)

**Checksum computation:**
```bash
sha256sum path/to/file
# or
python -c "import hashlib; print(hashlib.sha256(open('file','rb').read()).hexdigest())"
```

**When to update:**
- After any change to computation scripts
- When package versions are updated
- When new data sources are added
- Before final paper submission
