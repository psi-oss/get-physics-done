---
template_version: 1
---

Treat stable knowledge docs surfaced through `active_reference_context`, `reference_artifacts_content`, or the shared reference context as reviewed background syntheses only. They may refine assumptions or method choice when they agree with stronger sources, but they do not override `convention_lock`, `project_contract`, the PLAN `contract`, `contract_results`, `comparison_verdicts`, proof-review artifacts, or direct benchmark/result evidence. Keep them advisory unless the plan explicitly ties downstream gating to them.

Use explicit `knowledge_deps` when a plan materially depends on a reviewed knowledge doc and downstream gating should be enforced; keep implicit stable background advisory only. Do not invent a separate knowledge authority or ledger.
