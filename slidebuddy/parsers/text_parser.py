from pathlib import Path

def parse_text(file_path: Path) -> str:
    """Parse plain text or markdown files."""
    return file_path.read_text(encoding="utf-8")
