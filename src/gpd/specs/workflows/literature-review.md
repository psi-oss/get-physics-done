<purpose>
Conduct a systematic literature review for a physics research topic. Map the intellectual landscape: foundational works, methodological approaches, key results, controversies, and open questions. Produce LITERATURE-REVIEW.md consumed by planning and paper-writing workflows.

Also emit a machine-readable `GPD/literature/{slug}-CITATION-SOURCES.json` sidecar containing strict `CitationSource` objects keyed by stable `reference_id` values so paper-writing can reuse the discovered references without manual transcription.
include `bibtex_key` only when it is already known and verified. Extra keys are rejected by the downstream parser.

Called from gpd:literature-review command.

This workflow owns the staged init, scope fixing, deferred reference-artifact loading, and artifact gate. Do not frontload reference artifacts before the scope is fixed.

Keep all durable review artifacts rooted under `GPD/literature/` in the current workspace. In project-backed mode, that is the resolved project root's `GPD/literature/`; in standalone mode, it is `./GPD/literature/` in the invoking workspace.
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
load_literature_review_stage() {
  local stage_name="$1"
  shift
  local init_payload=""

  init_payload=$(gpd --raw init literature-review "$@" --stage "$stage_name" 2>/dev/null)
  if [ $? -ne 0 ] || [ -z "$init_payload" ]; then
    echo "ERROR: staged gpd initialization failed for stage '${stage_name}': ${init_payload}"
    return 1
  fi

  printf '%s' "$init_payload"
  return 0
}

BOOTSTRAP_INIT=$(load_literature_review_stage review_bootstrap "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $BOOTSTRAP_INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `commit_docs`, `state_exists`, `project_exists`, `project_contract`, `project_contract_gate`, `project_contract_load_info`, `project_contract_validation`, `contract_intake`, `effective_reference_intake`, `active_reference_context`, `topic`, `slug`.

- If `topic` is empty, do not invent or auto-derive it from project state, active references, or deferred artifacts.
- In project-backed mode, ask one focused question to lock the topic before broadening the search or loading scoped reference artifacts.
- In standalone mode, stop; centralized preflight should already have required explicit topic input.

Do not use `reference_artifact_files` or `reference_artifacts_content` yet. Keep them deferred until the review scope is fixed so reference artifacts cannot broaden the topic before the user has chosen it.

**Read mode settings:**

```bash
AUTONOMY=$(gpd --raw config get autonomy 2>/dev/null | gpd json get .value --default supervised 2>/dev/null || echo "supervised")
RESEARCH_MODE=$(gpd --raw config get research_mode 2>/dev/null | gpd json get .value --default balanced 2>/dev/null || echo "balanced")
```

**Mode-aware behavior:**
- `research_mode=explore`: Comprehensive review (30+ papers), include tangential fields, map full citation network, identify open questions.
- `research_mode=exploit`: Focused review (8-12 papers), direct relevance only, extract key results and methods.
- `research_mode=balanced` (default): Use the standard review depth for this workflow and keep the default anchor and contract coverage unless the topic needs broader or narrower review.
- `research_mode=adaptive`: Start with 15 papers, expand if citation network reveals critical gaps.
- `autonomy=supervised` (default): Pause after each review round for user feedback on scope and direction.
- `autonomy=balanced`: Complete the full review pipeline automatically. Pause only if the literature reveals scope ambiguity, contradictory evidence, or a change in recommendation.
- `autonomy=yolo`: Complete the review pipeline without pausing, but do NOT drop contract-critical anchors or user-mandated references.

- **If `state_exists` is true:** Extract `convention_lock` for notation context (helps identify which conventions are used in papers being reviewed). Extract active research topic, phase context, and any contract-critical references from `active_reference_context`.
- **If `state_exists` is false** (standalone usage): Proceed — the user will specify the topic directly.
- Treat `effective_reference_intake` as the machine-readable carry-forward ledger for anchors, prior outputs, baselines, user-mandated context, and unresolved gaps. Re-surface those items in the review even if the broader search expands beyond them.
- Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true. If the gate is blocked, keep the contract visible as context but do not promote it to approved review truth.

Project context helps focus the review on conventions and methods relevant to the current research.
</step>

<step name="scope_review">
Establish scope from command context:

The review topic must already be explicit or newly clarified; project existence alone does not satisfy subject selection.

- **Topic and focus**: Specific physics question or subfield
- **Depth**: Quick (~10 refs) | Standard (~30 refs) | Comprehensive (~50+ refs)
- **Time range**: All time | Last N years | Since specific result
- **Purpose**: Background | Method selection | Gap identification | Manuscript prep
- List the seed anchors already present in `project_contract`, `contract_intake`, `effective_reference_intake`, and `active_reference_context` before broadening the search

Define explicit include/exclude boundaries:

- Include: specific phenomena, methods, energy ranges, dimensions
- Exclude: tangential fields, historical reviews (unless depth=comprehensive)
- Record any contract-critical anchor that must be surfaced even if it falls outside the default search breadth
- Track contract-critical anchors in a compact registry with a `| Must Surface |` column.
- Set `Must Surface` to `yes` for any anchor that must be surfaced even if it falls outside the default search breadth; use roles like `benchmark`, `definition`, `method`, or `must_consider` to guide the fallback heuristic.
  </step>

<step name="load_scoped_reference_artifacts">
Once the scope is fixed, surface only the reference artifacts that remain relevant to the agreed topic.

```bash
SCOPE_LOCKED_INIT=$(load_literature_review_stage scope_locked "${topic:-$ARGUMENTS}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $SCOPE_LOCKED_INIT"
  exit 1
fi
```

- Parse the staged refresh for `reference_artifact_files`, `reference_artifacts_content`, `literature_review_files`, `research_map_reference_files`, `knowledge_doc_files`, `selected_protocol_bundle_ids`, `protocol_bundle_context`, and `active_references`.
- If `reference_artifact_files` is populated, read those files now and keep only the entries that support the confirmed scope.
- If `reference_artifacts_content` is available, use it now as supporting evidence for already-scoped anchors, baselines, prior outputs, and citation reuse.
- Only read or propagate the deferred reference-artifact context after the scope has been fixed.
- Do not use deferred reference artifacts to reopen the scope question.
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
The reviewer now owns the synthesis pass in fresh context. Use the stage-local scope, anchors, and reference context to write the review and sidecar, rather than synthesizing it inline in the orchestrator.

```bash
REVIEWER_MODEL=$(gpd resolve-model gpd-literature-reviewer)
```

Build the reviewer prompt from the scoped evidence:

```markdown
<objective>
Write a systematic literature review for {topic} and produce the matching review document and citation-sidecar outputs.
</objective>

<scope_summary>
Topic: {topic}
Slug: {slug}
Depth: {depth}
Seed anchors: {seed_anchors}
Confirmed boundaries: {scope_boundaries}
Contract-critical anchors: {contract_critical_anchors}
</scope_summary>

<context>
Project contract: {project_contract}
Contract intake: {contract_intake}
Effective reference intake: {effective_reference_intake}
Active references: {active_reference_context}
Scoped reference artifacts: {reference_artifacts_content}
</context>

<output>
Write `GPD/literature/{slug}-REVIEW.md` and `GPD/literature/{slug}-CITATION-SOURCES.json`.
</output>

<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - GPD/literature/{slug}-REVIEW.md
    - GPD/literature/{slug}-CITATION-SOURCES.json
expected_artifacts:
  - GPD/literature/{slug}-REVIEW.md
  - GPD/literature/{slug}-CITATION-SOURCES.json
shared_state_policy: return_only
</spawn_contract>
```

```
REVIEW_RETURN=$(
task(
  subagent_type="gpd-literature-reviewer",
  model="{reviewer_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-literature-reviewer.md for your role and instructions.\\n\\n" + review_prompt
)
)
```

**If the reviewer agent fails to spawn or returns an error:** Report the failure and stop. Offer: 1) Retry with the same scope, 2) Execute the review in the main context, 3) Abort.

**If the reviewer reports `gpd_return.status: completed`:**
- Verify `GPD/literature/{slug}-REVIEW.md` and `GPD/literature/{slug}-CITATION-SOURCES.json` are readable
- Verify both files are named in `gpd_return.files_written`
- Do not trust the runtime handoff status by itself. Require the files on disk and the file list to agree before advancing.
- Treat the handoff as incomplete if either file is missing, unreadable, or unnamed

**If the reviewer reports `gpd_return.status: checkpoint`:**
- Present the checkpoint to the user
- Collect the response
- Spawn a fresh continuation handoff with the updated scope and checkpoint response
- Re-run the same `gpd_return.files_written` and on-disk artifact gate before advancing

**If the reviewer reports `gpd_return.status: blocked` or `failed`:**
- Surface the blocker
- Offer: 1) Add context, 2) Narrow scope, 3) Abort

</step>

<step name="verify_citations">
**Phase 8: Citation Verification**

Spawn the bibliographer agent to verify all citations collected during the review. The bibliographer has the hallucination detection protocol, INSPIRE/ADS/arXiv search capability, and BibTeX management expertise needed for citation verification.

```bash
REVIEW_HANDOFF_INIT=$(load_literature_review_stage review_handoff "${topic:-$ARGUMENTS}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $REVIEW_HANDOFF_INIT"
  exit 1
fi
```

Parse the staged refresh for `citation_source_files`, `derived_citation_sources`, `selected_protocol_bundle_ids`, `protocol_bundle_context`, `active_references`, `derived_manuscript_reference_status`, and `derived_manuscript_proof_review_status` before spawning the bibliographer or accepting a completed review handoff.

Resolve bibliographer model:

```bash
BIBLIO_MODEL=$(gpd resolve-model gpd-bibliographer)
```
@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

```
task(
  subagent_type="gpd-bibliographer",
  model="{biblio_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-bibliographer.md for your role and instructions.\\n\\nVerify all citations in the literature review.\\n\\nMode: Audit bibliography\\n\\nReview file: GPD/literature/{slug}-REVIEW.md\\n\\nFor every reference listed in the Full Reference List and cited in the body:\\n1. Run the hallucination detection protocol (Steps 1-5) against INSPIRE, ADS, arXiv\\n2. Cross-check metadata (title, authors, year, journal, identifiers)\\n3. Flag any hallucinated or inaccurate citations\\n4. Correct metadata errors where possible\\n\\nWrite results to GPD/literature/{slug}-CITATION-AUDIT.md\\n\\nReturn a typed `gpd_return` envelope. Use `status: completed` when the bibliography task finished, even if the human-readable heading is `## CITATION ISSUES FOUND`; use `status: checkpoint` only when researcher input is required to continue. A completed return must list `GPD/literature/{slug}-CITATION-AUDIT.md` in `gpd_return.files_written`."
)
```

<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - GPD/literature/{slug}-CITATION-AUDIT.md
expected_artifacts:
  - GPD/literature/{slug}-CITATION-AUDIT.md
shared_state_policy: return_only
</spawn_contract>

**If the bibliographer agent fails to spawn or returns an error:** Treat the review as blocked until citation audit completes. Offer: 1) Retry citation audit, 2) Abort, 3) Return to the user with the review incomplete.

**If the bibliographer completed with issues recorded in the audit report:**

- Read the audit report
- Fix or remove hallucinated citations from the review document
- Update corrected metadata in the reference list
- Refresh `GPD/literature/{slug}-CITATION-SOURCES.json` so the sidecar stays aligned with the corrected review and reference keys.
- Re-run or refresh `GPD/literature/{slug}-CITATION-AUDIT.md` if citation fixes changed the review or sidecar.
- Note unresolvable citations in the return summary

**If the bibliographer reports `gpd_return.status: completed`:**

- Verify `GPD/literature/{slug}-CITATION-AUDIT.md` is readable, current for the review/sidecar pair, and named in `gpd_return.files_written`.
- Proceed only after the fresh citation-audit gate passes. A `BIBLIOGRAPHY UPDATED` heading or success prose alone is not enough.
  </step>

<step name="return_results">
Return to orchestrator through the typed child-return contract. Route on `gpd_return.status` and the artifact gate; the `## REVIEW COMPLETE` and `## CHECKPOINT REACHED` headings are presentation only.

```bash
COMPLETION_GATE_INIT=$(load_literature_review_stage completion_gate "${topic:-$ARGUMENTS}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $COMPLETION_GATE_INIT"
  exit 1
fi
```

Parse the completion refresh for `topic`, `slug`, and any final presentation/runtime fields before presenting results.

On completion:

- Verify `GPD/literature/{slug}-REVIEW.md` exists on disk
- Verify `GPD/literature/{slug}-CITATION-SOURCES.json` exists on disk and remains aligned with the review's Full Reference List
- Verify `GPD/literature/{slug}-CITATION-AUDIT.md` is fresh for the current review and sidecar
- Return `gpd_return.status: completed` only when the review, citation sidecar, and citation audit are named in `gpd_return.files_written` and present/readable on disk
- Include `papers_reviewed`, `field_assessment`, and citation verification details as needed
- If any required artifact is missing, malformed, or stale, return `gpd_return.status: blocked` or `failed` instead of `completed`

On checkpoint:

- Return `gpd_return.status: checkpoint`
- Include the decision question, context, options, and partial progress
- Record the user's answer as `checkpoint_response` for the fresh continuation handoff.
- Do not trust the runtime handoff status by itself.
- Stop and let the orchestrator present the checkpoint to the user, then spawn a fresh continuation run after the response

If the review is incomplete or blocked, use `gpd_return.status: blocked` or `failed` and list the missing artifact or unresolved scope issue explicitly.

</step>

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
