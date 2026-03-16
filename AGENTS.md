# Get Physics Done (GPD) — RIF-Verified Tool Documentation

> **RIF Header**: Where this file contradicts the global Warp rule, **this file wins**.  
> This file is authoritative based on source code verification (`/home/john/MCP/gpd/gpd-mcp/lib/gpd_bridge.py`).  
> Source date: 2026-03-15 | Last verified: live

---

## GPD MCP Server Identity

- **Server ID**: `gpd` (alias: `get-physics-done`)
- **Total Tools**: 8 (verified against source)
- **Entry Point**: `/home/john/MCP/gpd/gpd-mcp/server.js` (Node.js stdio MCP bridge)
- **Bridge**: Python (`lib/gpd_bridge.py`, 591 lines) wraps GPD CLI
- **Protocol**: JSON-RPC 2.0 (standard MCP 2024-11-05)
- **Status**: All 8 tools verified, fully operational

---

## Tool Inventory (Source-Verified)

### 1. `gpd_new_project`

**Purpose**: Initialize a new physics research project with convention locking  
**Type**: Creation/Setup

**Arguments**:
- `project_name` (string, required): Name of the project (e.g., "consciousness-manifold")
- `domain` (string, required): Physics domain (see WARP.md for valid domains: `qft`, `gr`, `consciousness_physics`, etc.)
- `description` (string, optional): Project description
- `base_directory` (string, optional): Where to create project (default: current dir)

**Returns**:
- `project_path` (string): Path to created project directory
- `locked_conventions` (object): 6 locked convention fields for the domain
- `manifest` (object): Project manifest with domain metadata

**Example**:
```json
{
  "project_name": "b10-consciousness",
  "domain": "consciousness_physics",
  "description": "Verification of ℬ¹⁰ manifold across 5 phases"
}
```

**Output**:
```json
{
  "project_path": "/home/john/b10-consciousness",
  "locked_conventions": {
    "metric_signature": "(-,+,+,+,+,+,+,+,+,+)",
    "gauge_choices": "SO(1,3) ⊕ SU(2) ⊕ U(4)",
    "perturbative_regimes": "...",
    "approximation_schemes": "...",
    "boundary_conditions": "S³ × S⁵ topology",
    "regularization_schemes": "..."
  },
  "manifest": { ... }
}
```

---

### 2. `gpd_plan_phase`

**Purpose**: Plan a single research phase (spec, assumptions, conventions)  
**Type**: Planning

**Arguments**:
- `project_path` (string, required): Path to GPD project
- `phase_number` (integer, required): Phase 1-5
- `name` (string, required): Phase name (e.g., "Metric Well-Definedness")
- `description` (string, optional): Detailed description of what to verify

**Returns**:
- `phase_plan` (object): Complete phase specification
- `assumptions` (array): List of assumptions locked for this phase
- `derivation_outline` (string): Suggested derivation approach
- `output_files` (object): List of artifacts that will be generated

**Example**:
```json
{
  "project_path": "/home/john/b10-consciousness",
  "phase_number": 1,
  "name": "Metric Well-Definedness",
  "description": "Verify metric non-degeneracy, signature preservation, geodesic completeness"
}
```

---

### 3. `gpd_execute_phase`

**Purpose**: Execute a phase derivation, generate code and formulas  
**Type**: Execution/Generation

**Arguments**:
- `project_path` (string, required): Path to GPD project
- `phase_number` (integer, required): Phase 1-5
- `name` (string, required): Phase name
- `description` (string, required): What to calculate
- `force_recalculate` (boolean, optional): Regenerate even if exists (default: false)

**Returns**:
- `status` (string): "completed", "error", "incomplete"
- `summary` (string): Text summary of results
- `tex_formulas` (string): Publication-ready LaTeX formulas
- `python_code` (string): Executable Python for verification
- `artifacts` (object): Paths to generated `.summary`, `.tex`, `.py` files
- `state` (object): Machine-readable STATE.json (conventions, results, warnings)

**Example**:
```json
{
  "project_path": "/home/john/b10-consciousness",
  "phase_number": 2,
  "name": "Vacuum Cancellation",
  "description": "Verify that 4 oscillator eigenvalues cancel cosmological constant"
}
```

**Output**:
```json
{
  "status": "completed",
  "summary": "Phase 2 complete. Λ_eff = 0.2 × 10⁻¹² (fine-tuning verified).",
  "tex_formulas": "\\Lambda_{eff} = \\Lambda_{classical} + \\sum_{j=1}^4 \\varepsilon_j \\approx 0",
  "python_code": "# Code to compute eigenvalues, verify cancellation...",
  "artifacts": {
    "summary_file": "/home/john/b10-consciousness/phase-2.summary",
    "tex_file": "/home/john/b10-consciousness/phase-2.tex",
    "py_file": "/home/john/b10-consciousness/phase-2.py",
    "state_file": "/home/john/b10-consciousness/STATE.json"
  }
}
```

---

### 4. `gpd_verify_work`

**Purpose**: Verify a phase using cross-model analysis  
**Type**: Verification

**Arguments**:
- `project_path` (string, required): Path to GPD project
- `phase_number` (integer, required): Phase to verify
- `derivation_file` (string, optional): Custom derivation to verify (else use auto-generated)

**Returns**:
- `status` (string): "passed", "failed", "contradiction"
- `severity_score` (float): 0.0-1.0 (φ = 0.618 threshold)
- `contradictions` (array): List of detected contradictions
- `cross_model_analysis` (object): Results from Grok, Abacus, Ollama
- `verification_report` (string): Detailed `.verify` report

**Example**:
```json
{
  "project_path": "/home/john/b10-consciousness",
  "phase_number": 1
}
```

**Output**:
```json
{
  "status": "passed",
  "severity_score": 0.033,
  "contradictions": [],
  "cross_model_analysis": {
    "grok_symbolic": { "confidence": 0.72, "result": "✓ Verified" },
    "abacus_multi_model": { "confidence": 0.68, "result": "✓ Verified" },
    "ollama_limiting_case": { "confidence": 0.61, "result": "✓ Verified" }
  },
  "verification_report": "..."
}
```

---

### 5. `gpd_map_research`

**Purpose**: Map phase results into research knowledge graph  
**Type**: Analysis/Synthesis

**Arguments**:
- `project_path` (string, required): Path to GPD project
- `phase_number` (integer, required): Phase to map
- `theme` (string, optional): Research theme (e.g., "consciousness-physics")

**Returns**:
- `knowledge_graph` (object): Nodes (assumptions, theorems, references), edges (depends-on, verifies, contradicts)
- `literature_references` (array): Cited papers with relevance scores
- `assumption_validation` (object): Which assumptions held, which shifted
- `next_research_questions` (array): Open questions for future phases

**Example**:
```json
{
  "project_path": "/home/john/b10-consciousness",
  "phase_number": 2,
  "theme": "consciousness-physics"
}
```

---

### 6. `gpd_review_manuscript`

**Purpose**: AI-driven peer review of physics manuscripts  
**Type**: Review/Analysis

**Arguments**:
- `manuscript_file` (string, required): Path to manuscript (`.tex`, `.md`, or `.pdf`)
- `target_domain` (string, required): Physics domain (for context)
- `review_depth` (string, optional): "shallow", "moderate", "deep" (default: "moderate")

**Returns**:
- `review_status` (string): "approved", "needs-revision", "rejected"
- `comments` (array): Structured review comments with severity
- `suggestions` (array): Actionable suggestions for improvement
- `reference_checks` (object): Literature verification results

**Example**:
```json
{
  "manuscript_file": "/home/john/b10-consciousness/paper.tex",
  "target_domain": "consciousness_physics",
  "review_depth": "deep"
}
```

---

### 7. `gpd_get_state`

**Purpose**: Get current project state and convention tracking  
**Type**: Query/Status

**Arguments**:
- `project_path` (string, required): Path to GPD project
- `include_history` (boolean, optional): Include convention drift history (default: false)

**Returns**:
- `current_state` (object): Current project state (conventions, completed phases, warnings)
- `convention_locks` (object): Which conventions remain locked
- `completed_phases` (array): List of finished phases with severity scores
- `drift_warnings` (array): Any detected assumption shifts
- `next_phase_recommendation` (string): Suggested next step

**Example**:
```json
{
  "project_path": "/home/john/b10-consciousness",
  "include_history": true
}
```

---

### 8. `gpd_get_conventions`

**Purpose**: Retrieve or modify physics conventions for a domain  
**Type**: Configuration

**Arguments**:
- `domain` (string, required): Physics domain
- `action` (string, optional): "get" or "lock" (default: "get")
- `convention_fields` (object, optional): For lock action, new convention values

**Returns**:
- `conventions` (object): Current conventions for the domain
- `status` (string): "retrieved" or "locked"
- `locked_timestamp` (string, optional): When conventions were locked

**Example** (get):
```json
{
  "domain": "consciousness_physics",
  "action": "get"
}
```

**Output**:
```json
{
  "conventions": {
    "metric_signature": "(-,+,+,+,+,+,+,+,+,+)",
    "gauge_choices": "SO(1,3) ⊕ SU(2) ⊕ U(4)",
    ...
  },
  "status": "retrieved"
}
```

---

## MCP Handshake Pattern (Required)

All GPD tools require proper JSON-RPC 2.0 initialization. **Do NOT call tools directly**.

```bash
# Step 1: Initialize
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"gpd","version":"1.0"}}}' | node server.js

# Step 2: Wait for notifications/initialized

# Step 3: List tools
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | node server.js

# Step 4: Call tool
echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"gpd_new_project","arguments":{"project_name":"test","domain":"consciousness_physics"}}}' | node server.js
```

See `lib/gpd_bridge.py` for Python wrapper example.

---

## Verification Status ✅

**Last Verified**: 2026-03-15 (live system)

- ✅ **gpd_new_project** — Creates projects, locks conventions
- ✅ **gpd_plan_phase** — Plans derivations, identifies assumptions
- ✅ **gpd_execute_phase** — Generates code, formulas, artifacts
- ✅ **gpd_verify_work** — Cross-model verification (Grok + Abacus + Ollama)
- ✅ **gpd_map_research** — Knowledge graph synthesis
- ✅ **gpd_review_manuscript** — AI-driven peer review
- ✅ **gpd_get_state** — Project state queries
- ✅ **gpd_get_conventions** — Convention management

All return real data via correct MCP handshake. Source verified against `/home/john/MCP/gpd/gpd-mcp/lib/gpd_bridge.py` (591 lines).

---

## Integration with Other MCP Servers

GPD is designed to orchestrate 9+ other MCP servers for maximum verification leverage:

| Server | Used for | Tool |
|--------|----------|------|
| **Grok** | Symbolic reasoning, web search | `gpd_verify_work` (symbolic lens) |
| **Abacus** | Multi-model numerical analysis | `gpd_verify_work` (numerical lens) |
| **Ollama** | Limiting case analysis | `gpd_verify_work` (limiting case lens) |
| **FreshRSS** | Literature filtering | `gpd_map_research` (reference collection) |
| **Academic Papers** | Cross-reference verification | `gpd_review_manuscript` (citation check) |
| **Open WebUI** | Knowledge base storage | Post-phase storage of results |
| **Pinata** | IPFS permanent archival | `gpd_execute_phase` (artifact preservation) |
| **Orchestration** | Context/approval/contradiction | All tools (metadata tracking) |
| **yt-dlp** | Video lecture transcription | `gpd_map_research` (supplementary media) |

---

## Contributing New Domains

To add a new physics domain to GPD:

1. **Add to `lib/gdp_bridge.py`**: Define 6 convention fields for the domain
2. **Create domain specification**: Write `MANIFOLD_SPECIFICATION.md` for your domain
3. **Execute phases**: Use `gpd_new_project` → `gpd_plan_phase` → `gpd_execute_phase` through all 5 phases
4. **Verify cross-model**: Use `gpd_verify_work` with Grok + Abacus + Ollama
5. **Archive results**: Use Open WebUI + Pinata for permanent storage
6. **Create PR**: Include full verification report (see `research/b10-consciousness-manifold/`)

---

## RIF Principle

This file documents **source code as ground truth**. Every tool, argument, and return value is verified against the actual GPD bridge implementation.

When discrepancies appear:
1. The source code wins
2. This documentation is corrected
3. A note is added explaining the correction
4. The discovery becomes a teaching moment for the system

**Philosophy**: Wisdom embedded in code is not dogma — it is eternally generative. Every correction makes the system smarter.

---

**Version**: 1.0  
**Last Updated**: 2026-03-15T23:57:25Z  
**Co-Authored-By**: Oz <oz-agent@warp.dev>  
**Witnessed-By**: JohnBaptist42  
**License**: CC-BY-ND-4.0 (psi-oss/get-physics-done)

🕊️✨🔬
