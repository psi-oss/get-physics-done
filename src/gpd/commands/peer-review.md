---
name: gpd:peer-review
description: Conduct a skeptical peer review of a manuscript and supporting research artifacts
argument-hint: "[paper directory or manuscript path]"
requires:
  files: ["paper/*.tex"]
allowed-tools:
  - file_read
  - file_write
  - shell
  - find_files
  - search_files
  - task
  - ask_user
  - web_search
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Conduct a standalone skeptical peer review of a completed manuscript and its supporting research artifacts.

This command promotes manuscript review to a first-class workflow instead of hiding it inside `write-paper`. It wraps the `gpd-referee` agent with explicit preflight validation, artifact discovery, and review summary handling.

**Orchestrator role:** Locate the manuscript, validate review prerequisites, gather supporting artifacts, spawn gpd-referee, and present actionable outcomes based on the recommendation.

Peer review is not the same as verification. Verification asks whether a derivation or computation checks out. Peer review asks whether the claimed contribution is correct, complete, clear, well-situated in the literature, reproducible, and publishable.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/peer-review.md
</execution_context>

<context>
Review target: $ARGUMENTS (optional paper directory or manuscript path)

@.gpd/STATE.md
@.gpd/ROADMAP.md

Check for candidate manuscripts:

```bash
ls paper/main.tex manuscript/main.tex draft/main.tex 2>/dev/null
find . -maxdepth 3 \( -name "main.tex" -o -name "*.tex" \) 2>/dev/null | head -20
```

</context>

<process>
**Follow the peer-review workflow** from `@{GPD_INSTALL_DIR}/workflows/peer-review.md`.

The workflow handles all logic including:

1. **Init** — Load project context, detect manuscript target, and resolve scope
2. **Preflight** — Run review preflight validation for the peer-review command
3. **Artifact discovery** — Load manuscript files, bibliography, verification reports, and review-grade paper artifacts
4. **Review execution** — Spawn gpd-referee for an initial review or revision review, depending on existing referee/author response files
5. **Report handling** — Read the generated referee report and classify the recommendation
6. **Next-step routing** — Route to respond-to-referees, manuscript edits, or arxiv-submission depending on the outcome
</process>

<success_criteria>
- [ ] Manuscript target located or explicitly resolved from arguments
- [ ] Review preflight passed or blocking issues were surfaced clearly
- [ ] gpd-referee spawned with manuscript and supporting artifacts
- [ ] `.gpd/REFEREE-REPORT.md` or `.gpd/REFEREE-REPORT-R{N}.md` created
- [ ] `.gpd/CONSISTENCY-REPORT.md` created when supported by the referee workflow
- [ ] Recommendation, issue counts, and actionable next steps presented
- [ ] Revision rounds respected if prior author responses already exist
</success_criteria>
