"""Plain text / markdown / docx extraction."""
from __future__ import annotations
from pathlib import Path


def read_text(path: str) -> str:
    p = Path(path)
    ext = p.suffix.lower()
    if ext in (".txt", ".md", ".json", ".xml", ".html", ".csv", ".tsv"):
        return p.read_text(errors="replace")
    if ext == ".docx":
        try:
            import docx  # python-docx
            return "\n".join(par.text for par in docx.Document(str(p)).paragraphs)
        except Exception as e:  # pragma: no cover
            return f"(docx unreadable: {e})"
    return ""
