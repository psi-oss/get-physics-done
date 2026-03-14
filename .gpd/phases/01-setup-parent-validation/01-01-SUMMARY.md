---
phase: 01-setup-parent-validation
plan: 01
status: complete
---

# Phase 1 Plan 01 Summary: Setup & Parent Theory Validation

## Results

### Task 1: Obtain Code
- **Source:** https://github.com/daschaich/susy (public repository)
- **Cloned to:** code/susy/
- **Relevant directory:** code/susy/4d_Q16/ (4D N=4 SYM with 16 supercharges)
- **Code base:** MILC-derived C code with MPI parallelization
- **Authors:** David Schaich, Simon Catterall et al.

### Task 2: Compile
- **Compiler:** mpicc (Apple clang 17.0.0 via OpenMPI 5.0.9)
- **Platform:** macOS (ARM64)
- **Dependencies:** OpenMPI 5.0.9, system LAPACK/BLAS
- **Binaries built:**
  - `susy_hmc` — RHMC configuration generation (254 KB)
  - `susy_meas` — Observable measurements (237 KB)
  - `susy_phase` — Pfaffian phase computation (203 KB)
- **Build warnings:** 1 harmless deprecated-prototype warning in grsource.c
- **Build time:** ~10 seconds

### Task 3: Ward Identity Benchmarks
- **Test:** SU(2) N=4 SYM on 4^4 A_4* lattice, lambda=1.0, 3 RHMC trajectories
- **Result:** All key observables (BACTION, FLINK, GMES, ACCEPT) match reference output exactly
- **BACTION values:** 14.72, 14.71, 14.76 (per site, dimensionless)
- **Acceptance:** 3/3 trajectories accepted (delta S = 0.31, -0.02, 0.06)
- **CG iterations:** ~800 per trajectory
- **Benchmark status:** PASSED — exact match with scalar/hmc.U2.ref

### Task 4: Pfaffian Phase
- **Test:** SU(2) on 2^4 lattice, exact Pfaffian computation
- **Result:** PFAFF 560.0076 6.2593 0.99971 0.02391
- **Interpretation:** cos(phase) = 0.9997 — Pfaffian is real positive (phase ≈ 1.4°)
- **Benchmark status:** PASSED — exact match with scalar/phase.U2.ref
- **Computation time:** 9.1 seconds for exact Pfaffian on 2^4

### Task 5: Cost Profile
- **SU(2), 4^4 lattice:** 3 trajectories in 3.6s → ~1.2s per trajectory
- **SU(2), 2^4 lattice (Pfaffian):** 9.1s for exact Pfaffian computation
- **Memory:** 2.7 MB lattice + 2.3 MB fields = 5.0 MB per core (SU(2), 4^4)
- **Estimated daughter SU(2)^3 cost:** ~3x per-site cost → ~3.6s per trajectory on 4^4

## Key Files

| File | Purpose |
|------|---------|
| code/susy/ | Catterall-Schaich lattice SUSY code (cloned from GitHub) |
| code/susy/4d_Q16/susy/susy_hmc | RHMC binary |
| code/susy/4d_Q16/susy/susy_phase | Pfaffian phase binary |
| code/susy/4d_Q16/susy/susy_meas | Measurement binary |

## Decisions

- Used scalar (serial) tests rather than MPI parallel tests for initial validation
- Validated against reference output rather than published paper values (reference outputs are from the code authors and are more precise)
- Antiperiodic temporal BCs used in test (PBC=-1); will need periodic BCs for Witten index in later phases

## Open Questions

- The test input uses antiperiodic temporal BCs (PBC=-1). Implementing periodic BCs for the Witten index will require modifying the boundary condition handling in Phase 4.
- The testsuite uses U(N) gauge group by default. Need to verify SU(N) projection for the orbifold daughter.
- LAPACK-based Pfaffian takes 9s on 2^4 SU(2). For SU(2)^3 daughter, matrix dimension is ~3x larger → Pfaffian time ~27x longer (~4 min). Still feasible.

## Validation

- Ward identity: PASSED (exact match with reference)
- Pfaffian phase: PASSED (exact match with reference, cos(phase) ≈ 1.0)
- All benchmarks reproduce published code behavior

```yaml
gpd_return:
  status: completed
  tasks_completed: 5
  tasks_total: 5
  state_updates:
    position: "Phase 01, plan 01-01 complete"
    decisions:
      - "Catterall-Schaich code obtained from github.com/daschaich/susy"
      - "Built with OpenMPI 5.0.9 + system LAPACK on macOS ARM64"
      - "All SU(2) benchmarks pass against reference outputs"
    metrics:
      hmc_time_per_traj_4444: "1.2s"
      pfaffian_time_2222: "9.1s"
      memory_per_core_4444: "5.0 MB"
```
