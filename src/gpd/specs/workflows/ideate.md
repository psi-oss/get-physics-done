<purpose>
Launch an ideation session through interactive intake, preset selection, and an editable launch summary.

This phase is deliberately narrow: prepare the ideation brief and execution posture cleanly, but do not run the multi-agent ideation loop yet, do not create durable session artifacts, and do not auto-load existing `GPD/` project context unless the user explicitly asks for named files or artifacts.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="orient_and_parse" priority="first">
Open with one short plain-English line:

`Phase 1 sets up the ideation launch: I will clarify the problem, preview the execution shape, and ask for approval before any ideation begins.`

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

- If `SEED_TEXT` is non-empty, briefly repeat it back as the current ideation seed.
- If `PRESET` is non-empty, say you will treat it as the initial launch preset unless the user edits it.
- If `HAS_GPD_PROJECT=true`, add one sentence: `I can use existing GPD project context if you want, but I will not pull it in automatically.`
- Always add one explicit phase-boundary sentence: `This phase stops after the launch summary. It does not yet run the multi-agent ideation loop or write files.`
</step>

<step name="capture_core_brief">
Ask for one dense freeform brief in the user's own words.

If `SEED_TEXT` is usable, weave it into the prompt rather than restarting from scratch:

`Using "{SEED_TEXT}" as the starting point, give me the ideation brief in your own words. Include the scientific question or domain, what outcome would be useful, any must-keep references/examples/prior outputs, any constraints or boundaries, and what would count as real progress versus false progress.`

If there is no usable seed, ask:

`What should this ideation session be about? Include the scientific question or domain, what outcome would be useful, any must-keep references/examples/prior outputs, any constraints or boundaries, and what would count as real progress versus false progress.`

Preserve the user's wording for decisive items. If the user wants an open-ended discussion instead of a sharply scoped problem, capture that explicitly rather than forcing premature precision.
</step>

<step name="optional_context_pull">
Do not auto-read project files or local documents.

Only if the user explicitly asks to include existing context, ask which exact artifact(s) should be included. Keep this bounded:

- named `GPD/` files such as `PROJECT.md`, `ROADMAP.md`, `RESEARCH.md`, or `STATE.md`
- an explicitly named local file the user wants to ground the ideation launch

Read only those named artifacts. Fold only decisive constraints, anchors, or framing details into the launch brief. Do not silently widen scope by loading broad project context "just in case."
</step>

<step name="adaptive_clarification">
Ask only the clarification needed to draft a usable launch summary.

Target at most two clarification rounds before drafting unless the user explicitly wants more. The goal is to tighten the launch, not to run the ideation itself.

Prioritize these gaps:

- no clear outcome or useful end product
- no anchor, baseline, reference, or prior output to keep visible
- no explicit constraint or boundary
- no success signal or false-progress warning
- no initial execution posture

If `ask_user` is available, use it for the low-cardinality choices and keep freeform follow-ups compact.

First, resolve the preset if it is still missing or uncertain:

```text
header: "Preset"
question: "What launch depth fits this ideation run?"
options:
- "Balanced (Recommended)" -- standard launch with enough structure to keep the ideation grounded
- "Fast" -- shortest launch path, useful when the problem is already crisp
- "Deep" -- more intake and a heavier launch brief before ideation
- "Keep it flexible" -- do not lock a preset yet
```

Then ask at most one more targeted clarification round for the most important remaining gap. Examples:

- outcome focus: generate hypotheses / resolve a confusion / compare candidate directions / define next research steps
- posture: rigorous by default / allow looser exploration / leave posture undecided

The user may bypass further questions at any time. If they say "draft it," "good enough," or equivalent, move to the summary with the remaining gaps made explicit instead of continuing to probe.
</step>

<step name="resolve_launch_preferences">
After the main intake is clear enough, ask one compact freeform preference question for the execution knobs that are useful to capture now but not required to finalize in Phase 1:

`Any launch preferences I should lock now, such as agent count, stronger skepticism, or a looser creative posture? If not, I will keep those flexible.`

Keep this light. If the user does not care yet, mark those preferences as flexible or undecided in the summary rather than forcing specificity.

Use the following defaults unless the user overrides them:

- preset: `balanced`
- posture: rigorous and research-oriented by default
- agent structure: to be finalized later
- existing project context: not loaded unless explicitly requested
</step>

<step name="draft_launch_summary">
Synthesize a concise structured launch brief that preserves the user's own framing.

Render it as a compact table or sectioned summary with these sections:

```markdown
## Phase 1: Ideation Launch

| Section | Current launch brief |
| --- | --- |
| Idea | [core question, domain, or open discussion framing] |
| Outcome | [what useful result this ideation session should aim to produce] |
| Anchors | [must-keep references, prior outputs, examples, or "None supplied yet"] |
| Constraints | [scope boundaries, time/rigor limits, exclusions, or "None supplied yet"] |
| Risks / Open Questions | [weakest assumptions, unresolved gaps, false-progress warnings] |
| Execution Preferences | `Preset: ...`; `Posture: ...`; `Agent count: ...`; `Project context: ...` |
```

Keep user-recognizable phrases visible for decisive items. Do not smooth them into generic placeholders.

Before the approval gate, add one short side-effect note:

`This phase will not create or update files. Approval only locks the launch summary for this run.`
</step>

<step name="approval_gate">
Present the repo-style approval gate.

If `ask_user` is available:

```text
header: "Ideate Launch"
question: "Does this look right before I prepare the ideation run?"
options:
- "Start ideation"
- "Adjust launch"
- "Review raw context"
- "Stop here"
```

If `ask_user` is not available, present the same four options as a short numbered list and wait for the user's reply.

Interpret `Start ideation` in this phase as: approve this launch packet as the starting point for later ideation work. Do not claim that the multi-agent round engine ran.

On `Review raw context`:

- Show the raw launch packet in a more literal form: seed text, preserved phrases, imported anchors, resolved preset, unresolved gaps, and any user-specified execution preferences.
- Then return to the same approval gate.

On `Adjust launch`:

- Reopen only the section the user wants to revise.
- Use a section-specific edit menu rather than restarting intake:

```text
header: "Adjust Launch"
question: "What do you want to change?"
options:
- "Edit Idea"
- "Edit Outcome"
- "Edit Anchors / Constraints"
- "Edit Risks / Open Questions"
- "Edit Execution Preferences"
- "Review summary again"
```

- Ask one targeted follow-up for the chosen section, preserve all unchanged sections by default, then rebuild the summary and return to the approval gate.

On `Stop here`:

- End cleanly.
- Say no files were created and the ideation launch was not finalized.
- End with the standard continuation block:

```markdown
---

## > Next Up

**gpd:ideate** -- restart the ideation launch when you want to continue refining the brief

`gpd:ideate [topic or question]`

<sub>`/clear` first, then run `gpd:ideate [topic or question]`</sub>

---

**Also available:**
- `gpd:suggest-next` -- ask GPD for the best next move from here
- `gpd:help --all` -- inspect the current command surface

---
```

On `Start ideation`:

- Confirm that the launch brief is approved.
- Restate the final approved summary compactly.
- Be explicit that Phase 1 stops here: no multi-agent rounds have run and no durable session files were created.
- End with the standard continuation block, using `gpd:suggest-next` as the primary follow-up because the launch packet is ready but the later ideation engine is outside this phase:

```markdown
---

## > Next Up

**gpd:suggest-next** -- choose the best follow-up now that the ideation launch brief is approved

`gpd:suggest-next`

<sub>`/clear` first, then run `gpd:suggest-next`</sub>

---

**Also available:**
- `gpd:ideate [topic or question]` -- revise this launch brief later
- `gpd:help --all` -- inspect the current command surface

---
```
</step>

</process>

<success_criteria>
- [ ] The user sees a plain-English launch orientation before any detailed questioning
- [ ] The workflow captures an ideation brief through one dense prompt plus limited adaptive clarification
- [ ] Existing project context remains opt-in and bounded
- [ ] The launch summary preserves the user's framing and exposes execution preferences clearly
- [ ] The user can start, adjust, review raw context, or stop without losing the repo-style control flow
- [ ] No durable artifacts or fake ideation-session claims are produced in Phase 1
</success_criteria>
