# Reproducibility Protocol

Computational reproducibility is a minimum standard for credible physics research. If a calculation cannot be reproduced -- by you, by a colleague, or by a future AI session -- the result is not reliable.

<core_principle>

**A result without a reproducibility trail is a result you cannot trust.**

Every computational phase must record enough information to exactly reproduce its outputs from scratch. This is not optional overhead; it is the computational analogue of showing your work in a derivation.

</core_principle>

<random_seeds>

## Random Seed Recording

Any computation involving stochastic elements must record and propagate seeds.

### What Requires Seeds

| Method | Seed Source | Recording Requirement |
|--------|-----------|----------------------|
| Monte Carlo (classical) | PRNG state | Master seed + per-replica seeds |
| Quantum Monte Carlo | PRNG state | Master seed + walker initialization |
| Molecular dynamics (stochastic thermostat) | Langevin noise | Seed per thermostat |
| Neural network training | Weight initialization, data shuffling | Framework seed + data loader seed |
| Stochastic optimization | Random search directions | Optimizer seed |
| Bootstrap resampling | Resampling indices | Analysis seed |
| Disorder averaging | Random potential configurations | Disorder realization seeds |

### Seed Recording Protocol

```python
# At the start of any stochastic computation
import numpy as np
import json
from datetime import datetime, timezone

def record_seeds(master_seed, output_dir):
    """Record seed state for reproducibility."""
    rng = np.random.default_rng(master_seed)

    seed_record = {
        "master_seed": master_seed,
        "numpy_rng_state": rng.bit_generator.state,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "derived_seeds": {
            "simulation": int(rng.integers(0, 2**32)),
            "analysis": int(rng.integers(0, 2**32)),
            "visualization": int(rng.integers(0, 2**32)),
        }
    }

    with open(f"{output_dir}/seeds.json", "w") as f:
        json.dump(seed_record, f, indent=2, default=str)

    return seed_record
```

### Verification Protocol

For any result that depends on stochastic sampling:

1. Record the master seed before the computation
2. Run the computation once, save results
3. Re-run with the same seed, verify bit-for-bit identical output
4. Run with a different seed, verify results agree within stated error bars

If step 3 fails, there is a non-determinism bug (threading race condition, GPU non-determinism, uncontrolled system state). Fix it before trusting results.

If step 4 fails beyond expected statistical fluctuation, the error bars are underestimated.

</random_seeds>

<software_versions>

## Software Version Tracking

### Required Version Records

Every computational phase must record:

```json
{
  "python_version": "3.11.7",
  "packages": {
    "numpy": "1.26.4",
    "scipy": "1.12.0",
    "sympy": "1.12",
    "matplotlib": "3.8.3"
  },
  "mcp_servers": {
    "gpd-verification": "0.1.5",
    "gpd-conventions": "0.1.5",
    "gpd-arxiv": "0.3.2"
  },
  "platform": {
    "os": "Linux 6.1.0",
    "arch": "x86_64"
  }
}
```

If you are recording GPD-managed MCP services, use the public server keys from the runtime descriptors (`gpd-conventions`, `gpd-errors`, `gpd-patterns`, `gpd-protocols`, `gpd-skills`, `gpd-state`, `gpd-verification`, `gpd-arxiv`).

### Automated Version Capture

```python
import sys
import platform
import importlib.metadata

def capture_environment():
    """Capture full computational environment for reproducibility."""
    packages = {}
    for dist in importlib.metadata.distributions():
        packages[dist.metadata["Name"]] = dist.version

    return {
        "python": sys.version,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "packages": packages,
    }
```

### When Versions Matter Most

| Scenario | Risk Level | Example |
|----------|-----------|---------|
| Floating-point operations | High | numpy BLAS backend affects summation order → different rounding |
| Symbolic simplification | Medium | SymPy version changes canonical form of expressions |
| Random number generation | Critical | numpy PRNG algorithm changed between versions |
| Linear algebra routines | High | LAPACK version affects eigenvalue ordering for degenerate cases |
| Optimization algorithms | Medium | scipy.optimize convergence criteria changed |

**Rule:** If you cannot reproduce a result after a package upgrade, the version difference is the first thing to check.

</software_versions>

<hardware_specs>

## Hardware Specifications

Record hardware details when results depend on computational performance or precision.

### When Hardware Matters

| Scenario | Why It Matters | What to Record |
|----------|---------------|---------------|
| GPU computation (CUDA) | GPU architecture affects floating-point behavior | GPU model, CUDA version, driver version |
| Exact diagonalization | Memory limits system size | RAM, CPU cores |
| Large-scale QMC | Wall time determines statistics | CPU model, core count, MPI topology |
| Neural network training | Batch parallelism affects convergence | GPU count, model, memory |
| Precision-sensitive | IEEE 754 compliance varies | CPU model, FP unit, compiler flags |

### Hardware Record Template

```json
{
  "cpu": "AMD EPYC 7763 64-Core",
  "cores_used": 32,
  "ram_gb": 256,
  "gpu": "NVIDIA A100 80GB",
  "gpu_count": 1,
  "cuda_version": "12.2",
  "compiler": "gcc 12.3.0",
  "compiler_flags": "-O3 -march=native",
  "mpi": "OpenMPI 4.1.5"
}
```

### Floating-Point Reproducibility

For results sensitive to floating-point precision:

- Record whether computations use float32 or float64
- Note if `-ffast-math` or equivalent flags are used (breaks IEEE compliance)
- For GPU code: note if tensor cores are used (mixed precision)
- Record summation order if it matters (Kahan summation vs naive)

</hardware_specs>

<data_provenance>

## Data Provenance

### Input Data Tracking

Every input dataset must have:

| Field | Description | Example |
|-------|-----------|---------|
| Source | Where the data came from | "NIST Atomic Spectra Database, version 5.10" |
| URL | Permanent link | "https://physics.nist.gov/asd" |
| Access date | When downloaded | "2025-11-15" |
| Checksum | SHA-256 of downloaded file | "a3f2b1c4..." |
| License | Usage rights | "Public domain" |
| Transformations | Any processing applied | "Converted from eV to Hartree, filtered Z > 10" |

### Data Integrity Verification

```python
import hashlib

def compute_checksum(filepath):
    """Compute SHA-256 checksum of a data file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def verify_data_integrity(filepath, expected_checksum):
    """Verify data file has not been modified."""
    actual = compute_checksum(filepath)
    if actual != expected_checksum:
        raise ValueError(
            f"Data integrity check failed for {filepath}:\n"
            f"  Expected: {expected_checksum}\n"
            f"  Actual:   {actual}"
        )
```

### Output Data Management

Every computational output must be traceable to its inputs:

```
output/
  results.json          # Computed results
  metadata.json         # Execution metadata (seeds, versions, hardware)
  inputs/
    data_manifest.json  # Input file checksums and provenance
  logs/
    execution.log       # Full computation log with timestamps
```

</data_provenance>

<output_verification>

## Output Reproducibility Verification

### Subset Re-Run Protocol

Full reproduction of a large computation may be expensive. Use subset re-runs:

1. **Identify representative subset:** Choose 3-5 parameter points spanning the range
2. **Re-run with recorded seeds:** Must produce bit-for-bit identical output
3. **Re-run with different seeds:** Must agree within stated error bars
4. **Cross-platform check:** Run subset on different machine; agree within numerical precision

### Reproducibility Levels

| Level | Requirement | When Needed |
|-------|-----------|------------|
| Bit-for-bit | Same hardware + software + seeds → identical output | Internal validation, debugging |
| Statistical | Different seeds → same mean within error bars | Published Monte Carlo results |
| Qualitative | Different implementation → same physics | Cross-method validation |
| Approximate | Same trends and order of magnitude | Exploratory phase, initial surveys |

**Minimum standard for any phase producing numerical results:** Statistical reproducibility verified with at least 2 independent seed sets.

</output_verification>

<phase_template>

## Phase Reproducibility Template

Include this in each phase directory that produces computational results:

```markdown
# REPRODUCIBILITY.md

## Computation Environment
- Python: [version]
- Key packages: numpy [ver], scipy [ver], [others]
- Hardware: [CPU/GPU if relevant]
- Date: [computation date]

## Random Seeds
- Master seed: [integer]
- Seed file: seeds.json

## Input Data
| File | Source | Checksum (SHA-256) | Access Date |
|------|--------|-------------------|-------------|
| [file] | [source] | [hash] | [date] |

## Outputs
| File | Description | Reproducibility Level |
|------|-----------|---------------------|
| [file] | [what it contains] | [bit-for-bit / statistical / qualitative] |

## Verification
- [ ] Re-run with same seeds: bit-for-bit match
- [ ] Re-run with different seeds: within error bars
- [ ] Version lock file present (requirements.txt or equivalent)

## Known Non-Determinism
[Document any known sources of non-determinism and their impact on results]
```

</phase_template>
