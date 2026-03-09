---
template_version: 1
---

# Research Template

Template for `.planning/phases/XX-name/{phase}-RESEARCH.md` - comprehensive literature and methods research before planning a physics research phase.

**Purpose:** Document what the agent needs to know to execute a research phase well - not just "which method" but "how do experts approach this problem, what's known, what's open, and what notation conventions exist."

**Depth parameter:** This is the comprehensive research template. For lighter pre-planning exploration, see `discovery.md` which produces DISCOVERY.md. Use the `depth` field to control scope:
- `quick` — Landscape scan: Summary, Key Findings, Recommended Methods, What Was NOT Found, Sources. Skip detailed analysis.
- `standard` — Balanced: all sections at moderate depth (default).
- `deep` — Thorough: all sections with full analysis, citation verification, controversy mapping.

---

## File Template

````markdown
# Phase [X]: [Name] - Research

**Researched:** [date]
**Domain:** [primary physics subfield / problem domain]
**Depth:** [quick|standard|deep]
**Confidence:** [HIGH/MEDIUM/LOW]

<user_constraints>

## User Constraints (from CONTEXT.md)

**CRITICAL:** If CONTEXT.md exists from $gpd-discuss-phase, copy locked decisions here verbatim. These MUST be honored by the planner.

### Locked Decisions

[Copy from CONTEXT.md `## Decisions` section - these are NON-NEGOTIABLE]

- [Decision 1]
- [Decision 2]

### Agent's Discretion

[Copy from CONTEXT.md - areas where researcher/planner can choose]

- [Area 1]
- [Area 2]

### Deferred Ideas (OUT OF SCOPE)

[Copy from CONTEXT.md - do NOT research or plan these]

- [Deferred 1]
- [Deferred 2]

**If no CONTEXT.md exists:** Write "No user constraints - all decisions at agent's discretion"
</user_constraints>

<research_summary>

## Summary

[2-3 paragraph executive summary]

- What was researched (which subfield, which problem)
- What the standard theoretical/computational approach is
- Key recommendations for the research direction

**Primary recommendation:** [one-liner actionable guidance for the research phase]
</research_summary>

<literature_landscape>

## Literature Landscape

Key papers and results organized by relevance:

### Foundational Papers

| Paper   | Authors   | Year   | Key Result            | Relevance                        |
| ------- | --------- | ------ | --------------------- | -------------------------------- |
| [title] | [authors] | [year] | [main result/theorem] | [why it matters for our problem] |
| [title] | [authors] | [year] | [main result/theorem] | [why it matters for our problem] |

### Recent Advances

| Paper   | Authors   | Year   | Key Result            | Relevance                        |
| ------- | --------- | ------ | --------------------- | -------------------------------- |
| [title] | [authors] | [year] | [main result/advance] | [why it matters for our problem] |
| [title] | [authors] | [year] | [main result/advance] | [why it matters for our problem] |

### Review Articles and Textbook Treatments

| Source  | Authors   | Coverage | Best For                     |
| ------- | --------- | -------- | ---------------------------- |
| [title] | [authors] | [scope]  | [what aspect it covers well] |

### Notation Conventions Across Papers

| Quantity   | Paper A notation | Paper B notation | Our convention  | Notes               |
| ---------- | ---------------- | ---------------- | --------------- | ------------------- |
| [quantity] | [symbol]         | [symbol]         | [chosen symbol] | [reason for choice] |
| [quantity] | [symbol]         | [symbol]         | [chosen symbol] | [reason for choice] |

**Key notational hazards:** [Where different papers use the same symbol for different things, or vice versa]
</literature_landscape>

<methods_and_approaches>

## Methods and Approaches

> This is the **primary methods template** for phase-level research. For analyzing an existing project's
> methods (via `map-theory`), see `analysis/methods.md`. For the raw new-project survey template consumed
> by workflows, see `research-project/METHODS.md` — do NOT use it directly; its content is incorporated here.

### Standard Analytical Methods

| Method   | When to Use                   | Limitations            | Key Reference    |
| -------- | ----------------------------- | ---------------------- | ---------------- |
| [method] | [conditions where it applies] | [where it breaks down] | [paper/textbook] |
| [method] | [conditions where it applies] | [where it breaks down] | [paper/textbook] |

### Computational Tools

| Tool/Package | Version | Purpose            | Why Standard         |
| ------------ | ------- | ------------------ | -------------------- |
| [name]       | [ver]   | [what it computes] | [why experts use it] |
| [name]       | [ver]   | [what it computes] | [why experts use it] |

### Supporting Tools

| Tool/Package | Version | Purpose        | When to Use |
| ------------ | ------- | -------------- | ----------- |
| [name]       | [ver]   | [what it does] | [use case]  |
| [name]       | [ver]   | [what it does] | [use case]  |

### Alternatives Considered

| Instead of        | Could Use     | Tradeoff                       |
| ----------------- | ------------- | ------------------------------ |
| [standard method] | [alternative] | [when alternative makes sense] |

**Installation / Setup:**

```bash
pip install [packages]
# or
uv add [packages]
```
````

</methods_and_approaches>

<known_results>

## Known Results and Benchmarks

### Established Results

| Result | Value/Expression   | Conditions           | Source  | Confidence        |
| ------ | ------------------ | -------------------- | ------- | ----------------- |
| [what] | [value or formula] | [regime/assumptions] | [paper] | [HIGH/MEDIUM/LOW] |

### Limiting Cases

| Limit                | Expected Behavior    | Expression         | Source      |
| -------------------- | -------------------- | ------------------ | ----------- |
| [parameter -> value] | [what should happen] | [formula if known] | [reference] |
| [parameter -> value] | [what should happen] | [formula if known] | [reference] |

### Numerical Benchmarks

| Quantity | Published Value         | Method Used    | Parameters   | Source  |
| -------- | ----------------------- | -------------- | ------------ | ------- |
| [what]   | [value +/- uncertainty] | [how computed] | [key params] | [paper] |

**Key insight:** [What the landscape of known results tells us about our problem]
</known_results>

<dont_rederive>

## Don't Re-derive

Problems that look simple but have established solutions:

| Problem   | Don't Derive From Scratch  | Use Instead           | Why                                           |
| --------- | -------------------------- | --------------------- | --------------------------------------------- |
| [problem] | [what you'd try to derive] | [known result/method] | [subtle issues, sign conventions, edge cases] |
| [problem] | [what you'd try to derive] | [known result/method] | [subtle issues, sign conventions, edge cases] |
| [problem] | [what you'd try to derive] | [known result/method] | [subtle issues, sign conventions, edge cases] |

**Key insight:** [Why custom derivations are error-prone in this domain - sign conventions, regularization subtleties, etc.]
</dont_rederive>

<common_pitfalls>

## Common Pitfalls

> Load pitfalls from the project-type template (see `templates/project-types/`). Add project-specific pitfalls below.

### Pitfall 1: [Name]

**What goes wrong:** [description of the error]
**Why it happens:** [root cause - e.g., sign convention mismatch, missing factor of 2pi]
**How to avoid:** [prevention strategy]
**Warning signs:** [how to detect early - e.g., dimensional analysis fails, wrong limiting behavior]

### Pitfall 2: [Name]

**What goes wrong:** [description]
**Why it happens:** [root cause]
**How to avoid:** [prevention strategy]
**Warning signs:** [how to detect early]

### Pitfall 3: [Name]

**What goes wrong:** [description]
**Why it happens:** [root cause]
**How to avoid:** [prevention strategy]
**Warning signs:** [how to detect early]
</common_pitfalls>

<key_derivations>

## Key Derivations and Formulas

Verified results from authoritative sources:

### [Key Formula/Derivation 1]

```
# Source: [textbook/paper reference]
[formula or derivation sketch in LaTeX-compatible notation]
```

**Valid when:** [conditions/assumptions]
**Breaks down when:** [regime where it fails]

### [Key Formula/Derivation 2]

```
# Source: [textbook/paper reference]
[formula or derivation sketch]
```

**Valid when:** [conditions/assumptions]
**Breaks down when:** [regime where it fails]

### [Key Formula/Derivation 3]

```
# Source: [textbook/paper reference]
[formula or derivation sketch]
```

**Valid when:** [conditions/assumptions]
**Breaks down when:** [regime where it fails]
</key_derivations>

<open_questions>

## Open Questions

Things that couldn't be fully resolved:

1. **[Question]**

   - What we know: [partial info]
   - What's unclear: [the gap]
   - Recommendation: [how to handle during planning/execution]

2. **[Question]**

   - What we know: [partial info]
   - What's unclear: [the gap]
   - Recommendation: [how to handle]

3. **[Question]**
   - What we know: [partial info]
   - What's unclear: [the gap]
   - Recommendation: [how to handle]
     </open_questions>

<not_found>

## What Was NOT Found

[Explicitly document gaps — questions investigated but unanswered, sources consulted without result, and methods that turned up no relevant literature. This prevents re-searching the same dead ends and flags genuine knowledge gaps for the planner.]

- [Question investigated but not answered, with sources checked]
- [Method/approach searched for but not found in literature]
- [Expected result that no published source confirms]
</not_found>

<sources>
## Sources

### Primary (HIGH)

- [Textbook/major review] - [topics covered]
- [Foundational paper] - [what was checked]

### Secondary (MEDIUM)

- [Recent paper, cross-checked with primary source] - [finding + verification]
- [Computational package documentation] - [what was checked]

### Tertiary (LOW - needs validation)

- [Preprint or single-source claim] - [finding, marked for validation during execution]
  </sources>

<metadata>
## Metadata

**Research scope:**

- Physics subfield: [what]
- Methods explored: [analytical, computational, experimental references]
- Known results catalogued: [what benchmarks/limits identified]
- Pitfalls: [areas checked for known issues]

**Confidence breakdown:**

- Literature coverage: [HIGH/MEDIUM/LOW] - [reason]
- Methods: [HIGH/MEDIUM/LOW] - [reason]
- Known results: [HIGH/MEDIUM/LOW] - [reason]
- Pitfalls: [HIGH/MEDIUM/LOW] - [reason]

**Research date:** [date]
**Valid until:** [estimate - 30 days for established physics, 7 days for fast-moving subfield]
</metadata>

---

_Phase: XX-name_
_Research completed: [date]_
_Ready for planning: [yes/no]_

````

---

## Good Example

```markdown
# Phase 2: SYK Spectral Form Factor - Research

**Researched:** 2025-06-15
**Domain:** Sachdev-Ye-Kitaev model, quantum chaos, random matrix theory
**Confidence:** HIGH

<research_summary>
## Summary

Researched the spectral form factor (SFF) of the SYK model as a diagnostic for quantum chaos. The SFF measures correlations in the energy spectrum and exhibits a characteristic dip-ramp-plateau structure that signals random matrix universality. The standard approach computes the disorder-averaged SFF analytically in the large-N limit using the replica method, then validates numerically via exact diagonalization at finite N.

Key finding: The ramp region is where physics lives - it emerges from the connected part of the two-point spectral correlator and requires careful treatment of disconnected contributions. The plateau height is fixed by the Hilbert space dimension. Do not attempt to derive the ramp analytically without the replica sigma-model or loop equations; use known RMT results.

**Primary recommendation:** Use exact diagonalization for N <= 34 Majorana fermions (Hilbert space dimension 2^{N/2}), compare against GUE predictions for the ramp slope, and use the disorder-averaged connected SFF to avoid self-averaging issues at early times.
</research_summary>

<literature_landscape>
## Literature Landscape

### Foundational Papers
| Paper | Authors | Year | Key Result | Relevance |
|-------|---------|------|------------|-----------|
| A simple model of quantum holography | Sachdev, Ye | 1993 | Original SY model with random exchange | Foundation of the model |
| Remarks on the SYK model | Maldacena, Stanford | 2016 | Large-N solution, conformal limit, chaos exponent | Standard reference for SYK analytics |
| Black holes and random matrices | Cotler et al. | 2017 | SFF computation, dip-ramp-plateau identification | Direct target of our computation |

### Recent Advances
| Paper | Authors | Year | Key Result | Relevance |
|-------|---------|------|------------|-----------|
| Spectral decoupling in many-body quantum chaos | Gharibyan et al. | 2018 | Late-time RMT universality verified numerically | Validates our numerical approach |
| SYK wormhole formation in real time | Plugge et al. | 2020 | Real-time SFF dynamics | Context for interpretation |

### Notation Conventions Across Papers
| Quantity | Maldacena-Stanford | Cotler et al. | Our convention | Notes |
|----------|-------------------|---------------|----------------|-------|
| Number of Majoranas | N | N | N | Consistent |
| Coupling variance | J^2 | J^2 2^{1-q} / q | J^2 (M-S convention) | Cotler normalizes differently - factor of 2^{1-q}/q |
| Inverse temperature | beta | beta | beta | Consistent |
| SFF | g(t) | K(t) | K(t, beta) | We use Cotler convention with explicit beta |
| Hilbert space dim | - | L = 2^{N/2} | L = 2^{N/2} | Following Cotler |

**Key notational hazards:** The coupling normalization differs by factors of 2 and q between Maldacena-Stanford and Cotler et al. Always check which convention a formula assumes before using it.
</literature_landscape>

<methods_and_approaches>
## Methods and Approaches

### Standard Analytical Methods
| Method | When to Use | Limitations | Key Reference |
|--------|-------------|-------------|---------------|
| Replica sigma-model | Ramp derivation, large-N | Fails at plateau, requires saddle-point | Saad, Shenker, Stanford 2019 |
| Moment method / loop equations | Spectral density, low moments | Combinatorial complexity at high order | Maldacena-Stanford 2016 |
| Random matrix theory (GUE) | Plateau and ramp predictions | Exact only in RMT limit (late time) | Mehta 2004 |

### Computational Tools
| Tool/Package | Version | Purpose | Why Standard |
|--------------|---------|---------|--------------|
| NumPy/SciPy | 1.26+ | Exact diagonalization, FFT | Standard scientific computing |
| QuSpin | 0.3.7 | Many-body Hamiltonian construction | Handles Majorana algebra correctly |
| matplotlib | 3.8+ | SFF visualization | Standard plotting |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Exact diag | Lanczos | Lanczos for larger N but only gives extremal eigenvalues, need full spectrum for SFF |
| QuSpin | Custom Fock space code | QuSpin handles fermion signs automatically, less error-prone |
</methods_and_approaches>

<known_results>
## Known Results and Benchmarks

### Established Results
| Result | Value/Expression | Conditions | Source | Confidence |
|--------|-----------------|------------|--------|------------|
| Plateau height | K_plateau = L = 2^{N/2} | t >> t_H (Heisenberg time) | Cotler et al. 2017 | HIGH |
| Ramp slope | dK/dt = L / (2 pi beta) | t_dip < t < t_H, beta << 1 | Cotler et al. 2017 | HIGH |
| Dip time | t_dip ~ O(1) in J units | All T | Cotler et al. 2017 | MEDIUM |
| Heisenberg time | t_H = 2 pi L / (Delta E) | Definition | Standard | HIGH |

### Limiting Cases
| Limit | Expected Behavior | Expression | Source |
|-------|-------------------|------------|--------|
| t -> 0 | K(0) = Z(beta)^2 | Partition function squared | Definition |
| t -> infinity | K -> L (plateau) | Hilbert space dimension | RMT universality |
| beta -> 0 | Ramp linear with slope L/(2pi) | High-T RMT limit | Cotler et al. |
| N -> infinity | Dip deepens, ramp sharpens | Approaches RMT prediction | Large-N limit |

### Numerical Benchmarks
| Quantity | Published Value | Method Used | Parameters | Source |
|----------|----------------|-------------|------------|--------|
| SFF ramp onset | t ~ 0.5 J^{-1} | Exact diag, 500 disorder avg | N=32, q=4, beta=5 | Cotler et al. Fig. 3 |
| Plateau agreement with GUE | < 1% deviation | Exact diag | N=28, t > t_H | Gharibyan et al. |
</known_results>

<sources>
## Sources

### Primary (HIGH)
- Cotler et al. 2017 (1611.04650) - SFF definition, dip-ramp-plateau, numerical benchmarks
- Maldacena and Stanford 2016 (1604.07818) - SYK model analytics, large-N solution
- Mehta, Random Matrices (3rd ed.) - GUE predictions for spectral correlations

### Secondary (MEDIUM)
- Gharibyan et al. 2018 (1803.09742) - Numerical verification of RMT universality
- QuSpin documentation - Majorana fermion implementation

### Tertiary (LOW - needs validation)
- None - all findings verified against multiple sources
</sources>

<metadata>
## Metadata

**Research scope:**
- Physics subfield: Quantum chaos, SYK model, random matrix theory
- Methods explored: Exact diagonalization, replica method, RMT analytics
- Known results catalogued: SFF structure (dip/ramp/plateau), limiting cases, numerical benchmarks
- Pitfalls: Normalization conventions, disconnected contributions, finite-size effects

**Confidence breakdown:**
- Literature coverage: HIGH - well-studied problem with clear references
- Methods: HIGH - standard exact diag approach is well-established
- Known results: HIGH - multiple groups have verified numerically
- Pitfalls: HIGH - documented in literature, clear warning signs

**Research date:** 2025-06-15
**Valid until:** 2025-07-15 (30 days - established physics, stable field)
</metadata>

---

*Phase: 02-syk-spectral-form-factor*
*Research completed: 2025-06-15*
*Ready for planning: yes*
````

---

## Guidelines

**Depth guide:**

- **quick**: Summary, Key Findings (from literature_landscape), Recommended Methods, What Was NOT Found, Sources. Skip detailed analysis tables, notation reconciliation, and key derivations.
- **standard**: All sections at moderate depth. Tables with 3-5 entries each. Notation table if multiple papers referenced.
- **deep**: All sections with full analysis, citation verification, controversy mapping, complete notation reconciliation, comprehensive pitfall catalog.

**When to create:**

- Before planning phases in unfamiliar or deep physics domains
- When notation conventions across papers need reconciliation
- When known results and limiting cases must be catalogued before computation
- When "how do experts approach this" matters more than "which tool"
- For quick landscape scans, use `depth: quick` (alternatively, use `discovery.md` for lightweight pre-planning exploration)

**Structure:**

- Use XML tags for section markers (matches GPD templates)
- Core sections: summary, literature_landscape, methods_and_approaches, known_results, dont_rederive, common_pitfalls, key_derivations, open_questions, not_found, sources
- All sections required at standard/deep depth; quick depth skips detailed subsections

**Content quality:**

- Literature: Specific papers with authors, years, and key results - not just titles
- Notation: Explicit reconciliation table across papers
- Known results: Include numerical values with conditions and confidence
- Don't re-derive: Be explicit about what established results to use rather than re-derive
- Pitfalls: Include warning signs grounded in physics (dimensional analysis failure, wrong limits)
- Sources: Mark confidence levels honestly

**Integration with planning:**

- RESEARCH.md loaded as @context reference in PLAN.md
- Literature informs approach selection
- Known results provide verification benchmarks
- Notation table prevents convention mismatches
- Pitfalls inform verification criteria
- Key derivations can be referenced in task actions

**After creation:**

- File lives in phase directory: `.planning/phases/XX-name/{phase}-RESEARCH.md`
- Referenced during planning workflow
- plan-phase loads it automatically when present
