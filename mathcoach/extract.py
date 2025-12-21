from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .models import FileKind


def detect_file_kind(filename: str) -> FileKind:
    name = (filename or "").lower().strip()
    if name.endswith(".pdf"):
        return FileKind.PDF
    if name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return FileKind.IMAGE
    return FileKind.UNKNOWN


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
    t = re.sub(r"(\d)\s*([a-zA-Z])", r"\1*\2", t)
    # variable followed by '(' : x( -> x*(
    t = re.sub(r"([a-zA-Z])\s*\(", r"\1*(", t)
    # number followed by '(' : 3( -> 3*(
    t = re.sub(r"(\d)\s*\(", r"\1*(", t)
    # ')' followed by number/variable: )( -> )*(  and )2 -> )*2
    t = re.sub(r"\)\s*(\d|[a-zA-Z])", r")*\1", t)
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


def extract_text_from_pdf(pdf_path: Path, max_pages: int = 8) -> str:
    """
    Best-effort PDF text extraction (no OCR).
    Uses PyMuPDF (fitz).
    """
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    try:
        chunks: list[str] = []
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            txt = page.get_text("text") or ""
            txt = txt.strip()
            if txt:
                chunks.append(txt)
        return "\n\n".join(chunks).strip()
    finally:
        doc.close()


def maybe_extract_upload_text(upload_path: Optional[Path], kind: FileKind) -> Optional[str]:
    if not upload_path:
        return None
    if kind == FileKind.PDF:
        try:
            return extract_text_from_pdf(upload_path)
        except Exception:
            return None
    # Images: MVP does not OCR; keep None.
    return None

