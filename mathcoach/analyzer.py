from __future__ import annotations

import re
from typing import Optional

import sympy as sp

from .textnorm import normalize_math_text
from .models import AnalysisResult, DetectedIssue, ErrorTag, SubmissionInput
from .scaffolding import build_scaffold
from .stepcheck import check_steps


_X = sp.Symbol("x")
_Y = sp.Symbol("y")


def _first_equation(text: str) -> Optional[str]:
    """
    Extract the first equation-like snippet containing '='.
    We keep it simple for MVP.
    """
    if not text:
        return None
    eq_snip = re.compile(r"([0-9xy+\-*/().\s]+=[0-9xy+\-*/().\s]+)")

    for line in text.splitlines():
        line = line.strip()
        if "=" in line and len(line) <= 120:
            # Prefer lines with x or y (junior-high algebra)
            m = eq_snip.search(line)
            if m and (re.search(r"\b[xy]\b", m.group(1)) or re.search(r"[xy]", m.group(1))):
                return m.group(1).strip()
    # fallback: any '=' line
    for line in text.splitlines():
        line = line.strip()
        if "=" in line and len(line) <= 120:
            m = eq_snip.search(line)
            if m:
                return m.group(1).strip()
            return line
    return None


def _safe_sympify(expr: str) -> sp.Expr:
    return sp.sympify(
        expr,
        locals={"x": _X, "y": _Y},
        evaluate=True,
    )


def _parse_equation(eq_text: str) -> Optional[sp.Eq]:
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


def _parse_final_answer(ans_text: str) -> Optional[sp.Expr]:
    """
    Accept formats like:
    - x=2
    - 2
    - x = -3/2
    """
    if not ans_text:
        return None
    t = normalize_math_text(ans_text)
    t = t.strip()
    m = re.search(r"\b[xy]\s*=\s*([^\s,;]+)", t)
    if m:
        t = m.group(1)
    # Strip trailing punctuation
    t = re.sub(r"[，,。;；]+$", "", t).strip()
    try:
        return _safe_sympify(t)
    except Exception:
        return None


def _detect_distribution_error(work: str) -> Optional[DetectedIssue]:
    # e.g., 2(x+3)=2x+3  (missed distributing 2 to constant)
    if not work:
        return None
    w = normalize_math_text(work)
    pat = re.compile(r"(\d+)\s*\(\s*x\s*\+\s*(\d+)\s*\)\s*=\s*\1x\s*\+\s*\2\b")
    if pat.search(w):
        return DetectedIssue(
            tag=ErrorTag.DISTRIBUTION_ERROR,
            evidence="你把 a(x+b) 寫成 ax+b（常數 b 沒有一起乘到 a）。",
            misconception="分配律：括號裡每一項都要乘到外面的係數",
        )
    return None


def _detect_transpose_error(problem_eq: str | None, work: str) -> Optional[DetectedIssue]:
    # Simple signature: original has "+c" then a step contains "=...+c" when moving to other side.
    if not problem_eq or not work:
        return None
    pe = normalize_math_text(problem_eq)
    w = normalize_math_text(work)

    # Find a '+ number' on left side in original
    left, right = (pe.split("=", 1) + [""])[:2]
    m = re.search(r"\+\s*(\d+)\b", left)
    if not m:
        return None
    c = m.group(1)

    # If in work we see "...= ... + c" alongside "x" isolation intent, flag
    if re.search(rf"=\s*.*\+\s*{re.escape(c)}\b", w) and re.search(r"\b\d*x\b|x\b", w):
        return DetectedIssue(
            tag=ErrorTag.TRANSPOSE_ERROR,
            evidence=f"移項時，原本在等號左邊的 +{c} 移到右邊應該變成 -{c}。",
            misconception="移項不是搬家；是做等量變形（兩邊同加/同減）",
        )
    return None


def _detect_sign_error(work: str) -> Optional[DetectedIssue]:
    if not work:
        return None
    w = normalize_math_text(work)
    # Heuristic: double negative confusion around parentheses
    if re.search(r"-\s*\(\s*[^)]+-\s*[^)]+\)", w):
        return DetectedIssue(
            tag=ErrorTag.SIGN_ERROR,
            evidence="看到負號加括號時，括號內每一項符號都可能要改變。",
            misconception="負號與括號：-(a-b)= -a + b",
        )
    return None


def analyze(sub: SubmissionInput) -> AnalysisResult:
    problem = normalize_math_text(sub.problem_text)
    work = normalize_math_text(sub.work_text or "")
    eq_text = _first_equation(problem) or _first_equation(sub.extracted_text or "") or None
    eq = _parse_equation(eq_text) if eq_text else None
    ans = _parse_final_answer(sub.final_answer_text or "")

    step_summary = check_steps(work) if work else None

    debug: dict[str, object] = {
        "equation_text": eq_text,
        "parsed_equation": str(eq) if eq is not None else None,
        "parsed_answer": str(ans) if ans is not None else None,
        "step_check": {
            "first_wrong_index": getattr(step_summary, "first_wrong_index", None),
            "first_wrong_line": getattr(step_summary, "first_wrong_line", None),
            "steps": [
                {
                    "index": s.index,
                    "line": s.line,
                    "is_equivalent_to_previous": s.is_equivalent_to_previous,
                    "note": s.note,
                }
                for s in (step_summary.steps if step_summary else [])
            ],
        },
    }

    is_correct: bool | None = None
    issues: list[DetectedIssue] = []

    # Detect common misconceptions from written steps (best-effort).
    for detector in (
        _detect_distribution_error,
        lambda w: _detect_transpose_error(eq_text, w),
        _detect_sign_error,
    ):
        try:
            issue = detector(work)
        except Exception:
            issue = None
        if issue:
            issues.append(issue)

    # Step-based diagnosis: if we can locate first wrong step, prioritize it (low-noise, high-signal).
    first_wrong_step_index = None
    first_wrong_step_text = None
    if step_summary and step_summary.first_wrong_index is not None and step_summary.issue is not None:
        first_wrong_step_index = int(step_summary.first_wrong_index)
        first_wrong_step_text = step_summary.first_wrong_line
        issues = [step_summary.issue] + [i for i in issues if i.tag != step_summary.issue.tag]

    # Try to verify correctness when the problem is a solvable equation and the student provided an answer.
    if eq is not None and ans is not None:
        try:
            sols = sp.solve(eq, _X, dict=False)
            debug["solutions"] = [str(s) for s in sols]
            if len(sols) == 1:
                is_correct = sp.simplify(sols[0] - ans) == 0
            else:
                # Multiple solutions: treat correct if answer matches any.
                is_correct = any(sp.simplify(s - ans) == 0 for s in sols)
        except Exception as e:
            debug["solve_error"] = repr(e)

    # Reduce noise: keep top 2 issues max (MVP).
    issues = issues[:2]

    if is_correct is True:
        short = "答案看起來是對的，我們把方法整理成可複製的步驟。"
    elif is_correct is False:
        if first_wrong_step_index is not None and first_wrong_step_text:
            short = f"我找到你『第一次偏掉』的那一步（第 {first_wrong_step_index + 1} 行附近）。我們從那一行開始修正就好。"
        else:
            short = "我覺得答案可能有一點偏掉；我們用『一步一步檢查』把錯抓出來。"
    else:
        short = "我先不急著判對錯；我會用逐步提示陪你把思路走順。"

    hint_path = build_scaffold(problem_text=problem, issues=issues, is_correct=is_correct)
    return AnalysisResult(
        is_correct=is_correct,
        short_feedback=short,
        issues=issues,
        hint_path=hint_path,
        debug=debug,
        first_wrong_step_index=first_wrong_step_index,
        first_wrong_step_text=first_wrong_step_text,
    )

