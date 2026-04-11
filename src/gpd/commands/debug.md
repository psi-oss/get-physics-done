---
name: gpd:debug
description: Systematic debugging of physics calculations with persistent state across context resets
argument-hint: "[issue description]"
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - task
  - ask_user
---
<objective>
Debug physics calculations using systematic isolation with subagent investigation.

**Orchestrator role:** Gather symptoms, spawn gpd-debugger agent, handle checkpoints, spawn continuations.

**Why subagent:** Investigation burns context fast. Fresh context keeps the orchestrator lean.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/debug.md
</execution_context>

<context>
User's issue: $ARGUMENTS

Check for active sessions:

```bash
ls GPD/debug/*.md 2>/dev/null | grep -v resolved | head -5
```

</context>

<process>

## 0. Initialize Context

```bash
INIT=$(gpd --raw init progress --include state,roadmap,config)
```

Extract `commit_docs` from init JSON. Resolve debugger model:

```bash
DEBUGGER_MODEL=$(gpd resolve-model gpd-debugger)
```

## 1. Check Active Sessions

If active sessions exist AND no $ARGUMENTS:

- List sessions with status, current hypothesis, next action
- User picks number to resume OR describes new issue

If $ARGUMENTS provided OR user describes new issue:

- Continue to symptom gathering

## 2. Gather Symptoms (if new issue)

Use ask_user for each. Physics-specific symptom gathering:

1. **Expected result** — What should the calculation give? (analytical prediction, known limit, published value, physical intuition)
2. **Actual result** — What do you get instead? (wrong magnitude, wrong sign, wrong functional form, divergence, nonsensical value)
3. **Discrepancy character** — How does the error behave?
   - Constant factor off (suggests combinatorial or normalization error)
   - Wrong sign (suggests convention mismatch or parity error)
   - Wrong power law (suggests missed contribution or wrong scaling argument)
   - Divergence where finite result expected (suggests regularization issue or missed cancellation)
   - Numerical instability (suggests ill-conditioned formulation or inadequate precision)
   - Gauge-dependent result for gauge-invariant observable (suggests gauge artifact)
4. **Where it breaks** — In what regime or parameter range does the problem appear?
   - Always wrong, or only for certain parameter values?
   - Does it get worse as some parameter increases?
   - Does the problem appear at a specific step in the derivation?
5. **What you have tried** — Any checks already performed?
   - Dimensional analysis?
   - Limiting cases?
   - Comparison with alternative derivation?
   - Numerical spot-checks?

After all gathered, confirm ready to investigate.

## 3. Spawn gpd-debugger Agent

Fill prompt and spawn:

```markdown
<objective>
Investigate physics issue: {slug}

**Summary:** {trigger}
</objective>

<symptoms>
expected: {expected}
actual: {actual}
discrepancy_character: {discrepancy_character}
where_it_breaks: {where_it_breaks}
already_tried: {already_tried}
</symptoms>

<mode>
symptoms_prefilled: true
goal: find_root_cause_only
</mode>

<debug_file>
Create: GPD/debug/{slug}.md
</debug_file>
```

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-debugger.md for your role and instructions.\n\n" + filled_prompt,
  subagent_type="gpd-debugger",
  model="{debugger_model}",
  readonly=false,
  description="Debug {slug}"
)
```

## 4. Handle Agent Return

Handle the debugger return once through the workflow-owned typed child-return contract. Do not branch on heading text here.

- `gpd_return.status: completed` -- Verify `GPD/debug/{slug}.md` exists and its frontmatter/body reconcile the expected debug session artifact before it passes the artifact gate, then present the confirmed root cause, evidence summary, and error classification, and offer: Fix now, Plan fix, Manual fix.
- `gpd_return.status: checkpoint` -- Present the checkpoint details to the user, collect the response, and spawn a fresh continuation run.
- `gpd_return.status: blocked` or `failed` -- Show what was checked, what was ruled out, and what remains unresolved, then offer: Continue investigating, Manual investigation, Add more context, Simplify the problem.

## 5. Spawn Fresh Continuation agent (After Checkpoint)

When user responds to checkpoint, spawn fresh agent:

```markdown
<objective>
Continue debugging {slug}. Evidence is in the debug file.
</objective>

<prior_state>
Debug file path: GPD/debug/{slug}.md
Read that file before continuing so you inherit the prior investigation state instead of relying on an inline `@...` attachment.
</prior_state>

<checkpoint_response>
**Type:** {checkpoint_type}
**Response:** {user_response}
</checkpoint_response>

<mode>
goal: find_root_cause_only
</mode>
```

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-debugger.md for your role and instructions.\n\n" + continuation_prompt,
  subagent_type="gpd-debugger",
  model="{debugger_model}",
  readonly=false,
  description="Continue debug {slug}"
)
```

</process>

<success_criteria>

- [ ] Active sessions checked
- [ ] Symptoms gathered with physics-specific characterization (if new)
- [ ] gpd-debugger spawned with context and diagnosis-only goal
- [ ] Checkpoints handled correctly
- [ ] Root cause confirmed and classified before fixing
- [ ] Error type identified (algebraic, numerical, conceptual, conventional)
      </success_criteria>
