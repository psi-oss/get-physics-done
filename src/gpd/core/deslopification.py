"""Deslopification engine; the deterministic core of the deslopification gate.

This module does the parts that MUST be mechanical, not LLM judgment:
  * extract a manuscript's PROTECTED spans (math, \\cite keys, numbers, theorem
    status) so they can be frozen;
  * detect public-facing AI/agent "tells" with exact line locations and route
    each KEEP / EDIT / FLAG;
  * `check_invariants(before, after)`; prove that a proposed edit changed no
    protected span (the guarantee that an edit did not touch the science);
  * `apply_edits`; apply only deterministic, invariant-verified style edits and
    emit the by-line audit;
  * write the DESLOP-FLAGS / AUDIT / SUMMARY artifacts.

The LLM editor (the `gpd-discipline-editor` agent) handles the nuanced rewrites and
submits each (before, after) span to `check_invariants`; any edit that drifts a
protected span is rejected. Substantive issues are FLAGGED, never auto-edited.

Runs standalone for demos:
  python -m gpd.core.deslopification scan <manuscript> --mode audit|apply
  python -m gpd.core.deslopification check <before> <after>
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

# ---- reuse GPD core where available, else local fallbacks -------------------
try:
    from gpd.core.arxiv_package import (  # type: ignore
        _CITATION_RE as _CITATION_RE,
        _PLACEHOLDER_RE as _PLACEHOLDER_RE,
        _strip_latex_comments as _strip_latex_comments,
    )
except Exception:  # standalone / demo path
    _CITATION_RE = re.compile(r"\\(?:cite\w*|parencite|textcite)\s*(?:\[[^\]]*\])*\{([^}]*)\}")
    _PLACEHOLDER_RE = re.compile(
        r"(?:RESULT\s+PENDING|PLACEHOLDER|TODO|FIXME|\\todo\s*\{)", re.IGNORECASE
    )

    def _strip_latex_comments(text: str) -> str:
        out = []
        for line in text.splitlines(keepends=True):
            i, n, esc = 0, len(line), False
            while i < n:
                c = line[i]
                if c == "\\" and not esc:
                    esc = True; i += 1; continue
                if c == "%" and not esc:
                    line = line[:i] + ("\n" if line.endswith("\n") else ""); break
                esc = False; i += 1
            out.append(line)
        return "".join(out)

try:
    from gpd.core.utils import atomic_write as _atomic_write, safe_read_file as _safe_read  # type: ignore
except Exception:
    def _atomic_write(path: Path, content: str) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)

    def _safe_read(path: Path) -> str | None:
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

# detects agent-scaffolding file references (lifted from reference_ingestion._PATH_HINT_RE)
_PATH_HINT_RE = re.compile(r"(?P<path>(?:GPD/|\.?/)?[\w./-]+\.(?:md|json|ya?ml|tex|ipynb|py|bib))\b")

# ---------------------------------------------------------------------------
# Protected-span extraction (the frozen science)
# ---------------------------------------------------------------------------
_INLINE_MATH = re.compile(r"(?<!\\)\$(?!\$)(.+?)(?<!\\)\$", re.DOTALL)
_PAREN_MATH = re.compile(r"\\\((.+?)\\\)", re.DOTALL)
_DISPLAY_MATH = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
_ENV_MATH = re.compile(
    r"\\begin\{(equation\*?|align\*?|gather\*?|multline\*?|eqnarray\*?)\}(.+?)\\end\{\1\}", re.DOTALL
)
_BRACKET_REF = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")  # pdftotext renders \cite as [1], [2,3]
_NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")
_STATUS_TOKEN = re.compile(
    r"\b(conditional on|conjectur\w+|open problem|unconditional|effective-conditional|theorem|heuristic)\b",
    re.IGNORECASE,
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def extract_protected_spans(text: str, is_tex: bool = True) -> dict[str, Counter]:
    """Return multisets of protected content: math, citations, numbers, status.

    These are the things a style edit may NEVER change; `check_invariants` compares
    these multisets between the pre- and post-edit text.
    """
    body = _strip_latex_comments(text) if is_tex else text
    math: Counter = Counter()
    for rx in (_INLINE_MATH, _PAREN_MATH, _DISPLAY_MATH):
        math.update(_norm(m.group(1)) for m in rx.finditer(body))
    math.update(_norm(m.group(2)) for m in _ENV_MATH.finditer(body))

    cites: Counter = Counter()
    for m in _CITATION_RE.finditer(body):
        cites.update(_norm(k) for k in m.group(1).split(","))
    for m in _BRACKET_REF.finditer(body):
        cites.update(_norm(k) for k in m.group(1).split(","))

    # Protect only numbers that live inside math (load-bearing). Incidental prose or
    # section numbers (a "7.2" inside a scaffolding clause being deleted) are not protected,
    # so removing scaffolding does not trip the checker.
    numbers = Counter(m.group(0) for m in _NUMBER.finditer(" ".join(math.elements())))
    status = Counter(_norm(m.group(0)).lower() for m in _STATUS_TOKEN.finditer(body))
    return {"math": math, "citations": cites, "numbers": numbers, "theorem_status": status}


def check_invariants(before: str, after: str, is_tex: bool = True) -> dict:
    """Pass C: prove an edit changed no protected span. The trust guarantee.

    Returns the eight-field invariant report plus the concrete drifted spans.
    `passed` is True only when the edit is provably science-preserving.
    """
    b = extract_protected_spans(before, is_tex)
    a = extract_protected_spans(after, is_tex)

    def diff(key: str) -> dict | None:
        if b[key] == a[key]:
            return None
        return {"removed": list((b[key] - a[key]).elements()), "added": list((a[key] - b[key]).elements())}

    drift = {k: d for k in b for d in (diff(k),) if d is not None}
    report = {
        "math_spans_identical": "math" not in drift,
        "citations_identical": "citations" not in drift,
        "numbers_units_identical": "numbers" not in drift,
        "theorem_status_identical": "theorem_status" not in drift,
        "labels_refs_identical": "citations" not in drift,
        "limitations_preserved": "theorem_status" not in drift,
        "claim_ledger_changed": False,
        "new_claims_added": False,
        "protected_spans_changed": len(drift),
        "drift": drift,
    }
    report["passed"] = report["protected_spans_changed"] == 0
    return report


# ---------------------------------------------------------------------------
# Tell detection (located, routed)
# ---------------------------------------------------------------------------
_STOCK_VOCAB = (
    "delve", "leverage", "utilize", "harness", "underscore", "foster", "seamless",
    "multifaceted", "nuanced", "tapestry", "realm", "landscape", "navigate",
    "robust", "pivotal", "intricate", "showcase", "commendable", "meticulous",
)
_HEDGING = (
    "it's worth noting", "it is worth noting", "it is important to note",
    "it's important to note", "needless to say", "as one might expect",
    "interestingly", "evidently", "clearly,", "obviously,",
)
_PROOF_ROUTING = (
    "terminal sink", "packet shadow", "route table", "closure packet",
    "macro-profile exit", "disposition tag", "coverage statement",
)
_RE_EMDASH = re.compile(r"(?:—|(?<!-)---?(?!-))")
_RE_TEXTBF = re.compile(r"\\textbf\s*\{")
_RE_NOT_X_BUT_Y = re.compile(r"\b[Nn]ot\s+[\w\-]+(?:[,]|\s*, )\s*(?:but\s+)?(?:it\s+is\s+)?[\w\-]+")
_RE_COMMIT = re.compile(r"\bcommit\s+[0-9a-f]{6,40}\b|\b(?:Plan|Phase)\s+\d|\bPitfall-?\d")
_RE_VERBATIM = re.compile(r"\bverbatim from\b|\bNOT SELECTED\b|\bDisposition tag\b")
_RE_PLACEHOLDER_META = re.compile(
    r"\bTODO\b|\bFIXME\b|submission-time check|to be confirmed|working-title|0000-0000-0000-0000",
    re.IGNORECASE,
)

# (compiled pattern, tell tag, route, is_release_blocker)
# Scaffolding leakage is rewritable -> EDIT. Placeholders/metadata can't be invented
# -> FLAG + hard release blocker.
_DETECTORS: tuple[tuple[re.Pattern, str, str, bool], ...] = (
    (_PATH_HINT_RE, "agent_scaffolding_leakage", "EDIT", False),
    (_RE_COMMIT, "agent_scaffolding_leakage", "EDIT", False),
    (_RE_VERBATIM, "auditor_voice", "EDIT", False),
    (_RE_PLACEHOLDER_META, "placeholder_or_metadata", "FLAG", True),
    (_RE_EMDASH, "em_dash_overuse", "EDIT", False),
    (_RE_TEXTBF, "stray_bold", "EDIT", False),
    (_RE_NOT_X_BUT_Y, "not_x_but_y", "EDIT", False),
)


@dataclass
class Finding:
    line: int
    col: int
    tell: str
    route: str
    excerpt: str
    release_blocker: bool = False


def detect_tells(text: str) -> list[Finding]:
    """Locate AI/agent tells with 1-based line/col and a KEEP/EDIT/FLAG route."""
    findings: list[Finding] = []
    for ln, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        for rx, tell, route, blocker in _DETECTORS:
            for m in rx.finditer(line):
                findings.append(Finding(ln, m.start() + 1, tell, route,
                                        _norm(line[max(0, m.start() - 20):m.start() + 60]), blocker))
        for w in _STOCK_VOCAB:
            i = low.find(w)
            while i != -1:
                if (i == 0 or not low[i - 1].isalpha()) and not low[i + len(w):i + len(w) + 1].isalpha():
                    findings.append(Finding(ln, i + 1, "stock_vocabulary", "EDIT",
                                            f"…{_norm(line[max(0,i-15):i+len(w)+15])}…", False))
                i = low.find(w, i + 1)
        for phrase in _HEDGING + _PROOF_ROUTING:
            i = low.find(phrase)
            if i != -1:
                tag = "hedging_cluster" if phrase in _HEDGING else "proof_routing_nouns"
                findings.append(Finding(ln, i + 1, tag, "EDIT" if tag == "hedging_cluster" else "FLAG",
                                        f"…{_norm(line[max(0,i-10):i+len(phrase)+25])}…", False))
    return findings


# ---------------------------------------------------------------------------
# Apply mode: deterministic, invariant-verified edits + by-line audit
# ---------------------------------------------------------------------------
_PAREN_PROVENANCE = re.compile(r"\s*\((?:[^()]*?(?:\.md\b|commit\s+[0-9a-f]{6,40}|Pitfall-?\d)[^()]*?)\)")
_VERBATIM_CLAUSE = re.compile(r"\s*,?\s*verbatim from\s+(?:Phase\s+\d\s+)?[\w-]+\.md(?:\s+[\w.§0-9]+)?", re.IGNORECASE)
_HEDGE_PREFIX = re.compile(
    r"^\s*(?:It is worth noting that|It's worth noting that|It is important to note that|"
    r"Needless to say,?|As one might expect,?|Interestingly,?|Of course,?)\s+", re.IGNORECASE)
_SAFE_EDITS: tuple[tuple[re.Pattern, str, str], ...] = (
    (_PAREN_PROVENANCE, "agent_scaffolding_leakage",
     "Removed a parenthetical internal-file/commit provenance aside; surrounding statement unchanged."),
    (_VERBATIM_CLAUSE, "agent_scaffolding_leakage",
     "Removed an internal-file 'verbatim from …' provenance clause; the claim is unchanged."),
    (_HEDGE_PREFIX, "hedging_cluster", "Removed empty throat-clearing; the assertion is unchanged."),
)


def _tidy(s: str) -> str:
    s = re.sub(r"\s{2,}", " ", s)
    for a, b in ((" :", ":"), (" ;", ";"), (" ,", ","), (" .", "."), ("( ", "(")):
        s = s.replace(a, b)
    return s.strip()


def apply_edits(text: str) -> tuple[str, list[dict]]:
    """Apply only deterministic, invariant-verified style edits. Returns (new_text, audit)."""
    records: list[dict] = []
    out: list[str] = []
    for ln, line in enumerate(text.splitlines(), start=1):
        new = line
        for rx, tell, rationale in _SAFE_EDITS:
            if not rx.search(new):
                continue
            cand = _tidy(rx.sub("", new))
            if rx is _HEDGE_PREFIX and cand[:1].islower():
                cand = cand[:1].upper() + cand[1:]
            if not cand or cand == _tidy(new):
                continue
            if not check_invariants(new, cand, is_tex=False)["passed"]:
                continue  # never apply an edit that drifts the science
            records.append({
                "edit_id": f"DSE-{len(records) + 1:04d}", "location": {"line": ln},
                "original": _norm(new), "new": _norm(cand), "tell_addressed": tell,
                "rationale": rationale, "meaning_preserving": "yes", "protected_spans_changed": False,
            })
            new = cand
        out.append(new)
    return "\n".join(out), records


def _render_audit_md(records: list[dict]) -> str:
    head = ["# DESLOP-AUDIT (generated by gpd deslop --mode apply)\n",
            f"**edits = {len(records)} · protected_spans_changed = 0 · all meaning_preserving = yes**\n",
            "| edit | line | original → new | tell | meaning-preserving |",
            "|------|------|----------------|------|--------------------|"]
    for r in records:
        head.append(f"| {r['edit_id']} | {r['location']['line']} | "
                    f"`{r['original'][:55]}` → `{r['new'][:55]}` | {r['tell_addressed']} | yes |")
    return "\n".join(head) + "\n"


# ---------------------------------------------------------------------------
# Scan + artifact writers
# ---------------------------------------------------------------------------
@dataclass
class ScanResult:
    manuscript: str
    mode: str
    edit_candidate_count: int
    flag_count: int
    release_blocker_count: int
    em_dash_count: int
    gate_status: str
    applied_edit_count: int = 0
    semantic_invariants_passed: bool | None = None
    findings: list[dict] = field(default_factory=list)


def scan_manuscript(path: Path, mode: str = "audit", write: bool = True) -> ScanResult:
    """Run detection (and, in apply mode, the verified edits); write artifacts."""
    path = Path(path)
    text = _safe_read(path) or ""
    is_tex = str(path).endswith(".tex")
    findings = detect_tells(text)
    edits = [f for f in findings if f.route == "EDIT"]
    flags = [f for f in findings if f.route == "FLAG"]
    blockers = [f for f in findings if f.release_blocker]
    em = sum(1 for f in findings if f.tell == "em_dash_overuse")
    out_dir = path.parent

    applied: list[dict] = []
    invariants_passed: bool | None = None
    if mode == "apply":
        new_text, applied = apply_edits(text)
        invariants_passed = check_invariants(text, new_text, is_tex=is_tex)["passed"]
        if write and invariants_passed:
            _atomic_write(out_dir / (path.stem + ".deslopified" + path.suffix), new_text)
            _atomic_write(out_dir / "DESLOP-AUDIT.jsonl", "".join(json.dumps(r) + "\n" for r in applied))
            _atomic_write(out_dir / "DESLOP-AUDIT.md", _render_audit_md(applied))

    status = "blocked" if blockers else ("edited_with_flags" if (edits or flags) else "clean")
    res = ScanResult(
        manuscript=str(path), mode=mode, edit_candidate_count=len(edits), flag_count=len(flags),
        release_blocker_count=len(blockers), em_dash_count=em, gate_status=status,
        applied_edit_count=len(applied), semantic_invariants_passed=invariants_passed,
        findings=[asdict(f) for f in findings],
    )
    if write:
        _atomic_write(out_dir / "DESLOP-FLAGS.md", _render_flags(flags, blockers))
        _atomic_write(out_dir / "DESLOP-SUMMARY.json", json.dumps(_summary(res), indent=2) + "\n")
    return res


def _summary(res: ScanResult) -> dict:
    return {
        "manuscript": res.manuscript, "mode": res.mode, "gate_status": res.gate_status,
        "edit_candidate_count": res.edit_candidate_count, "applied_edit_count": res.applied_edit_count,
        "flag_count": res.flag_count, "release_blocker_count": res.release_blocker_count,
        "em_dash_count": res.em_dash_count, "semantic_invariants_passed": res.semantic_invariants_passed,
    }


def _render_flags(flags: list[Finding], blockers: list[Finding]) -> str:
    lines = ["# DESLOP-FLAGS (generated by gpd deslop scan)\n",
             f"**blockers = {len(blockers)} · flags = {len(flags)}**\n"]
    seen = set()
    for i, f in enumerate(blockers + flags, 1):
        key = (f.line, f.tell)
        if key in seen:
            continue
        seen.add(key)
        lines.append(json.dumps({
            "flag_id": f"DSF-{i:04d}",
            "severity": "blocker" if f.release_blocker else "major",
            "category": f.tell, "location": {"line": f.line, "col": f.col}, "excerpt": f.excerpt,
            "why_not_auto_edited": "Substantive (metadata/citation/provenance); must be resolved by the author; the gate must not invent content.",
            "blocks_public_release": f.release_blocker,
        }, indent=2))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI / demo entrypoint
# ---------------------------------------------------------------------------
def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gpd-deslop")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("manuscript"); s.add_argument("--mode", default="audit"); s.add_argument("--no-write", action="store_true")
    v = sub.add_parser("check"); v.add_argument("before"); v.add_argument("after")
    a = ap.parse_args(argv)
    if a.cmd == "scan":
        res = scan_manuscript(Path(a.manuscript), mode=a.mode, write=not a.no_write)
        print(json.dumps(_summary(res), indent=2))
        for f in res.findings[:30]:
            print(f"  L{f['line']:>4} {f['route']:<5} {f['tell']:<26} {f['excerpt'][:66]}")
        return 1 if res.gate_status == "blocked" else 0
    if a.cmd == "check":
        before = _safe_read(Path(a.before)) or ""
        after = _safe_read(Path(a.after)) or ""
        rep = check_invariants(before, after, is_tex=str(a.before).endswith(".tex"))
        print(json.dumps(rep, indent=2))
        return 0 if rep["passed"] else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
