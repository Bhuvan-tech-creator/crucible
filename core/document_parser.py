"""
core/document_parser.py
Handles extracting plain text from uploaded engineering documents.
Supports PDF, DOCX, TXT, Markdown, and plain text files.
"""

import PyPDF2
import docx


def extract_text(file) -> str:
    """
    Extract plain text from a werkzeug FileStorage object.
    Dispatches to the appropriate parser based on file extension.
    Raises ValueError if the file type is unsupported or the result is empty.
    """
    filename = file.filename.lower()

    if filename.endswith(".pdf"):
        text = _parse_pdf(file)
    elif filename.endswith(".docx"):
        text = _parse_docx(file)
    elif any(filename.endswith(ext) for ext in (".txt", ".md", ".text", ".markdown")):
        text = _parse_plain(file)
    else:
        # Best-effort decode for anything else (RTF, CSV, etc.)
        text = _parse_plain(file, strict=False)

    if not text.strip():
        raise ValueError(
            "The document appears to be empty or contains no extractable text. "
            "Make sure it is a text-based file (not a scanned image PDF)."
        )

    return text


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_pdf(file) -> str:
    try:
        reader = PyPDF2.PdfReader(file)
        pages = []
        for i, page in enumerate(reader.pages):
            raw = page.extract_text()
            if raw:
                pages.append(raw.strip())
        return "\n\n".join(pages)
    except Exception as exc:
        raise ValueError(f"PDF parsing failed: {exc}") from exc


def _parse_docx(file) -> str:
    try:
        doc = docx.Document(file)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as exc:
        raise ValueError(f"DOCX parsing failed: {exc}") from exc


def _parse_plain(file, strict: bool = True) -> str:
    try:
        raw = file.read()
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        if strict:
            raise ValueError("File is not valid UTF-8 text.")
        return raw.decode("utf-8", errors="ignore")