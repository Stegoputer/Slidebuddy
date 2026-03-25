from pathlib import Path
from typing import Optional

SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".pptx": "pptx",
    ".txt": "txt",
    ".md": "markdown",
    ".markdown": "markdown",
    ".csv": "excel",
    ".tsv": "excel",
    ".xlsx": "excel",
    ".xls": "excel",
    ".xlsm": "excel",
    ".html": "html",
    ".htm": "html",
}


def parse_source(file_path: Path) -> str:
    """Parse a source file based on its extension."""
    ext = file_path.suffix.lower()
    source_type = SUPPORTED_EXTENSIONS.get(ext)

    if source_type == "pdf":
        from slidebuddy.parsers.pdf_parser import parse_pdf
        return parse_pdf(file_path)
    elif source_type == "pptx":
        from slidebuddy.parsers.pptx_parser import parse_pptx
        return parse_pptx(file_path)
    elif source_type in ("txt", "markdown"):
        from slidebuddy.parsers.text_parser import parse_text
        return parse_text(file_path)
    elif source_type == "excel":
        from slidebuddy.parsers.excel_parser import parse_excel
        return parse_excel(file_path)
    elif source_type == "html":
        from slidebuddy.parsers.html_parser import parse_html
        return parse_html(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def get_source_type(file_path: Path) -> Optional[str]:
    """Get the source type string for a file."""
    return SUPPORTED_EXTENSIONS.get(file_path.suffix.lower())
