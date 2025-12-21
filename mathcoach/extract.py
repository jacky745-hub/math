from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .models import FileKind
from .textnorm import normalize_math_text


def detect_file_kind(filename: str) -> FileKind:
    name = (filename or "").lower().strip()
    if name.endswith(".pdf"):
        return FileKind.PDF
    if name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return FileKind.IMAGE
    return FileKind.UNKNOWN


## NOTE: normalization moved to mathcoach.textnorm to avoid circular imports.


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
    if kind == FileKind.IMAGE:
        try:
            from .ocr import ocr_image

            res = ocr_image(upload_path)
            return res.text if res else None
        except Exception:
            return None
    return None

