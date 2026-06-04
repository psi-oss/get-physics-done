# gpd:ideate Local Demo Verification

This runbook is for the `feature/gpd-ideate-mvp` branch after the MVP
implementation has landed. It is intentionally local and operator-driven: use it
before presenting `gpd:ideate`, and keep demo artifacts out of commits unless a
maintainer explicitly asks for them.

The planned demo surface is three durable session files under
`GPD/blackboards/`:

```text
GPD/blackboards/ideate-YYYY-MM-DD-<topic-slug>.md
GPD/blackboards/ideate-YYYY-MM-DD-<topic-slug>-transcript.md
GPD/blackboards/ideate-YYYY-MM-DD-<topic-slug>-report.md
```

If a session slug already exists, the implementation should append a numeric
suffix such as `-2` without overwriting the earlier session.

## 1. Setup

Work from the repo root:

```bash
cd /Users/adamlevine/PSI-GPD
git branch --show-current
uv sync --dev
```

Expected branch:

```text
feature/gpd-ideate-mvp
```

For PDF or arXiv ingestion, install optional extras before the PDF/arXiv smoke:

```bash
uv sync --dev --extra paper --extra arxiv
```

The TeX-only demo below does not require those extras.

`gpd:ideate` is a runtime command, not a same-name local CLI subcommand. Use the
local `gpd` CLI for metadata, validators, and install/readiness checks. Install
the current checkout into the runtime you will present from, for example:

```bash
uv run gpd install codex --local
uv run gpd doctor --runtime codex --local
```

For another runtime, replace `codex` with `claude-code`, `gemini`, `copilot-cli`,
or `opencode`.

## 2. Stop-Early Wiring Checks

Run these before any live demo. If any command returns `unknown_command`, the
public command surface has not landed yet.

```bash
uv run gpd --raw help --command ideate
uv run gpd --raw command field-access ideate --style json
```

Expected highlights:

- `ok: true`
- `canonical_command: gpd:ideate`
- `context_mode: project-aware`
- output policy points at `GPD/blackboards`

Check that `ideate` also works before a GPD project exists:

```bash
tmpdir="$(mktemp -d)"
uv run gpd --raw --cwd "$tmpdir" validate command-context ideate \
  "JT half-omega corrections"
rm -rf "$tmpdir"
```

Expected highlights:

- `passed: true`
- `project_exists: false` is non-blocking
- the explicit topic/source argument is accepted
- managed output root resolves under `./GPD/blackboards`

If this check fails because no explicit input is supplied, that is expected for
an empty standalone invocation. The live workflow should ask for a topic and
sources rather than silently inventing ideas.

## 3. Focused Pytest Commands

Run the focused tests from the approved plan after all implementation files are
present. Missing files in this list are implementation blockers, not optional
skips.

```bash
uv run pytest \
  tests/core/test_ideate_sources.py \
  tests/core/test_ideate_blackboard.py \
  tests/core/test_ideate_prompt_contract.py \
  -q
```

```bash
uv run pytest \
  tests/test_registry.py \
  tests/core/test_prompt_wiring.py \
  tests/core/test_command_prompt_budget.py \
  -q
```

```bash
uv run pytest \
  tests/core/test_agent_prompt_budget.py \
  tests/core/test_agent_role_prompting.py \
  tests/core/test_agent_spawn_policy.py \
  tests/core/test_config.py \
  -q
```

```bash
uv run pytest \
  tests/core/test_help_inventory_contract.py \
  tests/core/test_help_public_surface_sync.py \
  tests/core/test_help_renderer.py \
  -q
```

Broader verification if time allows:

```bash
uv run pytest \
  tests/test_metadata_consistency.py \
  tests/core/test_repo_interdependency_graph.py \
  tests/core/test_generated_surface_target_registry.py \
  -q
```

```bash
uv run pytest \
  tests/adapters/test_runtime_projected_prompt_parity.py \
  tests/adapters/test_runtime_projected_command_requirement_coverage.py \
  tests/adapters/test_frontmatter_projection.py \
  -q
```

## 4. Generated-Surface Checks

After implementation changes that alter registry, command help, public surfaces,
or repo graph metadata, regenerate first:

```bash
uv run python scripts/render_help_surface.py
uv run python scripts/sync_repo_graph_contract.py
```

Then check:

```bash
uv run python scripts/render_help_surface.py --check
uv run python scripts/sync_repo_graph_contract.py --check
uv run python scripts/render_public_surface.py --check
```

If a check fails, inspect the generated diff. Do not hand-edit generated marker
regions.

## 5. Minimal Source Corpus Demo

Use a temp workspace so `GPD/blackboards/` output is easy to inspect and clean
up.

```bash
demo_root="$(mktemp -d /tmp/gpd-ideate-demo.XXXXXX)"
mkdir -p "$demo_root/sources"
cat > "$demo_root/sources/mini-jt-half-omega.tex" <<'EOF'
\documentclass{article}
\begin{document}
\section{Toy source for ideation}
We study a near-extremal Jackiw-Teitelboim saddle with a deformation parameter
\(\delta\). The working assumption is \(|\delta| \ll 1\) and fixed boundary
temperature. A half-omega correction changes the response coefficient as
\[
C(\delta) = C_0 + \delta C_1 + O(\delta^2).
\]
The source result is that \(C_1\) vanishes when the boundary mode has exact
time-reflection symmetry, but not when the regulator breaks that symmetry.
The open question is whether this cancellation survives after adding a weak
irrelevant boundary operator. A useful next calculation is to derive the
\(O(\delta \lambda)\) correction and compare the symmetric and regulator-broken
limits.
\end{document}
EOF
```

Optionally add the local sample PDF if the paper extra is installed:

```bash
cp /Users/adamlevine/PSI-GPD/papers/jt_delta_half_omega_analysis.pdf "$demo_root/sources/" 2>/dev/null || true
uv run gpd --cwd "$demo_root" validate artifact-text \
  sources/jt_delta_half_omega_analysis.pdf \
  --output sources/jt_delta_half_omega_analysis.txt
```

If PDF extraction fails, skip the PDF and run the TeX-only demo. The TeX source
is sufficient for the mandatory local smoke.

Launch the runtime from the demo workspace:

```bash
cd "$demo_root"
codex
```

Inside the runtime, run the command with your runtime's GPD command prefix. For
Codex this is expected to look like:

```text
$gpd-ideate --depth fast "half-omega corrections in near-extremal JT saddles" sources/mini-jt-half-omega.tex
```

For runtimes that expose canonical slash labels, use the equivalent
`gpd:ideate` command label. Keep the first demo at `fast` depth.

The workflow should ask for depth only if no depth was supplied. It should not
ask for source-search consent because the TeX source is explicit.

## 6. Expected Blackboard Outputs

After a successful source-backed run:

```bash
find GPD/blackboards -maxdepth 1 -type f -name 'ideate-*.md' | sort
```

Expected:

- one blackboard file
- one matching `-transcript.md`
- one matching `-report.md`
- all under the demo workspace's `GPD/blackboards/`

The blackboard should contain these sections:

```bash
bb="$(find GPD/blackboards -maxdepth 1 -type f -name 'ideate-*.md' ! -name '*-transcript.md' ! -name '*-report.md' | sort | tail -n 1)"
rg -n "## Session|## User Preferences|## Source Manifest|## Source Digests|## Candidate Ideas|## Critic Notes|## Vetoed Ideas|## Ranked Questions|## Next Experiments Or Calculations|## Open Steering Questions" "$bb"
```

Source manifest expectations:

- at least one `SRC-NNN` row for the TeX file
- source kind is `tex` or an implementation-specific directory item that points
  at the TeX file
- final source status is `completed` or `reused`
- topic rows, if present, are not used as evidence
- blocked rows, if present, do not support final ranked ideas

## 7. Inspect Transcript And Report

Transcript:

```bash
transcript="${bb%.md}-transcript.md"
sed -n '1,220p' "$transcript"
rg -n "Turn 1|gpd-ideator|gpd-ideation-critic|Parent Synthesis|Durable Effects" "$transcript"
```

Expected transcript evidence:

- a generator turn from `gpd-ideator`
- a critic turn from `gpd-ideation-critic`
- a revision or parent synthesis turn
- enough text to reconstruct the generator-critic exchange after the demo

Report:

```bash
report="${bb%.md}-report.md"
sed -n '1,260p' "$report"
rg -n "Executive Summary|Source Corpus|Ranked Research Questions|Next Best Experiments Or Calculations|Possible Issues|Vetoed Ideas|Recommended Next Actions" "$report"
rg -n "question_id:|research_question:|source_ids:|novelty:|physics_importance:|feasibility:|overall:|next_best_experiment:|possible_issues:" "$report"
```

Expected report evidence:

- ranked research questions are present
- every non-vetoed idea cites at least one completed or reused `SRC-NNN`
- no final visible label says `grounded`, `mixed`, or `speculative`
- every non-vetoed idea includes novelty, physics importance, feasibility, and
  overall scores
- every non-vetoed idea includes a next best experiment, calculation,
  derivation, simulation, or literature check
- possible issues are visible
- vetoed ideas appear in a separate `Vetoed Ideas` section when any were vetoed

## 8. Topic-Only Guard Smoke

Run this only after the source-backed demo, because it is expected to stop before
final ranking:

```text
$gpd-ideate --depth fast "half-omega corrections with no supplied sources"
```

Expected behavior:

- the workflow asks whether to supply paper/arXiv/PDF/folder sources or search
  for candidate papers
- if no sources are selected, it may create a blocked blackboard/transcript
- it must not produce final ranked source-grounded ideas from the topic alone

## 9. Troubleshooting

`unknown_command` from help or command-context:

- `src/gpd/commands/ideate.md` is missing or not registered
- generated help surfaces may not have been refreshed
- rerun the stop-early wiring checks after the command/workflow worker lands

Command-context fails in a temp workspace:

- `context_mode` is probably not `project-aware`
- the subject policy may not accept explicit topic/source input
- managed output may not be declared under `GPD/blackboards`

No files appear under `GPD/blackboards/`:

- the runtime may have launched from the wrong working directory
- the workflow may still be project-required instead of project-aware
- output policy may point at a different subtree

PDF extraction fails with a `pypdf` message:

- install the optional paper extra with `uv sync --dev --extra paper`
- or skip the PDF and use the TeX mini-corpus

The report ranks ideas from a topic-only run:

- this is a source-grounding regression; stop the demo
- final ideas must cite completed or reused source rows

The report is missing next experiments, scores, source IDs, possible issues, or
vetoed ideas:

- the parent synthesis or critic handoff is incomplete
- rerun the prompt-contract tests and inspect the report template

Generated-surface checks fail:

- run the corresponding generator without `--check`
- inspect the diff
- do not hand-edit generated marker regions

Focused pytest files are missing:

- the implementation is incomplete for the approved MVP
- do not substitute broad tests for missing source/blackboard/prompt-contract
  tests; add the focused tests first

Clean up the demo workspace when done:

```bash
rm -rf "$demo_root"
```
