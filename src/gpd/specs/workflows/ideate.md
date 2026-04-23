<purpose>
Run `gpd:agentic-discussion` as a projectless conversational multi-agent research session for exploring, pressure-testing, and refining a research direction before committing to durable project artifacts.

Phase 2 keeps that contract and its non-goals while pushing the orchestrator further backstage and making cheap research operations first-class inside the same bounded parent-owned engine. Preserve the bounded parent-owned round engine under the hood, but make clean turns read as agent-first conversation: keep the fast-start path light, keep launch preferences conditional and mostly off-screen, show agent exchange first, allow one bounded optional reaction layer, default clean turns to open continuation unless the user interrupts or a blocker/checkpoint needs routing, and end with a short natural handoff instead of a visible moderator loop. Visible summaries, recaps, and raw-detail review are secondary and should surface only when the user asks, when a blocker or checkpoint needs routing, when agent output diverges enough to need a short frame, or at session close. Preserve structured closeout, any optional narrower follow-up as a light parent-owned extension of the current turn, and the parent workflow's ownership of the research brief, round state, follow-up routing, and any fresh continuation handoff.

Keep the boundary explicit from the start: project context is opt-in only, orchestration stays in memory, and this phase does not create durable ideation files or session artifacts. Non-goals for this phase include `RESEARCH.md` writes, `GPD/ideation/`, durable ideation artifact directories, resumable ideation session state, `resume-work` integration, staged init or stage-manifest semantics, automatic project-state ingestion, session IDs, transcript storage or replay, and promotion of temporary focused follow-up into durable sessions.
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

If participant count would help and the first-turn group size is still missing or obviously undecided, resolve it with a compact choice:

```text
header: "Participants"
question: "How many participants do you want in the first turn?"
options:
- "Use the default" -- start with the default two-participant cast: `Literature-Aware Skeptic` and `Technical Calculator`
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

`Any first-pass preferences I should lock now, such as a faster or deeper pass, stronger skepticism, a looser exploratory posture, or whether you want to override the default two-role cast? If not, I will keep the defaults and leave the rest flexible.`

If the user has not asked to shape these knobs and the current brief is already sufficient, apply the defaults silently and leave them mostly backstage.

Defaults unless the user overrides them:

- preset: `balanced`
- posture: rigorous and research-oriented by default
- existing project context: not loaded unless explicitly requested
- participant setup default:
  - keep the default cast backstage unless the user asks to shape it: default participant count is `2`, and the default cast is exactly two roles, `Literature-Aware Skeptic` and `Technical Calculator`
  - use the full role names on first appearance; after that, use `Skeptic` and `Calculator` as the recurring short labels
  - keep internal posture diversity by default so the discussion includes both pressure-testing and exploratory idea generation unless the user overrides it
  - preserve optional tuning for participant count, skepticism, creativity, and specialization when the user wants to shape them

If the user provides partial participant or stance preferences but not a full setup, preserve the explicit overrides and fill the remaining discussant mix with these defaults.
</step>

<step name="draft_launch_summary">
Synthesize a concise pre-round working brief that preserves the user's own framing and keeps the launch light.

If the brief is sufficient for a fast start, keep the working frame internal by default on the happy path. Use it to anchor the first bounded discussion turn, but do not automatically render a visible `Working Frame` block plus a second launch restatement.
The visible happy path should read like the start of a transcript, not like the user is stepping through a launch menu.

Internally preserve:

- Focus: [core question, domain, or open discussion framing]
- Outcome: [what useful result this research session should aim to produce]
- Anchors: [must-keep references, prior outputs, examples, or "None supplied yet"]
- Constraints: [scope boundaries, exclusions, or "None supplied yet"]
- Risks / Watchouts: [weakest assumptions, unresolved gaps, tempting dead ends, or misleading directions]

On the happy path, move directly into the first agent turn after one short paraphrase or launch line such as:

- `Using that framing, I am opening the discussion.`
- `Using that framing, I am starting a first bounded discussion turn.`
- `I have enough to start, so I am moving straight into the first discussion turn.`

Only surface a visible mini-frame before the first turn if the user asks for it or if one short frame is needed to avoid a real ambiguity.

Only mention execution defaults here if the user explicitly shaped them or if one setting materially affects how the first bounded discussion turn should be interpreted. Otherwise keep preset, posture, participant count, and participant-mix defaults backstage.

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

`Approving this framing starts the first bounded multi-agent discussion turn, but it does not create durable session files.`
</step>

<step name="approval_gate">
Use a two-path launch rule.

If the brief is sufficient and there is no remaining risk that needs explicit user confirmation, do not present a launch menu. Do not default to a visible `Working Frame` block on the happy path. Give one short paraphrase or launch line, say you are starting the first discussion turn, and continue directly into the bounded round loop.
The happy path should feel like opening the transcript, not like asking the user to choose from a menu.

If the brief is incomplete, materially risky, or the user is still clearly deciding between framing options, present a lighter fallback gate for the session brief. Keep the gate light and focused on the minimum pre-first-turn decision.

If `ask_user` is available for the fallback gate:

```text
header: "Ideate Launch"
question: "This looks workable but still has a few launch choices or gaps. What do you want to do before the first discussion turn begins?"
options:
- "Start"
- "Adjust"
- "Stop here"
```

If `ask_user` is not available, present the same three options as a short numbered list and wait for the user's reply.

Raw-context review remains available on demand, but do not force it as a standard visible option. If the user asks to inspect the raw context before starting:

- show the raw launch details in a more literal form: seed text, preserved phrases, imported anchors, resolved preset, default cast assumptions, visible transcript labels, per-agent overrides, and unresolved gaps
- then return to the same approval gate

On `Adjust`:

- reopen only the section the user wants to revise
- preserve all unchanged sections by default
- rebuild the summary and return to the same approval gate without spawning workers yet

On `Stop here`:

- end cleanly
- say no files were created and the research brief was not finalized
- if a next move would help, suggest only the most relevant one in context, such as restarting `gpd:agentic-discussion`, asking `gpd:suggest-next`, or simply leaving it there

On `Start`:

- confirm that the current framing is approved for launch
- restate the final approved summary compactly
- continue directly into the bounded round loop and spawn fresh one-shot workers for the first transcript-style turn
- do not stop at a launch-summary-only state, and do not leave a worker waiting for user input in place
</step>

<step name="run_round_loop">
If the launch is approved, begin the conversational multi-agent research session using the current bounded round engine.

Run one bounded research turn at a time under the hood, but present each bounded segment to the user as a conversational turn rather than a moderator-led round ceremony.
Spawn ideation workers as one-shot handoffs.
Maintain internal posture diversity, including a skeptical pass when useful, unless the user overrides it.
Rounds are one-shot and use the current internal stance mix unless overridden.

Keep orchestration in memory for this phase. The parent workflow owns the research brief, round counter, shared discussion, current configuration, and any fresh continuation handoff. Do not create durable ideation session files, `RESEARCH.md`, `GPD/ideation/`, or artifact directories in this phase.

Resolve the ideation-worker model through the existing profile-and-tier path before the first round:

```bash
IDEATION_WORKER_MODEL=$(gpd resolve-model gpd-ideation-worker)
```

If `IDEATION_WORKER_MODEL` is empty or `null`, omit the `model` parameter and let the runtime use its default model.

Keep the internal execution sequence parent-owned: `round_bootstrap`, `round_fanout`, `round_collect`, bounded optional reaction handling, synthesis/state update, and the user handoff still happen each cycle. Do not foreground that choreography as visible headings or make `Round 1`, `Round 2`, and so on the primary visible shape unless clarity requires a light reference.

The visible default should feel like an ongoing scientific discussion between the two default participants, `Literature-Aware Skeptic` and `Technical Calculator`:

- agent contributions are the primary visible unit
- use the full role names on first appearance; recurring transcript labels use `Skeptic` and `Calculator`
- visible clean-turn render semantics are transcript-first: a completed participant may `speak` with a direct contribution, `ask` a natural question that still counts as completed-turn content, or `skip` with a brief explicit nothing-new-to-add; these are render semantics only and do not change `gpd_return.status`
- each active agent contributes a short research-facing message in the first pass, and those visible first-pass messages may be grounded hypotheses, literature results, evidence checks, or bounded calculation results rather than commentary alone
- if a claim is cheaply checkable, at least one participant should check it with the lightest suitable tool instead of leaving every contribution in speculative discussion
- after that first pass, allow one bounded optional reaction layer where an agent may respond selectively to another agent's point or stay silent
- do not add an automatic recap after a clean turn
- visible synthesis is secondary and lightweight; use it only when the user asks for it or when blocker, divergence, or routing pressure makes a short frame necessary
- on a clean turn, default the visible close to open continuation unless the user interrupts, redirects, or a blocker/checkpoint requires a more explicit routing question
- end the turn with a conversational handoff instead of a rigid control menu; keep it short on clean turns

For each round:

1. Build a round brief from:
   - the approved research brief
   - the current round number
   - the shared discussion so far
   - any user-injected thoughts from the prior parent handoff
   - any per-agent assignments the user has locked
   - current preset and posture settings
   - any research guidance already present in context, such as `research_enabled`, `research_mode`, or soft source/tool-use limits
2. Decide the round participants. If the user left the count flexible, default participant count is `2`: `Literature-Aware Skeptic` and `Technical Calculator`. Maintain internal posture diversity by default unless the user explicitly overrides it. If a material claim is cheaply checkable, assign at least one participant to run the check rather than leaving the point purely conversational.
3. Fan out the configured ideation agents. Use the same ideation-worker surface for all participants, varying prompt-level posture, skepticism, creativity, and assignment instructions as needed. Unless the user overrides the cast, keep the default participant roles explicit at this seam: `Literature-Aware Skeptic` and `Technical Calculator`.
   If one participant is carrying the strongest skeptical stance for the turn, use that stance to pressure-test assumptions, contradictions, missing baselines, and weak causal stories without foregrounding it as a special visible panel role.
4. Require each worker to return a typed `gpd_return` envelope with structured `research_contributions` plus `gpd_return.status`. Contributions may include grounded hypotheses, critiques, evidence checks, computational checks, questions, next probes, or direct responses to earlier agent output when that materially advances, clarifies, or pressure-tests the discussion. Substantive items should distinguish `sourced`, `computed`, `speculative`, or `mixed` provenance when the worker can support that distinction. Failed or partial lookups and calculations should remain explicit in the returned contribution rather than being silently dropped. Completed participants feed parent-owned synthesis/state updates. Keep `speak` / `ask` / `skip` as visible-turn render semantics inside completed-turn content rather than as new runtime statuses. Any `checkpoint`, `blocked`, or `failed` participant becomes a parent-owned ambiguity for the turn handoff. No worker waits for user input in place.
5. Surface the first-pass agent messages first. Each active agent should visibly contribute a short message that feels like a participant in the discussion, not a hidden lane feeding an orchestrator summary. Render those first-pass messages as direct transcript turns with minimal stage directions, use the full role names on first appearance, and use `Skeptic` / `Calculator` thereafter for the default cast. Literature results, evidence checks, and bounded computational checks belong in that first visible exchange when they materially resolve uncertainty. Do not follow that exchange with an automatic recap after a clean turn.
6. Add one bounded optional reaction layer. After the first pass, allow an agent to respond selectively to another agent's point when doing so sharpens a disagreement, reinforces a convergence, or corrects a weak assumption. Do not require every agent to react, and do not allow open-ended back-and-forth beyond this single bounded layer.
7. Keep synthesis secondary. Maintain parent-owned synthesis/state updates each cycle so routing, continuity, optional focused follow-up setup, and fresh continuation semantics stay intact, but do not emit a default recap after a clean turn. Surface visible synthesis only when the user asks, when a blocker or checkpoint needs routing, or when agent output diverges enough that a short frame is necessary. When shown mid-session, keep it brief and place it after the agent messages and any reactions.
8. End each turn with a lightweight conversational handoff centered on open continuation by default. The workflow-owned priority rule at that handoff is `user interruption > pending agent follow-up > default continuation`. On clean turns, any new user reaction, redirect, setup adjustment, synthesis request, pause, or stop instruction takes priority over any pending follow-up. If the user does not interrupt and no checkpoint, blocker, or user-requested narrow follow-up needs routing, leave the turn open and ready to continue. Keep those capabilities available in natural language instead of surfacing them as a front-stage menu unless clarity really requires it. If the user wants narrower follow-up after the turn, route it through the configuration-adjustment path and run at most one bounded focused fan-out or targeted check before folding the result back into the parent discussion. Raw worker detail remains available only when the user explicitly asks for it.
9. If the turn is ambiguous or a worker returns a checkpoint-worthy blocker, surface that ambiguity in the conversational handoff instead of letting a worker linger or pretending the normal open-continuation default still applies.

When using task delegation, keep it lightweight and parent-owned. Reuse the repo's one-shot handoff semantics:

@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

> If subagent spawning is unavailable, degrade explicitly to a clearly labeled single-context pass in the main context. In that fallback, keep the pass useful with shell/file-grounded checks, but do not present fresh web or literature/source checks as completed unless the main context actually has the worker-equivalent web tools needed to perform them.

```text
task(
  subagent_type="gpd-ideation-worker",
  model="{IDEATION_WORKER_MODEL}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-ideation-worker.md for your role and instructions.

<objective>
Contribute one bounded research contribution set for discussion turn {round_number} of this projectless research session.
</objective>

<context>
Approved research brief: {launch_brief}
Current round brief: {round_brief}
Shared discussion so far: {shared_discussion}
Participant instructions: {lane_instructions}
</context>

<contract>
This is a one-shot handoff. Return a typed `gpd_return` envelope with structured `research_contributions` plus `gpd_return.status`. Use typed contributions such as `hypothesis`, `critique`, `evidence_check`, `computational_check`, `clarifying_question`, or `next_probe`; respond directly to earlier agent output when useful; include confidence and `responds_to` or `decisive_check` when they materially help. For visible rendering, make completed-turn content easy to surface as one of three transcript-first shapes: direct contribution (`speak`), natural question (`ask`), or explicit nothing-new-to-add (`skip`). These are render semantics only; keep `gpd_return.status` unchanged, and keep non-blocking questions inside normal completed-turn content rather than promoting them to `checkpoint`. Treat `web_search`, `web_fetch`, and `shell` as first-class inline research instruments for this turn when they materially improve the contribution. Prefer the lightest tool that can settle the question. Use `web_search` for recent or unstable claims, candidate sources, benchmarks, or opposing evidence; use `web_fetch` before making source-specific or citation-bearing claims; use `shell` for bounded calculations, estimates, unit conversions, or tiny inline scripts. If a claim is cheaply checkable, check it instead of only discussing it. Keep tool use inline and fileless.

For each substantive item, distinguish whether it is `sourced`, `computed`, `speculative`, or `mixed`, and include optional `source_refs`, `computation_note`, or `assumptions` when they materially clarify what the item rests on. If the round context includes `research_enabled`, `research_mode`, or soft source/tool-use limits, treat them as guidance for scope and depth rather than as a reason to widen the turn.

If web search or fetch fails, a source is paywalled or garbled, `shell` is unavailable, a binary/interpreter/library is missing, or a calculation cannot be completed trustworthily, say so explicitly, lower confidence or mark the item partial, `blocked`, or `checkpoint` as appropriate, and never pretend the check succeeded. Do not install packages or write helper files to rescue a one-shot ideation turn.

If human input is required, return `gpd_return.status: checkpoint` and stop. Do not wait in place. The parent orchestrator owns any fresh continuation handoff.
</contract>",
  description="Research turn {round_number}: participant stance"
)
```

If the quoted delegation note forces a main-context fallback, label that turn plainly as a `single-context fallback` so the user can distinguish it from the normal worker-backed path. In that fallback:

- keep the turn bounded and useful with local shell checks, repo/file inspection, and other tools actually present in the parent context
- treat fresh literature, source-validation, and opposing-evidence checks as provisional or deferred unless the parent context can really perform them with available web tools
- do not claim a fresh web search, source fetch, literature scan, or citation-bearing check was completed when the main context lacks the worker's `web_search` / `web_fetch` surface
- preserve honesty in visible agent-style output by naming the degraded mode and carrying forward any resulting confidence downgrade or unresolved verification gap
- prefer explicit wording such as `single-context fallback: shell/file-grounded pass only` when that is the real capability boundary for the turn

Do not add spawn-contract blocks in this phase. Do not rely on file-writing freshness checks in this phase. Child work is fileless and return-only here.
Do not create files or claim durable session ownership in this phase.
</step>

<step name="round_review_gate">
After each conversational turn, keep the user handoff light and natural. Agent messages should already be on screen. On a clean turn, default to a short natural handoff with no recap. If a brief synthesis is helpful, make it compact, secondary, and request-driven or exception-driven. Raw turn details remain available only on demand. Any narrower follow-up happens only from this parent handoff, not mid-turn.
On a clean turn, the visible default is open continuation. If the user replies with a normal reaction, follow-up thought, or new angle, treat that as continuation rather than asking them to explicitly say `continue`.

Do not present a rigid fixed menu by default. Do not end clean turns with a visible capability list unless clarity requires it. The workflow-owned priority rule at this handoff is `user interruption > pending agent follow-up > default continuation`.

Interpret the handoff in that order:

- user interruption: any normal reaction, follow-up thought, redirect, setup adjustment, request for synthesis, raw-detail request, pause, or stop instruction overrides any pending agent-side follow-up and becomes the next parent-owned action
- pending agent follow-up: if the turn surfaced a checkpoint-worthy blocker or the user explicitly asked for one narrow focused follow-up or targeted check, route that next from the parent handoff with fresh one-shot workers; do not leave a worker waiting in place
- default continuation: only when the user has not interrupted and no pending follow-up needs routing should the clean-turn default remain open; in that case, increment the round counter and run the next bounded ideation turn under the hood without asking for an explicit menu choice

If the user adds thoughts or redirects, capture the injection, restate how it changes the shared discussion, and include it in the next turn brief.
If the user tunes the setup, capture only the requested changes such as preset, participant count, posture, skepticism, creativity, per-participant assignments, or one temporary focused follow-up or selective fan-out for the next bounded segment; preserve everything else.
If the user asks for synthesis, show one compact synthesis keyed to the current turn, then return to the same conversational handoff.
If the user explicitly asks for raw details, show the raw worker takeaways plus any compact synthesized view, then return to the same conversational handoff.
If the user wants to stop or pause, stop or pause cleanly without claiming durable persistence.

Prefer handoff language such as:

- `I can keep going from here. If you want to redirect, ask for a short synthesis, change the setup, or stop, just say so.`
- `If you want to change the direction, tell me what to change and I will rebuild the next brief from there.`

If the user adds thoughts or adjusts configuration, treat that as a fresh continuation rather than resuming workers in place.
Rebuild the next turn brief from the approved research brief, prior turn syntheses, and the new user input, then spawn a fresh set of one-shot workers. Do not resume a prior child run.

If a turn is ambiguous or a worker returns a checkpoint-worthy blocker, surface the ambiguity at the parent handoff instead of letting a worker linger.
</step>

<step name="focused_follow_up_note">
Do not run a dedicated subgroup mode as part of the default workflow contract.

If the user asks for a narrower follow-up after a turn, route it through the normal adjustment path from the parent handoff. Keep that follow-up user-initiated, parent-owned, bounded, and fileless. Run at most one short focused fan-out or targeted check using fresh one-shot workers, then fold the result back as a short reintegration note rather than a dedicated subgroup artifact or transcript.

Do not create a separate subgroup session, long-lived child conversation, durable file, resumable state, or promotion path. Keep the main turn loop paused only for the duration of that bounded follow-up, then return to the same parent handoff with the summary-first reintegration note and any remaining open question or next probe.
</step>

<step name="session_finish">
When the user stops, end cleanly and keep the stop path lighter by default.

If the user simply wants to stop, close in a short conversational way. A brief natural wrap-up is enough. Do not force a compact structured closeout summary, a fixed closing question, or a fixed `Next Up` block every time.

Offer a compact summary when it would help, when the user asks for one, or when the discussion surfaced enough divergence, uncertainty, or useful traction that a short synthesis would materially improve the handoff. When you do provide a structured closeout summary, keep it lightweight and conversational and use only the structure that fits the moment. Typical useful elements include:

- main ideas explored
- unresolved disagreements or confusions
- promising next steps
- open questions
- suggested follow-up actions

Keep next moves available rather than mandatory. Ask what the user wants to do next when that is useful, but do not pin every stop to one exact closing question. A direct handoff like "What do you want to do next?" remains available as a strong default when that explicit handoff helps.

If suggesting follow-up actions, offer only the most relevant ones for the session outcome. Keep them concise and context-sensitive. Suggestions may include:

- `gpd:suggest-next`
- `gpd:agentic-discussion [topic or question]`
- `gpd:new-project` only when the discussion has stabilized enough for durable project scaffolding
- `gpd:research-phase` only when the user already has a project phase and wants artifacted phase research
- `gpd:help --all`

Also keep non-GPD next moves available when that is more useful than another command, and say plainly that the user can ask for a non-GPD next step instead if that is more useful.

This projectless research-session closeout remains in-memory only. Keep the non-durable boundary explicit, but do not let it dominate the stop UX. Do not add or imply durable ideation history, session IDs, focused-follow-up transcripts, resumable session files, tags, imported-document state, archived artifacts, or any save-resume-session-management machinery.
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
- [ ] The workflow frames `gpd:agentic-discussion` as a projectless conversational multi-agent research session before any durable project workflow
- [ ] Existing project context remains opt-in and is never auto-loaded into the session
- [ ] The orchestrator stays mostly backstage, with clean turns defaulting to agent exchange plus a short natural handoff
- [ ] Clean turns default to open continuation, so the user can keep engaging without selecting an explicit menu option
- [ ] A strong first message can reach the first bounded discussion turn with substantially less launch ceremony and no default visible launch frame on the happy path
- [ ] When the brief is already sufficient, defaults stay mostly backstage unless the user asks to shape them
- [ ] A lighter pre-round brief still preserves focus, outcome, anchors, constraints, and key risks
- [ ] Revise and stop paths still exist before the first turn when the framing needs explicit confirmation
- [ ] Raw-context review stays available on demand without being a mandatory front-stage launch option
- [ ] The working research brief leads into a bounded multi-agent turn loop with the bounded round engine kept internal
- [ ] The `Deep` preset implies richer agent exploration rather than guaranteed orchestrator synthesis
- [ ] The default participant mix preserves some skeptical pressure-testing unless the user changes the setup
- [ ] Agent contributions are the primary visible unit of each turn
- [ ] Visible clean-turn render semantics allow direct contributions, natural questions, or explicit skips without changing runtime statuses
- [ ] Cheaply checkable claims are normalized as visible first-pass evidence or computational contributions rather than discussion-only commentary
- [ ] First-pass visible agent messages may surface literature results, evidence checks, or bounded calculations, not only commentary
- [ ] Worker-facing turn contracts use structured `research_contributions` plus `gpd_return.status` instead of legacy idea/critique/open-question fields, and they distinguish `sourced`, `computed`, `speculative`, or `mixed` items when supported
- [ ] One bounded optional reaction layer is available inside a turn without opening unbounded back-and-forth
- [ ] Workers may respond directly to prior agent output when that materially advances, clarifies, or pressure-tests the discussion
- [ ] Worker-facing turn contracts make `web_search`, `web_fetch`, and `shell` normal inline options when they materially improve the turn, while keeping tool use fileless and bounded
- [ ] If subagent spawning is unavailable, the workflow degrades to a clearly labeled single-context fallback instead of silently implying the normal worker-backed research surface
- [ ] In a single-context fallback that lacks worker web tools, fresh web or literature/source checks are marked provisional or deferred rather than presented as completed
- [ ] Failed lookups, paywalls, missing tools, and untrustworthy calculations are surfaced honestly with downgraded confidence or typed blocker status rather than being implied away
- [ ] There is no automatic recap after a clean turn, and visible synthesis is on-demand or exception-driven when routing pressure makes it necessary
- [ ] User thought injection happens at turn boundaries through the parent handoff
- [ ] Per-agent assignments can be updated between turns without restarting the session
- [ ] Optional focused follow-up stays parent-owned, bounded, fileless, and summary-first when folded back into the main discussion
- [ ] The conversational handoff preserves continue, add or redirect, setup tuning, ask for synthesis, and stop, while raw details stay available on demand without a rigid menu
- [ ] Raw details remain available on demand and do not return as a default visible handoff affordance
- [ ] Stopping the session stays lightweight by default, with compact closeout or next-move suggestions used only when they materially help and non-GPD next steps still allowed
- [ ] The workflow stays fileless for ideation and temporary focused follow-up state in this phase
- [ ] No `RESEARCH.md`, `GPD/ideation/`, durable ideation history, session IDs, transcript storage or replay, resumable session files, tags, imported-document state, promotion of temporary focused follow-up into durable sessions, or archived artifacts.
</success_criteria>
