<purpose>
Create all phases necessary to close research gaps identified by `/gpd:audit-milestone`. Reads MILESTONE-AUDIT.md, groups gaps into logical phases, creates phase entries in ROADMAP.md, and offers to plan each phase. One command creates all fix phases -- no manual `/gpd:add-phase` per gap.

Research gaps include: missing derivations, unchecked limiting cases, incomplete analysis, missing figures, unvalidated numerical results, missing comparisons with literature.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

## 1. Load Audit Results

```bash
# Find the most recent audit file
ls -t .gpd/v*-MILESTONE-AUDIT.md 2>/dev/null | head -1
```

Parse YAML frontmatter to extract structured gaps:

- `gaps.requirements` -- unsatisfied research requirements
- `gaps.consistency` -- cross-phase physics inconsistencies
- `gaps.completeness` -- missing analysis, unchecked cases, incomplete work

If no audit file exists or has no gaps, error:

```
No audit gaps found. Run `/gpd:audit-milestone` first.
```

## 2. Prioritize Gaps

Group gaps by priority from REQUIREMENTS.md:

| Priority | Action                                                                                    |
| -------- | ----------------------------------------------------------------------------------------- |
| `must`   | Create phase, blocks milestone (e.g., missing key derivation, unverified central claim)   |
| `should` | Create phase, recommended (e.g., additional limiting case, comparison with second method) |
| `nice`   | Ask researcher: include or defer? (e.g., additional plots, extended parameter range)      |

For consistency/completeness gaps, infer priority from affected requirements and research impact.

## 3. Group Gaps into Phases

Cluster related gaps into logical research phases:

**Grouping rules:**

- Same physics topic -> combine into one phase
- Same computational method -> combine
- Dependency order (derive first, then validate numerically)
- Keep phases focused: 2-4 tasks each

**Example grouping:**

```
Gap: REQ-03 unsatisfied (Limiting cases not checked)
Gap: Consistency: Phase 1 uses k_B=1 but Phase 3 uses SI units
Gap: Completeness: No comparison with Monte Carlo benchmarks

-> Phase 6: "Validate and Cross-Check Results"
  - Check all limiting cases (weak coupling, high-T, classical)
  - Unify unit conventions across all derivations
  - Run Monte Carlo comparison at three benchmark points
  - Generate comparison plots
```

## 4. Determine Phase Numbers

Find highest existing phase:

```bash
# Get sorted phase list, extract last one
PHASES=$(gpd phase list)
HIGHEST=$(echo "$PHASES" | gpd json get .directories[-1] --default "")
if [ -z "$HIGHEST" ]; then
  echo "ERROR: No existing phases found. Create phases with /gpd:plan-phase first."
  # STOP — cannot determine gap phase numbering without existing phases
fi
```

New phases continue from there:

- If Phase 5 is highest, gaps become Phase 6, 7, 8...

## 5. Present Gap Closure Plan

```markdown
## Research Gap Closure Plan

**Milestone:** {version}
**Gaps to close:** {N} requirements, {M} consistency, {K} completeness

### Proposed Phases

**Phase {N}: {Name}**
Closes:

- {REQ-ID}: {description}
- Consistency: {issue description}
  Tasks: {count}

**Phase {N+1}: {Name}**
Closes:

- {REQ-ID}: {description}
- Completeness: {what is missing}
  Tasks: {count}

{If nice-to-have gaps exist:}

### Deferred (nice-to-have)

These gaps are optional. Include them?

- {gap description}
- {gap description}

---

Create these {X} phases? (yes / adjust / defer all optional)
```

Wait for researcher confirmation.

## 6. Update ROADMAP.md

Add new phases to current milestone:

```markdown
### Phase {N}: {Name}

**Goal:** {derived from gaps being closed}
**Requirements:** {REQ-IDs being satisfied}
**Gap Closure:** Closes gaps from audit
```

## 7. Create Phase Directories

```bash
mkdir -p ".gpd/phases/{NN}-{name}"
```

## 8. Commit Roadmap Update

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/ROADMAP.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs(roadmap): add gap closure phases {N}-{M}" --files .gpd/ROADMAP.md
```

## 9. Offer Next Steps

```markdown
## Gap Closure Phases Created

**Phases added:** {N} - {M}
**Gaps addressed:** {count} requirements, {count} consistency, {count} completeness

---

## > Next Up

**Plan first gap closure phase**

`/gpd:plan-phase {N}`

<sub>`/clear` first -> fresh context window</sub>

---

**Also available:**

- `/gpd:execute-phase {N}` -- if plans already exist
- `cat .gpd/ROADMAP.md` -- see updated roadmap

---

**After all gap phases complete:**

`/gpd:audit-milestone` -- re-audit to verify gaps closed
`/gpd:complete-milestone {version}` -- archive when audit passes
```

</process>

<gap_to_phase_mapping>

## How Research Gaps Become Tasks

**Requirement gap -> Tasks:**

```yaml
gap:
  id: REQ-03
  description: "Verify all limiting cases"
  reason: "Only weak-coupling limit checked; strong-coupling and classical limits missing"
  missing:
    - "Strong-coupling expansion and comparison"
    - "Classical limit (hbar -> 0) recovery"
    - "High-temperature expansion to leading order"

becomes:

phase: "Complete Limiting Case Analysis"
tasks:
  - name: "Derive strong-coupling limit"
    files:
      [derivations/strong_coupling.tex, notebooks/strong_coupling_check.ipynb]
    action: "Expand in 1/U, verify leading-order term matches known result"

  - name: "Check classical limit"
    files: [derivations/classical_limit.tex]
    action: "Take hbar -> 0 systematically, verify classical action recovered"

  - name: "High-temperature expansion"
    files: [derivations/high_T.tex, notebooks/high_T_check.ipynb]
    action: "Expand free energy in beta, compare first three terms with known series"
```

**Consistency gap -> Tasks:**

```yaml
gap:
  phase_a: 1
  phase_b: 3
  issue: "Inconsistent unit conventions"
  reason: "Phase 1 uses natural units (hbar=c=1), Phase 3 uses SI for numerical comparison"
  missing:
    - "Explicit unit conversion factors"
    - "Consistent notation table"

becomes:

phase: "Unify Notation and Units"
tasks:
  - name: "Create notation table"
    files: [docs/notation.md]
    action: "Define all symbols, units, and conventions used across phases"

  - name: "Add conversion factors to Phase 3"
    files: [notebooks/numerical_comparison.ipynb]
    action: "Insert explicit conversion from natural to SI units with dimensional checks"
```

**Completeness gap -> Tasks:**

```yaml
gap:
  name: "Missing comparison with literature"
  what_is_missing: "No quantitative comparison with published results"
  reason: "Results computed but not benchmarked against Bulla et al. (1999) or Georges et al. (1996)"
  missing:
    - "Extract published data points from literature"
    - "Generate comparison plots"
    - "Quantify agreement/disagreement"

becomes:

phase: "Literature Comparison"
tasks:
  - name: "Compile benchmark data"
    files: [data/literature_benchmarks.json]
    action: "Extract key data points from Bulla 1999 Table II and Georges 1996 Fig. 3"

  - name: "Generate comparison plots"
    files: [notebooks/literature_comparison.ipynb]
    action: "Plot our results against literature with error bars, compute relative deviations"

  - name: "Write comparison summary"
    files: [docs/comparison_summary.md]
    action: "Summarize agreement, explain any discrepancies, assess overall validity"
```

</gap_to_phase_mapping>

<success_criteria>

- [ ] MILESTONE-AUDIT.md loaded and gaps parsed
- [ ] Gaps prioritized (must/should/nice)
- [ ] Gaps grouped into logical research phases
- [ ] Researcher confirmed phase plan
- [ ] ROADMAP.md updated with new phases
- [ ] Phase directories created
- [ ] Changes committed
- [ ] Researcher knows to run `/gpd:plan-phase` next

</success_criteria>
