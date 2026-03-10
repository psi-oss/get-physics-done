<ui_patterns>

Visual patterns for user-facing GPD output. Orchestrators @-reference this file.

## Stage Banners

Use for major workflow transitions.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD ► {STAGE NAME}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Stage names (uppercase):**

- `FORMULATING PROBLEM`
- `SURVEYING LITERATURE`
- `DEFINING SCOPE`
- `CREATING ROADMAP`
- `PLANNING PHASE {N}`
- `EXECUTING WAVE {N}`
- `VERIFYING`
- `PHASE {N} COMPLETE ✓`
- `MILESTONE COMPLETE ⚛️`

---

## Checkpoint Boxes

User action required. 62-character width.

```
╔══════════════════════════════════════════════════════════════╗
║  CHECKPOINT: {Type}                                          ║
╚══════════════════════════════════════════════════════════════╝

{Content}

──────────────────────────────────────────────────────────────
→ {ACTION PROMPT}
──────────────────────────────────────────────────────────────
```

**Types:**

- `CHECKPOINT: Verification Required` → `→ Type "approved" or describe issues`
- `CHECKPOINT: Decision Required` → `→ Select: option-a / option-b`
- `CHECKPOINT: Action Required` → `→ Type "done" when complete`
- `CHECKPOINT: Physics Check Required` → `→ Confirm dimensional consistency / limiting cases`

---

## Status Symbols

```
✓  Complete / Passed / Verified
✗  Failed / Inconsistent / Divergent
◆  In Progress
○  Pending
⚡ Auto-verified (dimensional analysis, symmetry check)
⚠  Warning (suspicious but not proven wrong)
⚛️  Milestone complete (only in banner)
∇  Gradient/field operation in progress
∞  Divergence detected
≈  Approximate agreement
```

---

## Progress Display

**Phase/milestone level:**

```
Progress: ████████░░ 80%
```

**Task level:**

```
Tasks: 2/4 complete
```

**Plan level:**

```
Plans: 3/5 complete
```

**Convergence display (numerical phases):**

```
Convergence: |δE| = 2.3e-6 → 1.1e-8 → 4.7e-11  ✓ (tol: 1e-8)
```

---

## Spawning Indicators

```
◆ Spawning researcher...

◆ Spawning 4 researchers in parallel...
  → Symmetry analysis
  → Perturbative expansion
  → Numerical estimation
  → Literature cross-check

✓ Researcher complete: SYMMETRY_ANALYSIS.md written
```

---

## Next Up Block

Always at end of major completions.

```
───────────────────────────────────────────────────────────────

## ▶ Next Up

**{Identifier}: {Name}** — {one-line description}

`{copy-paste command}`

*(`/clear` first → fresh context window)*

───────────────────────────────────────────────────────────────

**Also available:**
- `$gpd-alternative-1` — description
- `$gpd-alternative-2` — description

───────────────────────────────────────────────────────────────
```

---

## Error Box

```
╔══════════════════════════════════════════════════════════════╗
║  ERROR                                                       ║
╚══════════════════════════════════════════════════════════════╝

{Error description}

**To fix:** {Resolution steps}
```

---

## Physics-Specific Display Elements

**Equation reference:**

```
Eq. (3.14): H = p²/2m + V(x)
```

**Unit annotation:**

```
[E] = GeV    [L] = fm    [T] = fm/c
```

**Parameter table:**

```
| Parameter | Value | Units | Source |
|-----------|-------|-------|--------|
| m_e       | 0.511 | MeV/c² | PDG 2024 |
| α         | 1/137.036 | dimensionless | CODATA |
| Λ_QCD     | 217 | MeV | lattice |
```

**Verification summary:**

```
Checks:
  ✓ Dimensional analysis
  ✓ Non-relativistic limit → Schrodinger equation
  ✓ Energy conservation (ΔE/E < 1e-12)
  ⚠ Gauge invariance (numerical, not exact)
  ○ Lorentz covariance (pending)
```

---

## Tables

```
| Phase | Status | Plans | Progress |
|-------|--------|-------|----------|
| 1     | ✓      | 3/3   | 100%     |
| 2     | ◆      | 1/4   | 25%      |
| 3     | ○      | 0/2   | 0%       |
```

---

## Anti-Patterns

- Varying box/banner widths
- Mixing banner styles (`===`, `---`, `***`)
- Skipping `GPD ►` prefix in banners
- Random emoji (keep to defined symbol set above)
- Missing Next Up block after completions
- Displaying raw floating-point without appropriate significant figures
- Omitting units on dimensional quantities

</ui_patterns>
