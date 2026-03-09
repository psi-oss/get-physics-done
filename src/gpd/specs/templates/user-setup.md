---
template_version: 1
---

# User Setup Template

Template for `.planning/phases/XX-name/{phase}-USER-SETUP.md` - human-required configuration that GPD cannot automate.

**Purpose:** Document setup tasks that literally require human action - obtaining licensed software, downloading restricted datasets, configuring HPC credentials, setting up institutional access. GPD automates everything possible; this file captures only what remains.

---

## File Template

````markdown
# Phase {X}: User Setup Required

**Generated:** [YYYY-MM-DD]
**Phase:** {phase-name}
**Status:** Incomplete

Complete these items for the research environment to function. GPD automated everything possible; these items require human access to external resources or institutional credentials.

## Environment Variables

| Status | Variable       | Source                                      | Add to |
| ------ | -------------- | ------------------------------------------- | ------ |
| [ ]    | `ENV_VAR_NAME` | [Source description -> Path -> To -> Value] | `.env` |
| [ ]    | `ANOTHER_VAR`  | [Source description -> Path -> To -> Value] | `.env` |

## Computational Environment

[Only if specific software or HPC configuration is required]

- [ ] **Install [Software/Library]**

  - Source: [URL or package manager]
  - Version: [required version or constraint]
  - Skip if: Already installed and version-compatible

- [ ] **Configure HPC access**
  - Cluster: [cluster name]
  - Account: [allocation/project code]
  - Modules: [required module loads]

## Data and References

[Only if external data files or references are required]

- [ ] **Obtain [dataset/reference]**
  - Source: [URL, database, or institutional repository]
  - Format: [expected format]
  - Place in: [target directory path]
  - Notes: [access restrictions, license terms]

## LaTeX and Bibliography

[Only if document preparation configuration is required]

- [ ] **Set up LaTeX template**

  - Template: [journal style file or institutional template]
  - Source: [URL or journal submission page]
  - Place in: [target directory]

- [ ] **Configure bibliography**
  - BibTeX file: [path]
  - Citation style: [style name, e.g., apsrev4-2]
  - Notes: [any special bibliography requirements]

## Notation Conventions

[Only if project-wide notation conventions need human review]

- [ ] **Review notation document**
  - File: [path to notation conventions file]
  - Action: Confirm conventions match collaborator expectations
  - Notes: [any conventions that need group consensus]

## Verification

After completing setup, verify with:

```bash
# [Verification commands]
```
````

Expected results:

- [What success looks like]

---

**Once all items complete:** Mark status as "Complete" at top of file.

````

---

## When to Generate

Generate `{phase}-USER-SETUP.md` when plan frontmatter contains `user_setup` field.

**Trigger:** `user_setup` exists in PLAN.md frontmatter and has items.

**Location:** Same directory as PLAN.md and SUMMARY.md.

**Timing:** Generated during execute-plan.md after tasks complete, before SUMMARY.md creation.

---

## Frontmatter Schema

In PLAN.md, `user_setup` declares human-required configuration:

```yaml
user_setup:
  - service: hpc-cluster
    why: "Large-scale simulation requires HPC allocation"
    env_vars:
      - name: SLURM_ACCOUNT
        source: "HPC portal -> Allocations -> Active -> Project code"
      - name: SCRATCH_DIR
        source: "HPC portal -> Storage -> Scratch filesystem path"
    setup_steps:
      - task: "Load required modules"
        details: "module load python/3.11 openmpi/4.1 fftw/3.3"
      - task: "Test job submission"
        details: "Submit test.slurm to verify allocation is active"
  - service: restricted-dataset
    why: "Experimental data requires institutional access"
    data_files:
      - name: "NIST atomic spectra database export"
        source: "https://physics.nist.gov/PhysRefData/ASD/ -> select elements -> download"
        format: "CSV"
        destination: "data/nist_spectra/"
````

---

## The Automation-First Rule

**USER-SETUP.md contains ONLY what GPD literally cannot do.**

| GPD CAN Do (not in USER-SETUP)    | GPD CANNOT Do (-> USER-SETUP)                      |
| --------------------------------- | -------------------------------------------------- |
| `pip install numpy scipy`         | Obtain licensed software (VASP, Gaussian)          |
| Write simulation scripts          | Get HPC allocation credentials                     |
| Create `.env` file structure      | Copy actual API keys or tokens                     |
| Set up project directory tree     | Download access-restricted datasets                |
| Write LaTeX document skeleton     | Obtain journal-specific style files behind paywall |
| Install open-source tools         | Authenticate with institutional SSO                |
| Generate BibTeX entries from DOIs | Access papers behind institutional proxy           |
| Write analysis notebooks          | Configure VPN for cluster access                   |

**The test:** "Does this require a human with institutional credentials, licensed access, or account ownership?"

- Yes -> USER-SETUP.md
- No -> GPD does it automatically

---

## Research-Specific Examples

<hpc_example>

````markdown
# Phase 3: User Setup Required

**Generated:** 2025-01-14
**Phase:** 03-large-scale-simulation
**Status:** Incomplete

Complete these items for HPC simulation to function.

## Environment Variables

| Status | Variable          | Source                                                       | Add to |
| ------ | ----------------- | ------------------------------------------------------------ | ------ |
| [ ]    | `SLURM_ACCOUNT`   | HPC portal -> Allocations -> Active projects -> Project code | `.env` |
| [ ]    | `SCRATCH_DIR`     | HPC portal -> Storage -> Your scratch path                   | `.env` |
| [ ]    | `OMP_NUM_THREADS` | Set based on node architecture (typically 32 or 64)          | `.env` |

## Computational Environment

- [ ] **Verify HPC allocation is active**

  - URL: [HPC portal URL]
  - Check: Sufficient SUs remaining for estimated computation (~50,000 core-hours)
  - Skip if: Allocation confirmed active this quarter

- [ ] **Load and test required modules**
  - SSH into cluster
  - Run: `module load python/3.11 openmpi/4.1 fftw/3.3 hdf5/1.14`
  - Test: `python -c "import mpi4py; print(mpi4py.get_config())"`

## Data and References

- [ ] **Transfer input configurations to cluster**
  - Source: `data/input_configs/` (generated by Phase 2)
  - Destination: `$SCRATCH_DIR/project/inputs/`
  - Method: `rsync -avz data/input_configs/ user@cluster:$SCRATCH_DIR/project/inputs/`

## Verification

After completing setup:

```bash
# Test job submission
sbatch --account=$SLURM_ACCOUNT test_job.slurm

# Check job status
squeue -u $USER

# Verify output
cat test_job.out  # Should show "Test completed successfully"
```
````

Expected: Test job runs and completes within 5 minutes, output files appear in scratch directory.

---

**Once all items complete:** Mark status as "Complete" at top of file.

````
</hpc_example>

<licensed_software_example>
```markdown
# Phase 1: User Setup Required

**Generated:** 2025-01-14
**Phase:** 01-electronic-structure
**Status:** Incomplete

Complete these items for DFT calculations to function.

## Computational Environment

- [ ] **Install VASP** (licensed)
  - Source: VASP portal (requires institutional license)
  - Version: 6.4.x
  - Skip if: Already installed on target machine
  - Note: GPD has prepared all input files (INCAR, POSCAR, KPOINTS, POTCAR paths); only the binary is needed

- [ ] **Obtain pseudopotential library**
  - Source: VASP portal -> Downloads -> Pseudopotentials -> PAW PBE
  - Place in: `$VASP_PP_PATH` (set in `.env`)
  - Required elements: C, N, O, H, Fe

## Environment Variables

| Status | Variable | Source | Add to |
|--------|----------|--------|--------|
| [ ] | `VASP_PP_PATH` | Path where you placed pseudopotential files | `.env` |
| [ ] | `VASP_COMMAND` | Full path to vasp_std binary | `.env` |

## Verification

After completing setup:

```bash
# Verify VASP is accessible
$VASP_COMMAND --version

# Run minimal test calculation (prepared by GPD)
cd tests/vasp_sanity/ && mpirun -np 4 $VASP_COMMAND
````

Expected: VASP runs, produces OUTCAR with "General timing" section, total energy converged.

---

**Once all items complete:** Mark status as "Complete" at top of file.

````
</licensed_software_example>

<latex_example>
```markdown
# Phase 7: User Setup Required

**Generated:** 2025-01-14
**Phase:** 07-manuscript-preparation
**Status:** Incomplete

Complete these items for manuscript compilation to function.

## LaTeX and Bibliography

- [ ] **Obtain journal style file**
  - Journal: Physical Review Letters
  - Source: https://journals.aps.org/revtex -> Download REVTeX 4.2
  - Place in: `manuscript/` directory
  - Skip if: REVTeX already installed via texlive (`kpsewhich revtex4-2.cls`)

- [ ] **Review notation conventions document**
  - File: `manuscript/notation-conventions.md`
  - Action: Confirm notation matches collaborator preferences
  - Key items: Fourier transform convention, metric signature, natural units definition

- [ ] **Verify bibliography completeness**
  - File: `manuscript/references.bib`
  - Action: Confirm all cited works are present and DOIs are correct
  - GPD has auto-generated entries from DOIs; verify institutional access for any paywalled references

## Verification

After completing setup:

```bash
# Compile manuscript
cd manuscript/ && latexmk -pdf main.tex

# Check for undefined references
grep -c "undefined" main.log  # Should be 0
````

Expected: PDF compiles without errors, all references resolve, figures render correctly.

---

**Once all items complete:** Mark status as "Complete" at top of file.

```
</latex_example>

---

## Guidelines

**Never include:** Actual secret values. Steps GPD can automate (package installs, code generation, directory creation).

**Naming:** `{phase}-USER-SETUP.md` matches the phase number pattern.
**Status tracking:** User marks checkboxes and updates status line when complete.
**Searchability:** `grep -r "USER-SETUP" .planning/` finds all phases with user requirements.
```
