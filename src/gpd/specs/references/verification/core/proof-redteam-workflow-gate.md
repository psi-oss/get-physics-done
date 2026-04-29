Use this gate anywhere a workflow might create, execute, or verify theorem-style work.

Treat work as proof-bearing when any of these are true:

- the active contract names `proof_obligation`, populates proof fields, or uses proof-bearing `ProjectContract` vocabulary such as `claim_kind: theorem | lemma | corollary | proposition | claim`
- the goal, deliverable, manuscript section, or task carries theorem/proof/formal metadata: `theorem`, `lemma`, `corollary`, `proposition`, `proof`, `prove`, `we prove`, non-empty theorem assumptions or parameters, proof artifact paths, or an explicit `show that` / existence / uniqueness target with named hypotheses, parameters, quantifiers, domains, or conclusion clauses
- the result is a formal derivation whose truth depends on named hypotheses, parameters, quantifiers, or conclusion clauses

A generic manuscript claim, Paper `ClaimRecord.claim_kind: claim`, ordinary result claim, or the bare word `claim` is not proof-bearing by itself. Require theorem/proof/formal metadata before routing generic manuscript claims through proof-redteam.

If classification remains ambiguous after inspecting available theorem/proof/formal metadata, default to proof-bearing.

The proof-redteam artifact is mandatory and fail-closed. It must contain: exact theorem/claim text, named parameters, hypotheses, quantifier or domain obligations, conclusion clauses, coverage notes mapped to proof locations, at least one adversarial special-case or counterexample probe, and canonical `status: passed | gaps_found | human_needed`.

Missing artifacts, malformed artifacts, missing theorem inventory, or `status != passed` are blocking gaps. Do not accept a clean summary, locally correct algebra, a proof of one special case, later human inspection, or executor self-review as a substitute.

When runtime delegation is available, `gpd-check-proof` is the canonical owner of the proof-redteam artifact. Spawn it in a fresh context, require checkpoint-and-return semantics if user input is needed, and verify the artifact on disk before accepting completion.
