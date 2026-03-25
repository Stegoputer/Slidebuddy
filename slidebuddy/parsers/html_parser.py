"""Parse HTML files — strip all markup, scripts, styles and return clean text."""

import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag


# Tags that carry no useful content
_STRIP_TAGS = {"script", "style", "noscript", "svg", "iframe", "nav", "footer", "header"}

# Block-level tags that produce paragraph breaks
_BLOCK_TAGS = frozenset({
    "p", "div", "section", "article", "blockquote", "pre",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "tr", "figcaption", "dt", "dd",
})


def parse_html(file_path: Path) -> str:
    """Read an HTML file and return clean, readable plain text."""
    raw = file_path.read_text(encoding="utf-8", errors="replace")
    return html_to_text(raw)


def html_to_text(html: str) -> str:
    """Convert an HTML string to clean plain text.

    - Removes scripts, styles, nav, footer etc.
    - Extracts only leaf-level block elements to avoid duplication
    - Preserves heading hierarchy as markdown-style markers
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove useless tags entirely
    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()

    # Extract metadata if available (reader-mode HTML)
    title = ""
    credits = ""
    title_el = soup.find(id="reader-title") or soup.find("h1")
    if title_el:
        title = title_el.get_text(strip=True)
    credits_el = soup.find(id="reader-credits")
    if credits_el:
        credits = credits_el.get_text(strip=True)

    # Walk the tree — only extract leaf-level block elements
    # (those that don't contain other block elements as children)
    seen_texts: set[str] = set()
    blocks: list[str] = []

    if title:
        blocks.append(f"# {title}")
        seen_texts.add(title)
    if credits:
        blocks.append(credits)
        seen_texts.add(credits)

    for element in soup.find_all(_BLOCK_TAGS):
        # Skip if this element contains child block elements —
        # those children will be visited separately
        if _has_block_children(element):
            continue

        text = element.get_text(" ", strip=True)
        if not text or len(text) < 3:
            continue

        # Deduplicate identical text blocks
        if text in seen_texts:
            continue
        seen_texts.add(text)

        # Add heading markers
        tag_name = element.name
        if tag_name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag_name[1])
            text = f"{'#' * level} {text}"

        blocks.append(text)

    result = "\n\n".join(blocks)

    # Collapse excessive whitespace within lines
    result = re.sub(r"[ \t]+", " ", result)
    # Collapse 3+ newlines to 2
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


def _has_block_children(tag: Tag) -> bool:
    """Check if a tag contains any block-level child elements."""
    for child in tag.children:
        if isinstance(child, Tag) and child.name in _BLOCK_TAGS:
            return True
    return False
