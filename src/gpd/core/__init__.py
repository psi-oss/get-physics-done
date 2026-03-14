"""GPD core state management — the authoritative source for all GPD state operations.

Modules:
    state       — STATE.md parser/renderer, JSON sync, atomic writes
    phases      — Phase/roadmap/milestone management, wave validation
    conventions — Convention lock (18 physics fields + custom)
    results     — Intermediate results with BFS dependency graphs
    health      — project diagnostic dashboard
    storage_paths — storage-path policy and durable-output routing
    query       — Cross-phase dependency tracing
    frontmatter — YAML frontmatter CRUD + verification suite
    patterns    — Error pattern library (8 categories, 13 domains)
    extras      — Approximations, uncertainties, questions
    context     — Context assembly for AI agents
    suggest     — Next-action intelligence
    config      — Multi-runtime config, model tiers
    trace       — JSONL execution tracing
"""

__all__: list[str] = []
