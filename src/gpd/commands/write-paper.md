---
name: gpd:write-paper
description: Structure and write a physics paper from research results
argument-hint: "[paper title or topic] [--from-phases 1,2,3]"
context_mode: project-required
review-contract:
  review_mode: publication
  schema_version: 1
  required_outputs:
    - paper/main.tex
    - ".gpd/REFEREE-REPORT.md"
    - ".gpd/REFEREE-REPORT.tex"
  required_evidence:
    - existing manuscript
    - phase summaries or milestone digest
    - verification reports
    - bibliography audit
    - artifact manifest
    - reproducibility manifest
  blocking_conditions:
    - missing project state
    - missing roadmap
    - missing conventions
    - missing manuscript
    - no research artifacts
    - degraded review integrity
  preflight_checks:
    - project_state
    - roadmap
    - conventions
    - research_artifacts
    - manuscript
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
  - task
  - web_search
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Structure and write a physics paper from completed research results. Handles the full pipeline from research digest through polished draft: paper-readiness audit, scope and outline, figure generation, wave-parallelized section drafting, notation audit, bibliography verification, staged pre-submission peer review, and revision handling.

**Orchestrator role:** Establish paper scope and structure, spawn gpd-paper-writer agents for section drafting (wave-parallelized), gpd-bibliographer for citation verification, run the staged peer-review panel (`gpd-review-reader`, `gpd-review-literature`, `gpd-review-math`, `gpd-review-physics`, `gpd-review-significance`, then `gpd-referee` as final adjudicator), coordinate revisions, ensure internal consistency.

**Why subagent:** Paper writing requires holding the full research context while drafting coherent prose. Each section needs access to derivations, numerical results, and literature context. Fresh 200k context per section ensures quality. Main context coordinates the overall structure.

Writing a physics paper is not writing a report. A paper has a narrative arc: it poses a question, develops the tools to answer it, presents the answer, and explains why the answer matters. Every equation must earn its place. Every figure must make a point. Every paragraph must advance the argument.

Routes to the write-paper workflow which handles all logic including:

1. Research digest loading (from milestone completion) with digest-to-paper section mapping
2. Paper-readiness audit (SUMMARY completeness, convention consistency, numerical stability, figure readiness, citation readiness) with gate decision
3. Scope establishment, artifact cataloging, and outline creation
4. Figure generation before section drafting
5. Wave-parallelized section drafting (Wave 1: Results+Methods, Wave 2: Introduction, Wave 3: Discussion, Wave 4: Conclusions, Wave 5: Abstract, Wave 6: Appendices)
6. LaTeX compilation checks after each wave (if pdflatex available)
7. Consistency check, notation audit, and RESULT PENDING placeholder resolution
8. Bibliography verification via gpd-bibliographer
9. Pre-submission staged peer review via specialist panel plus final gpd-referee adjudication
10. Bounded revision loop (max 3 iterations) for addressing referee issues
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/write-paper.md
@{GPD_INSTALL_DIR}/templates/paper/paper-config-schema.md
</execution_context>

<context>
Paper topic: $ARGUMENTS

Check for existing drafts:

```bash
ls paper/ manuscript/ draft/ 2>/dev/null
ls .gpd/paper/*.md 2>/dev/null
find . -name "*.tex" -maxdepth 2 2>/dev/null | head -10
```

Load research context:

```bash
cat .gpd/ROADMAP.md 2>/dev/null
ls .gpd/phases/*/SUMMARY.md .gpd/phases/*/*-SUMMARY.md 2>/dev/null
cat .gpd/research-map/FORMALISM.md 2>/dev/null
```

</context>

<process>
**Follow the write-paper workflow** from `@{GPD_INSTALL_DIR}/workflows/write-paper.md`.

The workflow handles all logic including:

1. **Init** — Load project context via `gpd init phase-op`, check pdflatex availability, verify conventions
2. **Load research digest** — Check for RESEARCH-DIGEST.md from milestone completion; map digest sections to paper structure; fall back to raw phase data if no digest found. Supports `--from-phases` flag to select specific phases.
3. **Establish scope** — Target journal, paper type, key result (ONE sentence), audience, available artifacts
4. **Catalog artifacts** — Gather derivations, numerical results, figures, literature, verification results from phases
5. **Paper-readiness audit** — 5 checks (SUMMARY completeness, convention consistency, numerical stability, figure readiness, citation readiness) with gate decision (0 critical gaps to proceed, or user approval)
6. **Create outline** — Detailed per-section outline (purpose, key content, equations, figures, citations, dependencies) adapted to journal format. Present for approval.
7. **Generate files** — Create `paper/PAPER-CONFIG.json` using `@{GPD_INSTALL_DIR}/templates/paper/paper-config-schema.md`, then materialize the canonical manuscript scaffold with `gpd paper-build` (emits `paper/main.tex`, bibliography artifacts, and `paper/ARTIFACT-MANIFEST.json`)
8. **Generate figures** — Generate matplotlib scripts from phase data, execute to paper/figures/, update FIGURE_TRACKER.md
9. **Draft sections** — Wave-parallelized spawning of gpd-paper-writer agents:
   - Wave 1: Results + Methods (no dependency)
   - Wave 2: Introduction (depends on Results)
   - Wave 3: Discussion (depends on Results + Methods)
   - Wave 4: Conclusions
   - Wave 5: Abstract (write LAST)
   - Wave 6: Appendices
   - LaTeX compilation check after each wave (if pdflatex available)
   - Per-wave checkpointing: skip waves whose .tex outputs already exist
10. **Consistency check** — Notation audit, cross-reference audit, placeholder resolution (RESULT PENDING markers), physics consistency, narrative flow
11. **Notation audit** — Cross-reference all symbols against NOTATION_GLOSSARY.md (if exists)
12. **Verify references** — Spawn gpd-bibliographer to verify all citations against INSPIRE/ADS/arXiv, detect orphans, check formatting
13. **Pre-submission review** — Run the same staged peer-review panel used by `/gpd:peer-review`
14. **Final review** — Abstract standalone check, equation proofread, figure references, word/page count
15. **Paper revision** — Bounded revision loop (max 3 iterations) for addressing referee issues; spawns paper-writer agents for targeted section fixes

For a standalone rerun of the referee stage after the manuscript already exists, use `/gpd:peer-review`.
</process>

<success_criteria>
- [ ] Project context loaded and research artifacts cataloged
- [ ] Paper-readiness audit passed (0 critical gaps or user approved)
- [ ] Paper scope established (journal, type, key result, audience)
- [ ] Detailed outline created and approved
- [ ] All sections drafted by gpd-paper-writer agents (Results first, Abstract last)
- [ ] Every equation numbered, defined, and contextualized
- [ ] Every figure captioned and discussed in text
- [ ] Citations verified via gpd-bibliographer (no hallucinated references)
- [ ] Pre-submission staged peer review completed with final gpd-referee adjudication
- [ ] Internal consistency verified (notation, cross-references, conventions)
- [ ] Paper directory created with buildable LaTeX structure
</success_criteria>
