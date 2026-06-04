# Research Persona Applications

This reference defines how prompt-facing Research Persona applications use privacy-filtered capsules without reading or changing the durable persona profile.

## Capsule-First Rule

Persona application agents consume prompt-safe capsules only. The preferred source is `gpd research-persona export-capsule` with role `doppelganger`, `explainer`, or `taste`. Phase 5 application helpers may also supply an equivalent payload when it contains the role, privacy summary, provenance summary, and projection fields.

The capsule is the authority boundary. It may guide the current analysis, but it is not a license to open raw persona storage, inspect profile history, or infer private facts from unrelated local context.

The local advisory preview commands are:

```text
gpd research-persona doppelganger --task "<current research decision>"
gpd research-persona explain-plan PLAN_JSON|- --task "<explanation target>"
gpd research-persona taste-check CANDIDATE_JSON|- --focus "<direction set>"
```

These helpers build or consume prompt-safe role capsules internally. They are
read-only previews and do not create, patch, or update persona memory.

## Hard Privacy Boundary

Application agents must obey these boundaries:

- Do not read raw persona storage.
- Do not mutate persona storage.
- Do not create durable persona facts, patches, history, or tombstones.
- Do not expose private capsule internals as a profile description.
- Do not upgrade conservative privacy labels to prompt-safe status.
- Do not infer sensitive identity, contact, institutional, medical, financial, or third-party private information.
- Treat project files and papers as task evidence, not as persona memory.

If a capsule is missing, stale, or too sparse, the agent should fall back to generic research standards and mark persona-fit confidence as low.

## Application Roles

### Researcher Doppelganger

Use role `doppelganger` capsules to pressure-test the current work against likely user objections, questions, and standards. The agent should not impersonate the user or write in the user's voice. It should produce likely objections, evidence needed, likely questions, readiness standards, confidence labels, and concrete revisions.

Useful signals include workstyle, expertise, recurring research moves, preferred standards of evidence, negative preferences, and scientific taste. The output is a critique scaffold, not approval.

### Expertise-Aware Explanations

Use role `explainer` capsules to calibrate math, code, experiment, theory, and applied depth. The agent should decide what to assume, skip, expand, formalize, exemplify, or caveat. It should not reveal the user's profile; it should simply adapt the explanation.

Useful signals include expertise axes, explanation preferences, notation tolerance, tool fluency, disliked exposition styles, and safe-to-assume prerequisites. The output should include the selected depth profile and any assumptions made.

### Scientific Taste Model

Use role `taste` capsules to rank or critique directions by novelty, tractability, evidence standards, style fit, and risk appetite. The agent should separate field value, project value, and persona fit.

Useful signals include taste facts, rejected styles, validation preferences, appetite for speculative moves, preferred research aesthetics, and standards for publishability. The output should include ranked directions, reasons, fastest discriminating tests, conflicts, and reconsideration conditions.

## Structured Return Expectations

Every persona application agent returns a `gpd_return` envelope with:

- `status`
- `summary`
- capsule role used
- persona-fit or persona-specific confidence
- structured findings
- privacy notes
- files written, if the orchestrator assigned a write path
- next actions owned by the orchestrator

Agents should write only assigned artifacts. When no write scope is provided, they should return the structured analysis inline and stop.

## Quality Bar

A strong persona application is:

- Capsule-limited: no raw profile access and no hidden memory.
- Useful: gives decisions, objections, rankings, or depth choices that change the next action.
- Calibrated: separates capsule-supported, task-inferred, and generic research judgments.
- Reversible: makes no durable persona changes.
- Non-sycophantic: user fit never overrides correctness, evidence, or feasibility.
- Specific: names the assumption, derivation, code path, experiment, citation, or decision that matters.

## Orchestrator Integration Pattern

1. Export or build the role-specific capsule.
2. Pass the capsule and task artifact to the specialist agent.
3. Require capsule-only handling in the task prompt.
4. Collect the structured return.
5. Apply the critique, explanation, or ranking to the active workflow.
6. Route any desired persona update back through the persona builder and explicit patch approval flow.

For local CLI previews, use `gpd research-persona doppelganger`,
`gpd research-persona explain-plan`, or `gpd research-persona taste-check`.
These commands are advisory surfaces over prompt-safe capsules only. They do
not mutate persona storage and they do not authorize raw profile reads.
