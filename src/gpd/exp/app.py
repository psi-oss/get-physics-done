"""GPD-Exp experiment dashboard — minimal web UI using only stdlib.

Provides a read-only artifact viewer (no dependencies beyond stdlib).

Scans the working directory (or --dir) for experiment artifact JSON files
produced by /gpd:new-experiment and /gpd:run-experiment, then
serves a self-contained HTML dashboard on localhost.

Usage:
    python -m gpd.exp.app                    # serve current directory
    python -m gpd.exp.app --dir ./output     # serve specific directory
    python -m gpd.exp.app --port 8080        # custom port
"""

from __future__ import annotations

import argparse
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def _load_json(path: Path) -> dict | list | None:
    """Load a JSON file, returning None if missing or invalid."""
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _cents_to_display(cents: int) -> str:
    """Format integer cents as a dollar string."""
    return f"${cents / 100:,.2f}"


def _build_dashboard_html(artifacts_dir: Path) -> str:
    """Build the complete dashboard HTML from artifact JSON files."""
    protocol = _load_json(artifacts_dir / "protocol.json")
    cost = _load_json(artifacts_dir / "cost_estimate.json")
    bounty_spec = _load_json(artifacts_dir / "bounty_spec.json")
    ethics = _load_json(artifacts_dir / "ethics_screening.json")

    has_data = any(x is not None for x in [protocol, cost, bounty_spec, ethics])

    # Build sections
    if not has_data:
        body = _section_empty(artifacts_dir)
    else:
        sections = []
        sections.append(_section_overview(protocol))
        sections.append(_section_design(protocol))
        sections.append(_section_budget(cost))
        sections.append(_section_bounties(bounty_spec))
        sections.append(_section_ethics(ethics))
        body = "\n".join(sections)

    return _HTML_TEMPLATE.replace("{{BODY}}", body).replace(
        "{{TITLE}}",
        _extract_title(protocol),
    )


def _extract_title(protocol: dict | None) -> str:
    if protocol and "question" in protocol:
        q = protocol["question"]
        return q[:80] + "..." if len(q) > 80 else q
    return "GPD-Exp Dashboard"


def _section_empty(artifacts_dir: Path) -> str:
    return f"""
    <div class="card">
      <h2>No Experiment Found</h2>
      <p class="dim">No experiment artifacts found in <code>{artifacts_dir}</code>.</p>
      <p>Run <code>/gpd:new-experiment</code> to design an experiment. Artifacts will be saved here:</p>
      <ul>
        <li><code>protocol.json</code> — Experiment protocol</li>
        <li><code>cost_estimate.json</code> — Cost breakdown</li>
        <li><code>bounty_spec.json</code> — Bounty specification</li>
        <li><code>ethics_screening.json</code> — Ethics check</li>
      </ul>
    </div>
    """


def _section_overview(protocol: dict | None) -> str:
    if not protocol:
        return '<div class="card muted"><h2>Protocol</h2><p>Not yet designed.</p></div>'

    question = protocol.get("question", "—")
    sample = protocol.get("sample_size_target", "—")
    procedure = protocol.get("measurement_procedure", "—")
    duration = protocol.get("expected_duration_minutes", "—")
    materials = protocol.get("materials_required", [])

    hypotheses_html = ""
    for h in protocol.get("hypotheses", []):
        hypotheses_html += f"""
        <div class="hypothesis">
          <div><span class="label">H0:</span> {h.get("null_hypothesis", "—")}</div>
          <div><span class="label">H1:</span> {h.get("alternative_hypothesis", "—")}</div>
          <div class="dim">Direction: {h.get("direction", "—")} | Effect size: {h.get("predicted_effect_size", "—")}</div>
        </div>"""

    return f"""
    <div class="card">
      <h2>Experiment Overview</h2>
      <div class="question">{question}</div>
      <div class="stats-row">
        <div class="stat"><div class="stat-value">{sample}</div><div class="stat-label">Target N</div></div>
        <div class="stat"><div class="stat-value">{duration} min</div><div class="stat-label">Duration/task</div></div>
        <div class="stat"><div class="stat-value">{len(materials)}</div><div class="stat-label">Materials</div></div>
      </div>
      <h3>Hypotheses</h3>
      {hypotheses_html or '<p class="dim">None specified.</p>'}
      <h3>Procedure</h3>
      <p>{procedure}</p>
    </div>
    """


def _section_design(protocol: dict | None) -> str:
    if not protocol:
        return ""

    design = protocol.get("study_design", {})
    design_type = design.get("design_type", "—")

    details = ""
    if design_type == "between_subjects":
        groups = ", ".join(design.get("groups", []))
        method = design.get("assignment_method", "—")
        details = f"Groups: {groups}<br>Assignment: {method}"
    elif design_type == "within_subjects":
        conditions = ", ".join(design.get("conditions", []))
        details = f"Conditions: {conditions}<br>Counterbalanced: {design.get('counterbalance', '—')}"
    elif design_type == "factorial":
        factors = ", ".join(design.get("factors", []))
        levels = design.get("levels_per_factor", {})
        levels_str = " x ".join(str(len(v)) for v in levels.values())
        details = f"Factors: {factors}<br>Design: {levels_str}"

    variables_html = ""
    for v in protocol.get("variables", []):
        role = v.get("role", "—")
        badge_class = {
            "independent": "badge-iv",
            "dependent": "badge-dv",
            "confound": "badge-confound",
            "control": "badge-control",
        }.get(role, "")
        variables_html += f"""
        <div class="variable">
          <span class="badge {badge_class}">{role.upper()}</span>
          <strong>{v.get("name", "—")}</strong>
          <span class="dim">({v.get("variable_type", "—")}{", " + v.get("unit", "") if v.get("unit") else ""})</span>
        </div>"""

    return f"""
    <div class="card">
      <h2>Study Design</h2>
      <div class="design-type">{design_type.replace("_", " ").title()}</div>
      <p>{details}</p>
      <h3>Variables</h3>
      <div class="variables-list">{variables_html or '<p class="dim">None specified.</p>'}</div>
    </div>
    """


def _section_budget(cost: dict | None) -> str:
    if not cost:
        return '<div class="card muted"><h2>Budget</h2><p>Not yet estimated.</p></div>'

    total = cost.get("estimated_total_cents", 0)
    low = cost.get("confidence_low_cents", 0)
    high = cost.get("confidence_high_cents", 0)

    items_html = ""
    for li in cost.get("line_items", []):
        items_html += f"""
        <tr>
          <td>{li.get("description", "—")}</td>
          <td class="num">{li.get("quantity", "—")}</td>
          <td class="num">{_cents_to_display(li.get("unit_price_cents", 0))}</td>
          <td class="num"><strong>{_cents_to_display(li.get("subtotal_cents", 0))}</strong></td>
        </tr>"""

    return f"""
    <div class="card">
      <h2>Budget Estimate</h2>
      <div class="stats-row">
        <div class="stat"><div class="stat-value">{_cents_to_display(total)}</div><div class="stat-label">Estimated Total</div></div>
        <div class="stat"><div class="stat-value">{_cents_to_display(low)}</div><div class="stat-label">Low Estimate</div></div>
        <div class="stat"><div class="stat-value">{_cents_to_display(high)}</div><div class="stat-label">High Estimate</div></div>
      </div>
      <table>
        <thead><tr><th>Item</th><th>Qty</th><th>Unit</th><th>Subtotal</th></tr></thead>
        <tbody>{items_html}</tbody>
      </table>
      <p class="dim">{cost.get("reasoning", "")}</p>
    </div>
    """


def _section_bounties(spec: dict | None) -> str:
    if not spec:
        return '<div class="card muted"><h2>Bounty Spec</h2><p>Not yet translated.</p></div>'

    # Handle both single spec and list of specs
    specs = spec if isinstance(spec, list) else [spec]
    cards = ""
    for s in specs:
        skills = ", ".join(s.get("skills_needed", [])) or "None"
        reqs = "".join(f"<li>{r}</li>" for r in s.get("requirements", []))
        price = _cents_to_display(s.get("price_cents", 0))
        spots = s.get("spots_available", 1)
        cards += f"""
        <div class="bounty">
          <h3>{s.get("title", "Untitled Bounty")}</h3>
          <div class="stats-row">
            <div class="stat"><div class="stat-value">{price}</div><div class="stat-label">Per Worker</div></div>
            <div class="stat"><div class="stat-value">{spots}</div><div class="stat-label">Spots</div></div>
          </div>
          <p>{s.get("description", "—")[:300]}</p>
          <div class="dim">Skills: {skills}</div>
          {f"<ul>{reqs}</ul>" if reqs else ""}
        </div>"""

    return f'<div class="card"><h2>Bounty Specifications</h2>{cards}</div>'


def _section_ethics(ethics: dict | None) -> str:
    if not ethics:
        return '<div class="card muted"><h2>Ethics</h2><p>Not yet screened.</p></div>'

    passed = ethics.get("ethics_passed", False)
    severity = ethics.get("severity", "unknown")
    status_class = "status-pass" if passed else "status-fail"
    status_text = "PASS" if passed else "FAIL"

    concerns = ""
    for c in ethics.get("concerns", []):
        concerns += f"<li>{c}</li>"

    flags = ""
    for f in ethics.get("keyword_flags", []):
        flags += f'<span class="badge badge-confound">{f}</span> '

    return f"""
    <div class="card">
      <h2>Ethics Screening</h2>
      <div class="stats-row">
        <div class="stat"><div class="stat-value {status_class}">{status_text}</div><div class="stat-label">Status</div></div>
        <div class="stat"><div class="stat-value">{severity}</div><div class="stat-label">Severity</div></div>
      </div>
      {f"<div>Keyword flags: {flags}</div>" if flags else ""}
      {f"<h3>Concerns</h3><ul>{concerns}</ul>" if concerns else '<p class="dim">No concerns identified.</p>'}
      <p class="dim">{ethics.get("reasoning", "")}</p>
    </div>
    """


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>{{TITLE}} — GPD-Exp</title>
<style>
  :root {
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #e6edf3; --dim: #8b949e; --accent: #58a6ff;
    --green: #3fb950; --red: #f85149; --yellow: #d29922; --purple: #bc8cff;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg); color: var(--text); padding: 2rem; max-width: 960px; margin: 0 auto; line-height: 1.6; }
  h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
  h2 { font-size: 1.2rem; margin-bottom: 1rem; color: var(--accent); border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }
  h3 { font-size: 1rem; margin: 1rem 0 0.5rem; color: var(--text); }
  .header { margin-bottom: 2rem; }
  .header .logo { color: var(--purple); font-weight: bold; font-size: 1.1rem; }
  .dim { color: var(--dim); font-size: 0.9rem; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    padding: 1.5rem; margin-bottom: 1.5rem; }
  .card.muted { opacity: 0.6; }
  .question { font-size: 1.1rem; font-style: italic; margin-bottom: 1rem; padding: 0.75rem;
    background: var(--bg); border-left: 3px solid var(--accent); border-radius: 4px; }
  .stats-row { display: flex; gap: 2rem; margin: 1rem 0; flex-wrap: wrap; }
  .stat { text-align: center; }
  .stat-value { font-size: 1.5rem; font-weight: bold; }
  .stat-label { font-size: 0.8rem; color: var(--dim); text-transform: uppercase; }
  .status-pass { color: var(--green); }
  .status-fail { color: var(--red); }
  .hypothesis { margin-bottom: 0.75rem; padding: 0.5rem; background: var(--bg); border-radius: 4px; }
  .label { font-weight: bold; color: var(--dim); }
  .design-type { font-size: 1.2rem; font-weight: bold; color: var(--purple); margin-bottom: 0.5rem; }
  .variables-list { display: flex; flex-direction: column; gap: 0.5rem; }
  .variable { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0; }
  .badge { font-size: 0.7rem; padding: 0.15rem 0.5rem; border-radius: 3px; font-weight: bold; text-transform: uppercase; }
  .badge-iv { background: #1f3a1f; color: var(--green); }
  .badge-dv { background: #1a2a40; color: var(--accent); }
  .badge-confound { background: #3a2a0a; color: var(--yellow); }
  .badge-control { background: #2a1a3a; color: var(--purple); }
  .bounty { padding: 1rem; background: var(--bg); border-radius: 6px; margin: 0.75rem 0; }
  table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
  th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid var(--border); }
  th { color: var(--dim); font-size: 0.85rem; text-transform: uppercase; }
  .num { text-align: right; font-variant-numeric: tabular-nums; }
  ul { padding-left: 1.5rem; margin: 0.5rem 0; }
  li { margin: 0.25rem 0; }
  code { background: var(--bg); padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.9rem; }
  p { margin: 0.5rem 0; }
</style>
</head>
<body>
  <div class="header">
    <span class="logo">GPD-Exp</span> <span class="dim">Experiment Dashboard</span>
    <h1>{{TITLE}}</h1>
    <p class="dim">Auto-refreshes every 30 seconds</p>
  </div>
  {{BODY}}
</body>
</html>
"""


class _DashboardHandler(BaseHTTPRequestHandler):
    """HTTP handler that serves the experiment dashboard."""

    artifacts_dir: Path  # Set via partial

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            html = _build_dashboard_html(self.artifacts_dir)
            self._respond(200, "text/html", html.encode())
        elif self.path == "/api/status":
            data = {
                "protocol": _load_json(self.artifacts_dir / "protocol.json") is not None,
                "cost_estimate": _load_json(self.artifacts_dir / "cost_estimate.json") is not None,
                "bounty_spec": _load_json(self.artifacts_dir / "bounty_spec.json") is not None,
                "ethics_screening": _load_json(self.artifacts_dir / "ethics_screening.json") is not None,
            }
            self._respond(200, "application/json", json.dumps(data).encode())
        else:
            self._respond(404, "text/plain", b"Not Found")

    def _respond(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Suppress default stderr logging."""


def make_handler(artifacts_dir: Path) -> type[_DashboardHandler]:
    """Create a handler class bound to a specific artifacts directory."""

    class BoundHandler(_DashboardHandler):
        pass

    BoundHandler.artifacts_dir = artifacts_dir  # type: ignore[attr-defined]
    return BoundHandler


def serve(artifacts_dir: Path, port: int = 8111) -> None:
    """Start the dashboard HTTP server."""
    handler = make_handler(artifacts_dir)
    server = HTTPServer(("127.0.0.1", port), handler)

    bold = "\033[1m"
    purple = "\033[35m"
    dim = "\033[2m"
    reset = "\033[0m"

    print(f"{purple}{bold}GPD-Exp Dashboard{reset}")
    print(f"{dim}Serving experiment artifacts from: {artifacts_dir}{reset}")
    print(f"{bold}Open: http://127.0.0.1:{port}{reset}")
    print(f"{dim}Press Ctrl+C to stop{reset}")
    print()

    webbrowser.open(f"http://127.0.0.1:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{dim}Shutting down...{reset}")
        server.shutdown()


def main() -> None:
    """CLI entry point for the dashboard."""
    parser = argparse.ArgumentParser(
        prog="gpd-exp-dashboard",
        description="Serve the GPD-Exp experiment dashboard",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path.cwd(),
        help="Directory containing experiment artifact JSON files (default: cwd)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8111,
        help="Port to serve on (default: 8111)",
    )
    args = parser.parse_args()
    serve(artifacts_dir=args.dir.resolve(), port=args.port)


if __name__ == "__main__":
    main()
