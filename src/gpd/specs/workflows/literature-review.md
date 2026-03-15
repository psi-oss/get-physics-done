<purpose>
Conduct a systematic literature review for a physics research topic. Map the intellectual landscape: foundational works, methodological approaches, key results, controversies, and open questions. Produce LITERATURE-REVIEW.md consumed by planning and paper-writing workflows.

Called from /gpd:literature-review command.
</purpose>

<core_principle>
A physics literature review is not a bibliography. It is a structured map of who computed what, using which methods, with what assumptions, getting what results, and where they agree or disagree. The goal is to understand the state of a field well enough to identify what is known, what is open, and where new work can contribute.
</core_principle>

<source_hierarchy>
**MANDATORY: Authoritative sources BEFORE general search**

1. **Textbooks and monographs** -- For established results, standard methods, and field context

   - Use specific textbooks by subfield (Peskin & Schroeder for QFT, Sakurai for QM, Jackson for E&M, Landau & Lifshitz series, etc.)
   - These define conventions and standard results

2. **Review articles** -- For field overviews and method surveys

   - Rev. Mod. Phys., Physics Reports, Annual Reviews of Physics
   - Recent reviews (last 5 years) for current state-of-the-art

3. **Seminal papers** -- Original derivations of key results

   - Identify the papers everyone in the field cites
   - Read the actual papers, not just the citations

4. **Recent arXiv preprints** -- For cutting-edge developments

   - arXiv categories: hep-th, hep-ph, hep-lat, cond-mat._, quant-ph, gr-qc, astro-ph._, nucl-th, etc.
   - Sort by relevance and citation count

5. **Conference proceedings** -- For very recent results and community direction

   - Lattice, ICHEP, APS meetings, etc.

6. **web_search** -- Last resort for community discussions, code repos, numerical benchmarks

</source_hierarchy>

<process>

<step name="load_context" priority="first">
**Load project context (if available):**

```bash
INIT=$(gpd init progress --include state,config)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `commit_docs`, `state_exists`, `project_exists`, `project_contract`, `contract_intake`, `effective_reference_intake`, `active_reference_context`, `reference_artifact_files`, `reference_artifacts_content`.

**Read mode settings:**

```bash
AUTONOMY=$(gpd --raw config get autonomy 2>/dev/null | gpd json get .value --default balanced 2>/dev/null || echo "balanced")
RESEARCH_MODE=$(gpd --raw config get research_mode 2>/dev/null | gpd json get .value --default balanced 2>/dev/null || echo "balanced")
```

**Mode-aware behavior:**
- `research_mode=explore`: Comprehensive review (30+ papers), include tangential fields, map full citation network, identify open questions.
- `research_mode=exploit`: Focused review (8-12 papers), direct relevance only, extract key results and methods.
- `research_mode=adaptive`: Start with 15 papers, expand if citation network reveals critical gaps.
- `autonomy=supervised`: Pause after each review round for user feedback on scope and direction.
- `autonomy=balanced` (default): Complete the full review pipeline automatically. Pause only if the literature reveals scope ambiguity, contradictory evidence, or a change in recommendation.
- `autonomy=yolo`: Complete the review pipeline without pausing, but do NOT drop contract-critical anchors or user-mandated references.

- **If `state_exists` is true:** Extract `convention_lock` for notation context (helps identify which conventions are used in papers being reviewed). Extract active research topic, phase context, and any contract-critical references from `active_reference_context`.
- **If `state_exists` is false** (standalone usage): Proceed — the user will specify the topic directly.
- Treat `effective_reference_intake` as the machine-readable carry-forward ledger for anchors, prior outputs, baselines, user-mandated context, and unresolved gaps. Re-surface those items in the review even if the broader search expands beyond them.
- Use `reference_artifacts_content` as supporting evidence when existing literature/research-map artifacts already pin down benchmark values, prior outputs, or anchor wording that should remain stable.

Project context helps focus the review on conventions and methods relevant to the current research.
</step>

<step name="scope_review">
Establish scope from command context:

- **Topic and focus**: Specific physics question or subfield
- **Depth**: Quick (~10 refs) | Standard (~30 refs) | Comprehensive (~50+ refs)
- **Time range**: All time | Last N years | Since specific result
- **Purpose**: Background | Method selection | Gap identification | Manuscript prep
- List the seed anchors already present in `project_contract`, `contract_intake`, `effective_reference_intake`, and `active_reference_context` before broadening the search

Define explicit include/exclude boundaries:

- Include: specific phenomena, methods, energy ranges, dimensions
- Exclude: tangential fields, historical reviews (unless depth=comprehensive)
- Record any contract-critical anchor that must be surfaced even if it falls outside the default search breadth
  </step>

<step name="identify_foundations">
**Phase 1: Foundational Works**

Every subfield has seminal papers that defined the field. Identify them:

1. Search for review articles first (they cite the seminal works):

   ```
   web_search: "[topic] review" site:arxiv.org
   web_search: "[topic]" site:journals.aps.org/rmp
   ```

2. From review articles, extract:

   - The 5-10 most-cited papers
   - The textbook treatments
   - The original derivation of key results

3. For each foundational work, record:

   - Full citation (authors, title, journal, year)
   - Stable `anchor_id` and concrete `locator` if the work is contract-critical or likely to be reused downstream
   - Key contribution (what they showed/computed/proved)
   - Method used
   - Conventions (units, metric signature, normalization)
   - Where the result is used downstream
   - Whether it should be treated as a contract-critical anchor for later planning or verification

4. Build a citation timeline showing how the field developed.
   </step>

<step name="map_methods">
**Phase 2: Methodological Landscape**

Catalog all methods that have been applied to this problem:

For each method:

| Field              | Detail                                                              |
| ------------------ | ------------------------------------------------------------------- |
| Method name        | Formal name and common abbreviations                                |
| Type               | Analytical / Numerical / Mixed                                      |
| Key idea           | One-sentence description of the approach                            |
| Regime of validity | Where it works (weak coupling, high T, large N, etc.)               |
| Limitations        | Where it fails (strong coupling, low dimension, sign problem, etc.) |
| Accuracy           | Typical precision achievable                                        |
| Computational cost | Scaling with system size, time, memory                              |
| Key references     | Original paper + best application to this system                    |
| Available codes    | Open-source implementations, if any                                 |

Organize methods by approach type:

- **Exact methods**: Bethe ansatz, integrability, conformal bootstrap, etc.
- **Perturbative**: Weak coupling, 1/N, epsilon expansion, etc.
- **Variational**: Trial wavefunctions, DMRG, tensor networks, etc.
- **Monte Carlo**: DQMC, PIMC, VMC, AFQMC, etc.
- **Mean-field and beyond**: Hartree-Fock, RPA, GW, DMFT, etc.
- **Effective theories**: EFT, renormalization group, etc.

Note which methods agree and where they disagree -- this reveals the interesting physics.
</step>

<step name="catalog_results">
**Phase 3: Key Results Catalog**

For each significant result in the literature:

| Field       | Detail                                                                 |
| ----------- | ---------------------------------------------------------------------- |
| Quantity    | What was computed (energy, correlation function, phase boundary, etc.) |
| Value       | Numerical result or analytical expression                              |
| Method      | How it was obtained                                                    |
| Uncertainty | Error bars, systematic uncertainties, convergence status               |
| Conventions | Units, normalization, sign conventions used                            |
| Regime      | Parameter values, approximations in effect                             |
| Reference   | Full citation                                                          |
| Agreement   | How it compares with other determinations                              |

Tabulate results for the SAME quantity across different papers/methods to expose:

- Agreement (convergence of independent methods)
- Disagreement (controversial values)
- Trends (how results evolved as methods improved)
- Which values are decisive benchmarks versus optional background comparisons
  </step>

<step name="trace_citations">
**Phase 4: Citation Network Analysis**

Map intellectual lineages:

1. **Method lineages**: paper_A -> paper_B -> paper_C (each improving on the previous)
2. **Competing approaches**: lineage_X vs lineage_Y (different methods for same problem)
3. **Reconciliation**: papers that compared or unified different approaches
4. **Branching points**: where the field split into sub-problems

This reveals:

- Which methods are still actively developed (recent citations)
- Which are considered superseded (cited only for historical context)
- Which groups are leading each approach
- Where cross-pollination between approaches has been fruitful
  </step>

<step name="find_controversies">
**Phase 5: Controversies and Disagreements**

Actively search for disagreements in the literature:

1. **Numerical discrepancies**: Different groups get different values for the same quantity

   - How significant is the disagreement? (In sigma)
   - Is the discrepancy resolution-dependent? (Finite-size, continuum limit)
   - Has anyone explained the discrepancy?

2. **Methodological disagreements**: Different methods give inconsistent results

   - Which method is more reliable in this regime?
   - Are the approximations comparable?
   - Could both be right in different limits?

3. **Conceptual disagreements**: Different physical interpretations of the same result

   - Is this a genuine physics disagreement or a convention difference?
   - What experiment or calculation could distinguish between interpretations?

4. **Convention conflicts**: Different papers use different conventions
   - Catalog convention choices across the major references
   - Note where convention mismatches could cause apparent disagreements
     </step>

<step name="identify_gaps">
**Phase 6: Open Questions**

Systematically identify what has NOT been done:

1. **Uncomputed quantities**: Observables mentioned in the literature but never calculated
2. **Unexplored regimes**: Parameter ranges where no reliable method works
3. **Unresolved puzzles**: Anomalous results with no accepted explanation
4. **Missing connections**: Two related results that nobody has connected
5. **Unverified predictions**: Theoretical predictions awaiting experimental confirmation
6. **Long-standing conjectures**: Claims without proof, supported only by numerical evidence

For each gap:

- Why hasn't it been addressed? (Too hard? Not important enough? Technical obstacle?)
- What would it take to address it? (Better methods? More computing power? New data?)
- What would we learn? (Is it worth the effort?)
- Whether a missing anchor or missing benchmark is currently blocking downstream planning
  </step>

<step name="assess_frontier">
**Phase 7: Current Frontier**

Map the state-of-the-art:

1. **Most recent results** (last 1-2 years)

   - What has been computed or measured recently?
   - How does it change the picture from the review articles?

2. **Active groups**

   - Which groups are producing results in this area?
   - What methods are they using?
   - What are their current projects? (Check recent arXiv submissions)

3. **Emerging methods**

   - New theoretical or computational approaches being applied
   - Machine learning / AI applications to this problem
   - New experimental techniques

4. **Community direction**
   - What was discussed at recent conferences?
   - Where is the field heading?
     </step>

<step name="create_review_document">
Ensure the output directory exists:

```bash
mkdir -p .gpd/literature
```

Write `.gpd/literature/{slug}-REVIEW.md`:

```markdown
---
topic: { topic }
date: { YYYY-MM-DD }
depth: { quick/standard/comprehensive }
paper_count: { N }
status: completed | checkpoint
---

# Literature Review: {Topic}

## Executive Summary

{3-5 key takeaways from the review. What should a physicist entering this area know first?}

## Foundational Works

| #   | Reference                | Year   | Key Contribution   |
| --- | ------------------------ | ------ | ------------------ |
| 1   | {Author et al., Journal} | {year} | {what they showed} |

{Brief narrative connecting these works and showing how the field developed.}

## Methodological Landscape

### Exact Methods

{Description of applicable exact methods, regimes, limitations}

### Perturbative Methods

{Description of perturbative approaches, convergence properties}

### Numerical Methods

{Description of computational approaches, costs, accuracies}

### Effective Theories

{Description of effective theory approaches, energy scales}

### Method Comparison

| Method   | Regime           | Accuracy            | Cost      | Key Reference |
| -------- | ---------------- | ------------------- | --------- | ------------- |
| {method} | {where it works} | {typical precision} | {scaling} | {citation}    |

## Key Results

| Quantity     | Value             | Method   | Reference  | Status                |
| ------------ | ----------------- | -------- | ---------- | --------------------- |
| {observable} | {value +/- error} | {method} | {citation} | {confirmed/contested} |

## Citation Network

{Intellectual lineages showing how ideas evolved. Key branching and merging points.}

## Controversies and Disagreements

### {Controversy 1}

- **The disagreement:** {what's contested}
- **Side A:** {position, evidence, key reference}
- **Side B:** {position, evidence, key reference}
- **Current status:** {resolved/active/dormant}

## Open Questions

1. **{Question}** -- {Why it matters, why it's hard, what it would take}

## Current Frontier

{State-of-the-art: most recent results, active groups, emerging methods}

## Active Anchor Registry

| Anchor ID | Anchor | Type | Source / Locator | Why It Matters | Contract Subject IDs | Required Action | Carry Forward To |
| --------- | ------ | ---- | ---------------- | -------------- | -------------------- | --------------- | ---------------- |
| {stable-anchor-id} | {reference or artifact} | {benchmark/method/background/prior artifact} | {citation, dataset id, or path} | {claim, observable, deliverable, or convention constrained} | {claim-id, deliverable-id, or blank} | {read/use/compare/cite} | {planning/execution/verification/writing} |

`Carry Forward To` is workflow stage scope only. If exact contract subject IDs are known, store them in `Contract Subject IDs` instead of collapsing them into stage labels.

## Convention Catalog

| Convention     | Choice A  | Choice B  | Used By        |
| -------------- | --------- | --------- | -------------- |
| {e.g., metric} | (-,+,+,+) | (+,-,-,-) | {which papers} |

## Recommended Reading Path

For someone entering this area, read in this order:

1. {Textbook chapter for background}
2. {Review article for overview}
3. {Seminal paper for key result}
4. {Recent paper for current state}

## Full Reference List

{Formatted citations, organized by topic/method}
```

</step>

<step name="verify_citations">
**Phase 8: Citation Verification**

Spawn the bibliographer agent to verify all citations collected during the review. The bibliographer has the hallucination detection protocol, INSPIRE/ADS/arXiv search capability, and BibTeX management expertise needed for citation verification.

Resolve bibliographer model:

```bash
BIBLIO_MODEL=$(gpd resolve-model gpd-bibliographer)
```
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  subagent_type="gpd-bibliographer",
  model="{biblio_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-bibliographer.md for your role and instructions.

Verify all citations in the literature review.

Mode: Audit bibliography

Review file: .gpd/literature/{slug}-REVIEW.md

For every reference listed in the Full Reference List and cited in the body:
1. Run the hallucination detection protocol (Steps 1-5) against INSPIRE, ADS, arXiv
2. Cross-check metadata (title, authors, year, journal, identifiers)
3. Flag any hallucinated or inaccurate citations
4. Correct metadata errors where possible

Write results to .gpd/literature/{slug}-CITATION-AUDIT.md

Return BIBLIOGRAPHY UPDATED or CITATION ISSUES FOUND."
)
```

**If the bibliographer agent fails to spawn or returns an error:** Proceed without citation audit. Note in the review summary that citations are unverified. The user should manually check key references against INSPIRE-HEP/ADS.

**If CITATION ISSUES FOUND:**

- Read the audit report
- Fix or remove hallucinated citations from the review document
- Update corrected metadata in the reference list
- Note unresolvable citations in the return summary

**If BIBLIOGRAPHY UPDATED:**

- All citations verified, proceed to return results
  </step>

<step name="return_results">
Return to orchestrator with:
- Summary of findings (5-10 lines)
- Paper count and coverage assessment
- Key takeaways
- Identified gaps
- Report path
- Citation verification status

Format:

```markdown
## REVIEW COMPLETE

**Topic:** {topic}
**Papers reviewed:** {N}
**Report:** .gpd/literature/{slug}-REVIEW.md

**Key takeaways:**

1. {takeaway}
2. {takeaway}
3. {takeaway}

**Open questions identified:** {N}
**Active controversies:** {N}
**Recommended starting point:** {key reference}
**Citation verification:** {all verified | N issues found -- see .gpd/literature/{slug}-CITATION-AUDIT.md}
```

If the review is incomplete (too broad, need user guidance):

```markdown
## CHECKPOINT REACHED

**Type:** decision
**Progress:** Reviewed {N} papers, identified {M} subtopics

### Checkpoint Details

**Decision needed:** The topic branches into {N} distinct subtopics. Which should I focus on?

**Options:**

- **A:** {subtopic A} -- {why relevant}
- **B:** {subtopic B} -- {why relevant}
- **C:** All of them (comprehensive, will take longer)
```

</step>

**Commit the report:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files "${OUTPUT_PATH}" 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs: literature review — ${topic_slug:-standalone}" \
  --files "${OUTPUT_PATH}"
```

Where `${OUTPUT_PATH}` is the path where LITERATURE-REVIEW.md was written.

</process>

<success_criteria>

- [ ] Source hierarchy followed (textbooks -> reviews -> papers -> arXiv -> web)
- [ ] Foundational works identified with key contributions
- [ ] Methods cataloged with regimes, limitations, and key references
- [ ] Results tabulated with uncertainties and conventions
- [ ] Citation network traced showing intellectual development
- [ ] Controversies and disagreements documented
- [ ] Open questions identified with feasibility assessment
- [ ] Current frontier mapped (recent results, active groups, emerging methods)
- [ ] Conventions cataloged across references
- [ ] LITERATURE-REVIEW.md created with all sections
- [ ] Recommended reading path provided
- [ ] Citations verified via gpd-bibliographer (no hallucinated references)

</success_criteria>
