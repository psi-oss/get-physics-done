# Worked Example: Contradiction Resolution with Confidence Weighting

This example shows how to resolve a real contradiction between research files where both sides present seemingly strong evidence.

## The Contradiction

**METHODS.md** (HIGH confidence):
> "For the 2D Hubbard model at half-filling, DMRG is the method of choice. Ground state
> energies converge to 6 significant figures with bond dimension χ = 4000. The Mott gap
> Δ = 0.68(1) t at U/t = 4 is well-established."

**PITFALLS.md** (HIGH confidence):
> "DMRG for the 2D Hubbard model has known cylinder-geometry artifacts. The Mott gap
> extracted from DMRG on width-6 cylinders is systematically 10-15% too large compared
> to AFQMC on larger square lattices. Use Δ = 0.59(3) t from AFQMC as the benchmark."

**COMPUTATIONAL.md** (MEDIUM confidence):
> "DFT+DMFT gives Δ = 0.72(5) t at U/t = 4 but this includes vertex corrections
> that DMRG and AFQMC neglect. The 'true' gap depends on the observable definition."

## Resolution Process

**Step 1: Classify** — This is a numerical disagreement (Δ = 0.68 vs 0.59 vs 0.72), not a convention conflict. All use the same units (energy in units of t) and the same definition of the Mott gap (single-particle spectral gap).

**Step 2: Check regime differences** — All three quote U/t = 4 for the half-filled 2D Hubbard model. Same regime. But:
- DMRG: cylinder geometry (width 6 × length 48)
- AFQMC: square lattice (12 × 12)
- DFT+DMFT: infinite lattice (but with bath approximation)

The geometries differ. The "same regime" is not exactly the same system.

**Step 3: Assess source reliability with confidence weighting**

| Finding | Source | Confidence | Method quality | Geometry | Systematic errors |
|---------|--------|-----------|---------------|----------|-------------------|
| Δ = 0.68(1) | METHODS.md | HIGH | DMRG is exact for 1D/quasi-1D | Cylinder (finite width) | Cylinder boundary effects not fully controlled |
| Δ = 0.59(3) | PITFALLS.md | HIGH | AFQMC exact for half-filling | Square lattice | Constrained-path approximation (exact at half-filling) |
| Δ = 0.72(5) | COMPUTATIONAL.md | MEDIUM | DFT+DMFT approximate | Infinite lattice | Impurity solver truncation, bath discretization |

**Step 4: Apply confidence-weighted resolution**

Both HIGH-confidence findings conflict. Per the High-Confidence Contradiction Protocol:

1. **Do NOT average** (0.68 + 0.59)/2 = 0.635 is physically meaningless
2. **Identify assumptions:** DMRG assumes cylinder geometry is representative of 2D; AFQMC assumes constrained-path approximation is exact at half-filling (it is)
3. **Assess for THIS project:** If the project targets 2D thermodynamic limit, AFQMC on square lattices is more representative. If the project targets quasi-1D systems, DMRG is more appropriate.
4. **Recommendation:** For a 2D project, use AFQMC value Δ = 0.59(3) as primary benchmark. Note DMRG cylinder value Δ = 0.68(1) as upper bound from finite-width effects.

**Step 5: Document in SUMMARY.md**

```markdown
### Contradiction: Mott Gap at U/t = 4

**Conflict:** METHODS.md cites Δ = 0.68(1) t (DMRG, cylinder); PITFALLS.md cites
Δ = 0.59(3) t (AFQMC, square lattice); COMPUTATIONAL.md cites Δ = 0.72(5) t (DFT+DMFT).

**Diagnosis:** Geometry-dependent systematic error, not a convention or definition issue.
DMRG cylinder width-6 results are known to overestimate 2D gaps by 10-15% (Zheng et al.,
Science 2017). AFQMC at half-filling has no sign problem, making it numerically exact.
DFT+DMFT result higher due to approximate nature of the bath.

**Resolution:** Adopt AFQMC value Δ = 0.59(3) t as primary benchmark for 2D calculations.
Use DMRG value Δ = 0.68(1) t as cross-check for quasi-1D limit. Flag DFT+DMFT value
as upper bound. [CONFIDENCE: HIGH for resolution]

**Roadmap impact:** Phase 3 (numerical benchmarking) should reproduce AFQMC value
before proceeding to novel calculations.
```

## Key Principles Demonstrated

1. **Don't average conflicting values** — averages hide systematic errors
2. **Trace each value to its assumptions** — geometry, method limitations, approximations
3. **Weight by relevance to THIS project** — the "best" value depends on what you're computing
4. **Document the full chain of reasoning** — the roadmapper needs to understand WHY you chose this value
5. **Assign confidence to the resolution itself** — "I'm confident in this choice because..."
