<purpose>
Run `gpd:ideate` as a projectless conversational multi-agent research session for exploring, pressure-testing, and refining a research direction before committing to durable project artifacts.

Phase 5 keeps that contract and its non-goals while pushing the orchestrator further backstage. Preserve the bounded parent-owned round engine under the hood, but make clean turns read as agent-first conversation: keep the fast-start path light, keep launch preferences conditional and mostly off-screen, show agent exchange first, allow one bounded optional reaction layer, and end with a short natural handoff instead of a visible moderator loop. Visible summaries, recaps, and raw-detail review are secondary and should surface only when the user asks, when a blocker or checkpoint needs routing, when agent output diverges enough to need a short frame, or at session close. Preserve optional subgroup breakouts, structured closeout, and the parent workflow's ownership of the research brief, round state, subgroup routing, and any fresh continuation handoff.

Keep the boundary explicit from the start: project context is opt-in only, orchestration stays in memory, and this phase does not create durable ideation files or session artifacts. Non-goals for this phase include `RESEARCH.md` writes, `GPD/ideation/`, durable ideation artifact directories, resumable ideation session state, `resume-work` integration, staged init or stage-manifest semantics, automatic project-state ingestion, session IDs, transcript storage or replay, and subgroup promotion into durable sessions.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="orient_and_parse" priority="first">
Open with one short plain-English line:

`I will help sharpen the question, keep the constraints in view, and explore a first pass.`

Then parse the optional preset and separate it from the seed text:

```bash
PRESET=""
SEED_TEXT="$ARGUMENTS"

if echo "$ARGUMENTS" | grep -qE -- '--preset[[:space:]]+(fast|balanced|deep)'; then
  PRESET=$(printf '%s\n' "$ARGUMENTS" | sed -nE 's/.*--preset[[:space:]]+(fast|balanced|deep).*/\1/p' | head -n 1)
  SEED_TEXT=$(printf '%s\n' "$ARGUMENTS" | sed -E 's/[[:space:]]*--preset[[:space:]]+(fast|balanced|deep)//' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
fi

HAS_GPD_PROJECT=false
if [ -f GPD/PROJECT.md ] || [ -f GPD/STATE.md ] || [ -f GPD/ROADMAP.md ]; then
  HAS_GPD_PROJECT=true
fi
```

Use the parsed state to set expectations:

- If `SEED_TEXT` is non-empty, briefly repeat it back as the current session seed.
- If `PRESET` is non-empty, say you will treat it as the initial ideation preset unless the user edits it.
- If `HAS_GPD_PROJECT=true`, add one sentence: `I can use existing GPD project context if you want, but I will not pull it in automatically into this projectless session.`
- Always add one explicit boundary sentence: `This is a projectless, in-memory research session: I will not auto-load project state or create durable ideation files, session artifacts, or resumable session state.`
</step>

<step name="capture_core_brief">
Start from the user's first message instead of forcing a restart. A strong first message can become the working research brief directly.

Treat the current seed plus any named context as sufficient for a fast start when it already gives:

- a clear enough research focus, question, or discussion target
- a useful outcome or an explicit open-ended exploration mode
- at least one anchor, constraint, or risk to keep visible, or an explicit statement that none is available yet
- no unresolved blocker that would obviously misdirect the first bounded discussion turn

If the seed is already sufficient, preserve it as the working brief and ask only for the single most important missing detail if one lightweight clarification would materially improve the first bounded discussion turn. Do not ask for a fresh dense rewrite just to normalize the intake.

Ask for one dense freeform research brief only when the seed is too thin or too ambiguous to support even a conservative first bounded discussion turn.

If `SEED_TEXT` is usable but not yet sufficient on its own, weave it into the prompt rather than restarting from scratch:

`Using "{SEED_TEXT}" as the starting point, give me the research brief in your own words. Include the scientific question or domain, what outcome would be useful, any must-keep references/examples/prior outputs, any constraints or boundaries, and what might look promising at first but would actually miss the point or mislead the session.`

If there is no usable seed, ask:

`What should this research session be about? Include the scientific question or domain, what outcome would be useful, any must-keep references/examples/prior outputs, any constraints or boundaries, and what might look promising at first but would actually miss the point or mislead the session.`

Preserve the user's wording for decisive items. If the user wants an open-ended discussion instead of a sharply scoped problem, capture that explicitly rather than forcing premature precision.
</step>

<step name="optional_context_pull">
Do not auto-read project files or local documents.

Only if the user explicitly asks to include existing context, ask which exact artifact(s) should be included. Keep this bounded:

- named `GPD/` files such as `PROJECT.md`, `ROADMAP.md`, `RESEARCH.md`, or `STATE.md`
- an explicitly named local file the user wants to ground the research brief

Read only those named artifacts. Fold only decisive constraints, anchors, or framing details into the research brief. Do not silently widen scope by loading broad project context "just in case."
</step>

<step name="adaptive_clarification">
Ask only the clarification needed to draft a usable research brief and decide whether to fast-start or use the fallback launch gate.

Default to zero clarification rounds when the intake is already sufficient. Otherwise target one targeted clarification round first. Use a second clarification round only if the user explicitly wants more setup before launch or the brief would still be too risky to start without it. The goal is to tighten the brief, not to run the discussion itself.

Prioritize these gaps:

- no clear research question, confusion, or direction to examine
- no clear outcome or useful end product
- no anchor, baseline, reference, or prior output to keep visible
- no explicit constraint or boundary
- no weak point, tempting dead end, or misleading direction to keep visible

Treat execution posture and agent count as secondary intake details. Ask about them only if they would materially improve the first bounded discussion turn or the user is clearly deciding between options.

If `ask_user` is available, use it for low-cardinality choices and keep freeform follow-ups compact.

Use a conservative fast-start check after the initial intake and again after the first clarification. If the brief is now sufficient, stop clarifying, skip any unnecessary launch ceremony, and move to a short working frame for the first bounded discussion turn.

Ask at most one targeted clarification round first for the most important remaining research gap. Examples:

- outcome focus: generate hypotheses / resolve a confusion / compare candidate directions / define next research steps
- anchors: name the paper, result, example, or prior output that should stay in frame
- boundaries: say what to ignore, approximate, or refuse to optimize for
- weak points: call out the assumption, attractive dead end, or misleading analogy that should stay visible

If the intake is already strong enough to draft, do not ask extra setup questions just to fill every slot.

If preset depth would help and it is still missing or uncertain, resolve it with a compact choice:

```text
header: "Preset"
question: "What kind of first pass do you want?"
options:
- "Balanced (Recommended)" -- standard round depth with enough structure to keep the ideation grounded
- "Fast" -- shorter rounds, fewer defaults, useful when the problem is already crisp
- "Deep" -- richer, slower multi-agent exploration with more room for agents to develop and pressure-test ideas before each user checkpoint
- "Keep it flexible" -- do not lock a preset yet
```

If the number of perspectives would help and the worker count is still missing or obviously undecided, resolve it with a compact choice:

```text
header: "Agents"
question: "How many perspectives do you want in the first turn?"
options:
- "Use the default" -- let the workflow pick a preset-shaped starting count
- "I will choose a number" -- provide the exact count in the next reply
- "Keep it flexible" -- decide after seeing the draft summary
```

If execution posture is still worth resolving before the draft summary, keep it light. Example:

- posture: rigorous by default / allow looser exploration / leave posture undecided

The user may bypass further questions at any time. If they say "draft it," "good enough," or equivalent, move to the summary with the remaining gaps made explicit instead of continuing to probe.
</step>

<step name="resolve_launch_preferences">
Run this step only when the user clearly wants to shape the defaults or when a missing preference would materially change the first bounded discussion turn. Do not foreground this as a separate setup step in the happy path.

If a preference check is warranted, ask one compact freeform preference question for the execution knobs that are useful to capture now:

`Any first-pass preferences I should lock now, such as a faster or deeper pass, stronger skepticism, a looser exploratory posture, or a specific number of perspectives? If not, I will keep the defaults and leave the rest flexible.`

If the user has not asked to shape these knobs and the current brief is already sufficient, apply the defaults silently and leave them mostly backstage.

Defaults unless the user overrides them:

- preset: `balanced`
- posture: rigorous and research-oriented by default
- existing project context: not loaded unless explicitly requested
- worker count defaults:
  - `fast` -> `3`
  - `balanced` -> `4`
  - `deep` -> `5`
- default worker roster:
  - one skeptical reviewer by default in the current hard-critic slot, with high skepticism and medium creativity
  - all remaining agents are literature-aware theorists with medium skepticism and medium-to-high creativity

If the user provides partial per-agent preferences but not a full roster, preserve the explicit overrides and fill the remaining slots with these defaults.
</step>

<step name="draft_launch_summary">
Synthesize a concise pre-round working brief that preserves the user's own framing and keeps the launch light.

If the brief is sufficient for a fast start, keep the working frame internal by default on the happy path. Use it to anchor the first bounded discussion turn, but do not automatically render a visible `Working Frame` block plus a second launch restatement.

Internally preserve:

- Focus: [core question, domain, or open discussion framing]
- Outcome: [what useful result this research session should aim to produce]
- Anchors: [must-keep references, prior outputs, examples, or "None supplied yet"]
- Constraints: [scope boundaries, exclusions, or "None supplied yet"]
- Risks / Watchouts: [weakest assumptions, unresolved gaps, tempting dead ends, or misleading directions]

On the happy path, move directly into the first agent turn after one short paraphrase or launch line such as:

- `Using that framing, I am starting a first bounded discussion turn.`
- `I have enough to start, so I am moving straight into the first discussion turn.`

Only surface a visible mini-frame before the first turn if the user asks for it or if one short frame is needed to avoid a real ambiguity.

Only mention execution defaults here if the user explicitly shaped them or if one setting materially affects how the first bounded discussion turn should be interpreted. Otherwise keep preset, posture, worker count, and roster defaults backstage.

If the brief is not yet strong enough for an immediate start, render a slightly fuller but still lightweight session brief:

```markdown
## Session Brief

- Focus: [core question, domain, or open discussion framing]
- Outcome: [what useful result this research session should aim to produce]
- Anchors: [must-keep references, prior outputs, examples, or "None supplied yet"]
- Constraints: [scope boundaries, exclusions, or "None supplied yet"]
- Risks / Open Questions: [weakest assumptions, unresolved gaps, tempting dead ends, or misleading directions]
```

Include only the execution preferences that the user explicitly set or that must be surfaced because they change launch behavior. Keep the initial agent shape concise when shown.

Before any fallback gate, add one short side-effect note:

`Approving this framing starts the bounded multi-agent discussion turns, but it does not create durable session files.`
</step>

<step name="approval_gate">
Use a two-path launch rule.

If the brief is sufficient and there is no remaining risk that needs explicit user confirmation, do not present a launch menu. Do not default to a visible `Working Frame` block on the happy path. Give one short paraphrase or launch line, say you are starting the first discussion turn, and continue directly into the bounded round loop.

If the brief is incomplete, materially risky, or the user is still clearly deciding between framing options, present a lighter fallback gate for the session brief. Keep the gate light and focused on the minimum pre-first-turn decision.

If `ask_user` is available for the fallback gate:

```text
header: "Ideate Launch"
question: "This looks workable but still has a few launch choices or gaps. What do you want to do before the first turn?"
options:
- "Start"
- "Adjust"
- "Stop here"
```

If `ask_user` is not available, present the same three options as a short numbered list and wait for the user's reply.

Raw-context review remains available on demand, but do not force it as a standard visible option. If the user asks to inspect the raw context before starting:

- show the raw launch details in a more literal form: seed text, preserved phrases, imported anchors, resolved preset, worker count assumptions, per-agent overrides, and unresolved gaps
- then return to the same approval gate

On `Adjust`:

- reopen only the section the user wants to revise
- preserve all unchanged sections by default
- rebuild the summary and return to the approval gate

On `Stop here`:

- end cleanly
- say no files were created and the research brief was not finalized
- end with the standard continuation block:

```markdown
---

## > Next Up

**gpd:ideate** -- restart the session setup when you want to continue refining the brief

`gpd:ideate [topic or question]`

<sub>`/clear` first, then run `gpd:ideate [topic or question]`</sub>

---

**Also available:**
- `gpd:suggest-next` -- ask GPD for the best next move from here
- `gpd:help --all` -- inspect the current command surface

---
```

On `Start`:

- confirm that the current framing is approved for launch
- restate the final approved summary compactly
- Continue directly into the bounded round loop. Do not stop at a launch-summary-only state.
</step>

<step name="run_round_loop">
If the launch is approved, begin the conversational multi-agent research session using the current bounded round engine.

Run one bounded ideation round at a time under the hood, but present each bounded segment to the user as a conversational turn rather than a moderator-led round ceremony.
Spawn ideation workers as one-shot handoffs.
Reserve one default skeptical-reviewer / hard-critic slot unless the user overrides it.
Rounds are one-shot and use the current default hard critic unless overridden.

Keep orchestration in memory for this phase. The parent workflow owns the research brief, round counter, shared discussion, current configuration, and any fresh continuation handoff. Do not create durable ideation session files, `RESEARCH.md`, `GPD/ideation/`, or artifact directories in this phase.

Resolve the ideation-worker model through the existing profile-and-tier path before the first round:

```bash
IDEATION_WORKER_MODEL=$(gpd resolve-model gpd-ideation-worker)
```

If `IDEATION_WORKER_MODEL` is empty or `null`, omit the `model` parameter and let the runtime use its default model.

Keep the internal execution sequence parent-owned: `round_bootstrap`, `round_fanout`, `round_collect`, bounded optional reaction handling, synthesis/state update, and the user handoff still happen each cycle. Do not foreground that choreography as visible headings or make `Round 1`, `Round 2`, and so on the primary visible shape unless clarity requires a light reference.

The visible default should feel like an ongoing scientific discussion:

- agent contributions are the primary visible unit
- each active agent contributes a short research-facing message in the first pass
- after that first pass, allow one bounded optional reaction layer where an agent may respond selectively to another agent's point or stay silent
- do not add an automatic recap after a clean turn
- visible synthesis is secondary and lightweight; use it only when the user asks for it or when blocker, divergence, or routing pressure makes a short frame necessary
- end the turn with a conversational handoff instead of a rigid control menu; keep it short on clean turns

For each round:

1. Build a round brief from:
   - the approved research brief
   - the current round number
   - the shared discussion so far
   - any user-injected thoughts from the prior parent handoff
   - any per-agent assignments the user has locked
   - current preset and posture settings
2. Decide the round lanes. If the user left the count flexible, choose a bounded lane count that matches the current preset. Keep one lane reserved as the hard critic by default unless the user explicitly overrides it.
3. Fan out the configured ideation agents. Use the same ideation-worker surface for all lanes, varying prompt-level posture, skepticism, creativity, and assignment instructions as needed.
   If you are the hard critic, pressure-test assumptions, contradictions, missing baselines, and weak causal stories.
4. Require each worker to return a typed `gpd_return` envelope with shareable ideas, critiques, open questions, and `gpd_return.status`. Completed lanes feed parent-owned synthesis/state updates. Any `checkpoint`, `blocked`, or `failed` lane becomes a parent-owned ambiguity for the turn handoff. No worker waits for user input in place.
5. Surface the first-pass agent messages first. Each active agent should visibly contribute a short message that feels like a participant in the discussion, not a hidden lane feeding an orchestrator summary. Do not follow that exchange with an automatic recap after a clean turn.
6. Add one bounded optional reaction layer. After the first pass, allow an agent to respond selectively to another agent's point when doing so sharpens a disagreement, reinforces a convergence, or corrects a weak assumption. Do not require every agent to react, and do not allow open-ended back-and-forth beyond this single bounded layer.
7. Keep synthesis secondary. Maintain parent-owned synthesis/state updates each cycle so routing, continuity, subgroup setup, and fresh continuation semantics stay intact, but do not emit a default recap after a clean turn. Surface visible synthesis only when the user asks, when a blocker or checkpoint needs routing, or when agent output diverges enough that a short frame is necessary. When shown mid-session, keep it brief and place it after the agent messages and any reactions.
8. End each turn with a lightweight conversational handoff centered on: continue, add or redirect with user thoughts, adjust configuration, ask for synthesis, or stop cleanly. Temporary subgroup work remains available through the configuration-adjustment path when the user asks for it. Raw worker detail remains available only when the user explicitly asks for it.
9. If the turn is ambiguous or a worker returns a checkpoint-worthy blocker, surface that ambiguity in the conversational handoff instead of letting a worker linger.

When using task delegation, keep it lightweight and parent-owned. Reuse the repo's one-shot handoff semantics:

@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

> If subagent spawning is unavailable, execute these steps sequentially in the main context.

```text
task(
  subagent_type="gpd-ideation-worker",
  model="{IDEATION_WORKER_MODEL}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-ideation-worker.md for your role and instructions.

<objective>
Contribute one bounded agent perspective for discussion turn {round_number} of this projectless research session.
</objective>

<context>
Approved research brief: {launch_brief}
Current round brief: {round_brief}
Shared discussion so far: {shared_discussion}
Lane instructions: {lane_instructions}
</context>

<contract>
This is a one-shot handoff. Return a typed `gpd_return` envelope with shareable ideas, critiques, open questions, and `gpd_return.status`. If human input is required, return `gpd_return.status: checkpoint` and stop. Do not wait in place. The parent orchestrator owns any fresh continuation handoff.
</contract>",
  description="Research turn {round_number}: {lane_role}"
)
```

Do not add spawn-contract blocks for Phase 2. Do not rely on file-writing freshness checks in this phase. Child work is fileless and return-only here.
Do not create files or claim durable session ownership in this phase.
</step>

<step name="round_review_gate">
After each conversational turn, keep the user handoff light and natural. Agent messages should already be on screen. On a clean turn, default to a short natural handoff with no recap. If a brief synthesis is helpful, make it compact, secondary, and request-driven or exception-driven. Raw turn details remain available only on demand. Subgroup creation happens only from this parent handoff, not mid-turn.

Do not present a rigid fixed menu by default. Instead, end with a conversational handoff that makes these capabilities available in natural language:

- continue to the next bounded turn
- add or redirect with the user's own thoughts
- adjust configuration
- ask for synthesis
- stop

Interpretation:

- continue: increment the round counter and run the next bounded ideation round under the hood
- add or redirect: capture the user's injection, restate how it changes the shared discussion, and include it in the next turn brief
- adjust configuration: capture only the requested changes such as preset, agent count, posture, skepticism, creativity, per-agent assignments, or a temporary subgroup batch for the next bounded segment; preserve everything else
- ask for synthesis: show one compact synthesis keyed to the current turn, then return to the same conversational handoff
- stop: stop cleanly without claiming durable persistence
- raw details on demand: if the user explicitly asks, show the raw worker takeaways plus any compact synthesized view, then return to the same conversational handoff

If the user explicitly asks to pause instead of stopping, pause or stop cleanly without claiming durable persistence.

Prefer handoff language such as:

- `If you want, I can keep pushing on this line, fold in your reaction, retune the setup, give a short synthesis, or stop here.`
- `If you want to redirect, tell me what to change and I will rebuild the next brief from there.`

If the user adds thoughts or adjusts configuration, treat that as a fresh continuation rather than resuming workers in place.
Rebuild the next turn brief from the approved research brief, prior turn syntheses, and the new user input, then spawn a fresh set of one-shot workers. Do not resume a prior child run.

If a turn is ambiguous or a worker returns a checkpoint-worthy blocker, surface the ambiguity at the parent handoff instead of letting a worker linger.
</step>

<step name="subgroup_micro_loop">
Subgroups are optional focused breakouts and only user-initiated from the existing parent handoff. Do not create them at launch, mid-worker, or automatically. Route subgroup setup through the configuration-adjustment path so the main handoff stays stable. Only create subgroups from the parent handoff after the current turn's agent exchange.

When the user asks for subgroup work through the configuration-adjustment path:

1. confirm the subgroup objective in one compact prompt
2. confirm the subgroup members by stable lane labels such as `Agent 1`, `Agent 2`, and `Agent 3`
3. confirm the bounded subgroup round count

Keep one active subgroup batch at a time in this phase. Treat it as a temporary parent-owned configuration change inside the current research session, not as a new top-level ideation path. Do not route subgroup formation through launch intake, worker-local decisions, or any mid-worker branch.

Subgroup defaults and boundaries:

- subgroup rounds must stay bounded; default to `2` if the user does not specify a count
- keep each subgroup batch to `1-3` rounds in this phase
- if the user wants more subgroup exploration after that, return to the parent handoff and let them launch another subgroup batch explicitly

While a subgroup batch is active:

- Pause the main group while the subgroup runs.
- pause main-loop progression
- keep the parent workflow responsible for subgroup state, synthesis, and any checkpoint routing
- build each subgroup round brief from the approved research brief, the relevant slice of shared discussion, the subgroup objective, any locked assignments, and any user-specified subgroup instructions
- reuse `gpd-ideation-worker` for subgroup lanes
- reuse fresh one-shot `gpd-ideation-worker` handoffs for subgroup lanes; do not create a long-lived child conversation
- subgroup workers remain one-shot handoffs
- Do not keep a long-lived subgroup child conversation.
- if a subgroup lane needs user input, surface it at the parent handoff as a fresh continuation rather than waiting in place

Subgroup execution stays fileless in this phase. Do not add `<spawn_contract>` blocks, do not create durable subgroup transcripts, and do not claim subgroup resumability, subgroup promotion, or independent subgroup sessions. Subgroups stay inside the parent ideation run in this phase. Do not promote a subgroup into its own session in this phase. Do not create durable subgroup artifacts or promotion surfaces in this phase. Do not promise durable subgroup transcripts, promotion, spawn contracts, resumable subgroup persistence, dedicated ideation state, or ideation files in this phase.

At subgroup completion, synthesize one compact breakout recap instead of replaying raw subgroup transcripts. Rejoin is summary-only in this phase. Reintegrate only a subgroup summary into the main shared discussion. The breakout recap should include:

- subgroup objective
- subgroup members
- subgroup rounds completed
- strongest idea or hypothesis
- strongest critique or failure mode
- what changed for the main discussion
- the remaining open question or recommended next focus

Fold only that subgroup summary into the main shared discussion, then return to the normal parent handoff. Do not auto-start the next main round after subgroup completion.
</step>

<step name="session_finish">
When the user stops, end with one compact structured closeout summary. Keep it lightweight and conversational, but make the structure explicit with short labeled bullets or equivalent headings that cover:

- main ideas explored
- unresolved disagreements or confusions
- promising next steps
- open questions
- suggested follow-up actions

This projectless research-session closeout is in-memory only. Do not add or imply durable ideation history, session IDs, subgroup transcripts, resumable session files, tags, imported-document state, archived artifacts, or any save-resume-session-management machinery.

Immediately after the summary, ask this exact short closing question:

`What do you want to do next?`

Then offer a short list of only the most relevant GPD follow-up actions for the session outcome, such as:

- `gpd:suggest-next`
- `gpd:ideate [topic or question]`
- `gpd:new-project`
- `gpd:help --all`

Also say plainly that the user can ask for a non-GPD next step instead if that is more useful.

End with:

```markdown
---

## > Next Up

**gpd:suggest-next** -- ask GPD for the best next move from here

`gpd:suggest-next`

<sub>`/clear` first, then run `gpd:suggest-next`</sub>

---

**Also available:**
- `gpd:ideate [topic or question]` -- run another research session or revise the brief
- `gpd:new-project` -- turn a strong direction into a project-backed workflow
- `gpd:help --all` -- inspect the current command surface

---
```
</step>

<step name="typed_return_discipline">
Keep the ideation loop aligned with repo-native orchestration rules:

- parent workflow owns the continuation and the user gates
- ideation workers are one-shot handoffs
- route on typed `gpd_return.status`
- do not let a worker wait in place for user input
- if user input is required, surface it at the parent handoff and spawn a fresh worker on the next turn

Human-readable labels in worker text are presentation only. Do not route on them.
</step>

</process>

<success_criteria>
- [ ] The workflow frames `gpd:ideate` as a projectless conversational multi-agent research session before any durable project workflow
- [ ] Existing project context remains opt-in and is never auto-loaded into the session
- [ ] The orchestrator stays mostly backstage, with clean turns defaulting to agent exchange plus a short natural handoff
- [ ] A strong first message can reach the first bounded discussion turn with substantially less launch ceremony and no default visible launch frame on the happy path
- [ ] When the brief is already sufficient, defaults stay mostly backstage unless the user asks to shape them
- [ ] A lighter pre-round brief still preserves focus, outcome, anchors, constraints, and key risks
- [ ] Revise and stop paths still exist before the first turn when the framing needs explicit confirmation
- [ ] Raw-context review stays available on demand without being a mandatory front-stage launch option
- [ ] The working research brief leads into a bounded multi-agent turn loop with the bounded round engine kept internal
- [ ] The `Deep` preset implies richer agent exploration rather than guaranteed orchestrator synthesis
- [ ] One hard critic is present by default unless the user changes the roster
- [ ] Agent contributions are the primary visible unit of each turn
- [ ] One bounded optional reaction layer is available inside a turn without opening unbounded back-and-forth
- [ ] There is no automatic recap after a clean turn, and visible synthesis is on-demand or exception-driven when routing pressure makes it necessary
- [ ] User thought injection happens at turn boundaries through the parent handoff
- [ ] Per-agent assignments can be updated between turns without restarting the session
- [ ] Optional subgroup work stays parent-owned, bounded, fileless, and summary-first on rejoin
- [ ] The conversational handoff preserves continue, add or redirect, adjust configuration, ask for synthesis, and stop, while raw details stay available on demand without a rigid menu
- [ ] Raw details remain available on demand and do not return as a default visible handoff affordance
- [ ] Stopping the session yields a structured summary, an explicit what-next prompt, and relevant GPD follow-up suggestions while allowing non-GPD next steps
- [ ] The workflow stays fileless for ideation and subgroup state in this phase
- [ ] No `RESEARCH.md`, `GPD/ideation/`, durable ideation history, session IDs, transcript storage or replay, resumable session files, tags, imported-document state, subgroup promotion, or archived artifacts.
</success_criteria>
