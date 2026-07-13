"""HTML/Markdown sanitizer for LLM output.

Removes dangerous elements (script tags, event handlers, javascript: links)
while preserving safe structural markup (headings, paragraphs, lists, tables,
links with http/https, bold, italic, code blocks).

Used to sanitize all LLM-generated HTML and markdown output before storage,
preventing injection attacks per Requirement 5.11.
"""

import re
from html.parser import HTMLParser


# Tags that are safe to preserve in output
SAFE_TAGS = frozenset({
    # Headings
    "h1", "h2", "h3", "h4", "h5", "h6",
    # Text structure
    "p", "br", "hr", "div", "span",
    # Lists
    "ul", "ol", "li",
    # Tables
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption", "colgroup", "col",
    # Inline formatting
    "strong", "b", "em", "i", "u", "s", "del", "ins", "mark", "small", "sub", "sup",
    # Code
    "pre", "code", "kbd", "samp", "var",
    # Links and media (filtered further for safe href/src)
    "a", "img",
    # Definitions
    "dl", "dt", "dd",
    # Block quotes
    "blockquote", "cite",
    # Details/summary
    "details", "summary",
    # Figure
    "figure", "figcaption",
})

# Tags that should be completely removed along with their content
DANGEROUS_TAGS = frozenset({"script", "style", "iframe", "object", "embed", "applet", "form"})

# Void elements (self-closing, no end tag)
VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})

# Event handler attributes (anything starting with "on")
EVENT_HANDLER_PATTERN = re.compile(r"^on\w+$", re.IGNORECASE)

# Safe URL schemes for href/src attributes
SAFE_SCHEMES = frozenset({"http", "https", "mailto", "#", ""})

# Pattern to detect dangerous URI schemes
DANGEROUS_SCHEME_PATTERN = re.compile(
    r"^\s*(javascript|vbscript|data)\s*:", re.IGNORECASE
)


class HTMLSanitizer(HTMLParser):
    """HTML parser that removes dangerous elements and preserves safe markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._output_parts: list[str] = []
        self._skip_depth: int = 0
        self._skip_tags_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()

        # If we're inside a dangerous tag, increase skip depth
        if self._skip_depth > 0:
            if tag_lower not in VOID_ELEMENTS:
                self._skip_depth += 1
            return

        # Dangerous tags: skip entirely (including content)
        if tag_lower in DANGEROUS_TAGS:
            # Void elements have no content/end tag, so just drop them
            if tag_lower in VOID_ELEMENTS:
                return
            self._skip_depth = 1
            self._skip_tags_stack.append(tag_lower)
            return

        # Unknown/unsafe tags: drop the tag but keep content
        if tag_lower not in SAFE_TAGS:
            return

        # Safe tag: filter attributes
        safe_attrs = self._filter_attributes(tag_lower, attrs)
        self._output_parts.append(self._build_tag(tag_lower, safe_attrs))

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        # If we're inside a dangerous tag
        if self._skip_depth > 0:
            self._skip_depth -= 1
            if self._skip_depth == 0 and self._skip_tags_stack:
                self._skip_tags_stack.pop()
            return

        # Only output end tags for safe tags
        if tag_lower in SAFE_TAGS:
            self._output_parts.append(f"</{tag_lower}>")

    def handle_data(self, data: str) -> None:
        # Skip content inside dangerous tags
        if self._skip_depth > 0:
            return
        self._output_parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if self._skip_depth > 0:
            return
        self._output_parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self._skip_depth > 0:
            return
        self._output_parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        # Strip all HTML comments
        pass

    def _filter_attributes(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> list[tuple[str, str | None]]:
        """Filter attributes, removing event handlers and dangerous URLs."""
        safe_attrs: list[tuple[str, str | None]] = []

        for attr_name, attr_value in attrs:
            attr_name_lower = attr_name.lower()

            # Remove event handler attributes (onclick, onload, onerror, etc.)
            if EVENT_HANDLER_PATTERN.match(attr_name_lower):
                continue

            # For href and src, validate the URL scheme
            if attr_name_lower in ("href", "src"):
                if attr_value is not None and self._is_dangerous_url(attr_value):
                    continue

            safe_attrs.append((attr_name_lower, attr_value))

        return safe_attrs

    def _is_dangerous_url(self, url: str) -> bool:
        """Check if a URL uses a dangerous scheme (javascript:, vbscript:, data:)."""
        if not url:
            return False
        return bool(DANGEROUS_SCHEME_PATTERN.match(url))

    def _build_tag(self, tag: str, attrs: list[tuple[str, str | None]]) -> str:
        """Build an HTML opening tag string from tag name and attributes."""
        if not attrs:
            return f"<{tag}>"

        attr_parts = []
        for name, value in attrs:
            if value is None:
                attr_parts.append(name)
            else:
                # Escape attribute value
                escaped_value = (
                    value.replace("&", "&amp;")
                    .replace('"', "&quot;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                attr_parts.append(f'{name}="{escaped_value}"')

        attrs_str = " ".join(attr_parts)
        return f"<{tag} {attrs_str}>"

    def get_output(self) -> str:
        """Return the sanitized HTML string."""
        return "".join(self._output_parts)


def sanitize_html(content: str) -> str:
    """Sanitize HTML/Markdown content by removing dangerous elements.

    Removes:
    - script tags and their content
    - style tags and their content
    - iframe, object, embed, applet, form tags and their content
    - Event handler attributes (onclick, onload, onerror, onmouseover, etc.)
    - Links with javascript: scheme
    - Links with data: scheme
    - Links with vbscript: scheme
    - HTML comments

    Preserves:
    - Headings (h1-h6)
    - Paragraphs (p)
    - Lists (ul, ol, li)
    - Tables (table, thead, tbody, tr, th, td)
    - Links with http/https scheme (a href)
    - Bold (strong, b), italic (em, i)
    - Code blocks (pre, code)
    - Images with http/https src
    - Block quotes
    - Other safe structural markup

    Args:
        content: Raw HTML or markdown-embedded HTML string.

    Returns:
        Sanitized string with dangerous elements removed.
    """
    if not content:
        return ""

    sanitizer = HTMLSanitizer()
    try:
        sanitizer.feed(content)
    except Exception:
        # If parsing fails, do aggressive regex-based cleanup
        return _regex_sanitize(content)

    return sanitizer.get_output()


def _regex_sanitize(content: str) -> str:
    """Fallback regex-based sanitization for malformed HTML.

    This is a last resort when the HTML parser fails.
    """
    # Remove script tags and content
    content = re.sub(
        r"<script\b[^>]*>.*?</script>",
        "",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Remove style tags and content
    content = re.sub(
        r"<style\b[^>]*>.*?</style>",
        "",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Remove event handlers from remaining tags
    content = re.sub(
        r'\s+on\w+\s*=\s*"[^"]*"',
        "",
        content,
        flags=re.IGNORECASE,
    )
    content = re.sub(
        r"\s+on\w+\s*=\s*'[^']*'",
        "",
        content,
        flags=re.IGNORECASE,
    )
    # Remove javascript: links
    content = re.sub(
        r'href\s*=\s*"[^"]*javascript:[^"]*"',
        'href=""',
        content,
        flags=re.IGNORECASE,
    )
    content = re.sub(
        r"href\s*=\s*'[^']*javascript:[^']*'",
        "href=''",
        content,
        flags=re.IGNORECASE,
    )
    return content
