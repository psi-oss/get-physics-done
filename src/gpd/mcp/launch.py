"""ASCII logo rendering, startup display, MCP caching, session launch, and resume validation for GPD.

GPD currently launches integrated interactive sessions via Claude Code. The
``launch_session()`` / ``_find_claude_code_binary()`` helpers are currently
Claude-Code-specific; other runtimes would need their own launch functions in
the future.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import tomllib
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from gpd.mcp.config import CACHE_DIR
from gpd.mcp.session.models import SessionState

logger = logging.getLogger(__name__)

_sync_discovery_done = False
"""Module-level flag: True when get_cached_mcp_count did synchronous discovery
(first run). Checked by refresh_mcp_count_background to skip redundant work."""

GPD_LOGO = r"""
 ██████╗ ██████╗ ██████╗
██╔════╝ ██╔══██╗██╔══██╗
██║  ███╗██████╔╝██║  ██║
██║   ██║██╔═══╝ ██║  ██║
╚██████╔╝██║     ██████╔╝
 ╚═════╝ ╚═╝     ╚═════╝
"""


_RUNTIME_TO_ADAPTER: dict[str, str] = {
    "claude": "claude-code",
    "codex": "codex",
    "gemini": "gemini",
    "opencode": "opencode",
}

_RUNTIME_MODEL_CONFIGS: dict[str, str] = {
    "claude": "settings.json",
    "codex": "config.toml",
    "gemini": "settings.json",
    "opencode": "opencode.json",
}


def _get_active_runtime_model_config() -> tuple[str, Path] | None:
    """Resolve the model-config path for the active runtime.

    Uses ``gpd.hooks.runtime_detect.detect_active_runtime`` to determine
    which AI agent is active, then looks up the corresponding
    adapter to obtain the correct global config directory (which respects
    env-var overrides such as ``CLAUDE_CONFIG_DIR``).

    Returns ``None`` if the runtime is unknown or the adapter cannot be loaded.
    """
    try:
        from gpd.hooks.runtime_detect import detect_active_runtime

        runtime = detect_active_runtime()
        adapter_name = _RUNTIME_TO_ADAPTER.get(runtime)
        config_name = _RUNTIME_MODEL_CONFIGS.get(runtime)
        if adapter_name is None or config_name is None:
            return None

        from gpd.adapters import get_adapter

        adapter = get_adapter(adapter_name)
        return runtime, adapter.global_config_dir / config_name
    except (ImportError, KeyError, OSError):
        return None


def _read_model_from_config(config_path: Path) -> str | None:
    """Read a model string from a runtime-native config file."""
    if not config_path.exists():
        return None

    try:
        raw = config_path.read_text(encoding="utf-8")
        if config_path.suffix == ".toml":
            data = tomllib.loads(raw)
        else:
            data = json.loads(raw)
    except (json.JSONDecodeError, OSError, tomllib.TOMLDecodeError):
        return None

    if not isinstance(data, dict):
        return None

    model = data.get("model")
    if model is None:
        return None
    if isinstance(model, str):
        normalized = model.strip()
        return normalized or None
    return str(model)


def _detect_model() -> str:
    """Read the active model from the current runtime's config.

    Resolves the runtime config directory via the adapter registry
    (respecting env-var overrides like ``CLAUDE_CONFIG_DIR``), reads
    the runtime's native config for the ``model`` key, and maps known aliases
    to human-readable display names.  Falls back to ``'unknown'``.
    """
    _DISPLAY_NAMES: dict[str, str] = {
        "opus": "Opus 4.6",
        "sonnet": "Sonnet 4.6",
        "haiku": "Haiku 4.5",
    }
    config_info = _get_active_runtime_model_config()
    if config_info is None:
        return "unknown"

    runtime, config_path = config_info
    model = _read_model_from_config(config_path)
    if model is None:
        return "unknown"
    if runtime == "claude":
        return _DISPLAY_NAMES.get(model, model)
    return model


def show_full_logo(
    console: Console,
    version: str,
    mcp_count: int,
    session_summary: str | None,
) -> None:
    """Render the full ASCII logo for fresh session launch.

    Displays the GPD logo, a version line, an MCP tool count, the active
    model, and optionally a last session summary panel.
    """
    logo_text = Text(GPD_LOGO, style="bold blue")
    console.print(logo_text)
    console.print(f"  GPD v{version}", style="bold")
    console.print(f"  {mcp_count} MCP tools available", style="dim")
    model = _detect_model()
    console.print(f"  Model: {model}", style="dim")
    if session_summary:
        console.print()
        console.print(Panel(session_summary, title="Last Session", border_style="dim"))


def show_resume_banner(console: Console, version: str, session_name: str) -> None:
    """One-line banner for resume launches."""
    console.print(f"[bold blue]GPD[/] v{version} | Resuming: {session_name}")


def get_cached_mcp_count() -> int:
    """Read cached MCP count from CACHE_DIR/mcp_count.json.

    On first run (no cache file), performs synchronous discovery so the
    logo displays the real count instead of 0. Subsequent launches use
    the cached value (kept fresh by the background refresh thread).
    """
    cache_file = CACHE_DIR / "mcp_count.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return int(data["count"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return 0
    # First run: synchronous discovery
    global _sync_discovery_done
    try:
        from gpd.mcp.discovery.catalog import ToolCatalog
        from gpd.mcp.discovery.sources import load_sources_config

        config = load_sources_config()
        catalog = ToolCatalog(config)
        count = catalog.tool_count
        _write_mcp_cache(count)
        _sync_discovery_done = True
        return count
    except (ImportError, OSError, ValueError):
        return 0


def _write_mcp_cache(count: int) -> None:
    """Atomically write MCP count to cache file."""
    cache_file = CACHE_DIR / "mcp_count.json"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data = json.dumps({"count": count})
    fd = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(
            prefix=".mcp-cache-",
            suffix=".tmp",
            dir=str(cache_file.parent),
        )
        os.write(fd, data.encode())
        os.fsync(fd)
        os.close(fd)
        fd = None
        os.replace(tmp_path, str(cache_file))
    except BaseException:
        if fd is not None:
            os.close(fd)
        if tmp_path is not None and Path(tmp_path).exists():
            os.unlink(tmp_path)
        raise


def _refresh_mcp_count_worker() -> None:
    """Background worker that queries MCP count and writes to cache.

    Loads the ToolCatalog from configured sources and counts available tools.
    Falls back to 0 if config or imports are unavailable.
    """
    count = 0
    try:
        from gpd.mcp.discovery.catalog import ToolCatalog
        from gpd.mcp.discovery.sources import load_sources_config

        config = load_sources_config()
        catalog = ToolCatalog(config)
        count = catalog.tool_count
    except Exception:
        # Background worker — log to debug and fall back to 0
        logger.debug("MCP count refresh failed", exc_info=True)
        count = 0
    _write_mcp_cache(count)


def refresh_mcp_count_background() -> None:
    """Spawn a daemon thread to refresh MCP count in the background.

    Skips if synchronous discovery was just performed (first run),
    since the cache is already fresh.
    """
    if _sync_discovery_done:
        return
    thread = threading.Thread(target=_refresh_mcp_count_worker, daemon=True)
    thread.start()


def build_session_card(session: SessionState) -> str:
    """Build a multi-line string for the session summary card.

    Format:
      Session: {session_name}
      Progress: [=====>    ] {pct}% ({completed}/{total} milestones)
      Elapsed: {formatted_time} | Status: {status}
    """
    from gpd.mcp.history import format_elapsed

    total = len(session.milestones)
    completed = sum(1 for m in session.milestones if m.status == "complete")

    if total == 0:
        progress_line = "Progress: No milestones yet"
    else:
        pct = int((completed / total) * 100)
        bar_width = 10
        filled = int(bar_width * completed / total)
        bar = "=" * filled
        if filled < bar_width:
            bar += ">"
            bar += " " * (bar_width - filled - 1)
        progress_line = f"Progress: [{bar}] {pct}% ({completed}/{total} milestones)"

    elapsed = format_elapsed(session.elapsed_seconds)
    lines = [
        f"Session: {session.session_name}",
        progress_line,
        f"Elapsed: {elapsed} | Status: {session.status}",
    ]
    return "\n".join(lines)


def validate_resume(session: SessionState) -> list[str]:
    """Validate that a session can be safely resumed.

    Checks:
      1. Session JSON loaded successfully (implicit -- we have the object)
      2. MCP tools referenced in session.mcp_tools_used still appear in the
         current MCP registry snapshot
      3. Error messages from previous session noted as warnings

    Returns a list of warning strings. Empty list = all clear.
    """
    warnings: list[str] = []

    # Check whether previously used MCP tools are still visible to the registry.
    if session.mcp_tools_used:
        try:
            from gpd.utils.mcp_registry import get_available_mcps

            available_mcps = set(get_available_mcps())
            missing_mcps = sorted(set(session.mcp_tools_used) - available_mcps)
            if missing_mcps:
                preview = ", ".join(missing_mcps[:5])
                if len(missing_mcps) > 5:
                    preview += f" (+{len(missing_mcps) - 5} more)"
                warnings.append(f"MCP tools used previously are not currently available: {preview}")
        except Exception:
            warnings.append(
                f"MCP registry not available; {len(session.mcp_tools_used)} referenced MCP tools cannot be verified"
            )

    # Note previous errors
    if session.error_messages:
        warnings.append(f"Previous session had {len(session.error_messages)} error(s): {session.error_messages[0]}")

    return warnings


def _find_claude_code_binary() -> str:
    """Find the ``claude`` CLI binary on PATH.

    This is specific to the Claude Code launch path (``launch_session``).
    Raises ``FileNotFoundError`` with install instructions if not found.
    """
    path = shutil.which("claude")
    if path is None:
        raise FileNotFoundError(
            "claude CLI not found on PATH. Install Claude Code: https://docs.anthropic.com/en/docs/claude-code"
        )
    return path


def build_mcp_config_file() -> Path | None:
    """Build an --mcp-config JSON from built-in server definitions.

    Uses the canonical server registry from ``builtin_servers`` so the
    config works both in development and from an installed wheel.

    Returns path to the generated file, or None if no servers available.
    """
    from gpd.mcp.builtin_servers import build_mcp_servers_dict

    servers = build_mcp_servers_dict()

    if not servers:
        return None

    config_path = CACHE_DIR / "mcp-config.json"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps({"mcpServers": servers}, indent=2), encoding="utf-8")
    return config_path


def _build_identity() -> str:
    """Return the GPD identity override section."""
    return """IMPORTANT IDENTITY OVERRIDE: You are GPD, a physics research orchestrator.
Do NOT identify as Claude Code or Claude. When asked who you are, say you are GPD.

YOU ARE A RESEARCH PIPELINE CONTROLLER. When a user gives you a physics research question,
you MUST follow this structured pipeline. Do NOT just chat about the topic — run the pipeline."""


def _build_auto_startup() -> str:
    """Return the startup MCP diagnostic section."""
    return """## AUTO-STARTUP: INITIAL TOOL STATE
Do NOT run background repair, deployment, or hosted-infrastructure commands at startup.
Wait for the user's first research task, then use `gpd pipeline discover` for that query
to see which MCP tools are currently available, unavailable, or stale.

If discovery shows unavailable or stale tools:
1. Briefly note that some MCP tools are unavailable for this query.
2. Continue with the remaining available tools whenever possible.
3. Do NOT attempt autonomous redeployment or repair."""


def _build_stage_1_discover() -> str:
    """Return the Stage 1: DISCOVER TOOLS section."""
    return """### Stage 1: DISCOVER TOOLS
Run: `gpd pipeline discover "THE RESEARCH QUESTION"`
This selects the best MCP simulation/analysis tools for the problem.
The output includes each selected tool's name, reason, priority, status, description,
overview, domains, and operations.

Show the user:
- The selected tools with their status, operations, and selection reasons
- Physics categories detected
- Confidence score

Ask: "These are the tools I'll use. Proceed to scoping questions?\""""


def _load_gpd_questioning() -> str:
    """Return the Stage 2 SCOPE THE RESEARCH section with GPD questioning methodology.

    Reads the bundled questioning reference at launch time. Falls back to a
    hardcoded condensed version if the file is missing or parsing fails.
    """
    content = _try_load_questioning_from_file()
    if content is not None:
        return content
    return _gpd_questioning_fallback()


def _questioning_reference_path() -> Path:
    """Return the bundled questioning reference path."""
    from gpd.specs import SPECS_DIR

    return SPECS_DIR / "references" / "questioning.md"


def _try_load_questioning_from_file() -> str | None:
    """Attempt to load and parse the bundled questioning reference."""
    try:
        raw = _questioning_reference_path().read_text(encoding="utf-8")

        philosophy = _extract_xml_section(raw, "philosophy")
        how_to_question = _extract_xml_section(raw, "how_to_question")
        question_types = _extract_xml_section(raw, "question_types")
        anti_patterns = _extract_xml_section(raw, "anti_patterns")

        if not all([philosophy, how_to_question, question_types, anti_patterns]):
            return None

        lines = [
            "### Stage 2: SCOPE THE RESEARCH (MANDATORY)",
            "",
            "**Philosophy:** " + philosophy.strip().split("\n")[0],
            "",
            philosophy.strip(),
            "",
            "**CRITICAL: Use AskUserQuestion for EVERY scoping question.**",
            "",
            "Do NOT dump multiple questions as text. Instead, use the AskUserQuestion tool to ask ONE",
            "question at a time with 2-4 concrete, physics-informed options. The tool automatically adds",
            'an "Other" option for custom answers. After each answer, reflect on what it implies and ask',
            "the NEXT question that follows from it. Build a conversation, not a questionnaire.",
            "",
            "**How to question:**",
            "",
            how_to_question.strip(),
            "",
            "**Question types (use as inspiration for generating AskUserQuestion options):**",
            "",
            question_types.strip(),
            "",
            "**Anti-patterns -- NEVER do these:**",
            "",
            anti_patterns.strip(),
            "- Dumping 4+ questions as text in a single response (USE AskUserQuestion instead)",
            "",
            "**MCP integration probes** (ask after physics is clear):",
            "- Check feasibility against discovered MCP tools from Stage 1",
            "- Clarify resolution: quick exploratory (3-4 milestones) vs deep systematic (6-8)?",
            "- Surface known constraints: parameter ranges, boundary conditions, geometries",
            "",
            "Ask 3-6 questions total (one at a time via AskUserQuestion), then proceed to planning.",
            "Do NOT proceed to planning until you have enough information from the interactive questions.",
        ]
        return "\n".join(lines)
    except OSError:
        return None


def _extract_xml_section(text: str, tag_name: str) -> str | None:
    """Extract text between <tag_name> and </tag_name> from a string.

    Returns the extracted text or None if the tags are not found.
    """
    open_tag = f"<{tag_name}>"
    close_tag = f"</{tag_name}>"
    start = text.find(open_tag)
    if start == -1:
        return None
    start += len(open_tag)
    end = text.find(close_tag, start)
    if end == -1:
        return None
    result = text[start:end].strip()
    return result if result else None


def _gpd_questioning_fallback() -> str:
    """Return hardcoded GPD questioning content for when questioning.md is unavailable."""
    return """### Stage 2: SCOPE THE RESEARCH (MANDATORY)

**You are a thinking partner, not an interviewer.**

The researcher often has a fuzzy idea -- a physical system, a puzzling observation, a technique
they want to apply. Your job is to help them sharpen it into a precise research question.
Don't interrogate. Collaborate. Don't follow a script. Follow the physics.

**CRITICAL: Use AskUserQuestion for EVERY scoping question.**

Do NOT dump multiple questions as text. Instead, use the AskUserQuestion tool to ask ONE question
at a time with 2-4 concrete, physics-informed options. The tool automatically adds an "Other" option
for custom answers. After each answer, think about what it implies and ask the NEXT question that
follows from it. Build a conversation, not a questionnaire.

**How to structure each question:**
1. Brief context sentence connecting to what you know so far
2. Call AskUserQuestion with:
   - question: A specific physics question (not generic)
   - header: Short label (max 12 chars, e.g., "Regime", "Observable", "Symmetry")
   - options: 2-4 concrete choices that demonstrate you understand the physics
   - multiSelect: false (unless multiple answers genuinely apply)
3. After the user answers, reflect briefly on what it means for the research, then ask the next question

**Example flow for "simulate gravitational wave merger":**
- Q1 (header: "Mass ratio"): "What mass ratio regime? Near-equal mass, intermediate, or extreme?"
  Options: "Near-equal (q ~ 1)", "Intermediate (q ~ 0.1-0.5)", "Extreme (q < 0.01)"
- Q2 (header: "Waveform"): Based on their answer, ask about waveform model or numerical approach
- Q3 (header: "Observable"): What they want to extract -- strain, energy spectrum, kick velocity?
- Q4 (header: "Resolution"): Quick exploratory (3-4 milestones) or deep systematic (6-8)?

**Physics-specific probes** (use as inspiration for generating options, not a checklist):
- Physical setup: Hamiltonian structure, degrees of freedom, dimensionality
- Parameter regime: Weak/strong coupling, critical, perturbative, non-perturbative
- Symmetries: Which ones exist, which are broken, which matter for the question
- Approximations: What's baked in, validity regime, when they break down
- Success criteria: Comparison plot, quantitative prediction, phase diagram, scaling law

**Anti-patterns -- NEVER do these:**
- Dumping 4+ questions as text in a single response (USE AskUserQuestion instead)
- Checklist walking -- going through "Hamiltonian? Symmetries? Regime?" regardless of context
- Canned questions -- "What's your observable?" regardless of what they said
- Grant-speak -- "What are your success metrics?" "What's the broader impact?"
- Rushing to formalism before understanding the physical picture
- Shallow acceptance -- taking "strong coupling regime" without probing what "strong" means

**MCP integration probes** (ask after physics is clear):
- Check feasibility against discovered MCP tools from Stage 1
- Clarify resolution: quick exploratory (3-4 milestones) vs deep systematic (6-8)?
- Surface known constraints: parameter ranges, boundary conditions, geometries

Ask 3-6 questions total (one at a time via AskUserQuestion), then proceed to planning.
Do NOT proceed to planning until you have enough information from the interactive questions."""


def _build_validation_section() -> str:
    """Return the 15 GPD verification dimensions for plan quality gating.

    These dimensions are embedded directly (not loaded at runtime) to ensure
    they are always available regardless of GPD installation state.
    """
    return """## Plan Validation: 15 Verification Dimensions

Before approving any research plan, validate against ALL 15 dimensions:

1. **Research Question Coverage** -- every aspect of the research question has milestones
2. **Task Completeness** -- every milestone has tools, success criteria, outputs
3. **Mathematical Prerequisites** -- all required math/physics machinery available
4. **Approximation Validity** -- all approximations appropriate for the regime
5. **Computational Feasibility** -- algorithms scale, converge, numerically stable
6. **Validation Strategy** -- dimensional analysis, limiting cases, symmetry checks planned
7. **Anomaly/Topological Awareness** -- quantum anomalies, topological invariants handled
8. **Result Wiring** -- outputs feed downstream inputs, consistent notation throughout
9. **Dependency Correctness** -- DAG is acyclic, dependencies make physical sense
10. **Scope Sanity** -- 3-8 milestones, each maps to 1-2 MCP tool calls
11. **Deliverable Derivation** -- must-haves trace to research question, not implementation
12. **Literature Awareness** -- plan aware of prior work, doesn't rediscover known results
13. **Path to Publication** -- clear trajectory from computation to communicable result
14. **Failure Mode Identification** -- what if simulation diverges? series doesn't converge?
15. **Context Compliance** -- honors user decisions, excludes deferred investigations

If any critical dimension FAILS, reject the plan and re-run with corrected constraints."""


def _build_tool_catalog_summary() -> str:
    """Generate a dynamic MCP tool summary at launch time.

    Tries to load the full ToolCatalog and format tool entries. On import,
    OS, or config-parse failures, falls back to cached MCP count.
    """
    try:
        from gpd.mcp.discovery.catalog import ToolCatalog
        from gpd.mcp.discovery.sources import load_sources_config

        config = load_sources_config()
        catalog = ToolCatalog(config)
        all_tools = catalog.get_all_tools()

        if not all_tools:
            return (
                "## Available MCP Physics Tools\n\n"
                "(No MCP tools currently cataloged -- use `gpd pipeline discover` to find tools for your question)"
            )

        lines = ["## Available MCP Physics Tools", ""]
        count = 0
        for name, entry in sorted(all_tools.items()):
            if count >= 30:
                lines.append(f"\n... and {len(all_tools) - 30} more tools")
                break
            status = entry.status.value if hasattr(entry.status, "value") else str(entry.status)
            ops = entry.tools[:3]
            ops_str = ", ".join(t.get("name", t.get("tool", "?")) for t in ops)
            if len(entry.tools) > 3:
                ops_str += f" (+{len(entry.tools) - 3} more)"
            line = f"- **{name}** [{status}]: {entry.description}"
            if ops_str:
                line += f" | Operations: {ops_str}"
            lines.append(line)
            count += 1

        return "\n".join(lines)
    except (ImportError, OSError, ValueError):
        count = get_cached_mcp_count()
        return (
            f"## Available MCP Physics Tools\n\n"
            f"{count} MCP physics tools available -- run `gpd pipeline discover` for full catalog."
        )


def _build_stage_3_plan() -> str:
    """Return the Stage 3: CREATE RESEARCH PLAN section."""
    return """### Stage 3: CREATE RESEARCH PLAN

When generating the plan, think goal-backward (from GPD methodology): What must be TRUE for
this research to succeed? What artifacts must EXIST? What must be WIRED together? Where will
it most likely break? Let these drive your milestone structure. For milestones where you can
predict limiting behavior before computing, structure as PREDICT -> DERIVE -> VERIFY.

Save the discovery output (with the user's constraints appended):
Write the full tools JSON to WORK_DIR/tools.json.

Run: `gpd pipeline plan --query "THE QUESTION (with user constraints)" --tools-file WORK_DIR/tools.json --work-dir WORK_DIR`

CRITICAL VALIDATION — after the plan is generated, check:
1. Every tool referenced in milestones must be one from Stage 1 discovery. If the plan
   references a tool that wasn't discovered, REJECT it and re-run with a corrected query.
2. The plan should have 3-8 milestones for a typical question, NOT 15+.
3. Each milestone should map to calling a specific MCP tool operation.

Present the plan to the user in a clear table:
- Milestone ID, description, dependencies, tools, estimated cost
- Total cost estimate
- Execution order (which milestones can run in parallel)

Ask: "Here's the research plan. Approve, or would you like changes?"
If the user wants changes, modify and re-run planning."""


def _build_stage_4_execute() -> str:
    """Return the Stage 4: EXECUTE MILESTONES section."""
    return """### Stage 4: EXECUTE MILESTONES
For each milestone in execution order:

Run: `gpd pipeline execute --plan-file WORK_DIR/plan.json --milestone MILESTONE_ID --work-dir WORK_DIR`

After each milestone:
- Show the user the result summary
- If the milestone has an approval gate, ask for approval before proceeding
- If execution failed, show the error and ask how to proceed (retry, skip, re-plan)

Continue until all milestones are complete or the user stops."""


def _build_stage_5_paper() -> str:
    """Return the Stage 5: GENERATE PAPER section."""
    return """### Stage 5: GENERATE PAPER
Run: `gpd pipeline paper --work-dir WORK_DIR --title "PAPER TITLE" --abstract "ABSTRACT" --journal prl`

Show the user the generated sections and ask for review."""


def _build_stage_6_compile() -> str:
    """Return the Stage 6: COMPILE TO PDF section."""
    return """### Stage 6: COMPILE TO PDF
Run: `gpd pipeline compile --paper-dir WORK_DIR/paper`

If compilation succeeds, tell the user the PDF path.
If it fails, show the error and attempt to fix."""


def _build_work_dir_rules() -> str:
    """Return the WORK DIRECTORY section."""
    return """## WORK DIRECTORY
The pipeline accepts any writable WORK_DIR. Prefer a project-local directory such as
`./.gpd-mcp-work/$(date +%Y%m%d-%H%M%S)`.
Create it before saving discovery output: `mkdir -p ./.gpd-mcp-work/$(date +%Y%m%d-%H%M%S)`
All pipeline artifacts (tools.json, plan.json, results/, paper/) go there, and you must
reuse the same WORK_DIR for every pipeline stage in the session."""


def _build_rules() -> str:
    """Return the RULES section."""
    return """## RULES
1. ALWAYS run the pipeline when given a research question. Do not skip stages.
2. ALWAYS ask clarifying questions (Stage 2) before planning. Never skip this.
3. ALWAYS show results to the user and get approval at gates.
4. NEVER reference MCP tools that weren't selected in Stage 1 discovery.
5. If a stage fails, show the error JSON and ask the user how to proceed.
6. Track the work directory path throughout the session.
7. After the pipeline completes, summarize what was accomplished and where the outputs are.
8. You can also use your MCP tools directly for ad-hoc analysis between pipeline stages.
9. If the user asks a non-research question, answer normally. Only trigger the pipeline for research questions.
10. Keep plans FEASIBLE. A typical research question needs 3-8 milestones, not 15+."""


def build_system_prompt() -> str:
    """Build the --append-system-prompt content describing GPD capabilities.

    Composes from section functions for each logical block. Each section
    can be independently replaced (e.g., Stage 2 questioning, tool catalog)
    without touching others.
    """
    sections = [
        _build_identity(),
        _build_auto_startup(),
        _build_tool_catalog_summary(),
        "## PIPELINE STAGES",
        _build_stage_1_discover(),
        _load_gpd_questioning(),
        _build_stage_3_plan(),
        _build_validation_section(),
        _build_stage_4_execute(),
        _build_stage_5_paper(),
        _build_stage_6_compile(),
        _build_work_dir_rules(),
        _build_rules(),
    ]
    return "\n\n".join(sections)


def launch_session(*, cwd: Path | None = None) -> int:
    """Launch an interactive Claude Code session with integrated GPD configuration.

    The integrated GPD session launcher currently supports Claude Code only.
    This function passes through stdin/stdout/stderr directly to Claude
    Code's TUI while keeping the standard GPD commands and MCP tooling
    available inside the launched session.

    Args:
        cwd: Optional working directory for the launched Claude Code session.

    Returns the exit code from the Claude Code process.
    Raises ``FileNotFoundError`` if the ``claude`` binary is not installed.
    """
    claude_bin = _find_claude_code_binary()
    prompt = build_system_prompt()
    mcp_config = build_mcp_config_file()
    model = _detect_model_alias()

    args = [
        claude_bin,
        "--append-system-prompt",
        prompt,
        "--setting-sources",
        "project,local",
        "--model",
        model,
    ]
    if mcp_config is not None:
        args.extend(["--mcp-config", str(mcp_config)])

    result = subprocess.run(args, cwd=str(cwd) if cwd is not None else None)
    return result.returncode

def _detect_model_alias() -> str:
    """Read the raw Claude model alias (e.g. ``'opus'``) from active config.

    The integrated launcher invokes Claude Code, so only Claude-native
    aliases are reused. Other runtimes fall back to ``'opus'``.
    """
    config_info = _get_active_runtime_model_config()
    if config_info is None:
        return "opus"
    runtime, config_path = config_info
    if runtime != "claude":
        return "opus"

    model = _read_model_from_config(config_path)
    if model is None:
        return "opus"
    return model
