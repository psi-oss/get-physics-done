---
name: gpd:respond-to-referees
description: Structure a point-by-point response to referee reports and update the manuscript
argument-hint: "[path to referee report or 'paste']"
context_mode: project-required
requires:
  files: ["paper/*.tex", "paper/*.md", "manuscript/*.tex", "manuscript/*.md", "draft/*.tex", "draft/*.md"]
review-contract:
  review_mode: publication
  schema_version: 1
  required_outputs:
    - "GPD/review/REFEREE_RESPONSE{round_suffix}.md"
    - "GPD/AUTHOR-RESPONSE{round_suffix}.md"
  required_evidence:
    - existing manuscript
    - referee report source when provided as a path
  blocking_conditions:
    - missing project state
    - missing manuscript
    - missing referee report source when provided as a path
    - missing conventions
    - degraded review integrity
  preflight_checks:
    - command_context
    - project_state
    - manuscript
    - referee_report_source
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
<objective>
Structure a point-by-point response to referee reports and revise the manuscript accordingly.

Handles the full revision pipeline: parsing referee comments, categorizing by priority and type, drafting responses, spawning revision agents for manuscript changes, tracking new calculations needed, verifying consistency after revisions, and producing both the internal author-response tracker and the journal-facing response letter.

**Orchestrator role:** Parse and triage referee comments, coordinate revision agents, track new calculation requests, and keep the internal and journal-facing response artifacts synchronized.

**Why subagent:** Each section revision needs the full context of the referee comment, current section text, and planned response. Fresh context per section revision improves quality while the main context coordinates the overall response structure.

Responding to referees is collaborative improvement: every comment, even an incorrect one, reveals something about how the paper communicates its results. The goal is a stronger paper.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/respond-to-referees.md
@{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md
@{GPD_INSTALL_DIR}/templates/paper/bibliography-audit-schema.md
@{GPD_INSTALL_DIR}/templates/paper/review-ledger-schema.md
@{GPD_INSTALL_DIR}/templates/paper/referee-decision-schema.md
</execution_context>

<context>
Referee report source: $ARGUMENTS (file path or "paste" for inline input)

@GPD/STATE.md
@GPD/AUTHOR-RESPONSE{round_suffix}.md
@GPD/review/REFEREE_RESPONSE{round_suffix}.md
@GPD/review/REVIEW-LEDGER{round_suffix}.json
@GPD/review/REFEREE-DECISION{round_suffix}.json

Check for prior response and staged review files:

```bash
ls GPD/AUTHOR-RESPONSE*.md 2>/dev/null
ls GPD/review/REFEREE_RESPONSE*.md 2>/dev/null
ls GPD/review/REVIEW-LEDGER*.json GPD/review/REFEREE-DECISION*.json 2>/dev/null
```

Use centralized preflight to resolve the active manuscript only from the canonical manuscript roots `paper/`, `manuscript/`, or `draft/` via the manuscript-root manifest/config/entrypoint resolver. For this command, the explicit argument is the referee-report source path (or the `paste` sentinel), not a manuscript selector. Do not reintroduce first-match wildcard discovery here.

</context>

<process>
Execute the respond-to-referees workflow from @{GPD_INSTALL_DIR}/workflows/respond-to-referees.md end-to-end.
If staged peer-review artifacts exist under `GPD/review/`, absorb them as structured decision context while keeping `GPD/REFEREE-REPORT{round_suffix}.md` as the canonical issue-ID source.
Treat `GPD/review/REVIEW-LEDGER{round_suffix}.json` and `GPD/review/REFEREE-DECISION{round_suffix}.json` as schema-governed artifacts: use the loaded review-ledger/referee-decision schemas and peer-review reliability reference literally instead of inventing repair fields or accepting blank `manuscript_path` placeholders.
Do not invent hidden fields or placeholder `manuscript_path` fallbacks when reconciling the response artifacts.
Preserve all validation gates (report parsing, triage confirmation, compilation check, consistency verification, bounded revision loop).
</process>

<success_criteria>
- [ ] Referee reports parsed and all comments categorized and prioritized
- [ ] `GPD/review/REVIEW-LEDGER*.json` and `GPD/review/REFEREE-DECISION*.json` consumed when available
- [ ] `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/review/REFEREE_RESPONSE{round_suffix}.md` created with complete point-by-point structure
- [ ] Comments triaged into response-only, revision, and new calculation groups
- [ ] All responses drafted and revisions applied via paper-writer agents
- [ ] Revised manuscript compiles without errors
- [ ] Internal consistency verified after revisions (max 3 iterations)
- [ ] Response letter generated with change summary
- [ ] All artifacts committed
</success_criteria>
