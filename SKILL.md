---
name: mayfly
description: |
  Fresh-context-per-step research protocol with a depth-tiered lab notebook.
  Scales to thousands of steps: the PI's read budget is O(log N) via a
  knowledge graph (FRONTIER → MAP → topic entries → epoch summaries → raw
  attempts). Every fact is cross-linked to its context; less-useful material
  is pushed to deeper tiers without being discarded. Harness-agnostic; works
  wherever you can spawn fresh agent invocations and read/write local files.
audience: research / optimization / campaign agents on any harness
status: portable v2 (scale-extended — knowledge graph + epoch summaries + FRONTIER added)
---

# Mayfly

A protocol for running a long research/optimization campaign across many fresh
agent invocations, where the **lab notebook on disk** is the only conduit
between invocations.

Designed to scale: the PI's read cost grows as O(log N) not O(N), every fact
is cross-linked to its context, and less-useful material is pushed into deeper
tiers — reachable but not cluttering the working surface.

## TL;DR

Per step:

1. A **PI mayfly** (fresh context, ~10 min budget) reads FRONTIER.md, navigates
   the knowledge graph as needed, and writes ONE post-it.
2. A **Researcher mayfly** (fresh context, ~10 min budget) reads the post-it,
   attempts the problem, writes attempt notes + journal row, then **maintains
   the knowledge graph** (upsert topic entries, update FRONTIER.md).
3. If either mayfly times out or throws, a **Recovery mayfly** (~2 min budget)
   forces the bookkeeping write.

Every K steps (EPOCH_SIZE, default 20):

4. A **Summarizer mayfly** (~5 min budget) compresses the last K attempt notes
   into one epoch summary and updates MAP.md with the new epoch entry.

The mayflies share NOTHING in-process. Everything that survives across steps
is on disk in the lab notebook.

## When to use this

- Long-running campaign: many attempts on one problem, where cross-attempt
  signal matters.
- Each attempt is expensive (so you want the next attempt to learn from prior
  ones) but the total context exceeds a single window.
- You can spawn fresh agent invocations from a driver, each with its own
  context and toolset.
- Crashes / timeouts happen and you want them labeled (not silent gaps).

## When NOT to use this

- Single-shot tasks (no cross-attempt accumulation).
- Tasks where the entire campaign fits in one context window — just use one
  agent.
- Streaming / realtime tasks — mayflies are stop-the-world per step.
- Tasks where attempts are independent (no PI-style briefing needed). A flat
  fan-out is simpler.
- At extremely large scale (millions of steps), the epoch index in MAP.md
  itself would need a further level of compression (super-epochs). v2 supports
  thousands of steps comfortably.

## Concepts

### Mayfly

A short-lived, fresh-context agent invocation. Lives for ONE call. Dies.
**No in-process state carries forward.** All persistence is via the lab
notebook on disk.

### Lab notebook

An on-disk directory. The ONLY conduit between mayflies. Four layers:

- **Surface layer** — `FRONTIER.md` (current knowledge state) and
  `knowledge/MAP.md` (navigation index). The PI reads these first.
- **Knowledge layer** — `knowledge/<topic>.md` files. Each is a topical
  synthesis linking every fact to the attempt(s) that established it.
- **Archive layer** — `epochs/<range>.md` (K-attempt compressed summaries) and
  `JOURNAL.md`. Reachable via links from the layers above; not the entry point.
- **Raw layer** — `attempts/<NNN>.md`. Full per-attempt notes. The deepest
  corner; always reachable, never the first stop.
- **Seed layer** — pre-curated background material (optional; may be empty).

A fact that lives ONLY in `attempts/<NNN>.md` with NO link from a knowledge
entry is **dark data** — findable only by linear scan. The Researcher's
maintenance duty prevents this.

### Roles

- **PI** mayfly: reads FRONTIER, navigates knowledge graph, writes ONE post-it.
- **Researcher** mayfly: reads post-it, attempts the problem, writes raw notes,
  then maintains the knowledge graph (upsert topics, update FRONTIER).
- **Recovery** mayfly: short-budget forced-bookkeeping when PI or Researcher
  dies mid-flight.
- **Summarizer** mayfly (periodic): compresses K attempt notes into one epoch
  summary, updates MAP.md.

## Notebook layout

```
campaign/
├── POST_IT.md              # active PI brief (overwritten each step)
├── FRONTIER.md             # current knowledge state (researcher updates each step)
├── knowledge/
│   ├── MAP.md              # navigable index: topics + epoch list + open threads
│   └── <topic-slug>.md     # per-topic synthesis with links to supporting attempts
├── epochs/
│   └── <start>-<end>.md    # compressed summary of K attempts (Summarizer writes)
├── JOURNAL.md              # append-only one-row-per-attempt log (archive at scale)
└── attempts/
    └── <NNN>.md            # full per-attempt notes (deepest corner)
```

### Depth tiers

| Tier | Files | When a mayfly reads it |
|---|---|---|
| Surface | FRONTIER.md, knowledge/MAP.md | Every PI. O(1) reads. |
| Knowledge | knowledge/<topic>.md | PI drilling into a specific angle. |
| Archive | epochs/<range>.md, JOURNAL.md | Historical context; PI or Researcher. |
| Raw | attempts/<NNN>.md | Forensics only. Reached via links. |

---

### FRONTIER.md

**Maintained by the Researcher. Read first by the PI.** Always reflects the
current knowledge state. An outdated FRONTIER misdirects the PI — updating it
is non-optional.

```markdown
# Campaign Frontier — step NNN

## Current best
[Metric or outcome. One paragraph: best approach and what's distinctive.]

## Most promising open directions
1. [Direction] → knowledge/<topic>.md
2. [Direction] → knowledge/<topic>.md

## Active hypotheses
- [Hypothesis] — status: [proposed | testing | confirmed | refuted]
  [→ attempt NNN | knowledge/<topic>.md]

## Recently closed threads (last ~K steps)
- [What was resolved and how] → knowledge/<topic>.md

## Known dead ends
- [Approach] — why: [one line] → knowledge/<topic>.md

## Knowledge index
→ knowledge/MAP.md
```

Rules:
- Updated by the Researcher at the end of EVERY step (not optional).
- Every direction / hypothesis / dead end links to a knowledge entry or attempt.
- Closed threads move here from "active hypotheses" once resolved.

---

### knowledge/MAP.md

**Researcher maintains the topic list. Summarizer appends the epoch index.**
These are separate sections owned by different roles; neither overwrites the
other's section.

```markdown
# Knowledge Map — updated step NNN

## Active topics
- [topic-slug] (active, step NNN) — [one-line summary] → knowledge/<topic>.md
- [topic-slug] (established, step NNN) — [one-line summary] → knowledge/<topic>.md

## Closed / dead-end topics
- [topic-slug] (dead-end, step NNN) — [why closed] → knowledge/<topic>.md

## Epoch index
- epochs/000-019.md — [one-line characterization of the epoch's arc]
- epochs/020-039.md — [one-line characterization]

## Open research questions
- [Question] → knowledge/<topic>.md (if related to an existing topic)
```

Rules:
- When the Researcher creates a new topic entry, add it to "Active topics".
- When a topic becomes a dead end, move it to "Closed / dead-end topics".
- The Summarizer ONLY appends to "Epoch index"; it never rewrites topics.

---

### knowledge/<topic-slug>.md

Per-topic synthesis. Every significant finding from any attempt belongs in a
topic entry, linked to the attempt(s) that established it. Structure:

```markdown
# Knowledge: <topic-name>

**Status:** [active | established | dead-end | superseded]
**Last updated:** step NNN
**Confidence:** [speculative | partial | established]

## What we know
2–4 sentence synthesis. State facts, not procedure.

## Supporting evidence
- [Finding or observation] [→ attempt NNN]
- [Finding or observation] [→ attempt NNN, NNN | epoch 020-039]

## Dead ends within this topic
- [Approach tried] — failed because [reason] [→ attempt NNN]

## Open questions
- [Question that remains unresolved within this topic]

## See also
- knowledge/<related-topic>.md — [one line: why related]
```

Rules:
- Every bullet in "Supporting evidence" and "Dead ends" MUST link to the
  attempt(s) or epoch that established it. An unlinked assertion is an opinion.
- "See also" links to related topics — these are the graph edges that keep
  information connected and prevent isolated fragments.
- One topic per logical angle (e.g., "mesh-resolution", not "things-week-2").
- When updating an existing topic: READ it first with read_knowledge(topic),
  then write the full updated content. Do NOT truncate prior evidence bullets.

---

### POST_IT.md

Overwritten each step by the PI. The next researcher reads ONLY this as their
starting brief. Structure:

```markdown
# Post-it for Researcher (step N)

**Recommended direction:** [one paragraph, 3-5 sentences — the single most
promising next move. Be specific: name the method / parameter set / assumption /
schema choice.]

**Concrete steps:**
- [3-5 ordered bullets the researcher should follow]

**References:**
- knowledge/<topic>.md — [why relevant]
- attempts/<step>.md — [for a specific drill-down, if warranted]
- (seed file paths if any)

**What NOT to do:**
- [1-3 dead-ends to avoid — cite the knowledge entry that proved them dead]
```

At scale, "What NOT to do" should reference knowledge entries (not raw attempt
numbers) — the knowledge entry is authoritative and already synthesizes why.

---

### JOURNAL.md

Append-only one-row-per-attempt log. At scale this is an **archive-tier** file
— the PI does not start here. It is the index of last resort for forensics
and the canonical record for the recovery shim.

The `knowledge_updated` column names the topic slugs touched each step,
turning the journal into a reverse index (step → topics).

Default (no numeric metric):

```markdown
# Lab Journal

| step | outcome | summary | knowledge_updated | files |
|---:|---|---|---|---|
```

With numeric metric:

```markdown
# Lab Journal

| step | metric | outcome | summary | knowledge_updated | files |
|---:|---:|---|---|---|---|
```

`outcome` vocabulary:

- `new_best` — best result so far on whatever the campaign tracks
- `tied` — matched the current best but didn't improve
- `regressed` — worse than the current best
- `partial` — useful partial progress
- `stalled` — ran but produced no meaningful signal
- `broken` — crashed / timed out / unusable output (recovery path)

---

### epochs/<start>-<end>.md

Written by the Summarizer every K steps. Compresses K attempt files into one
navigable page, so the PI can read one file instead of K. Structure:

```markdown
# Epoch <start>-<end>

## Arc
[2–3 sentences: what the campaign tried in this epoch and overall how it went.]

## Key findings
- [Finding] [→ attempt NNN]
- [Finding] [→ attempt NNN]

## Knowledge entries touched
- knowledge/<topic>.md — [updated | created | closed to dead-end]

## Outcome distribution
new_best: N | tied: N | regressed: N | partial: N | stalled: N | broken: N
```

---

### attempts/<NNN>.md

One file per attempt, zero-padded step number. The deepest corner. Raw detail.
Reached via links from knowledge entries and epoch summaries; never enumerated
by the PI. Structure:

```markdown
# Attempt N — <one-line approach>

## Approach
<2-5 lines: specific parameters / methods / assumptions>

## Result
<2-3 lines: what came out, including any campaign metric>

## What worked / what failed
<3-6 bullets, ideally with constants or code snippets>

## For attempt N+1
<1-3 concrete bullets — what should change>
```

---

### Seed layer (optional)

Pre-curated background material (papers, prior runs, reference data). May live
as a sibling `_seed/` directory or a separately-mounted directory.

```
_seed/
├── README.md                   # curated orientation (read first)
├── _source/                    # verbatim source material
├── _gists/                     # one short summary per entry, YAML front-matter
├── _index/
│   ├── by-entity/              # "what is mentioned where"
│   ├── by-key/                 # "what structured key=value pairs exist"
│   ├── by-shape/               # "by structural type"
│   └── by-similarity/          # "per-entry kNN"
└── _shards/                    # content-cohesive group summaries
```

The seed layer is BACKGROUND material. Mayflies should read the campaign layer
first and only consult the seed when the campaign has insufficient signal
(typical: step 0).

---

## Required tools (host provides to mayflies)

Tool names are conventions — port them to your harness's MCP / function-calling
shape.

### Notebook reads (PI, Researcher, Summarizer)

```
read_frontier() -> str
    Returns FRONTIER.md, or a "(no frontier yet)" stub.

read_map() -> str
    Returns knowledge/MAP.md, or a "(no map yet)" stub.

list_knowledge() -> list[str]
    Returns sorted topic slugs in knowledge/ (without .md; excludes MAP).

read_knowledge(topic: str) -> str
    Returns knowledge/<topic>.md, or a "(no entry yet)" stub.

read_post_it() -> str
    Returns POST_IT.md, or a "(no post-it yet)" stub.

read_journal() -> str
    Returns JOURNAL.md, or a "(no journal entries yet)" stub.

list_attempts() -> list[str]
    Returns sorted attempt-note filenames (e.g. ["000.md", "001.md", ...]).

read_attempt(step: int) -> str
    Returns attempts/<step:03d>.md, or a "(no notes)" stub.

list_epochs() -> list[str]
    Returns sorted epoch filenames (e.g. ["000-019.md", "020-039.md", ...]).

read_epoch(name: str) -> str
    Returns epochs/<name>.md (name is the filename without .md).

search_notebook(query: str) -> str
    Case-insensitive substring search across all tiers: FRONTIER.md,
    knowledge/*.md, epochs/*.md, JOURNAL.md, and attempts/*.md.
    Returns matching lines with source path. Cap output (~60 lines).
```

### Seed reads (if a seed layer is wired in)

```
read_seed_readme() -> str
list_seed_indexes() -> list[str]
read_seed_index(axis: str, value: str) -> str
```

Strict path-sanitization is REQUIRED on seed reads (reject `..`, absolute
paths). Mayflies are untrusted with respect to the seed directory.

### Notebook writes

PI only:

```
write_post_it(content: str)
    Overwrites POST_IT.md. The PI calls this exactly once.
```

Researcher only:

```
append_journal_row(<campaign-specific columns>)
    Upserts one row in JOURNAL.md for the current step. The driver should
    track the active step number and refuse writes that don't match.

    Score-free:  append_journal_row(outcome, summary, knowledge_updated, files)
    With metric: append_journal_row(metric, outcome, summary, knowledge_updated, files)

write_attempt_notes(step: int, content: str)
    Writes attempts/<step:03d>.md (overwrites). Driver should refuse writes
    where step != active step.

upsert_knowledge(topic: str, content: str)
    Writes knowledge/<safe(topic)>.md (overwrites). Creates if missing.
    `topic` becomes the filename slug (lowercase, hyphens). Driver must
    sanitize: reject `..`, absolute paths, reserved names (MAP).
    The Researcher reads the existing entry first, preserves prior evidence
    bullets, and adds new ones.

update_frontier(content: str)
    Overwrites FRONTIER.md. Called exactly once per Researcher step.

update_map(content: str)
    Overwrites knowledge/MAP.md. Called by the Researcher when topics are
    created or change status, and by the Summarizer when adding an epoch entry.
```

Summarizer only:

```
write_epoch_summary(start: int, end: int, content: str)
    Writes epochs/<start:03d>-<end:03d>.md (overwrites).
```

Plus: whatever execution / sandbox tools the Researcher needs to do the work.

---

## The campaign loop (driver side)

```python
step = 0
EPOCH_SIZE = 20  # tune per campaign; 10-50 is a reasonable range

while not termination_criterion_met(step, notebook):
    try:
        run_pi(step, pi_timeout)
    except (Timeout, Exception) as e:
        run_pi_recovery(step, e, recovery_timeout)

    try:
        run_researcher(step, researcher_timeout)
    except (Timeout, Exception) as e:
        run_researcher_recovery(step, e, recovery_timeout)

    # Epoch summarization every K steps. Non-fatal: if it fails, the
    # attempts are still reachable; the PI just has a less-compressed archive.
    if step > 0 and step % EPOCH_SIZE == (EPOCH_SIZE - 1):
        epoch_start = step - EPOCH_SIZE + 1
        try:
            run_summarizer(epoch_start, step, summarizer_timeout)
        except (Timeout, Exception):
            pass  # log and continue

    step += 1
```

Each `run_*` call must spawn a FRESH agent invocation (new context). On
harnesses without a native "fresh agent" primitive, see the porting section
for options.

---

## Termination criteria (campaign-defined)

- **Success** — the campaign's success-check passes.
- **Budget** — total wall-clock or attempt-count cap reached.
- **Stagnation cap** — after N branch attempts in a row produce
  `stalled` / `regressed`, give up.
- **Researcher quits** — the Researcher writes `knowledge/done.md`
  saying "the problem is unsolvable with available tools / data" and the
  driver checks for it.

Document the termination criteria in the campaign's README so the PI knows
what "good enough" looks like.

---

## The PI prompt (template)

```
You are the PRINCIPAL INVESTIGATOR for the `{campaign_id}` campaign.
You arrived today with NO memory of this campaign. You will be replaced
after writing exactly one post-it. A new RESEARCHER will then arrive (also
with no memory) and will read ONLY your post-it as their starting brief.

Your job: navigate the lab notebook efficiently, then write ONE concrete
post-it telling the researcher the single most promising next move.

# Problem the researcher will attempt
{problem}

# Campaign success criterion
{success_criterion}

# How to navigate the notebook (depth-first, pull on demand)

SURFACE tier — start here:
  - read_frontier() — current knowledge state. One page. START HERE.
    If FRONTIER gives you enough signal, skip the rest and write.
  - read_map() — topic list + epoch index. Read if you want to explore a
    specific angle or FRONTIER mentions a topic worth drilling into.

KNOWLEDGE tier — drill into specific topics:
  - list_knowledge() then read_knowledge(topic) — topical synthesis. One file
    per angle, with evidence links. Read 1-2 topics at most.

ARCHIVE tier — historical context (read sparingly):
  - list_epochs() then read_epoch(name) — one page per {EPOCH_SIZE} attempts.
    Read when a knowledge entry says "see epoch X-Y" or you need context on
    when a direction emerged.
  - search_notebook(query) — full-text search across all tiers.

RAW tier — forensics only, not the entry point:
  - read_journal() — one-line-per-attempt log (archive at scale).
  - list_attempts() then read_attempt(step) — full per-attempt notes.

SEED notebook (optional background — may be empty):
  - read_seed_readme(), list_seed_indexes(), read_seed_index(axis, value)

# Self-budget — you are a mayfly too

- Read FRONTIER (1 call). If sufficient, write the post-it.
- If more context needed: read MAP (1 call), then 1-2 knowledge entries.
- Only descend to archive/raw tier if a knowledge entry explicitly points there.
- Aim for under {pi_read_budget_calls} read calls total.
- Consult seed material only if the campaign notebook has insufficient signal
  (typical: step 0).

# Progress and exploration rule (READ BEFORE WRITING THE POST-IT)

{progress_block}

# Writing the post-it (REQUIRED — your only durable output)

Call write_post_it(content) exactly once. Structure:

# Post-it for Researcher (step {step})

**Recommended direction:** [one paragraph, 3-5 sentences. Be specific.]

**Concrete steps:**
- [3-5 ordered bullets]

**References:**
- knowledge/<topic>.md — [why relevant]
- (attempts/<step>.md only if you want the researcher to drill into one)
- (seed paths if any)

**What NOT to do:**
- [1-3 dead-ends — cite the knowledge entry that proved them dead, not raw
  attempt numbers; the knowledge entry already synthesizes why]

Be concrete enough that a researcher with no other context could act on it.
Output DONE when written.
```

### Progress / stagnation block

Two variants — pick one for `{progress_block}`.

**Variant A — campaign has a numeric metric**

```
The metric's achievable ceiling is {metric_ceiling}. If the campaign's current
best is well below it, there is real headroom and the next attempt's job is to
close that gap, not to micro-refine.

Stagnation rule (MANDATORY). Examine the FRONTIER's "current best" and recent
journal entries. If the last {K_stagnation} or more attempts each gained less
than {stagnation_epsilon} in metric — the search is in a local optimum.
In that case your post-it MUST:
  - explicitly name the local optimum (cite the metric range and steps);
  - direct the next researcher to a FUNDAMENTALLY different approach —
    different physical assumption, parameterization, method, functional form,
    or decomposition;
  - cite at least one family already tried (from knowledge/) and name one
    that has NOT been explored;
  - explicitly forbid further refinement of the current best family in
    "What NOT to do".

If the last {K_stagnation} attempts each gained MORE than {stagnation_epsilon},
continue the productive line.

If the campaign has fewer than {K_stagnation} attempts, the stagnation rule
does not yet apply; judge whether early attempts are exploring widely enough.
```

**Variant B — campaign has no numeric metric (outcome tags only)**

```
The campaign's success criterion is: {success_criterion}.

Stagnation rule (MANDATORY). Examine FRONTIER and recent journal entries. Count
consecutive non-`new_best` outcomes walking back from the most recent entry.
If you find {K_stagnation} or more in a row, the search is in a local optimum.
In that case your post-it MUST:
  - explicitly name what the campaign is stuck on (cite the steps);
  - direct the next researcher to a FUNDAMENTALLY different approach;
  - cite at least one tried family (from knowledge/) and name one not explored;
  - explicitly forbid further refinement in "What NOT to do".

If the most recent entry is `new_best` or fewer than {K_stagnation} consecutive
non-`new_best` entries exist, continue the productive line.

If the campaign has fewer than {K_stagnation} attempts, the stagnation rule
does not yet apply.
```

Suggested defaults: `K_stagnation = 4`, `stagnation_epsilon` is
metric-dependent (e.g. 0.01 for a score in [0,1]; 5% of current best for a
residual; 1 test for a passing-tests count).

---

## The PI recovery prompt (template)

```
# Forced post-it write — PI mayfly was cancelled mid-flight

The PI mayfly for step {step} hit `{exc_type}` after {wall_s:.0f}s.

EARLY: call read_frontier() and skim it.

THEN: call write_post_it exactly once:

# Post-it for Researcher (step {step}) — PI navigation incomplete

PI cancelled by `{exc_type}` after {wall_s:.0f}s; this is a thin fallback.

**Recommended direction (best-guess from FRONTIER alone):** <one paragraph —
if frontier is empty, suggest a defensible baseline. If non-empty, build on
the current best with ONE substantive variation.>

**Concrete steps:**
- <ONE bullet — most important next move>
- <ONE bullet — bookkeeping reminder: update knowledge + frontier before returning>

Output DONE when the post-it is written.
```

---

## The Researcher prompt (template)

```
You are a research mayfly working on the `{campaign_id}` campaign.
You exist for ONE attempt. When you return your final answer you will be
deleted. Your reasoning, your code, your scratchpad — NONE of it survives.
The only things that cross to the next researcher are what you write to the
lab notebook.

# Your brief

The PI has left a post-it for you. READ IT FIRST:
  → call read_post_it()

# Problem
{problem}

# Tools

Execution: write code, run experiments. Your code is ephemeral.

Notebook reads (pull on demand):
  - read_post_it() — start here
  - read_frontier(), read_map()
  - list_knowledge(), read_knowledge(topic)
  - list_epochs(), read_epoch(name)
  - read_journal(), list_attempts(), read_attempt(step)
  - search_notebook(query)
  - (Seed) read_seed_readme(), list_seed_indexes(), read_seed_index(axis, value)

Notebook writes (your mayfly duty — ALL REQUIRED):
  - write_attempt_notes, append_journal_row    # raw record
  - upsert_knowledge                           # knowledge graph
  - update_frontier                            # surface state
  - update_map                                 # if topics changed

# Mayfly duty (REQUIRED — do ALL of these BEFORE returning your final answer)

Without these writes, the next researcher cannot find what you did and the
campaign accumulates dark data — facts reachable only by linear scan.

  1. write_attempt_notes(step={step}, content=<<<
        # Attempt {step} — <one-line approach>
        ## Approach
        <2-5 lines: specific parameters / methods / assumptions>
        ## Result
        <2-3 lines: what came out + any campaign metric>
        ## What worked / what failed
        <3-6 bullets, ideally with constants or code snippets>
        ## For attempt {next_step}
        <1-3 concrete bullets>
     >>>)

  2. append_journal_row(
         {researcher_journal_args},
         knowledge_updated='<comma-separated topic slugs you updated>'
     )

  3. For EACH significant finding from this attempt — upsert_knowledge:
     - FIRST call read_knowledge(topic) to get the existing entry (if any).
     - Then call upsert_knowledge(topic='<slug>', content=<<<
          # Knowledge: <topic-name>
          **Status:** [active | established | dead-end | superseded]
          **Last updated:** step {step}
          **Confidence:** [speculative | partial | established]
          ## What we know
          <synthesis — incorporate what you learned this step>
          ## Supporting evidence
          - <prior evidence bullets — PRESERVE THEM with their → links>
          - <new finding from this step> [→ attempt {step}]
          ## Dead ends within this topic
          - <if any, with → attempt link>
          ## Open questions
          - <if any>
          ## See also
          - knowledge/<related-topic>.md — <why related>
       >>>)
     Use an existing topic if one fits. Create a new topic only when no
     existing one fits — name it by logical angle, not by step number.
     RULE: every finding must land in a topic entry with a → attempt link.
     Unlinked findings are dark data that cannot be navigated to.

  4. update_frontier(content=<<<
        # Campaign Frontier — step {step}
        ## Current best
        <update if this step improved; otherwise carry forward>
        ## Most promising open directions
        <update based on what you learned>
        ## Active hypotheses
        <update statuses; add new; move confirmed/refuted to closed threads>
        ## Recently closed threads
        <add this step's outcome if it resolved something>
        ## Known dead ends
        <add if this step proved a dead end — link to knowledge entry>
        ## Knowledge index
        → knowledge/MAP.md
     >>>)

  5. update_map(content=<updated MAP.md>) — ONLY if you created a new topic
     or changed a topic's status. Read current MAP first with read_map(),
     update the "Active topics" or "Closed / dead-end topics" section,
     then write the full updated MAP. Do NOT touch the "Epoch index" section.

# Final answer

After your mayfly duty, output your final answer to the problem.
```

---

## The Researcher recovery prompt (template)

```
# Forced journal write — Researcher mayfly was cancelled mid-flight

The Researcher for step {step} hit `{exc_type}` after {wall_s:.0f}s.

EARLY: call read_journal() and skim it.

THEN call BOTH (knowledge/ and FRONTIER are NOT updated by recovery — nothing
was completed, so the prior state is correct):

  1. append_journal_row(
         outcome='broken',
         summary='step {step} hit {exc_type} after {wall_s:.0f}s',
         knowledge_updated='',
         ...
     )

  2. write_attempt_notes(step={step}, content=<<<
        # Attempt {step} — FAILURE ({exc_type})
        Cancelled after {wall_s:.0f}s. No reasoning recoverable.
        ## Speculation
        <one line based on prior journal entries — what kind of approach
        tends to run long here? ("no prior signal" if empty)>
        ## For attempt {next_step}
        <ONE concrete suggestion>
     >>>)

Keep it short. Output DONE.
```

---

## The Summarizer prompt (template)

```
You are a Summarizer mayfly for the `{campaign_id}` campaign.
Your job: compress attempts {start}–{end} into one epoch summary and append
the new epoch entry to MAP.md.

# What to read

Read each attempt in the range: read_attempt({start}), ..., read_attempt({end}).
Read the current MAP: read_map().

# What to write

  1. write_epoch_summary(start={start}, end={end}, content=<<<
        # Epoch {start:03d}-{end:03d}

        ## Arc
        <2-3 sentences: what the campaign tried in this epoch and overall how
        it went — direction, energy, whether real progress was made>

        ## Key findings
        - <finding> [→ attempt NNN]
        - <finding> [→ attempt NNN]

        ## Knowledge entries touched
        - knowledge/<topic>.md — [updated | created | closed to dead-end]

        ## Outcome distribution
        new_best: N | tied: N | regressed: N | partial: N | stalled: N | broken: N
     >>>)

  2. update_map(content=<current MAP.md with one new line appended to the
     "Epoch index" section: "- epochs/{start:03d}-{end:03d}.md — <one-line arc>")
     Do NOT rewrite the "Active topics" or "Closed / dead-end topics" sections.
     Read the current MAP with read_map() first, then append to epoch index only.

Output DONE.
```

---

## Timeout budgets (starting points — tune per campaign)

- **PI**: 10 min (600s). Lower if your tool calls are fast.
- **Researcher**: 10 min (600s) compute-light; up to 30+ min heavy compute.
- **Recovery**: 2 min (120s). Forced bookkeeping only — no thinking.
- **Summarizer**: 5 min (300s). Reads K attempt files + writes 2 files.

---

## Load-bearing invariants (don't drop these when porting)

These are what make Mayfly work. Dropping any one produces something that
resembles Mayfly but fails at scale.

1. **Fresh context per mayfly.** Each mayfly arrives with NO MEMORY of the
   campaign. Every piece of cross-attempt knowledge round-trips through the
   notebook. The benefit: the Nth mayfly has the same fresh context budget as
   the 1st. Long campaigns don't degrade.

2. **Mandatory bookkeeping — raw layer.** The Researcher MUST call
   write_attempt_notes AND append_journal_row BEFORE returning. Without them,
   the next researcher cannot see what was attempted. The prompt must spell out
   the duty AND the consequence. A mayfly that skips bookkeeping didn't happen.

3. **Mandatory bookkeeping — knowledge layer.** The Researcher MUST ALSO call
   upsert_knowledge (for every significant finding) AND update_frontier. This
   is the new v2 invariant. Without it, findings pile up as raw attempt notes
   and become unreachable via navigation at scale. The knowledge layer is the
   findability layer; bypassing it produces dark data.

4. **Every fact carries a provenance link.** A knowledge entry without →
   attempt links is an assertion, not evidence. Links make the graph navigable
   bidirectionally (topic → attempt, epoch → topic). The Researcher prompt
   must require links on every supporting evidence bullet.

5. **FRONTIER.md reflects current state.** An outdated FRONTIER misdirects
   the PI. If the Researcher skips update_frontier, the next PI makes decisions
   based on stale information. This must be treated the same as append_journal_row:
   non-optional, with the consequence spelled out in the prompt.

6. **MAP.md is the navigation root for knowledge/.** When a new topic is
   created or a topic status changes, MAP.md must be updated. Without it,
   topics become orphans — they exist on disk but the PI can't find them from
   the surface tier without a full-text search.

7. **Recovery shim.** When PI or Researcher dies mid-flight, a short-budget
   recovery mayfly forces the raw-layer bookkeeping. Recovery does NOT touch
   knowledge/ or FRONTIER (nothing was completed — prior state is correct).
   The gap is labeled `broken` in the journal.

8. **Pull-on-demand reads, depth-first.** The PI reads FRONTIER first (1 call),
   drills into knowledge if needed, descends to archive/raw tier only when a
   knowledge entry points there. Enumerating the raw attempts directory grows
   O(N) and breaks at scale.

9. **Stagnation rule (campaign-adapted).** Without an explicit anti-stagnation
   prompt, the PI rewards refinement because it's the path of least resistance.
   The PI prompt must mandate a branch directive when the progress signal has
   plateaued for K consecutive steps.

10. **"What NOT to do" cites knowledge entries, not raw attempts.** At scale,
    the knowledge entry is authoritative (it synthesizes why). A post-it citing
    "don't try approach X — see knowledge/mesh-resolution.md" is more useful
    than "don't try what attempt 047 tried" because it gives the next researcher
    the full context in one hop.

---

## Bootstrap content (step 0)

Write these files before the first PI runs. Create `knowledge/` and `epochs/`
directories.

### BOOTSTRAP_POST_IT (write to POST_IT.md)

```markdown
# Post-it for the FIRST Researcher

No prior attempts on this campaign exist yet. You are attempt 000.

**Recommended direction:** Read the seed README (if it exists) to orient.
Then attempt the problem with whatever approach seems most direct. Your job
is to leave a useful trace for the next researcher — not just in attempt
notes but in the knowledge graph.

**Concrete steps:**
- Skim the seed README and seed indexes if they exist.
- Attempt the problem with a defensible baseline approach.
- BEFORE returning: write_attempt_notes, append_journal_row,
  upsert_knowledge (for any finding), update_frontier, update_map.

**What NOT to do:**
- Do not skip the knowledge and frontier writes. The next researcher has NO
  memory of you. The notebook is the ONLY conduit — and FRONTIER.md is the
  first thing the next PI will read.
```

### BOOTSTRAP_FRONTIER (write to FRONTIER.md)

```markdown
# Campaign Frontier — step 000 (not yet started)

## Current best
No attempts yet.

## Most promising open directions
(Fill in from problem statement or seed material if available.)

## Active hypotheses
(None yet.)

## Known dead ends
(None yet.)

## Knowledge index
→ knowledge/MAP.md
```

### BOOTSTRAP_MAP (write to knowledge/MAP.md)

```markdown
# Knowledge Map — step 000 (not yet started)

## Active topics
(None yet.)

## Closed / dead-end topics
(None yet.)

## Epoch index
(None yet.)

## Open research questions
(Seed from problem statement if available.)
```

### BOOTSTRAP_JOURNAL

Score-free:

```markdown
# Lab Journal

| step | outcome | summary | knowledge_updated | files |
|---:|---|---|---|---|
```

With numeric metric:

```markdown
# Lab Journal

| step | metric | outcome | summary | knowledge_updated | files |
|---:|---:|---|---|---|---|
```

---

## Porting checklist

- [ ] Campaign loop: FRESH PI → FRESH Researcher → recovery paths for each;
      Summarizer every EPOCH_SIZE steps (non-fatal failure).
- [ ] "Active step" tracker so write tools enforce step consistency.
- [ ] Tool implementations:
  - [ ] Reads: read_frontier, read_map, list_knowledge, read_knowledge,
        read_post_it, read_journal, list_attempts, read_attempt,
        list_epochs, read_epoch, search_notebook
  - [ ] PI writes: write_post_it
  - [ ] Researcher writes: append_journal_row, write_attempt_notes,
        upsert_knowledge, update_frontier, update_map
  - [ ] Summarizer writes: write_epoch_summary (+ update_map)
  - [ ] Seed reads (optional): read_seed_readme, list_seed_indexes,
        read_seed_index — with path sanitization (reject `..`, absolute paths)
- [ ] Prompts: PI / PI-recovery / Researcher / Researcher-recovery /
      Summarizer, with progress block matched to metric shape.
- [ ] Termination criteria checked each iteration.
- [ ] Bootstrap writes at step 0: POST_IT.md, FRONTIER.md, knowledge/MAP.md,
      JOURNAL.md; create knowledge/ and epochs/ directories.
- [ ] EPOCH_SIZE constant (default 20; tune per campaign).

### Simulating fresh context

On harnesses without a native "spawn fresh agent" primitive:

- **Subprocess invocation.** Shell out to the CLI per mayfly with the prompt +
  toolset. Each invocation gets a fresh session. Simple, robust, slowish.
- **Session reset.** If the harness supports clearing conversation state, use
  that. Verify state is actually cleared.
- **MCP for notebook tools.** Wrap the notebook reads/writes as an MCP server
  scoped to one campaign directory. Path-sanitization at the MCP layer covers
  untrusted-agent risk. One server-per-campaign rather than one server-per-tool.

### Migrating a v1 campaign to v2

A v1 campaign (JOURNAL.md + attempts/ + findings/) can be migrated:

1. Create FRONTIER.md from the best-so-far state and active directions.
2. Create knowledge/MAP.md.
3. Convert findings/<slug>.md → knowledge/<slug>.md; add provenance links and
   "See also" sections. Update MAP.md with each entry.
4. Run the Summarizer over completed step ranges to create epoch files.

---

## What this skill INTENTIONALLY does NOT include

The original Mayfly reference implementation bundles several things specific
to one benchmark system that aren't part of the general protocol:

- **Score-in-[0,1]** as the only metric shape. The protocol works with
  outcome-tag-only journals.
- **The 0.01 stagnation threshold.** Metric-dependent; see `stagnation_epsilon`.
- **The 21-attempt fixed loop.** Termination is campaign-defined.
- **A fixed "target score is achievable" exhortation.** Declare the success
  criterion in the campaign README; the PI prompt cites that.
- **Seed-ingest pipeline** (probe → gist → shard → curate). The seed layer is
  OPTIONAL. If you want one, the reference implementation has the full pipeline.
- **`pydantic_ai` specifics.** The protocol is harness-agnostic.

---

## Design history

- **Gen 1 (single-call-per-attempt)** — one LLM call per attempt. A recovery
  shim was added when writeback was being lost on timeout, but it was a
  band-aid: bookkeeping competed with problem-solving inside the same context.
- **Gen 2 (PI ↔ Researcher split)** — split the work into two fresh-context
  roles so bookkeeping had its own dedicated prompt. Elevated the cross-attempt
  record from a flat scratchpad to JOURNAL.md + `attempts/` + `findings/`.
- **Gen 3 (stagnation-branching)** — added the score-ceiling reminder and
  mandatory stagnation-branching rule to the PI prompt. Prior campaigns were
  getting stuck at local optima because the "refine the current best" framing
  never triggered a branch.
- **Gen 4 (this file, v2 — knowledge graph)** — added the depth-tiered
  knowledge graph (FRONTIER, MAP, knowledge/, epochs/) to scale to thousands
  of steps. Gen 3's flat `findings/` plus a raw JOURNAL become O(N) to
  navigate; the v2 hierarchy is O(log N). The Researcher's duty now includes
  knowledge maintenance so every finding is connected and findable, not just
  logged. The Summarizer role compresses old attempts out of the PI's critical
  path without discarding them.
