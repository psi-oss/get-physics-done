# Journal

## 2026-04-09

### What GPD surfaced correctly

- `gpd suggest` correctly identified this workspace as a fresh project and recommended `new-project`.
- `gpd init new-project` correctly exposed the temporary defaults (`autonomy=balanced`, `research_mode=balanced`) and showed that no project artifacts existed yet.
- `gpd state set-project-contract` accepted a canonical scoping contract anchored on three concrete references:
  - [arXiv:2212.03881](https://arxiv.org/abs/2212.03881), submitted December 7, 2022 and revised October 23, 2023
  - [arXiv:2310.14396](https://arxiv.org/abs/2310.14396), submitted October 22, 2023
  - [arXiv:2510.13961](https://arxiv.org/abs/2510.13961), submitted October 15, 2025 and revised October 26, 2025
- Once `ROADMAP.md` and `STATE.md` existed, `gpd phase add` worked normally and created a new phase directory plus a roadmap entry.
- `gpd result add`, `gpd result upsert`, `gpd result deps`, and `gpd result downstream` were useful. They gave a real dependency graph rather than just a flat note list.
- After cleaning the bootstrap state, `gpd state validate` became a meaningful check. It now warns only about the 15 conventions that are still genuinely unset.

### What GPD missed or handled poorly

- The user-facing wrapper `/tooling/bin/gpd-main` was unusable in this sandbox because `uv` tried to touch `/Users/sergio/.cache/uv/...`, which is outside the permitted filesystem. The pinned `.venv` entrypoint worked.
- The shell-exposed CLI has `init new-project`, but not a callable `new-project` write pass. That meant there was no direct way, from the shell surface alone, to create `PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, and `config.json`. I had to bootstrap those from the canonical GPD templates.
- `gpd phase add` hard-fails without a preexisting roadmap. That is reasonable internally, but it means the missing `new-project` write step is a real blocker for phase creation in a fresh workspace.
- The first `convention check` contradicted `convention list` and `state.json`: it reported `natural_units` and `coordinate_system` as unset even though they had been written. After state cleanup, `convention check` behaved normally. This suggests an early reporting or sync bug.
- The actual CLI for `question resolve` does not match the prompt’s advertised interface. The prompt says "resolve <id> <answer>", but the real command only takes the question text and records no answer payload.
- `gpd verify phase 1` reported phase 1 as complete because there are no plan files yet. That is too weak for research state: the roadmap clearly lists three planned tasks for phase 1.
- `gpd progress table` rendered `0/0 plans` for every phase even though `ROADMAP.md` contains explicit plan counts and checkboxes. The progress renderer appears to count only plan artifacts on disk, not roadmap plans.
- `gpd approximation check` left both approximations in `unchecked` even though each approximation carries a meaningful `status`. That check clearly expects a narrower status vocabulary than the command help suggests.
- `gpd health` still reports `planning.commit_docs=false` even though `GPD/config.json` contains `"commit_docs": true`. That looks like a config parsing bug in the health diagnostic.

### Physics assessment from the anchored literature

- The benchmark paper [arXiv:2212.03881](https://arxiv.org/abs/2212.03881) establishes the main baseline: rQFC is proved in braneworld semiclassical gravity, but only subject to a technical assumption and with explicit reliance on higher-dimensional holographic control.
- The limiting-case paper [arXiv:2310.14396](https://arxiv.org/abs/2310.14396) matters because it shows that the restricted `Theta -> 0` regime is not empty formalism. It yields the improved energy condition

  `T_{kk} >= hbar/(2*pi*A) (S''_{out} - (1/2) theta S'_{out})`

  and sketches, rather than completes, a field-theory proof route. It is therefore a structural limiting-case constraint on any extension program, not by itself a general non-braneworld proof of rQFC.
- The newest anchor [arXiv:2510.13961](https://arxiv.org/abs/2510.13961) changes the research landscape materially. It proves rQFC in a class of JT-gravity-plus-QFT toy models and shows, in `d>2`, that rQFC forbids QNEC saturation faster than `O(A)` as the transverse area shrinks to zero. That is the strongest direct beyond-braneworld evidence in the current anchor set.

### Current research hypothesis

The most plausible route beyond braneworlds is not "replace holography with nothing" and hope the same proof goes through. The better hypothesis is:

1. Extract the benchmark ingredient set from the braneworld proof.
2. Identify which pieces are really about controlling second null variations of generalized entropy.
3. Replace the braneworld-specific bulk-Einstein input with a different structural control principle that is strong enough to recover the JT proof and the d>2 small-area consequence.

The weakest anchor remains the same one already visible in the contract: what replaces higher-dimensional Einstein-dual control in a truly general non-braneworld proof.

### Immediate next derivation targets

- Dissect the precise benchmark step in arXiv:2212.03881 that uses braneworld bulk Einstein dynamics rather than general semiclassical input.
- Translate the JT proof of arXiv:2510.13961 into the same ingredient language and test whether its success depends on genuinely two-dimensional/dilaton-specific structure.
- Reformulate the d>2 consequence of arXiv:2510.13961 as a concrete small-area control condition on generalized entropy variation, not just as a slogan about strengthened QNEC behavior.

### Session 3 continuation: deeper GPD coverage

Commands rerun or newly probed in this continuation included `gpd resume`, `gpd health`, `gpd state validate`, `gpd validate consistency`, `gpd suggest`, `gpd state snapshot`, `gpd roadmap analyze`, `gpd roadmap get-phase 01`, `gpd phase index 01`, `gpd phase validate-waves 01`, `gpd result deps R-02-dgtwo`, `gpd result downstream R-01-benchmark`, `gpd approximation check`, `gpd regression-check`, `gpd history-digest`, `gpd sync-phase-checkpoints`, `gpd convention list`, and `gpd convention check`.

- `gpd result deps` and `gpd result downstream` still form a coherent dependency graph:
  `R-01-benchmark -> {R-02-inec, R-02-jt} -> R-02-dgtwo`.
- `gpd convention list` and `gpd convention check` now agree with each other and with `state.json`. The earlier mismatch on `natural_units` and `coordinate_system` appears resolved after the bootstrap cleanup.
- `gpd regression-check`, `gpd history-digest`, and `gpd sync-phase-checkpoints` all handled the empty-phase state safely. They returned empty outputs or warnings rather than inventing completed work.
- `gpd state snapshot` correctly reports the live project state: current phase `01`, status `Ready to plan`, and `3` total plans in the current phase.
- By contrast, `gpd progress table`, `gpd roadmap analyze`, and `gpd phase index 01` all collapse the same project to `0/0` plans. `gpd roadmap get-phase 01` still sees the three roadmap plans. This strongly suggests a split between roadmap-text parsing and plan-artifact counting rather than actual roadmap corruption.
- `gpd resume` initially recognized the current workspace as a GPD project but reported `has_continuity_handoff=false` and no resumable target even though `HANDOFF.md` existed and `state.json.continuation.handoff` already contained session metadata. After `gpd state record-session --resume-file HANDOFF.md --last-result-id R-02-dgtwo`, the same resume surface switched to `session-handoff`, surfaced `HANDOFF.md`, and projected `R-02-dgtwo` as the active carried-forward result. The bug is therefore a strict metadata dependency rather than total handoff blindness.
- The `planning.commit_docs` mismatch is still reproducible. `GPD/config.json` contains `"commit_docs": true`, while `gpd resume`, `gpd health`, and `gpd validate consistency` all report `commit_docs=false`.
- `gpd suggest` currently routes the top action to `$gpd-debug` because of the historical bootstrap blocker. That is not a persuasive next-step recommendation now that the project files already exist and the blocker is informational rather than execution-blocking.
- `gpd approximation check` still leaves both approximations in `unchecked`, so the status-vocabulary mismatch from the previous session persists.

### Session 3 provisional assessment

- No new literature-grounded physics claim was added in this continuation. The existing assessment remains provisional by design.
- The direct beyond-braneworld evidence comes from the JT/d>2 paper. The `Theta -> 0` paper still stands as a limiting-case constraint, but not as a standalone non-braneworld proof of rQFC. The central unresolved issue is still the same: identify a replacement for the higher-dimensional Einstein-dual control used in the benchmark braneworld proof.
- The continuity metadata has now been refreshed successfully, so the next substantive research move should be the proof-ingredient audit of arXiv:2212.03881 rather than more bootstrap-only state repair.

### Session 4: projection-layer root-cause audit

- I began by following the session-3 restart checklist directly. `gpd resume` still surfaced `HANDOFF.md` and carried forward `R-02-dgtwo`, so the continuity problem from the earlier bootstrap state did not recur.
- `gpd state snapshot` and `gpd roadmap get-phase 01` still agree on the authoritative project picture: current phase `01`, status `Ready to plan`, and `3` roadmap plans in phase 1. The canonical state still does not look stale.
- The table-backed state surfaces are healthy. `gpd approximation list`, `gpd uncertainty list`, `gpd question list`, and `gpd calculation list` all reproduced the corresponding `STATE.md` tables cleanly.
- The `planning.commit_docs` split is narrower than it looked in session 3. `GPD/config.json` still literally contains `"commit_docs": true`, but `gpd config get planning.commit_docs`, `gpd resume`, `gpd health`, and `gpd validate consistency` all report the effective value `false` because `src/gpd/core/config.py::_apply_gitignore_commit_docs()` forces it off when `GPD/` is gitignored. `git check-ignore -v` confirms that this workspace is covered by the repo rule `.gitignore: automation/runs/`. The remaining problem is a raw-versus-effective config ambiguity, not a blind misread.
- The plan-count contradiction is also architectural rather than random. Reading `src/gpd/core/phases.py` showed that `gpd progress`, `gpd roadmap analyze`, and `gpd phase index` count on-disk `*-PLAN.md` files and summaries, while `gpd roadmap get-phase 01` reads the textual roadmap section that still says `**Plans:** 3 plans`. That explains why roadmap text preserves the tasks while artifact-counting surfaces collapse them to `0/0`.
- `gpd query deps`, `gpd query search`, and `gpd query assumptions` are not canonical result-ledger queries. `src/gpd/core/query.py` shows that they scan `SUMMARY.md` frontmatter only. Since this workspace has no summaries yet, their empty outputs are expected and do not imply a stale result graph.
- `gpd observe execution` and `gpd observe sessions` clarified another scope boundary. They look only at local observability telemetry, not at canonical continuation. Their empty outputs here mean no observability sessions were recorded, not that the handoff is missing.
- One real validator bug remains sharp: `gpd verify phase 01` still returns `complete=true` with `plan_count=0` and `summary_count=0`. That conflicts with both the roadmap text and the separate `is_phase_complete(plan_count > 0 and summary_count >= plan_count)` helper used elsewhere.
- A second stale-state bug showed up after the documentation refresh. `gpd state record-session` updated `STATE.md`, `state.json`, and `gpd state load` to the new `Last session` timestamp, but `gpd state snapshot` and `gpd resume` continued to project the older session timestamp. The session-continuity write path and the snapshot/resume read surfaces are therefore out of sync.
- Two additional misleading surfaces remain unchanged. `gpd roadmap analyze` still reports `current_phase: null` and `next_phase: "1"` because it only treats `planned` or `partial` on-disk phases as current, and `gpd approximation check` still classifies both approximations as `unchecked` despite meaningful status strings in `STATE.md`.
- The overall session-4 verdict is therefore tighter than the session-3 contradiction list. The canonical project state still does not look corrupted or stale. The persistent issues are mostly projection-scope mismatches plus one real phase-verification bug.

### Session 5: write-path retest and narrowed live issues

- I reran the main continuation and projection surfaces: `gpd resume`, `gpd state snapshot`, `gpd state load`, `gpd config get planning.commit_docs`, `gpd roadmap get-phase 01`, `gpd verify phase 01`, `gpd health`, `gpd state validate`, `gpd validate consistency`, `gpd progress table`, `gpd progress bar`, `gpd roadmap analyze`, `gpd phase index 01`, `gpd result deps R-02-dgtwo`, `gpd result downstream R-01-benchmark`, `gpd approximation list`, `gpd approximation check`, `gpd suggest`, `gpd state update-progress`, and `gpd observe sessions`.
- The baseline contradictions are still mostly where session 4 left them. `gpd verify phase 01` still says `complete=true` with `plan_count=0` and `summary_count=0`, while `gpd progress table`, `gpd progress bar`, `gpd roadmap analyze`, `gpd phase index 01`, and now `gpd state update-progress` all still reduce the project to artifact-counted `0/0` plans.
- The canonical dependency graph remains coherent. `gpd result deps` and `gpd result downstream` still produce `R-01-benchmark -> {R-02-inec, R-02-jt} -> R-02-dgtwo`.
- I pushed into reversible write-path probes. `gpd state update` on an existing field changed both `GPD/STATE.md` and `GPD/state.json`, and `gpd state snapshot` plus `gpd state load` immediately reflected the new value. `gpd state patch` likewise dual-wrote the successful key while leaving the failed key only in the returned `failed` list.
- The write-path failure semantics are looser than the JSON payload suggests. `gpd state update DoesNotExist probe-value`, `gpd state update Status nonsense-status`, and a no-op repeat update all returned structured `updated=false`, but the CLI still exited with code `0`. `gpd state patch` also exited `0` on mixed success/failure. That is a real automation risk because callers have to inspect payloads rather than exit status.
- The stale-session readback bug from the session-4 handoff did not reproduce. Before I reran `gpd state record-session`, the workspace still literally carried the session-3 continuity timestamp in both `STATE.md` and `state.json`. After a fresh `gpd state record-session --stopped-at ... --resume-file HANDOFF.md --last-result-id R-02-dgtwo`, `STATE.md`, `state.json`, `gpd state snapshot`, `gpd state load`, and `gpd resume` all agreed on the new session-5 timestamp and stop string.
- `gpd observe sessions` remained empty even after `state record-session`, which confirms again that observability telemetry and continuity metadata are separate surfaces.
- Reading `src/gpd/core/extras.py` clarified that `gpd approximation check` is not actually reading the human-authored approximation `status` field. It only tries to parse a numeric `current_value` against `validity_range`, which is why both entries land in `unchecked`.
- Reading `src/gpd/core/suggest.py` clarified that `gpd suggest` reporting `missing_conventions: []` is not a contradiction with the 15-unset-convention warning from `gpd state validate`. The suggest surface only tracks three core conventions: `metric_signature`, `natural_units`, and `coordinate_system`, all of which are set here.
- `gpd suggest` still routes the top action to `$gpd-debug`, though. The bootstrap blocker remains in `STATE.md`, so the heuristic still over-weights historical setup trouble even after the workspace is fully usable.
- Reading `src/gpd/core/state.py` showed why `gpd state update-progress` adds no new authority. It recomputes progress strictly from on-disk plan and summary artifacts and returns `updated=true` whenever the `**Progress:**` field exists, even if the percentage remains unchanged at `0%`.

### Session 5 provisional assessment

- The live issue set is now narrower than the session-4 handoff claimed. I no longer have a reproduced stale-session projection bug in the current workspace.
- The real remaining tooling problems are: zero-plan phase verification, roadmap-text versus artifact-count projections, approximation-status mismatch, lingering blocker-biased suggestions, and non-failing CLI exit codes for `state update` and `state patch`.
- The physics picture itself is still unchanged. Direct beyond-braneworld evidence remains real through the JT/d>2 anchor, while the `Theta -> 0` paper should be treated as a limiting-case structural input. The unresolved obstruction is still identifying a general replacement for the benchmark proof's higher-dimensional Einstein-dual control.

### Session 6: citation, equation, and stale-state audit

- I rechecked all three anchor citations against arXiv and their INSPIRE mappings. The arXiv IDs in the workspace point to the intended papers, and the two older anchors also have the expected publication metadata: `2212.03881 -> Phys. Rev. D 109 (2024) 066023` and `2310.14396 -> JHEP 02 (2024) 132`.
- The main literature correction is interpretive rather than bibliographic. arXiv:2310.14396 derives the improved quantum null energy condition in the `Theta -> 0` limit and sketches a field-theory proof route, but it should not be cited as a direct general non-braneworld proof of rQFC.
- The one explicit equation in the workspace,
  `T_{kk} >= hbar/(2*pi*A) (S''_{out} - (1/2) theta S'_{out})`,
  passes a dimensional audit if the affine parameter carries length dimension, `S_out` is dimensionless, and `A` is the local transverse area element. In the `theta -> 0` limit it reduces to `T_{kk} >= hbar/(2*pi*A) S''_{out}`, matching the intended limiting case.
- The `d>2` result from arXiv:2510.13961 was also sharpened. The source claim is not merely that rQFC constrains QNEC saturation qualitatively, but that in a broad class of states it forbids saturation faster than `O(A)` as the area shrinks.
- The GPD ledger carried one genuinely stale value set: both propagated uncertainties were tagged as last updated in phase `03` even though the workspace remains at phase `01`. I corrected those tags back to bootstrap-phase `00`, marked the literature anchor results as reverified, and wrote a cleaned manuscript note in `paper/restricted-qfc-corrected-note.md`.
