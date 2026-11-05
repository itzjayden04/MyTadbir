"""Citizen input rules: only text, images and files (PDF, DOC, DOCX) are accepted.

Files are read locally (no API call) and a short excerpt goes to the router with the message, so a
citizen can upload, say, a layout plan description or a notice letter instead of typing it out.
"""
from __future__ import annotations

from pathlib import Path

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
FILE_EXT = {".pdf", ".doc", ".docx"}
MAX_BYTES = 15 * 1024 * 1024
EXCERPT_CHARS = 1500


class InputRejected(ValueError):
    def __init__(self, en: str, bm: str):
        super().__init__(en)
        self.en, self.bm = en, bm


def check(filename: str, size: int, expect: str) -> str:
    ext = Path(filename).suffix.lower()
    allowed = IMAGE_EXT if expect == "image" else FILE_EXT
    if ext not in allowed:
        kinds = "JPG, PNG or WEBP images" if expect == "image" else "PDF, DOC or DOCX files"
        kinds_bm = "imej JPG, PNG atau WEBP" if expect == "image" else "fail PDF, DOC atau DOCX"
        raise InputRejected(f"{filename}: only {kinds} are accepted.", f"{filename}: hanya {kinds_bm} diterima.")
    if size > MAX_BYTES:
        raise InputRejected(f"{filename} is larger than 15 MB.", f"{filename} melebihi 15 MB.")
    return ext


def excerpt(path: str) -> str:
    p = Path(path)
    try:
        if p.suffix.lower() == ".pdf":
            from pypdf import PdfReader

            r = PdfReader(str(p))
            text = " ".join((pg.extract_text() or "") for pg in r.pages[:3])
        elif p.suffix.lower() == ".docx":
            import docx

            text = " ".join(par.text for par in docx.Document(str(p)).paragraphs)
        else:
            return ""  # legacy .doc: stored and passed to the officer, not read automatically
    except Exception:  # noqa: BLE001
        return ""
    return " ".join(text.split())[:EXCERPT_CHARS]
