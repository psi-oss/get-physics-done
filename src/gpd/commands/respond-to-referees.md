---
name: gpd:respond-to-referees
description: Structure a point-by-point response to referee reports and update the manuscript
argument-hint: "[path to referee report or paste inline]"
context_mode: project-required
requires:
  files: ["paper/*.tex", "manuscript/*.tex", "draft/*.tex"]
review-contract:
  review_mode: publication
  schema_version: 1
  required_outputs:
    - ".gpd/paper/REFEREE_RESPONSE.md"
    - ".gpd/AUTHOR-RESPONSE.md"
  required_evidence:
    - existing manuscript
    - structured referee issues
    - peer-review review ledger when available
    - peer-review decision artifacts when available
    - revision verification evidence
  blocking_conditions:
    - missing project state
    - missing manuscript
    - missing conventions
    - degraded review integrity
  preflight_checks:
    - project_state
    - manuscript
    - conventions
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
  - task
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Structure a point-by-point response to referee reports and revise the manuscript accordingly.

Handles the full revision pipeline: parsing referee comments, categorizing by priority and type, drafting responses, spawning revision agents for manuscript changes, tracking new calculations needed, verifying consistency after revisions, and producing both the internal author-response tracker and the journal-facing response letter.

**Orchestrator role:** Parse and triage referee comments, coordinate revision agents, track new calculation requests, and keep the internal and journal-facing response artifacts synchronized.

**Why subagent:** Each section revision needs the full context of the referee comment, current section text, and planned response. Fresh 200k context per section revision ensures quality. Main context coordinates the overall response structure.

Responding to referees is collaborative improvement: every comment, even an incorrect one, reveals something about how the paper communicates its results. The goal is a stronger paper.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/respond-to-referees.md
</execution_context>

<context>
Referee report source: $ARGUMENTS (file path or "paste" for inline input)

@.gpd/STATE.md
@.gpd/AUTHOR-RESPONSE.md
@.gpd/paper/REFEREE_RESPONSE.md
@.gpd/review/REVIEW-LEDGER.json
@.gpd/review/REFEREE-DECISION.json

Check for existing paper and prior response files:

```bash
ls paper/main.tex manuscript/main.tex draft/main.tex 2>/dev/null
ls .gpd/AUTHOR-RESPONSE*.md 2>/dev/null
ls .gpd/paper/REFEREE_RESPONSE*.md 2>/dev/null
ls .gpd/review/REVIEW-LEDGER*.json .gpd/review/REFEREE-DECISION*.json 2>/dev/null
```

</context>

<process>
Execute the respond-to-referees workflow from @{GPD_INSTALL_DIR}/workflows/respond-to-referees.md end-to-end.
If staged peer-review artifacts exist under `.gpd/review/`, absorb them as structured decision context while keeping `REFEREE-REPORT*.md` as the canonical issue-ID source.
Preserve all validation gates (report parsing, triage confirmation, compilation check, consistency verification, bounded revision loop).
</process>

<success_criteria>
- [ ] Referee reports parsed and all comments categorized and prioritized
- [ ] `.gpd/review/REVIEW-LEDGER*.json` and `.gpd/review/REFEREE-DECISION*.json` consumed when available
- [ ] `.gpd/AUTHOR-RESPONSE.md` and `.gpd/paper/REFEREE_RESPONSE.md` created with complete point-by-point structure
- [ ] Comments triaged into response-only, revision, and new calculation groups
- [ ] All responses drafted and revisions applied via paper-writer agents
- [ ] Revised manuscript compiles without errors
- [ ] Internal consistency verified after revisions (max 3 iterations)
- [ ] Response letter generated with change summary
- [ ] All artifacts committed
</success_criteria>
