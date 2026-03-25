from pathlib import Path
import unicodedata


def _fix_encoding(text: str) -> str:
    """Fix broken Unicode characters from PDF extraction.

    PyMuPDF sometimes returns text with wrong encoding for German umlauts
    and special characters. This tries latin-1 re-encoding and normalizes
    Unicode to NFC form.
    """
    # Try to fix mojibake: if the text was decoded as latin-1 but is actually utf-8
    try:
        fixed = text.encode("latin-1").decode("utf-8")
        if fixed != text:
            text = fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    # Normalize Unicode (e.g. composed vs decomposed umlauts)
    text = unicodedata.normalize("NFC", text)

    # Replace common broken sequences that slip through
    replacements = {
        "\u00e4": "ä", "\u00f6": "ö", "\u00fc": "ü",
        "\u00c4": "Ä", "\u00d6": "Ö", "\u00dc": "Ü",
        "\u00df": "ß",
        "\ufffd": "",  # replacement character
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def parse_pdf(file_path: Path) -> str:
    """Extract text from a PDF file using PyMuPDF."""
    import fitz  # PyMuPDF

    doc = fitz.open(str(file_path))
    pages = []
    for page_num, page in enumerate(doc, 1):
        text = page.get_text("text")
        text = _fix_encoding(text)
        if text.strip():
            pages.append(f"--- Seite {page_num} ---\n{text.strip()}")
    doc.close()
    return "\n\n".join(pages)
