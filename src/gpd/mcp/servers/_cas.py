"""Computer-algebra helpers backing executable verification checks.

These helpers turn the verification server's limiting-case and symmetry tools
from structural ``"documented"`` markers into actually-computed verdicts using
SymPy. They are deliberately conservative: any parse failure, timeout, or
genuine ambiguity downgrades to an ``INCONCLUSIVE`` verdict and never to a
``PASS``, so the oracle can never manufacture a false confirmation.

SymPy is imported lazily so importing the verification server stays cheap and
degrades gracefully (``inconclusive``) in environments where the CAS backend is
not yet installed, rather than hard-failing the whole server import.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable

# ─── Verdict vocabulary (shared with the verification server result schema) ────

VERDICT_PASS = "pass"  # computed result matches the expected result
VERDICT_FAIL = "fail"  # computed result provably differs from expected
VERDICT_COMPUTED = "computed"  # computed a real result; no machine-checkable expectation
VERDICT_INCONCLUSIVE = "inconclusive"  # could not parse / evaluate / decide — never a pass

_MAX_EXPR_LEN = 2000
_DEFAULT_TIMEOUT_S = 4.0

# Identifiers kept as SymPy callables/constants instead of being rebound to
# plain Symbols, so exp()/sin()/sqrt()/oo still work. Every other identifier
# (gamma, E, I, c, m, T, g, ...) is forced to a plain Symbol so physics notation
# is not silently reinterpreted as a SymPy special function or constant.
_FUNCTION_WHITELIST = frozenset(
    {
        "sin",
        "cos",
        "tan",
        "cot",
        "sec",
        "csc",
        "asin",
        "acos",
        "atan",
        "atan2",
        "sinh",
        "cosh",
        "tanh",
        "asinh",
        "acosh",
        "atanh",
        "exp",
        "log",
        "ln",
        "sqrt",
        "Abs",
        "re",
        "im",
        "oo",
        "pi",
    }
)

# Reject obviously unsafe tokens before handing a string to the parser.
_UNSAFE = re.compile(
    r"(__|\bimport\b|\blambda\b|\bexec\b|\beval\b|\bopen\b|"
    r"\bos\b|\bsys\b|\bsubprocess\b|\bgetattr\b|\bglobals\b|;|`|:=)"
)
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_INF = re.compile(r"\b(?:infinity|infty|inf)\b", re.IGNORECASE)

# ─── LaTeX support ─────────────────────────────────────────────────────────────
#
# Physics derivations are written in LaTeX, so the oracle also accepts LaTeX
# expressions. They are parsed with SymPy's grammar-based lark backend (which
# cannot execute code, unlike sympify). The lark grammar covers fractions,
# powers, roots, subscripts, most Greek letters, and standard functions, but
# rejects a handful of common macros (\hbar, \Omega, ...) and juxtaposed
# superscripted products (``a^2 b^2``). Unsupported macros are rewritten to a
# collision-free placeholder and substituted back; anything still unparseable
# returns None (→ inconclusive), never a false PASS.

# Macros lark rejects but that are common in physics → intended Symbol name.
_LATEX_SYMBOL_FIXUPS = {r"\hbar": "hbar", r"\Omega": "Omega", r"\sigma": "sigma", r"\ell": "ell"}
# Macros mapped to genuine SymPy constants rather than free symbols.
_LATEX_CONST_FIXUPS = (r"\pi",)  # → sympy.pi
# Supported single-token macros used as collision-free placeholders.
_LATEX_PLACEHOLDERS = (r"\eta", r"\zeta", r"\xi", r"\chi", r"\kappa", r"\iota", r"\upsilon", r"\digamma")
# Spacing / delimiter macros stripped before parsing.
_LATEX_STRIP = (r"\left", r"\right", r"\quad", r"\qquad", r"\,", r"\;", r"\:", r"\!", r"\(", r"\)", r"\[", r"\]")
# TeX constructs refused outright (environments / macro definitions / file IO).
_LATEX_DANGEROUS = re.compile(
    r"\\(?:input|include|def|csname|write|read|openin|catcode|immediate|loop|"
    r"expandafter|newcommand|renewcommand|usepackage|begin|end)\b"
)
_LATEX_COMMAND = re.compile(r"\\[A-Za-z]+")
# Arrow macros normalized to '->' when parsing a limit description.
_LATEX_ARROW = re.compile(r"\\(?:to|rightarrow|longrightarrow|mapsto)\b")

# ── delatexify fallback (for LaTeX the lark grammar rejects, e.g. a^2 b^2) ──
# Differential-operator notation cannot be faithfully turned into algebra, so we
# refuse it outright rather than risk a wrong verdict.
_DELATEX_DERIVATIVE = re.compile(r"\\partial|\\nabla|\\frac\s*\{\s*d\b")
# Literal macro → plain-token rewrites applied before structural conversion.
_DELATEX_REPLACERS = (
    (r"\cdot", "*"),
    (r"\times", "*"),
    (r"\div", "/"),
    (r"\ln", "log"),
    (r"\lg", "log"),
    (r"\infty", "oo"),
)


def _sympy():  # pragma: no cover - thin lazy import
    import sympy

    return sympy


def _looks_like_latex(text: str) -> bool:
    """Heuristic: does the string contain LaTeX math markup?"""
    return bool(_LATEX_COMMAND.search(text)) or "^{" in text or "_{" in text


def _parse_latex(text: str):
    """Parse a LaTeX physics expression into a SymPy object, or ``None``.

    Primary path is SymPy's grammar-based lark backend. When lark rejects the
    input (e.g. juxtaposed superscript products ``a^2 b^2``), a conservative
    delatexify fallback converts the LaTeX to a plain infix string and parses it
    with implicit multiplication. Differential-operator notation is refused so
    the fallback can never fabricate algebra from a derivative.
    """
    cleaned = text.strip().strip("$").replace("&", " ")
    if _LATEX_DANGEROUS.search(cleaned):
        return None
    for token in _LATEX_STRIP:
        cleaned = cleaned.replace(token, " ")
    if "=" in cleaned:
        cleaned = cleaned.split("=")[-1].strip()
    if not cleaned:
        return None
    result = _latex_via_lark(cleaned)
    if result is not None:
        return result
    return _latex_via_delatexify(cleaned)


def _latex_via_lark(cleaned: str):
    """Parse cleaned LaTeX with the lark backend (+ macro fixups), or ``None``."""
    try:
        sympy = _sympy()
        from sympy.parsing.latex import parse_latex
    except Exception:  # noqa: BLE001 - sympy/lark unavailable → unparseable
        return None

    substitutions = {}
    pool = [p for p in _LATEX_PLACEHOLDERS if p not in cleaned]
    fixups = [(m, _LATEX_SYMBOL_FIXUPS[m]) for m in _LATEX_SYMBOL_FIXUPS]
    fixups += [(m, None) for m in _LATEX_CONST_FIXUPS]
    try:
        for macro, name in fixups:
            pattern = re.escape(macro) + r"(?![A-Za-z])"
            if re.search(pattern, cleaned):
                if not pool:
                    return None
                placeholder = pool.pop(0)
                cleaned = re.sub(pattern, lambda _m, ph=placeholder: ph, cleaned)
                target = sympy.pi if name is None else sympy.Symbol(name)
                substitutions[sympy.Symbol(placeholder.lstrip("\\"))] = target
    except Exception:  # noqa: BLE001
        return None

    ok, parsed = run_with_timeout(lambda: parse_latex(cleaned, backend="lark"))
    if not ok or parsed is None:
        return None
    if not substitutions:
        return parsed
    ok2, substituted = run_with_timeout(lambda: parsed.subs(substitutions))
    return substituted if ok2 else None


def _latex_via_delatexify(cleaned: str):
    """Fallback: convert LaTeX to a plain infix string and parse it."""
    plain = _delatexify(cleaned)
    if plain is None:
        return None
    return _parse_plain(plain, implicit=True)


def _match_brace(s: str, start: int) -> int:
    """Return the index of the ``}`` matching the ``{`` at ``start``, or -1."""
    depth = 0
    for idx in range(start, len(s)):
        ch = s[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def _latex_frac(s: str) -> str | None:
    """Rewrite ``\\frac{A}{B}`` → ``((A)/(B))`` (brace-matched, nesting-safe)."""
    for _ in range(200):
        i = s.find(r"\frac")
        if i == -1:
            return s
        j = i + len(r"\frac")
        while j < len(s) and s[j] == " ":
            j += 1
        if j >= len(s) or s[j] != "{":
            return None
        a_end = _match_brace(s, j)
        if a_end == -1:
            return None
        k = a_end + 1
        while k < len(s) and s[k] == " ":
            k += 1
        if k >= len(s) or s[k] != "{":
            return None
        b_end = _match_brace(s, k)
        if b_end == -1:
            return None
        s = s[:i] + "((" + s[j + 1 : a_end] + ")/(" + s[k + 1 : b_end] + "))" + s[b_end + 1 :]
    return None


def _latex_sqrt(s: str) -> str | None:
    """Rewrite ``\\sqrt{A}`` → ``sqrt((A))`` and ``\\sqrt[n]{A}`` → ``((A)**(1/(n)))``."""
    for _ in range(200):
        i = s.find(r"\sqrt")
        if i == -1:
            return s
        j = i + len(r"\sqrt")
        while j < len(s) and s[j] == " ":
            j += 1
        root = None
        if j < len(s) and s[j] == "[":
            close = s.find("]", j)
            if close == -1:
                return None
            root = s[j + 1 : close]
            j = close + 1
            while j < len(s) and s[j] == " ":
                j += 1
        if j >= len(s) or s[j] != "{":
            return None
        end = _match_brace(s, j)
        if end == -1:
            return None
        inner = s[j + 1 : end]
        rep = f"(({inner})**(1/({root})))" if root else f"sqrt(({inner}))"
        s = s[:i] + rep + s[end + 1 :]
    return None


def _latex_braced(s: str, op: str, prefix: str, suffix: str) -> str | None:
    """Rewrite ``op{...}`` (e.g. ``^{...}``) → ``prefix...suffix`` (brace-matched)."""
    pattern = re.compile(re.escape(op) + r"\{")
    for _ in range(200):
        match = pattern.search(s)
        if not match:
            return s
        brace = match.end() - 1
        end = _match_brace(s, brace)
        if end == -1:
            return None
        s = s[: match.start()] + prefix + s[brace + 1 : end] + suffix + s[end + 1 :]
    return None


def _latex_subscript(s: str) -> str | None:
    """Rewrite ``a_{bc}`` → ``a_bc`` (subscripts folded into the symbol name)."""
    pattern = re.compile(r"_\{")
    for _ in range(200):
        match = pattern.search(s)
        if not match:
            return s
        brace = match.end() - 1
        end = _match_brace(s, brace)
        if end == -1:
            return None
        inner = re.sub(r"[^A-Za-z0-9]", "", s[brace + 1 : end])
        s = s[: match.start()] + (f"_{inner}" if inner else "") + s[end + 1 :]
    return None


def _delatexify(s: str) -> str | None:
    """Convert a LaTeX math string to a plain infix expression, or ``None``.

    Conservative: refuses differential operators and returns None on any
    unhandled construct (leftover braces/backslashes), so the caller stays
    inconclusive rather than guessing.
    """
    if _DELATEX_DERIVATIVE.search(s):
        return None
    for src, dst in _DELATEX_REPLACERS:
        s = s.replace(src, dst)
    for step in (
        _latex_frac,
        _latex_sqrt,
        lambda t: _latex_braced(t, "^", "**(", ")"),
        _latex_subscript,
    ):
        s = step(s)
        if s is None:
            return None
    s = s.replace("{", "(").replace("}", ")").replace("^", "**")
    s = re.sub(r"\\([A-Za-z]+)", r"\1", s)  # strip remaining macro backslashes
    if "\\" in s or "{" in s or "}" in s:
        return None
    return s


def run_with_timeout(fn: Callable[[], object], timeout_s: float = _DEFAULT_TIMEOUT_S) -> tuple[bool, object]:
    """Run ``fn()`` in a daemon worker thread.

    Returns ``(ok, value)`` on success or ``(False, reason)`` on timeout/error.
    A timed-out thread cannot be killed, but as a daemon it never blocks the
    response and is bounded by the caller's input-size cap.
    """
    box: dict[str, object] = {}

    def worker() -> None:
        try:
            box["value"] = fn()
            box["ok"] = True
        except BaseException as exc:  # noqa: BLE001 - report, never propagate
            box["ok"] = False
            box["reason"] = type(exc).__name__

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout_s)
    if thread.is_alive():
        return False, "timeout"
    if box.get("ok"):
        return True, box.get("value")
    return False, box.get("reason", "error")


def safe_parse(text: str):
    """Parse a physics expression string into a SymPy object, or ``None``.

    Conservative by design: rejects unsafe tokens, caps length, forces unknown
    identifiers to plain Symbols, normalizes ``^``/``infinity`` notation, takes
    the right-hand side of an equation (we reason about the formula), and
    returns ``None`` on any failure.
    """
    if not isinstance(text, str):
        return None
    raw = text.strip()
    if not raw or len(raw) > _MAX_EXPR_LEN:
        return None
    if _looks_like_latex(raw):
        return _parse_latex(raw)
    return _parse_plain(raw)


def _parse_plain(text: str, implicit: bool = False):
    """Parse a plain (non-LaTeX) expression string into a SymPy object, or None.

    ``implicit`` enables implicit multiplication/application (``2m`` → ``2*m``,
    ``sin x`` → ``sin(x)``); used by the delatexify fallback.
    """
    if _UNSAFE.search(text):
        return None
    expr_text = text
    if "=" in expr_text:
        expr_text = expr_text.split("=")[-1].strip()
        if not expr_text:
            return None
    normalized = _INF.sub("oo", expr_text).replace("^", "**")
    try:
        sympy = _sympy()
        from sympy.parsing.sympy_parser import (
            implicit_multiplication_application,
            parse_expr,
            standard_transformations,
        )

        transformations = standard_transformations
        if implicit:
            transformations = transformations + (implicit_multiplication_application,)
        local = {
            name: sympy.Symbol(name) for name in set(_IDENT.findall(normalized)) if name not in _FUNCTION_WHITELIST
        }
        ok, value = run_with_timeout(
            lambda: parse_expr(
                normalized,
                local_dict=local,
                transformations=transformations,
                evaluate=True,
            )
        )
        if not ok:
            return None
        return value
    except Exception:  # noqa: BLE001 - any parse/import failure → unparseable
        return None


def symbolic_equal(a, b, timeout_s: float = _DEFAULT_TIMEOUT_S):
    """Return ``True``/``False``/``None`` for whether two expressions are equal.

    ``None`` means "could not decide" — callers must treat it as inconclusive,
    never as equal.
    """
    try:
        sympy = _sympy()
    except Exception:  # noqa: BLE001
        return None

    def _check():
        diff = sympy.simplify(a - b)
        if diff == 0:
            return True
        verdict = a.equals(b)  # robust numeric+symbolic probe; may return None
        if verdict is True:
            return True
        if verdict is False:
            return False
        if diff.is_number and diff != 0:
            return False
        return None

    ok, value = run_with_timeout(_check, timeout_s)
    return value if ok else None


def parse_limit_target(description: str) -> tuple[str, str] | None:
    """Parse a limit description into ``(variable, point_text)`` or ``None``.

    Accepts ``"hbar -> 0"``, ``"c -> infinity"``, LaTeX arrows/macros such as
    ``r"\\hbar \\to 0"`` and ``r"c \\to \\infty"``, and descriptive prefixes such
    as ``"classical limit: hbar -> 0"`` (uses the last ``X -> Y`` occurrence).
    A composite ratio such as ``"v/c -> 0"`` is intentionally rejected because
    it is not a single limit variable.
    """
    if not isinstance(description, str):
        return None
    normalized = _LATEX_ARROW.sub("->", description.replace("$", ""))
    if "->" not in normalized:
        return None
    # An optional leading backslash lets LaTeX symbols (\hbar) match.
    matches = re.findall(r"(\\?[A-Za-z_][A-Za-z0-9_/]*)\s*->\s*([^,;]+)", normalized)
    if not matches:
        return None
    var_raw, point_raw = matches[-1]
    var = var_raw.lstrip("\\").strip()
    if "/" in var or not var:
        return None
    return var, point_raw.strip()


def check_limit(expression: str, limit_description: str, expected: str, timeout_s: float = _DEFAULT_TIMEOUT_S) -> dict:
    """Compute ``lim_{var->point} expression`` and compare to ``expected``.

    Returns an additive ``cas`` payload describing what was actually executed.
    The verdict is one of pass/fail/computed/inconclusive.
    """
    target = parse_limit_target(limit_description)
    if target is None:
        return {
            "attempted": False,
            "verdict": VERDICT_INCONCLUSIVE,
            "detail": "no machine-readable 'var -> point' in limit description",
        }
    var_name, point_text = target

    expr = safe_parse(expression)
    if expr is None:
        return {
            "attempted": False,
            "verdict": VERDICT_INCONCLUSIVE,
            "variable": var_name,
            "point": point_text,
            "detail": "expression is not machine-parseable",
        }
    point = safe_parse(point_text)
    if point is None:
        return {
            "attempted": False,
            "verdict": VERDICT_INCONCLUSIVE,
            "variable": var_name,
            "point": point_text,
            "detail": f"limit point '{point_text}' is not machine-parseable",
        }

    sympy = _sympy()
    var = sympy.Symbol(var_name)
    ok, value = run_with_timeout(lambda: sympy.limit(expr, var, point), timeout_s)
    if not ok:
        return {
            "attempted": True,
            "verdict": VERDICT_INCONCLUSIVE,
            "variable": var_name,
            "point": point_text,
            "detail": f"SymPy could not evaluate the limit ({value})",
        }

    payload: dict[str, object] = {
        "attempted": True,
        "variable": var_name,
        "point": point_text,
        "computed_limit": str(value),
    }
    expected_expr = safe_parse(expected)
    if expected_expr is None:
        payload["verdict"] = VERDICT_COMPUTED
        payload["expected_parsed"] = False
        payload["detail"] = "computed the limit; expected result is prose — compare the computed_limit manually"
        return payload

    payload["expected_parsed"] = True
    equal = symbolic_equal(value, expected_expr, timeout_s)
    if equal is True:
        payload["verdict"] = VERDICT_PASS
        payload["detail"] = "computed limit matches the expected result"
    elif equal is False:
        payload["verdict"] = VERDICT_FAIL
        payload["detail"] = "computed limit provably differs from the expected result"
    else:
        payload["verdict"] = VERDICT_COMPUTED
        payload["detail"] = "equality is undecidable — review computed_limit vs expected"
    return payload


# Substitution-based symmetries we can execute: name fragment → (transform var, label).
_PARITY_VARS = ("x", "r")
_TIME_VARS = ("t",)


def _pick_variable(free_names: list[str], preferred: tuple[str, ...]) -> str | None:
    for name in preferred:
        if name in free_names:
            return name
    if len(free_names) == 1:
        return free_names[0]
    return None


def _scale_symmetry(expr, free_names: list[str], timeout_s: float) -> dict:
    """Classify scale behavior via Euler's homogeneity theorem.

    Under ``v -> lambda v``, ``f -> lambda^n f`` iff ``v df/dv = n f`` with ``n``
    constant. Reports the homogeneity degree ``n`` in the chosen variable;
    scale-invariant means ``n == 0``.
    """
    var_name = _pick_variable(free_names, _PARITY_VARS)
    if var_name is None:
        return {
            "attempted": False,
            "verdict": VERDICT_INCONCLUSIVE,
            "detail": "could not unambiguously identify a single variable to scale",
        }
    sympy = _sympy()
    var = sympy.Symbol(var_name)
    ok, ratio = run_with_timeout(lambda: sympy.simplify(var * expr.diff(var) / expr), timeout_s)
    if not ok:
        return {
            "attempted": True,
            "verdict": VERDICT_INCONCLUSIVE,
            "transformation": f"{var_name} -> lambda*{var_name}",
            "detail": f"could not compute the scaling degree ({ratio})",
        }
    if ratio.free_symbols:
        return {
            "attempted": True,
            "verdict": VERDICT_COMPUTED,
            "transformation": f"{var_name} -> lambda*{var_name}",
            "classification": f"not scale-homogeneous in {var_name}",
            "invariant": False,
            "detail": f"expression is not homogeneous under {var_name} -> lambda*{var_name}",
        }
    degree = sympy.nsimplify(ratio) if ratio.is_Float else ratio
    invariant = degree == 0
    return {
        "attempted": True,
        "verdict": VERDICT_COMPUTED,
        "transformation": f"{var_name} -> lambda*{var_name}",
        "scale_degree": str(degree),
        "classification": f"homogeneous of degree {degree} in {var_name}",
        "invariant": bool(invariant),
        "detail": (
            f"expression is scale-invariant in {var_name} (degree 0)"
            if invariant
            else f"expression scales as lambda^{degree} under {var_name} -> lambda*{var_name}"
        ),
    }


def check_symmetry(expression: str, symmetry: str, timeout_s: float = _DEFAULT_TIMEOUT_S) -> dict:
    """Execute a symmetry check where one is well-defined.

    Handles parity (``x -> -x``) and time-reversal (``t -> -t``) by substitution
    (classifying even / odd / neither), and scale / dilation via Euler's
    homogeneity theorem (reporting the homogeneity degree). Other symmetries
    (gauge, Lorentz, ...) have no sound single-expression test and return
    inconclusive so the structural ``status`` field still drives those.
    """
    name = symmetry.lower().replace("_", " ").replace("-", " ")
    expr = safe_parse(expression)
    if expr is None:
        return {
            "attempted": False,
            "verdict": VERDICT_INCONCLUSIVE,
            "detail": "expression is not machine-parseable",
        }

    free_names = sorted(str(s) for s in expr.free_symbols)
    if "parity" in name:
        var_name = _pick_variable(free_names, _PARITY_VARS)
    elif "time" in name and "revers" in name:
        var_name = _pick_variable(free_names, _TIME_VARS)
    elif "scale" in name or "dilat" in name:
        return _scale_symmetry(expr, free_names, timeout_s)
    else:
        return {
            "attempted": False,
            "verdict": VERDICT_INCONCLUSIVE,
            "detail": "no executable transformation defined for this symmetry",
        }

    if var_name is None:
        return {
            "attempted": False,
            "verdict": VERDICT_INCONCLUSIVE,
            "detail": "could not unambiguously identify the variable to transform",
        }

    sympy = _sympy()
    var = sympy.Symbol(var_name)
    ok, transformed = run_with_timeout(lambda: expr.subs(var, -var), timeout_s)
    if not ok:
        return {
            "attempted": True,
            "verdict": VERDICT_INCONCLUSIVE,
            "transformation": f"{var_name} -> -{var_name}",
            "detail": f"substitution failed ({transformed})",
        }

    even = symbolic_equal(transformed, expr, timeout_s)
    odd = symbolic_equal(transformed, -expr, timeout_s)
    if even is True:
        classification, invariant = "invariant (even)", True
    elif odd is True:
        classification, invariant = "odd", False
    elif even is False and odd is False:
        classification, invariant = "neither even nor odd", False
    else:
        return {
            "attempted": True,
            "verdict": VERDICT_INCONCLUSIVE,
            "transformation": f"{var_name} -> -{var_name}",
            "transformed_expression": str(transformed),
            "detail": "could not classify behavior under the transformation",
        }

    return {
        "attempted": True,
        "verdict": VERDICT_COMPUTED,
        "transformation": f"{var_name} -> -{var_name}",
        "transformed_expression": str(transformed),
        "classification": classification,
        "invariant": invariant,
        "detail": f"expression is {classification} under {var_name} -> -{var_name}",
    }


# ─── Dimensional analysis of real expressions ──────────────────────────────────


class _DimError(Exception):
    """Internal: a dimensional-analysis failure with a classified ``kind``."""

    def __init__(self, message: str, kind: str) -> None:
        super().__init__(message)
        self.kind = kind  # "inconsistent" | "unknown" | "unsupported"


def _nonzero(dims: dict) -> dict:
    return {k: v for k, v in dims.items() if v != 0}


def _parse_dimension_side(text: str):
    """Parse one side of a dimensional equation (LaTeX or plain, implicit mult)."""
    parsed = safe_parse(text)
    if parsed is not None:
        return parsed
    if not _looks_like_latex(text):
        return _parse_plain(text, implicit=True)
    return None


def dimension_vector(expr, symbol_dims: dict) -> dict:
    """Return the base-dimension exponent map of ``expr``.

    ``symbol_dims`` maps each free-symbol name to a base-exponent dict (e.g.
    ``{"M": 1, "L": 2, "T": -2}``). Raises ``_DimError`` on an unknown symbol,
    an inconsistent sum, or an unsupported node — the caller maps those to a
    FAIL (inconsistent sum) or INCONCLUSIVE verdict.
    """
    sympy = _sympy()
    if expr.is_Number or getattr(expr, "is_NumberSymbol", False):
        return {}
    if expr is sympy.I or expr is sympy.zoo or expr is sympy.nan or expr is sympy.oo:
        return {}
    if expr.is_Symbol:
        name = str(expr)
        if name in symbol_dims:
            return dict(symbol_dims[name])
        raise _DimError(f"no dimension provided for symbol '{name}'", "unknown")
    if expr.is_Add:
        vectors = [dimension_vector(arg, symbol_dims) for arg in expr.args]
        base = _nonzero(vectors[0])
        for vector in vectors[1:]:
            if _nonzero(vector) != base:
                raise _DimError("terms in a sum have inconsistent dimensions", "inconsistent")
        return vectors[0]
    if expr.is_Mul:
        total: dict = {}
        for factor in expr.args:
            for key, value in dimension_vector(factor, symbol_dims).items():
                total[key] = total.get(key, 0) + value
        return total
    if expr.is_Pow:
        base, exponent = expr.args
        if not (exponent.is_Number and exponent.is_rational):
            raise _DimError("non-rational exponent in dimensional analysis", "unsupported")
        return {key: value * exponent for key, value in dimension_vector(base, symbol_dims).items()}
    if expr.is_Function:
        for arg in expr.args:
            if _nonzero(dimension_vector(arg, symbol_dims)):
                raise _DimError(f"argument of {expr.func} must be dimensionless", "inconsistent")
        return {}
    if expr.is_constant():
        return {}
    raise _DimError(f"unsupported expression node {expr.func}", "unsupported")


def check_dimensions(expression: str, symbol_dims: dict) -> dict:
    """Verify dimensional homogeneity of ``LHS = RHS`` given symbol dimensions.

    Returns an additive ``cas`` payload (pass/fail/inconclusive). A sum mixing
    incompatible dimensions, or LHS dimensions differing from RHS, is a FAIL;
    unknown symbols / unparseable sides are INCONCLUSIVE (never a false pass).
    """
    if "=" not in expression:
        return {
            "attempted": False,
            "verdict": VERDICT_INCONCLUSIVE,
            "detail": "expression must contain '=' to compare dimensions",
        }
    lhs_text, rhs_text = expression.split("=", 1)
    lhs = _parse_dimension_side(lhs_text)
    rhs = _parse_dimension_side(rhs_text)
    if lhs is None or rhs is None:
        return {
            "attempted": False,
            "verdict": VERDICT_INCONCLUSIVE,
            "detail": "one or both sides are not machine-parseable",
        }
    try:
        lhs_dims = _nonzero(dimension_vector(lhs, symbol_dims))
        rhs_dims = _nonzero(dimension_vector(rhs, symbol_dims))
    except _DimError as exc:
        verdict = VERDICT_FAIL if exc.kind == "inconsistent" else VERDICT_INCONCLUSIVE
        return {"attempted": exc.kind == "inconsistent", "verdict": verdict, "detail": str(exc)}
    except Exception:  # noqa: BLE001 - any other failure → inconclusive, never pass
        return {"attempted": False, "verdict": VERDICT_INCONCLUSIVE, "detail": "could not compute dimensions"}

    consistent = lhs_dims == rhs_dims
    return {
        "attempted": True,
        "verdict": VERDICT_PASS if consistent else VERDICT_FAIL,
        "lhs_dimensions": {k: int(v) if v == int(v) else str(v) for k, v in lhs_dims.items()},
        "rhs_dimensions": {k: int(v) if v == int(v) else str(v) for k, v in rhs_dims.items()},
        "detail": (
            "both sides share the same dimensions" if consistent else "left and right sides have different dimensions"
        ),
    }


# ─── Conservation-law drift along a trajectory ─────────────────────────────────


def check_conservation(
    quantity: str, trajectory: list[dict], tolerance: float = 1e-6, timeout_s: float = _DEFAULT_TIMEOUT_S
) -> dict:
    """Evaluate a conserved quantity at each state and measure its drift.

    ``quantity`` is an expression (plain or LaTeX) in the state variables;
    ``trajectory`` is a list of states, each a mapping name → number. Returns a
    pass/fail verdict on the relative drift versus ``tolerance`` (absolute drift
    when the quantity is ~0 throughout). Unparseable quantities, missing
    variables, or non-real values → inconclusive, never a false pass.
    """
    if len(trajectory) < 2:
        return {
            "verdict": VERDICT_INCONCLUSIVE,
            "detail": "need at least 2 states to measure drift",
        }
    expr = safe_parse(quantity)
    if expr is None:
        return {
            "verdict": VERDICT_INCONCLUSIVE,
            "detail": "quantity expression is not machine-parseable",
        }
    sympy = _sympy()
    free = {str(s) for s in expr.free_symbols}
    for index, state in enumerate(trajectory):
        missing = free - set(state.keys())
        if missing:
            return {
                "verdict": VERDICT_INCONCLUSIVE,
                "detail": f"state {index} is missing variables: {sorted(missing)}",
            }

    def _evaluate() -> list[float]:
        values: list[float] = []
        for state in trajectory:
            substitutions = {sympy.Symbol(name): state[name] for name in free}
            values.append(float(expr.subs(substitutions).evalf()))
        return values

    ok, values = run_with_timeout(_evaluate, timeout_s)
    if not ok:
        return {
            "verdict": VERDICT_INCONCLUSIVE,
            "detail": f"could not evaluate the quantity numerically ({values})",
        }

    q_min, q_max = min(values), max(values)
    abs_drift = q_max - q_min
    scale = max(abs(v) for v in values)
    if scale > 1e-300:
        rel_drift = abs_drift / scale
        conserved = rel_drift <= tolerance
        basis = "relative"
    else:
        rel_drift = 0.0
        conserved = abs_drift <= tolerance
        basis = "absolute"
    return {
        "verdict": VERDICT_PASS if conserved else VERDICT_FAIL,
        "conserved": conserved,
        "n_steps": len(values),
        "q_initial": values[0],
        "q_final": values[-1],
        "q_min": q_min,
        "q_max": q_max,
        "max_abs_drift": abs_drift,
        "max_relative_drift": rel_drift,
        "tolerance": tolerance,
        "drift_basis": basis,
        "detail": (
            f"quantity is conserved within tolerance ({basis} drift {rel_drift if basis == 'relative' else abs_drift:.3g})"
            if conserved
            else f"quantity drifts beyond tolerance ({basis} drift "
            f"{rel_drift if basis == 'relative' else abs_drift:.3g} > {tolerance:.3g})"
        ),
    }


# ─── Symbolic identity (equation) checking ─────────────────────────────────────

# Single-symbol assumptions that meaningfully change algebraic equality
# (e.g. sqrt(x**2) == x only when x is positive).
_ASSUMPTION_KEYS = frozenset(
    {"positive", "negative", "nonnegative", "nonzero", "real", "integer", "rational", "complex"}
)


def check_equation(lhs: str, rhs: str, assumptions: dict | None = None, timeout_s: float = _DEFAULT_TIMEOUT_S) -> dict:
    """Verify whether ``lhs == rhs`` symbolically (plain or LaTeX).

    Optional ``assumptions`` maps a symbol to one of positive/negative/real/
    integer/... so identities valid only under an assumption (e.g.
    ``sqrt(x**2) == x`` for ``x`` positive) can be confirmed. Returns
    pass/fail/inconclusive; undecidable comparisons are inconclusive, never pass.
    """
    left = safe_parse(lhs)
    right = safe_parse(rhs)
    if left is None or right is None:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": "one or both sides are not machine-parseable"}
    if assumptions:
        sympy = _sympy()
        replacements = {}
        for name, kind in assumptions.items():
            key = str(kind).strip().lower()
            if key in _ASSUMPTION_KEYS:
                replacements[sympy.Symbol(name)] = sympy.Symbol(name, **{key: True})
        if replacements:
            ok_l, left = run_with_timeout(lambda value=left: value.subs(replacements), timeout_s)
            ok_r, right = run_with_timeout(lambda value=right: value.subs(replacements), timeout_s)
            if not (ok_l and ok_r):
                return {"verdict": VERDICT_INCONCLUSIVE, "detail": "could not apply assumptions"}

    equal = symbolic_equal(left, right, timeout_s)
    if equal is True:
        return {"verdict": VERDICT_PASS, "detail": "left and right sides are equal"}
    result = {
        "verdict": VERDICT_FAIL if equal is False else VERDICT_INCONCLUSIVE,
        "detail": (
            "left and right sides are NOT equal"
            if equal is False
            else "equality is undecidable — review the simplified difference"
        ),
    }
    ok, difference = run_with_timeout(lambda: _sympy().simplify(left - right), timeout_s)
    if ok:
        result["difference"] = str(difference)
    return result


# ─── Series / asymptotic expansion checking ────────────────────────────────────


def check_series(
    expression: str,
    variable: str,
    point: str = "0",
    order: int = 6,
    expected: str | None = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
) -> dict:
    """Compute the series of ``expression`` in ``variable`` about ``point``.

    Returns the truncated expansion (through ``order``). When ``expected`` is
    given, compares the computed series to it → pass/fail; otherwise the verdict
    is ``computed``. Unparseable input or a series SymPy cannot evaluate →
    inconclusive, never a false pass.
    """
    expr = safe_parse(expression)
    if expr is None:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": "expression is not machine-parseable"}
    point_expr = safe_parse(point)
    if point_expr is None:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": f"expansion point '{point}' is not machine-parseable"}
    sympy = _sympy()
    var = sympy.Symbol(variable)
    ok, series = run_with_timeout(lambda: expr.series(var, point_expr, order).removeO(), timeout_s)
    if not ok or series is None:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": f"SymPy could not compute the series ({series})"}

    result: dict = {
        "variable": variable,
        "point": str(point_expr),
        "order": order,
        "computed_series": str(series),
    }
    if expected is None:
        result["verdict"] = VERDICT_COMPUTED
        result["detail"] = "computed the series expansion"
        return result
    expected_expr = safe_parse(expected)
    if expected_expr is None:
        result["verdict"] = VERDICT_COMPUTED
        result["expected_parsed"] = False
        result["detail"] = "computed series; expected expansion is prose — compare computed_series manually"
        return result
    result["expected_parsed"] = True
    equal = symbolic_equal(series, expected_expr, timeout_s)
    if equal is True:
        result["verdict"] = VERDICT_PASS
        result["detail"] = "computed series matches the expected expansion"
    elif equal is False:
        result["verdict"] = VERDICT_FAIL
        result["detail"] = "computed series does NOT match the expected expansion"
    else:
        result["verdict"] = VERDICT_COMPUTED
        result["detail"] = "equality undecidable — review computed_series vs expected"
    return result


# ─── ODE solution checking ─────────────────────────────────────────────────────

# function + primes, as a whole token: y, y', y'' ...
def _derivative_pattern(function: str) -> re.Pattern[str]:
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(function) + r"(?P<p>'*)(?![A-Za-z0-9_])")


def check_ode(
    equation: str, solution: str, variable: str = "x", function: str = "y", timeout_s: float = _DEFAULT_TIMEOUT_S
) -> dict:
    """Verify a candidate ``solution`` satisfies an ODE by substitution.

    The ODE uses prime notation for derivatives of ``function`` (``y``, ``y'``,
    ``y''`` …) and may be a residual or an ``LHS = RHS`` equation, e.g.
    ``"y'' + omega**2 * y = 0"``. Substitutes the solution and its derivatives
    and simplifies the residual: zero → pass, provably nonzero → fail.
    Unparseable input or an undecidable residual → inconclusive.
    """
    sol = safe_parse(solution)
    if sol is None:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": "solution is not machine-parseable"}
    lhs_text, rhs_text = (equation.split("=", 1) + ["0"])[:2] if "=" in equation else (equation, "0")

    pattern = _derivative_pattern(function)
    orders: set[int] = set()

    def _to_placeholder(match: re.Match[str]) -> str:
        order = len(match.group("p"))
        orders.add(order)
        return f"DERIVPLACE{order}"

    lhs_mod = pattern.sub(_to_placeholder, lhs_text)
    rhs_mod = pattern.sub(_to_placeholder, rhs_text)
    if not orders:
        return {
            "verdict": VERDICT_INCONCLUSIVE,
            "detail": f"function '{function}' (optionally primed) not found in the equation",
        }

    lhs_expr = _parse_plain(lhs_mod)
    rhs_expr = _parse_plain(rhs_mod)
    if lhs_expr is None or rhs_expr is None:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": "equation is not machine-parseable"}

    sympy = _sympy()
    var = sympy.Symbol(variable)
    substitutions = {}
    for order in orders:
        ok, derivative = run_with_timeout(lambda o=order: sympy.diff(sol, var, o), timeout_s)
        if not ok:
            return {"verdict": VERDICT_INCONCLUSIVE, "detail": "could not differentiate the solution"}
        substitutions[sympy.Symbol(f"DERIVPLACE{order}")] = derivative

    ok, residual = run_with_timeout(lambda: sympy.simplify((lhs_expr - rhs_expr).subs(substitutions)), timeout_s)
    if not ok:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": "could not simplify the residual"}

    is_zero = symbolic_equal(residual, _sympy().Integer(0), timeout_s)
    if is_zero is True:
        return {"verdict": VERDICT_PASS, "residual": "0", "detail": "solution satisfies the differential equation"}
    if is_zero is False:
        return {
            "verdict": VERDICT_FAIL,
            "residual": str(residual),
            "detail": "solution does NOT satisfy the equation (residual is nonzero)",
        }
    return {
        "verdict": VERDICT_INCONCLUSIVE,
        "residual": str(residual),
        "detail": "could not determine whether the residual vanishes",
    }


# ─── Tensor index / contraction consistency ────────────────────────────────────

_INDEX_TOKEN = re.compile(r"\\?[A-Za-z][A-Za-z0-9]*")
_UPPER_BRACED = re.compile(r"\^\{([^}]*)\}")
_LOWER_BRACED = re.compile(r"_\{([^}]*)\}")
_UPPER_SINGLE = re.compile(r"\^(\\?[A-Za-z][A-Za-z0-9]*)")
_LOWER_SINGLE = re.compile(r"_(\\?[A-Za-z][A-Za-z0-9]*)")


def _index_tokens(text: str) -> list[str]:
    return [re.sub(r"[^A-Za-z0-9]", "", tok) for tok in _INDEX_TOKEN.findall(text)]


def _term_indices(term: str) -> tuple[list[str], list[str]]:
    uppers: list[str] = []
    lowers: list[str] = []
    for match in _UPPER_BRACED.finditer(term):
        uppers += _index_tokens(match.group(1))
    for match in _LOWER_BRACED.finditer(term):
        lowers += _index_tokens(match.group(1))
    stripped = re.sub(r"[\^_]\{[^}]*\}", " ", term)
    for match in _UPPER_SINGLE.finditer(stripped):
        uppers += _index_tokens(match.group(1))
    for match in _LOWER_SINGLE.finditer(stripped):
        lowers += _index_tokens(match.group(1))
    return [u for u in uppers if u], [low for low in lowers if low]


def _analyze_term(term: str) -> tuple[dict[str, str] | None, str | None]:
    """Return (free-index map name->position, error) for one term."""
    uppers, lowers = _term_indices(term)
    names = set(uppers) | set(lowers)
    free: dict[str, str] = {}
    for name in names:
        up, down = uppers.count(name), lowers.count(name)
        total = up + down
        if total == 1:
            free[name] = "upper" if up else "lower"
        elif total == 2 and up == 1 and down == 1:
            continue  # valid contraction
        else:
            position = "upper" if up >= 2 else "lower" if down >= 2 else "mixed"
            if total > 2:
                return None, f"index '{name}' appears {total} times (max 2 for a valid contraction)"
            return None, f"index '{name}' is repeated in the same ({position}) position — cannot contract"
    return free, None


def _split_terms(side: str) -> list[str]:
    return [t.strip() for t in re.split(r"[+\-]", side) if t.strip()]


def check_tensor_indices(equation: str) -> dict:
    """Check free/dummy index consistency of a tensor equation.

    Each side is a sum of terms with indices written ``^{...}`` (upper) /
    ``_{...}`` (lower), space- or backslash-separated. Verifies that every term
    in a side carries the same free indices (in the same up/down position), that
    the two sides match, and that repeated indices are valid one-up/one-down
    contractions. Returns pass/fail; unparseable input → inconclusive.
    """
    if "=" not in equation:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": "equation must contain '=' to compare index structure"}
    left, right = equation.split("=", 1)
    left_terms, right_terms = _split_terms(left), _split_terms(right)
    if not left_terms or not right_terms:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": "could not parse terms on both sides"}

    issues: list[str] = []

    def _side_free(terms: list[str], label: str) -> dict[str, str] | None:
        side_free: dict[str, str] | None = None
        for term in terms:
            free, error = _analyze_term(term)
            if error is not None:
                issues.append(f"{label} term '{term}': {error}")
                continue
            if side_free is None:
                side_free = free
            elif free != side_free:
                issues.append(f"{label} term '{term}' has free indices {free}, expected {side_free}")
        return side_free

    left_free = _side_free(left_terms, "LHS")
    right_free = _side_free(right_terms, "RHS")

    if left_free is not None and right_free is not None and left_free != right_free:
        issues.append(f"LHS free indices {left_free} differ from RHS {right_free}")

    free_repr = sorted(f"{name}({pos})" for name, pos in (left_free or {}).items())
    if issues:
        return {"verdict": VERDICT_FAIL, "free_indices": free_repr, "issues": issues, "detail": "index structure is inconsistent"}
    return {
        "verdict": VERDICT_PASS,
        "free_indices": free_repr,
        "issues": [],
        "detail": "index structure is consistent across all terms and both sides",
    }


# ─── Integral checking ─────────────────────────────────────────────────────────


def check_integral(
    integrand: str,
    variable: str,
    claimed: str | None = None,
    lower: str | None = None,
    upper: str | None = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
) -> dict:
    """Verify a claimed integral of ``integrand`` w.r.t. ``variable``.

    Indefinite (no bounds): the claimed antiderivative is verified by
    differentiation — ``d(claimed)/dx == integrand`` — which is always decidable
    and so the robust direction. Definite (``lower`` & ``upper`` given): computes
    ``integrate(integrand, (x, lower, upper))`` and compares to ``claimed``.
    Unparseable input or an integral SymPy cannot evaluate → inconclusive.
    """
    integrand_expr = safe_parse(integrand)
    if integrand_expr is None:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": "integrand is not machine-parseable"}
    sympy = _sympy()
    var = sympy.Symbol(variable)
    definite = lower is not None and upper is not None

    if definite:
        a = safe_parse(lower)
        b = safe_parse(upper)
        if a is None or b is None:
            return {"verdict": VERDICT_INCONCLUSIVE, "detail": "integration bounds are not machine-parseable"}
        ok, value = run_with_timeout(lambda: sympy.integrate(integrand_expr, (var, a, b)), timeout_s)
        if not ok or value is None or value.has(sympy.Integral):
            return {"verdict": VERDICT_INCONCLUSIVE, "detail": "SymPy could not evaluate the definite integral"}
        result: dict = {"computed_value": str(value)}
        if claimed is None:
            result["verdict"] = VERDICT_COMPUTED
            result["detail"] = "computed the definite integral"
            return result
        claimed_expr = safe_parse(claimed)
        if claimed_expr is None:
            result["verdict"] = VERDICT_COMPUTED
            result["expected_parsed"] = False
            result["detail"] = "computed the definite integral; claimed value is prose — compare manually"
            return result
        equal = symbolic_equal(value, claimed_expr, timeout_s)
        result["verdict"] = VERDICT_PASS if equal is True else VERDICT_FAIL if equal is False else VERDICT_COMPUTED
        result["detail"] = (
            "computed definite integral matches the claimed value"
            if equal is True
            else "computed definite integral does NOT match the claimed value"
            if equal is False
            else "equality undecidable — review computed_value vs claimed"
        )
        return result

    # Indefinite.
    if claimed is not None:
        antiderivative = safe_parse(claimed)
        if antiderivative is None:
            return {"verdict": VERDICT_INCONCLUSIVE, "detail": "claimed antiderivative is not machine-parseable"}
        ok, derivative = run_with_timeout(lambda: sympy.diff(antiderivative, var), timeout_s)
        if not ok:
            return {"verdict": VERDICT_INCONCLUSIVE, "detail": "could not differentiate the claimed antiderivative"}
        equal = symbolic_equal(derivative, integrand_expr, timeout_s)
        return {
            "verdict": VERDICT_PASS if equal is True else VERDICT_FAIL if equal is False else VERDICT_INCONCLUSIVE,
            "derivative_of_claimed": str(derivative),
            "detail": (
                f"d(claimed)/d{variable} equals the integrand — antiderivative is correct"
                if equal is True
                else f"d(claimed)/d{variable} does NOT equal the integrand"
                if equal is False
                else f"could not decide whether d(claimed)/d{variable} equals the integrand"
            ),
        }
    ok, antiderivative = run_with_timeout(lambda: sympy.integrate(integrand_expr, var), timeout_s)
    if not ok or antiderivative is None or antiderivative.has(sympy.Integral):
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": "SymPy could not evaluate the indefinite integral"}
    return {"verdict": VERDICT_COMPUTED, "antiderivative": str(antiderivative), "detail": "computed the antiderivative"}


# ─── Commutator / operator-algebra checking ────────────────────────────────────

_DERIV_SYMBOL = re.compile(r"^f_(x+)$")


def _operator_action(text: str, func, var):
    """Parse an operator's action on a test function f into a SymPy expression.

    Uses ``f`` for the function and ``f_x``, ``f_xx`` … for its derivatives.
    Returns an expression in ``f(var)`` and its derivatives, or None.
    """
    parsed = _parse_plain(text)
    if parsed is None:
        return None
    sympy = _sympy()
    applied = func(var)
    replacements = {}
    for symbol in parsed.free_symbols:
        name = str(symbol)
        if name == "f":
            replacements[symbol] = applied
        else:
            match = _DERIV_SYMBOL.match(name)
            if match:
                replacements[symbol] = sympy.Derivative(applied, var, len(match.group(1)))
    return parsed.subs(replacements)


def check_commutator(
    operators: dict, a: str, b: str, expected: str, variable: str = "x", timeout_s: float = _DEFAULT_TIMEOUT_S
) -> dict:
    """Verify a commutator ``[A, B] = expected`` by acting on a test function.

    ``operators`` maps a name to its action on ``f`` (e.g. {"X": "x*f",
    "P": "-I*hbar*f_x"}); ``expected`` is the claimed result's action (e.g.
    "I*hbar*f" for ``[X, P] = i hbar``). Computes ``A(B f) - B(A f)`` symbolically
    and compares. Unparseable operators or an undecidable result → inconclusive.
    """
    if a not in operators or b not in operators:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": f"operators must include both '{a}' and '{b}'"}
    sympy = _sympy()
    var = sympy.Symbol(variable)
    func = sympy.Function("f")
    action_a = _operator_action(operators[a], func, var)
    action_b = _operator_action(operators[b], func, var)
    expected_expr = _operator_action(expected, func, var)
    if action_a is None or action_b is None or expected_expr is None:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": "operator action or expected result is not machine-parseable"}

    def _commutator():
        apply_a_to_b = action_a.subs(func, sympy.Lambda(var, action_b)).doit()
        apply_b_to_a = action_b.subs(func, sympy.Lambda(var, action_a)).doit()
        return sympy.simplify(apply_a_to_b - apply_b_to_a)

    ok, commutator = run_with_timeout(_commutator, timeout_s)
    if not ok:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": f"could not evaluate the commutator ({commutator})"}
    equal = symbolic_equal(commutator, expected_expr, timeout_s)
    return {
        "verdict": VERDICT_PASS if equal is True else VERDICT_FAIL if equal is False else VERDICT_INCONCLUSIVE,
        "commutator_action": str(commutator),
        "detail": (
            f"[{a}, {b}] matches the expected result"
            if equal is True
            else f"[{a}, {b}] does NOT match the expected result"
            if equal is False
            else f"could not decide whether [{a}, {b}] matches the expected result"
        ),
    }


# ─── PDE solution checking ─────────────────────────────────────────────────────


def check_pde(
    equation: str, solution: str, variables: list[str], function: str = "u", timeout_s: float = _DEFAULT_TIMEOUT_S
) -> dict:
    """Verify a candidate ``solution`` satisfies a PDE by substitution.

    Partial derivatives of ``function`` use subscript notation — each letter
    after ``_`` is one differentiation w.r.t. that variable: ``u_t``, ``u_xx``,
    ``u_xt`` (mixed). The equation may be a residual or ``LHS = RHS``, e.g. the
    heat equation ``"u_t = alpha * u_xx"``. Substitutes the solution and its
    partials and simplifies the residual: zero → pass, nonzero → fail.
    """
    sol = safe_parse(solution)
    if sol is None:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": "solution is not machine-parseable"}
    sympy = _sympy()
    var_syms: dict[str, object] = {}
    for name in variables:
        if not isinstance(name, str) or not name.isidentifier():
            return {"verdict": VERDICT_INCONCLUSIVE, "detail": f"invalid variable name '{name}'"}
        var_syms[name] = sympy.Symbol(name)

    lhs_text, rhs_text = (equation.split("=", 1) + ["0"])[:2] if "=" in equation else (equation, "0")
    pattern = re.compile(
        r"(?<![A-Za-z0-9_])" + re.escape(function) + r"(?:_(?P<sub>[A-Za-z]+))?(?![A-Za-z0-9_])"
    )
    subscripts: set[str] = set()

    def _to_placeholder(match: re.Match[str]) -> str:
        sub = match.group("sub") or ""
        subscripts.add(sub)
        return f"PDEDERIV_{sub or 'BASE'}"

    lhs_mod = pattern.sub(_to_placeholder, lhs_text)
    rhs_mod = pattern.sub(_to_placeholder, rhs_text)
    if not subscripts:
        return {
            "verdict": VERDICT_INCONCLUSIVE,
            "detail": f"function '{function}' (optionally subscripted) not found in the equation",
        }

    lhs_expr = _parse_plain(lhs_mod)
    rhs_expr = _parse_plain(rhs_mod)
    if lhs_expr is None or rhs_expr is None:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": "equation is not machine-parseable"}

    substitutions = {}
    for sub in subscripts:
        if not sub:
            derivative = sol
        else:
            diff_args = []
            for char in sub:
                if char not in var_syms:
                    return {"verdict": VERDICT_INCONCLUSIVE, "detail": f"subscript variable '{char}' is not in variables"}
                diff_args.append(var_syms[char])
            ok, derivative = run_with_timeout(lambda args=diff_args: sympy.diff(sol, *args), timeout_s)
            if not ok:
                return {"verdict": VERDICT_INCONCLUSIVE, "detail": "could not differentiate the solution"}
        substitutions[sympy.Symbol(f"PDEDERIV_{sub or 'BASE'}")] = derivative

    ok, residual = run_with_timeout(lambda: sympy.simplify((lhs_expr - rhs_expr).subs(substitutions)), timeout_s)
    if not ok:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": "could not simplify the residual"}
    is_zero = symbolic_equal(residual, sympy.Integer(0), timeout_s)
    if is_zero is True:
        return {"verdict": VERDICT_PASS, "residual": "0", "detail": "solution satisfies the PDE"}
    if is_zero is False:
        return {"verdict": VERDICT_FAIL, "residual": str(residual), "detail": "solution does NOT satisfy the PDE"}
    return {"verdict": VERDICT_INCONCLUSIVE, "residual": str(residual), "detail": "could not determine whether the residual vanishes"}


# ─── Matrix property checking ──────────────────────────────────────────────────

_MATRIX_DIFFS = {
    "symmetric": lambda m, eye: m - m.T,
    "antisymmetric": lambda m, eye: m + m.T,
    "skew-symmetric": lambda m, eye: m + m.T,
    "hermitian": lambda m, eye: m - m.H,
    "anti-hermitian": lambda m, eye: m + m.H,
    "unitary": lambda m, eye: m.H * m - eye,
    "orthogonal": lambda m, eye: m.T * m - eye,
    "idempotent": lambda m, eye: m * m - m,
    "projection": lambda m, eye: m * m - m,
    "involutory": lambda m, eye: m * m - eye,
    "normal": lambda m, eye: m.H * m - m * m.H,
}
_MATRIX_NEEDS_SQUARE = {
    "hermitian", "anti-hermitian", "unitary", "orthogonal", "idempotent", "projection", "involutory", "normal"
}


def check_matrix(rows: list[list[str]], prop: str, timeout_s: float = _DEFAULT_TIMEOUT_S) -> dict:
    """Verify a structural property of a matrix (entries are expression strings).

    ``prop`` is one of symmetric / antisymmetric / hermitian / anti-hermitian /
    unitary / orthogonal / idempotent (projection) / involutory / normal. ``I``
    in entries is the imaginary unit (e.g. Pauli ``Y = [[0, -I], [I, 0]]``).
    Returns pass/fail; unparseable entries or an undecidable comparison →
    inconclusive.
    """
    sympy = _sympy()
    parsed: list[list[object]] = []
    for row in rows:
        if not isinstance(row, list) or not row:
            return {"verdict": VERDICT_INCONCLUSIVE, "detail": "matrix must be a non-empty list of rows"}
        parsed_row = []
        for cell in row:
            entry = safe_parse(cell) if isinstance(cell, str) else None
            if entry is None:
                return {"verdict": VERDICT_INCONCLUSIVE, "detail": f"matrix entry '{cell}' is not machine-parseable"}
            parsed_row.append(entry.subs(sympy.Symbol("I"), sympy.I))
        parsed.append(parsed_row)
    if any(len(row) != len(parsed[0]) for row in parsed):
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": "matrix rows have differing lengths"}

    matrix = sympy.Matrix(parsed)
    key = prop.strip().lower().replace(" ", "-").replace("_", "-")
    if key == "antihermitian":
        key = "anti-hermitian"
    if key not in _MATRIX_DIFFS:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": f"unknown matrix property '{prop}'"}
    square = matrix.rows == matrix.cols
    if key in _MATRIX_NEEDS_SQUARE and not square:
        return {"verdict": VERDICT_FAIL, "shape": f"{matrix.rows}x{matrix.cols}", "detail": f"matrix is not square, so it cannot be {prop}"}

    eye = sympy.eye(matrix.rows) if square else None
    ok, difference = run_with_timeout(lambda: _MATRIX_DIFFS[key](matrix, eye).applyfunc(sympy.simplify), timeout_s)
    if not ok:
        return {"verdict": VERDICT_INCONCLUSIVE, "detail": "could not evaluate the matrix property"}
    zero = difference.is_zero_matrix
    return {
        "verdict": VERDICT_PASS if zero is True else VERDICT_FAIL if zero is False else VERDICT_INCONCLUSIVE,
        "property": prop,
        "shape": f"{matrix.rows}x{matrix.cols}",
        "detail": (
            f"matrix is {prop}" if zero is True else f"matrix is NOT {prop}" if zero is False else f"could not decide whether the matrix is {prop}"
        ),
    }
