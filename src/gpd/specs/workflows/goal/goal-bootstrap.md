# Goal Run Bootstrap

## Stage authority

This stage owns: goal-contract creation or resume, baseline snapshot, criteria
confirmation, the goal loop with its gates, and terminal-state handling. Phase
work inside each loop iteration follows the same discipline as the autonomous
workflow (discuss -> plan -> execute -> verify), but this workflow never
modifies autonomous stage files and goal runs never skip verification.

## 1. Resolve mode

- With a goal statement argument: new goal run. If `state.json` already has a
  `goal_contract` with status `active`, stop and tell the user to `--resume`
  or finish that goal first (one active goal per project).
- With `--resume`: load the existing contract via `gpd --raw goal status`.
  Keep `baseline_spent_usd` and `phases_completed` (caps measure the whole
  goal run across resumes). If `--budget-usd` / `--max-phases` were provided,
  replace those caps in the contract. Set status back to `active`.

## 2. Create the goal contract (new runs)

1. Snapshot the baseline: run `gpd --raw cost` and read
   `project.cost_usd`. If it is a number, record it as `baseline_spent_usd`;
   if it is null (no cost telemetry on this runtime), record null and require
   `--max-phases` — if the user did not provide one, ask for it now (this is
   part of the single upfront interaction). Never start an uncapped run.
2. Draft 2-5 success criteria from the goal statement. Each criterion gets an
   id (GC-1, GC-2, ...) and a `claim_ref` (goal-gc-1, goal-gc-2, ...): a
   plan-contract claim id that future phase plans MUST carry in their
   contracts so the verifier records its outcome in VERIFICATION.md
   `contract_results.claims`. Prefer fewer, decisive criteria.
3. Present the drafted criteria and the caps to the user for confirmation
   (single upfront interaction). Apply edits.
4. Validate before writing: pipe the contract JSON through
   `gpd --raw validate goal-contract -`. Fix any issues it reports.
5. Write the contract into `state.json` under the `goal_contract` key using
   the structured state update commands, and mirror a two-line summary into
   STATE.md.
6. Record the start event:
   `gpd observe event goal start --status ok --data '{"budget_usd": <amount or null>, "max_phases": <n or null>}'`.

## 3. Goal loop

Repeat until a terminal state:

1. **Gate.** Run `gpd --raw goal gate`.
   - Exit code non-zero (no enforceable cap, telemetry failure, invalid
     contract): FAIL CLOSED — surface the error to the user and stop. Never
     continue an ungated run.
   - `achieved: true` -> go to step 4 (achieved).
   - `budget_decision: stop` -> go to step 5 (budget stop).
   - `budget_decision: wrap_up` -> execute exactly one final consolidation
     phase in step 2 (verify and close existing threads decisively; no new
     exploratory work). `--max-phases N` therefore permits exactly N phases.
   - `budget_decision: continue` -> proceed to step 2.
   - Record: `gpd observe event goal budget_gate --status ok --data '<gate payload>'`.
2. **Phase iteration.** Execute exactly one phase through the standard
   discuss -> plan -> execute -> verify cycle (same child-command discipline
   as the autonomous workflow). The phase PLAN contract MUST include every
   still-pending goal criterion's `claim_ref` that this phase can decisively
   address; never invent claim outcomes — the verifier writes them.
3. **Account.** After the phase's verification completes, increment
   `goal_contract.phases_completed` by 1 via the structured state update
   commands, and record
   `gpd observe event goal criteria_check --status ok --data '<gate payload>'`.
   Loop to step 1.
4. **Achieved.** Set `goal_contract.status` to `achieved`, record
   `gpd observe event goal stop --status ok --data '{"terminal": "achieved"}'`,
   show the receipt (`gpd goal status`), and stop.
5. **Budget stop.** Checkpoint cleanly (same checkpoint discipline as the
   autonomous workflow's stop path), set `goal_contract.status` to
   `budget_stopped`, record
   `gpd observe event goal stop --status ok --data '{"terminal": "budget_stopped"}'`,
   and show the receipt plus resume instructions:
   `gpd:goal --resume [--budget-usd <new>] [--max-phases <new>]`.
6. **Blocked.** If a phase iteration reports an unrecoverable block, set
   `goal_contract.status` to `blocked`, record the stop event with
   `"terminal": "blocked"`, and surface the blocker with the receipt.
