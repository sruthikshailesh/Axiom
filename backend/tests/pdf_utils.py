from __future__ import annotations


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_text_pdf(text: str) -> bytes:
    """Build a minimal one-page PDF with a single line of Helvetica text."""
    content = "BT /F1 24 Tf 72 720 Td ({}) Tj ET".format(_escape(text)).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length "
        + str(len(content)).encode()
        + b" >>\nstream\n"
        + content
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += "{} 0 obj\n".format(number).encode() + body + b"\nendobj\n"

    xref_position = len(out)
    out += "xref\n0 {}\n".format(len(objects) + 1).encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += "{:010d} 00000 n \n".format(offset).encode()
    out += "trailer\n<< /Size {} /Root 1 0 R >>\nstartxref\n{}\n%%EOF\n".format(
        len(objects) + 1, xref_position
    ).encode()

    return bytes(out)


def make_blank_pdf() -> bytes:
    """A valid PDF whose page has no text, like a scanned page."""
    return make_text_pdf("")
