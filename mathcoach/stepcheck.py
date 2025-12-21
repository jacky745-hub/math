from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import sympy as sp

from .textnorm import normalize_math_text
from .models import DetectedIssue, ErrorTag


_X = sp.Symbol("x")


@dataclass(frozen=True)
class StepLine:
    raw: str
    normalized: str
    equation_text: Optional[str]
    parsed: Optional[sp.Eq]


@dataclass(frozen=True)
class StepCheck:
    index: int
    line: str
    is_equivalent_to_previous: Optional[bool]
    note: str


@dataclass(frozen=True)
class StepCheckSummary:
    steps: list[StepCheck]
    first_wrong_index: Optional[int]
    first_wrong_line: Optional[str]
    issue: Optional[DetectedIssue]


def _equation_snippet(line: str) -> Optional[str]:
    """
    Extract an equation-like substring.
    """
    if "=" not in line:
        return None
    m = re.search(r"([0-9xy+\-*/().\s]+=[0-9xy+\-*/().\s]+)", line)
    if m:
        return m.group(1).strip()
    return line.strip()


def _safe_sympify(expr: str) -> sp.Expr:
    return sp.sympify(expr, locals={"x": _X}, evaluate=True)


def _parse_eq(eq_text: str) -> Optional[sp.Eq]:
    if not eq_text or "=" not in eq_text:
        return None
    left, right = eq_text.split("=", 1)
    left = left.strip()
    right = right.strip()
    if not left or not right:
        return None
    try:
        return sp.Eq(_safe_sympify(left), _safe_sympify(right))
    except Exception:
        return None


def _is_constant_in_x(expr: sp.Expr) -> bool:
    try:
        return _X not in expr.free_symbols
    except Exception:
        return False


def _equivalent_equations(e1: sp.Eq, e2: sp.Eq) -> Optional[bool]:
    """
    MVP equivalence check (focus on single-variable algebra):
    Treat e1 and e2 equivalent if (lhs-rhs) differs by a nonzero constant multiple.
    """
    try:
        f1 = sp.simplify(e1.lhs - e1.rhs)
        f2 = sp.simplify(e2.lhs - e2.rhs)

        if sp.simplify(f1) == 0 and sp.simplify(f2) == 0:
            return True
        if sp.simplify(f1) == 0 or sp.simplify(f2) == 0:
            return False

        p1 = sp.Poly(f1, _X)
        p2 = sp.Poly(f2, _X)
        if p1.degree() != p2.degree():
            return False

        lc1 = p1.LC()
        lc2 = p2.LC()
        if sp.simplify(lc2) == 0:
            return None
        k = sp.simplify(lc1 / lc2)
        if sp.simplify(k) == 0 or (not _is_constant_in_x(k)):
            return False

        return sp.simplify(f1 - k * f2) == 0
    except Exception:
        return None


def _classify_wrong_step(prev: sp.Eq, cur: sp.Eq) -> Optional[DetectedIssue]:
    """
    Rule-based misconception classification based on how the equation changed.
    """
    try:
        L1, R1 = prev.lhs, prev.rhs
        L2, R2 = cur.lhs, cur.rhs

        # Transpose error (moved same-sign term across '=')
        # Wrong pattern: L2 = L1 - c, R2 = R1 + c  (instead of R1 - c)
        deltaL = sp.simplify(L1 - L2)
        deltaR = sp.simplify(R2 - R1)
        if _is_constant_in_x(deltaL) and sp.simplify(deltaL - deltaR) == 0 and sp.simplify(deltaL) != 0:
            return DetectedIssue(
                tag=ErrorTag.TRANSPOSE_ERROR,
                evidence="這一步像是把左邊的一項移到右邊，但符號沒有改變。",
                misconception="移項不是搬家；要用等量變形（兩邊同加/同減）來想",
            )

        # Distribution error (very common): a*(x+b) -> a*x + b
        s_prev = f"{sp.simplify(L1)}={sp.simplify(R1)}"
        s_cur = f"{sp.simplify(L2)}={sp.simplify(R2)}"
        if re.search(r"\d+\*\(x\+?\d+", s_prev) and re.search(r"\d+\*x\+\d+", s_cur):
            return DetectedIssue(
                tag=ErrorTag.DISTRIBUTION_ERROR,
                evidence="展開括號時，有一項可能沒有一起乘到外面的係數。",
                misconception="分配律：括號裡每一項都要乘到外面的係數",
            )

        # Like terms / arithmetic: equation changed but deltas are constant-ish
        if _is_constant_in_x(sp.simplify((L1 - R1) - (L2 - R2))):
            return DetectedIssue(
                tag=ErrorTag.ARITHMETIC_CARELESS,
                evidence="這一步看起來像是整理/計算時有一點小地方偏掉。",
                misconception="運算粗心或同類項整理不完整；建議逐行驗算",
            )
    except Exception:
        pass

    return DetectedIssue(
        tag=ErrorTag.UNKNOWN,
        evidence="我看到這一步和上一行不等價，但需要你確認你做了什麼操作（兩邊同加/同乘了什麼）。",
        misconception="等量變形：每一步只能做一個操作，且要對等號兩邊同時做",
    )


def parse_step_lines(text: str) -> list[StepLine]:
    if not text:
        return []
    lines = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        norm = normalize_math_text(raw)
        eq_txt = _equation_snippet(norm)
        parsed = _parse_eq(eq_txt) if eq_txt else None
        lines.append(StepLine(raw=raw, normalized=norm, equation_text=eq_txt, parsed=parsed))
    return lines


def check_steps(work_text: str) -> StepCheckSummary:
    parsed_lines = parse_step_lines(work_text)
    if not parsed_lines:
        return StepCheckSummary(steps=[], first_wrong_index=None, first_wrong_line=None, issue=None)

    # Keep only lines that look like equations (for step checking)
    eq_lines = [(i, sl) for i, sl in enumerate(parsed_lines) if sl.parsed is not None]
    if len(eq_lines) < 2:
        # Not enough to compare; still return what we have for display
        checks = [
            StepCheck(
                index=i,
                line=sl.normalized,
                is_equivalent_to_previous=None,
                note="（目前只有一行等式，無法做逐行等價檢查）",
            )
            for i, sl in eq_lines
        ]
        return StepCheckSummary(steps=checks, first_wrong_index=None, first_wrong_line=None, issue=None)

    checks: list[StepCheck] = []
    first_wrong_index: Optional[int] = None
    first_wrong_line: Optional[str] = None
    issue: Optional[DetectedIssue] = None

    prev_eq: Optional[sp.Eq] = None
    prev_idx: Optional[int] = None
    for idx, sl in eq_lines:
        if prev_eq is None:
            checks.append(
                StepCheck(index=idx, line=sl.normalized, is_equivalent_to_previous=None, note="起點（原式/第一行）")
            )
            prev_eq = sl.parsed
            prev_idx = idx
            continue

        assert sl.parsed is not None
        eqv = _equivalent_equations(prev_eq, sl.parsed)
        if eqv is True:
            checks.append(StepCheck(index=idx, line=sl.normalized, is_equivalent_to_previous=True, note="等價 ✅"))
            prev_eq = sl.parsed
            prev_idx = idx
            continue

        note = "這一步和上一行不等價 ⚠️"
        checks.append(StepCheck(index=idx, line=sl.normalized, is_equivalent_to_previous=False, note=note))
        if first_wrong_index is None:
            first_wrong_index = idx
            first_wrong_line = sl.normalized
            issue = _classify_wrong_step(prev_eq, sl.parsed)
        # Keep going so teacher can inspect later, but we keep first wrong as primary
        prev_eq = sl.parsed
        prev_idx = idx

    return StepCheckSummary(
        steps=checks,
        first_wrong_index=first_wrong_index,
        first_wrong_line=first_wrong_line,
        issue=issue,
    )

