---
template_version: 1
type: reproducibility-manifest
---
# Reproducibility Manifest Template

Template for documenting everything needed to reproduce computational results in a physics paper.

---

## File Template

```markdown
# Reproducibility Manifest

**Paper:** [Title]
**Date:** [YYYY-MM-DD]
**Contact:** [corresponding author email]

## Environment Specifications

### Python Environment

- **Python version:** [e.g., 3.11.7]
- **Package manager:** [pip / conda / uv]
- **Virtual environment:** [venv / conda env name]

### Required Packages

| Package | Version | Purpose |
|---------|---------|---------|
| numpy | [e.g., 1.26.4] | Array operations, linear algebra |
| scipy | [e.g., 1.12.0] | Optimization, integration, special functions |
| matplotlib | [e.g., 3.8.3] | Plotting |
| [domain-specific] | [version] | [purpose] |

**Lock file:** [requirements.txt / pyproject.toml / conda environment.yml] included in repository

### System Requirements

- **OS:** [e.g., Linux (tested on Ubuntu 22.04), macOS 14+]
- **Architecture:** [x86_64 / ARM64]
- **Compiler:** [if applicable, e.g., GCC 12+ for Fortran extensions]
- **GPU:** [if applicable, e.g., CUDA 12.x with NVIDIA A100]

## Data Provenance

### Input Data

| Dataset | Source | Version/Date | Download URL | Checksum (SHA-256) |
|---------|--------|-------------|-------------|-------------------|
| [name] | [origin] | [version] | [URL] | [hash] |

### Generated Data

| Dataset | Script | Parameters | Size | Checksum (SHA-256) |
|---------|--------|-----------|------|-------------------|
| [name] | [script.py] | [key params] | [MB/GB] | [hash] |

### External Dependencies

| Resource | Access Method | Restrictions |
|----------|-------------|-------------|
| [e.g., LHAPDF grid files] | [download URL] | [open / institutional / request] |
| [e.g., experimental data tables] | [journal supplemental] | [open access] |

## Script Execution Order

Run scripts in this order to reproduce all results:

```bash
# Step 1: Setup and data preparation
python scripts/01_prepare_data.py --config config/main.yaml

# Step 2: Core computation
python scripts/02_compute.py --input data/prepared/ --output results/

# Step 3: Analysis and post-processing
python scripts/03_analyze.py --results results/ --output analysis/

# Step 4: Generate figures
python scripts/04_plot.py --analysis analysis/ --output figures/

# Step 5: Generate tables for paper
python scripts/05_tables.py --analysis analysis/ --output tables/
```

**Total runtime:** [estimate, e.g., "~2 hours on 8-core workstation"]

**Parallelization:** [which steps can run in parallel, e.g., "Steps 2a and 2b are independent"]

## Expected Outputs

### Key Numerical Results

| Quantity | Expected Value | Tolerance | Script | Figure/Table |
|----------|---------------|-----------|--------|-------------|
| [e.g., T_c] | [0.893] | [+/- 0.005] | [02_compute.py] | [Table I] |
| [e.g., E_0] | [-0.4327] | [+/- 0.0003] | [02_compute.py] | [Table I] |

### Output Files

| File | Description | Approximate Size | Checksum (SHA-256) |
|------|-------------|-----------------|-------------------|
| results/spectrum.json | Energy eigenvalues | [KB] | [hash] |
| figures/fig1.pdf | Main result figure | [KB] | [hash, approximate — font rendering may vary] |

**Note:** Checksums for figures are approximate due to font rendering and floating-point differences across platforms. Numerical data checksums should match exactly.

## Computational Resource Requirements

| Step | CPU Cores | Memory (GB) | GPU | Wall Time | Notes |
|------|-----------|-------------|-----|-----------|-------|
| Data prep | 1 | [2] | No | [5 min] | |
| Core computation | [8] | [16] | [optional] | [1.5 hrs] | [scales linearly with cores] |
| Analysis | 1 | [4] | No | [10 min] | |
| Plotting | 1 | [2] | No | [2 min] | |

**Minimum viable:** [e.g., "4 cores, 8 GB RAM, ~3 hours"]
**Recommended:** [e.g., "8+ cores, 16 GB RAM, ~1.5 hours"]

## Random Seeds

| Computation | Seed | Purpose |
|-------------|------|---------|
| [e.g., Monte Carlo sampling] | [42] | [Reproducible disorder realizations] |
| [e.g., Bootstrap error estimation] | [123] | [Reproducible confidence intervals] |

**Seeding strategy:** [e.g., "Base seed in config; per-sample seeds derived as hash(base_seed, sample_index)"]

## Known Platform Differences

| Platform | Issue | Workaround |
|----------|-------|-----------|
| [e.g., macOS ARM] | [LAPACK gives slightly different eigenvalue ordering] | [Sort eigenvalues after diagonalization] |
| [e.g., Windows] | [Path separator differences in output files] | [Use pathlib throughout] |

## Verification

To verify a successful reproduction:

1. Run the full pipeline above
2. Compare key numerical results against Expected Outputs table (within stated tolerances)
3. Visual comparison of figures against published versions
4. Run `python scripts/verify_reproduction.py` for automated checks (if provided)

---

_Manifest created: [YYYY-MM-DD]_
_Last verified: [YYYY-MM-DD] on [platform]_
```

---

## Guidelines

**What must be pinned:**
- All Python packages with exact versions (not ranges)
- System libraries if compilation is involved
- Data file versions and checksums
- Random seeds for stochastic computations

**What can be approximate:**
- Figure checksums (font rendering varies)
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
