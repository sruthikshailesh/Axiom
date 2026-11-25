from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

TEXT_EXTENSIONS = {".txt", ".md"}


class UnsupportedFileType(Exception):
    """The uploaded file type is not supported (HTTP 415)."""


class ExtractionError(Exception):
    """The file could not be turned into text (HTTP 422)."""


def extract_text(filename: str, content: bytes) -> str:
    """Return the plain text of an uploaded .txt, .md or .pdf file."""
    suffix = Path(filename or "").suffix.lower()

    if suffix in TEXT_EXTENSIONS:
        return content.decode("utf-8", errors="replace")
    if suffix == ".pdf":
        return _extract_pdf(content)

    raise UnsupportedFileType(
        "Unsupported file type: {}.".format(suffix or "unknown")
    )


def _extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except (PdfReadError, OSError, ValueError) as exc:
        raise ExtractionError("Could not read PDF: the file is not a valid PDF.") from exc

    text = "\n\n".join(page for page in pages if page)
    if not text.strip():
        raise ExtractionError(
            "PDF contains no extractable text. Scanned PDFs need OCR before upload."
        )
    return text
