from __future__ import annotations

import re


def explicit_multiplication(text: str) -> str:
    """
    Turn implicit multiplication into explicit '*', e.g.:
    - 2x -> 2*x
    - 3(x+1) -> 3*(x+1)
    - (x+1)2 -> (x+1)*2
    - x(x+1) -> x*(x+1)
    """
    if not text:
        return ""
    t = text
    # number followed by variable: 2x -> 2*x
    # IMPORTANT: do not cross newlines; keep steps line-separated
    t = re.sub(r"(\d)[ \t]*([a-zA-Z])", r"\1*\2", t)
    # variable followed by '(' : x( -> x*(
    t = re.sub(r"([a-zA-Z])[ \t]*\(", r"\1*(", t)
    # number followed by '(' : 3( -> 3*(
    t = re.sub(r"(\d)[ \t]*\(", r"\1*(", t)
    # ')' followed by number/variable: )x -> )*x, )2 -> )*2
    t = re.sub(r"\)[ \t]*(\d|[a-zA-Z])", r")*\1", t)
    return t


def normalize_math_text(text: str) -> str:
    """
    Normalize common symbols students use into a more parseable form.
    """
    if not text:
        return ""
    t = text
    t = t.replace("（", "(").replace("）", ")")
    t = t.replace("＝", "=")
    t = t.replace("×", "*").replace("x", "x")
    t = t.replace("÷", "/")
    t = t.replace("^", "**")
    t = t.replace("﹣", "-").replace("－", "-").replace("–", "-").replace("—", "-")
    t = re.sub(r"[ \t]+", " ", t)
    t = explicit_multiplication(t)
    return t.strip()

