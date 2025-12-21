from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image

from .textnorm import normalize_math_text


@dataclass(frozen=True)
class OcrResult:
    text: str
    engine: str
    lang: str


def _tesseract_available() -> bool:
    try:
        import pytesseract  # noqa: F401

        return True
    except Exception:
        return False


def _preprocess_for_math(img: Image.Image) -> Image.Image:
    """
    Lightweight preprocessing to reduce noise and improve OCR on handwriting/worksheets.
    Uses OpenCV if available; falls back to grayscale.
    """
    try:
        import cv2
        import numpy as np

        arr = np.array(img.convert("RGB"))
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        # Adaptive threshold is robust across lighting conditions
        thr = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            7,
        )
        # Slight dilation can help broken strokes
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        thr = cv2.dilate(thr, kernel, iterations=1)
        return Image.fromarray(thr)
    except Exception:
        return img.convert("L")


def ocr_image(
    image_path: Path,
    *,
    lang: str = "chi_tra+eng",
) -> Optional[OcrResult]:
    """
    Best-effort OCR. Returns None if OCR engine isn't available.
    """
    if not _tesseract_available():
        return None

    import pytesseract

    img = Image.open(image_path)
    img = _preprocess_for_math(img)

    # PSM 6: assume a uniform block of text; works ok for worksheets
    config = "--psm 6"
    try:
        raw = pytesseract.image_to_string(img, lang=lang, config=config) or ""
        txt = normalize_math_text(raw)
        return OcrResult(text=txt, engine="tesseract", lang=lang)
    except Exception:
        # fallback: english only (common if chi_tra isn't installed)
        try:
            raw = pytesseract.image_to_string(img, lang="eng", config=config) or ""
            txt = normalize_math_text(raw)
            return OcrResult(text=txt, engine="tesseract", lang="eng")
        except Exception:
            return None

