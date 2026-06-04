# Blind Oracle Sub-Protocol

Executed, **numbers-vs-numbers** verification of a decisive quantitative claim. Re-deriving from the artifact's stated result anchors the verifier to the claim; this protocol removes the anchor by having an independent agent compute the quantity blind, then comparing the two number vectors deterministically in the engine. Used by `gpd-verifier` (Level 3) for any decisive quantitative claim that has a contracted observable and a constructible numeric evaluator.

## Roles

- **`gpd-blind-deriver`** — the only agent that authors an *independent* evaluator. It is blinded by tool starvation (its only tools are the `gpd-compute` MCP tools; it has no file/shell/search/web access) and by handoff scoping.
- **`gpd-compute`** — the optional no-network sandboxed numeric oracle (mpmath/numpy). Pure: source + sample points → values + a content hash of the executed source. No claim awareness.
- **`gpd-verifier`** — orchestrates: spawns the blind deriver, evaluates the claim side, and calls the engine's deterministic comparator. The engine compares numbers only; it calls no model and no oracle.

## Steps

1. **Spawn the blind deriver.** Spawn `gpd-blind-deriver` (via `task`) passing **only** the problem statement and the ConventionLock from `state.json`. Do **not** pass the artifact's claimed answer, the derivation, `STATE.md`, or the verification report. It returns a `blind_oracle` block: a typed restatement (observable id/kind + one-line statement), the sample points it chose (>= 20, spanning the regime), per-point `values`, and an `evaluator_hash` — or `oracle_status: no_oracle_yet` if no independent evaluator is constructible.

2. **Evaluate the claim side.** Build the claim-side evaluator yourself from the artifact's stated result and evaluate it at the **same** sample points via `mcp__gpd_compute__evaluate_expression`, obtaining claim-side `values` and a claim-side `evaluator_hash`. Re-confirm each side's hash with `mcp__gpd_compute__evaluator_hash` — a value without a verifiable backing executed-cell hash is not accepted (anti-fabrication).

3. **Compare in the engine.** Call `mcp__gpd_verification__run_contract_check` with `check_key: contract.numeric_oracle_agreement`:
   - `metadata`: `contracted_observable_id`, `contracted_observable_kind`, the blind agent's `typed_restatement_observable_id`/`_kind`/`_statement`, `numeric_tolerance`, `claim_cell_hash`, `blind_cell_hash`.
   - `observed`: `sample_points`, `claim_values`, `blind_values`.
   The engine diffs the two vectors at the shared usable points and returns a `status`:
   - `pass` — **GREEN**: every shared point agrees within tolerance, the blind restatement matches the contracted observable, and both backing hashes are present. Satisfies the Computational Oracle Gate.
   - `fail` — **RED**: genuine claim-vs-blind numeric disagreement. This is a `gaps_found` issue and enters the planner/checker loop.
   - `insufficient_evidence` — **INCONCLUSIVE**: a missing backing hash, a proposition-fidelity mismatch (the blind agent computed a different quantity), or fewer than the required shared usable points. Does **not** block and is **not** a pass.

4. **Record the verdict** as the decisive check's executed evidence in `VERIFICATION.md` (verdict, both hashes, points compared, fidelity, capability class).

## Why blinding matters

- **Anti-anchoring:** the blind agent never sees the answer, so agreement is corroboration, not confirmation bias.
- **Proposition fidelity:** the typed restatement must match the contracted observable, so numeric agreement on the *wrong* quantity cannot pass GREEN.
- **Anti-fabrication:** every accepted number carries a backing executed-cell hash the verifier independently re-confirms.

## Honest scope

On flagship hep-th workloads (interacting-QFT path integrals, GR-tensor canonicalization, and other classes needing symbolic canonicalization), an independent numeric evaluator often cannot be constructed; `gpd-compute` returns `no_oracle_yet` and the verdict is INCONCLUSIVE. That is intended, honest behavior — record it and fall back to a conventional Level 3 check; never treat `no_oracle_yet` as a failure or paper over it as a pass.
