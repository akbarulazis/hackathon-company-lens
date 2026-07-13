"""Property-based tests for crawler URL validation and HTML sanitization.

# Feature: company-lens-rebuild
# Property 15: HTML/Markdown Sanitization
# Property 16: URL Validation for Crawling

Validates: Requirements 5.3, 5.11, 18.4
"""

import re
import string

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.middleware.sanitize import sanitize_html
from app.research.crawler import validate_url


# ===========================================================================
# Strategies for Property 15: HTML/Markdown Sanitization
# ===========================================================================

# Safe tags that should be preserved after sanitization
SAFE_TAG_NAMES = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li",
                  "strong", "em", "blockquote", "pre", "code"]

# Event handler attribute names
EVENT_HANDLERS = ["onclick", "onload", "onerror", "onmouseover", "onmouseout",
                  "onfocus", "onblur", "onsubmit", "onkeydown", "onkeyup"]

# Strategy for safe text content
safe_text = st.text(
    alphabet=st.sampled_from(string.ascii_letters + string.digits + " .,!?-"),
    min_size=1,
    max_size=50,
)

# Strategy for generating dangerous script tags
script_tag_strategy = st.builds(
    lambda content: f"<script>{content}</script>",
    content=safe_text,
)

# Strategy for event handler attributes
event_handler_strategy = st.builds(
    lambda handler, code: f'{handler}="{code}"',
    handler=st.sampled_from(EVENT_HANDLERS),
    code=st.sampled_from(["alert(1)", "console.log(1)", "void(0)", "return false"]),
)

# Strategy for dangerous link hrefs
dangerous_href_strategy = st.sampled_from([
    "javascript:alert(1)",
    "javascript:void(0)",
    "javascript:document.cookie",
    "data:text/html,<script>alert(1)</script>",
    "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
    "vbscript:MsgBox",
])

# Strategy for safe link hrefs
safe_href_strategy = st.sampled_from([
    "https://example.com",
    "https://www.google.com/search",
    "http://localhost:8080",
    "https://docs.python.org/3/",
])

# Strategy for safe HTML elements
safe_element_strategy = st.builds(
    lambda tag, content: f"<{tag}>{content}</{tag}>",
    tag=st.sampled_from(SAFE_TAG_NAMES),
    content=safe_text,
)

# Strategy for safe anchor tags
safe_anchor_strategy = st.builds(
    lambda href, text: f'<a href="{href}">{text}</a>',
    href=safe_href_strategy,
    text=safe_text,
)

# Strategy for dangerous elements with event handlers on safe tags
dangerous_event_element_strategy = st.builds(
    lambda tag, handler, content: f"<{tag} {handler}>{content}</{tag}>",
    tag=st.sampled_from(["div", "p", "span", "a"]),
    handler=event_handler_strategy,
    content=safe_text,
)

# Strategy for dangerous anchor tags with javascript: href
dangerous_anchor_strategy = st.builds(
    lambda href, text: f'<a href="{href}">{text}</a>',
    href=dangerous_href_strategy,
    text=safe_text,
)


# Strategy combining dangerous + safe content
mixed_html_strategy = st.builds(
    lambda parts: "".join(parts),
    parts=st.lists(
        st.one_of(
            safe_element_strategy,
            safe_anchor_strategy,
            script_tag_strategy,
            dangerous_event_element_strategy,
            dangerous_anchor_strategy,
        ),
        min_size=1,
        max_size=5,
    ),
)


# ===========================================================================
# Strategies for Property 16: URL Validation for Crawling
# ===========================================================================

# Valid hostnames
valid_hostname_strategy = st.from_regex(
    r"[a-z][a-z0-9\-]{0,20}\.[a-z]{2,6}", fullmatch=True
)

# Valid paths
valid_path_strategy = st.one_of(
    st.just(""),
    st.just("/"),
    st.from_regex(r"/[a-z0-9\-/]{1,30}", fullmatch=True),
)

# Valid http/https URLs
valid_url_strategy = st.builds(
    lambda scheme, host, path: f"{scheme}://{host}{path}",
    scheme=st.sampled_from(["http", "https"]),
    host=valid_hostname_strategy,
    path=valid_path_strategy,
)

# Invalid schemes
invalid_scheme_strategy = st.sampled_from([
    "ftp", "file", "javascript", "data", "mailto", "ssh", "git", "telnet",
])

# URLs with invalid schemes
invalid_scheme_url_strategy = st.builds(
    lambda scheme, host: f"{scheme}://{host}",
    scheme=invalid_scheme_strategy,
    host=valid_hostname_strategy,
)

# Completely malformed strings (no scheme at all)
malformed_string_strategy = st.text(
    alphabet=st.sampled_from(string.ascii_letters + string.digits + ".-_/"),
    min_size=1,
    max_size=50,
).filter(lambda s: "://" not in s)


# ===========================================================================
# Property 15: HTML/Markdown Sanitization
# ===========================================================================


@given(html=mixed_html_strategy)
@settings(max_examples=200, deadline=None)
def test_property15_no_script_tags_remain(html: str) -> None:
    """Property 15: After sanitization, no <script> tags shall remain in output.

    **Validates: Requirements 5.11, 18.4**
    """
    result = sanitize_html(html)
    assert "<script" not in result.lower(), (
        f"Script tag found in sanitized output: {result!r}"
    )


@given(html=mixed_html_strategy)
@settings(max_examples=200, deadline=None)
def test_property15_no_event_handlers_remain(html: str) -> None:
    """Property 15: After sanitization, no event handler attributes shall remain.

    **Validates: Requirements 5.11, 18.4**
    """
    result = sanitize_html(html)
    # Check for any on* attribute pattern in the output
    event_pattern = re.compile(r'\bon\w+\s*=', re.IGNORECASE)
    assert not event_pattern.search(result), (
        f"Event handler found in sanitized output: {result!r}"
    )


@given(html=mixed_html_strategy)
@settings(max_examples=200, deadline=None)
def test_property15_no_javascript_links_remain(html: str) -> None:
    """Property 15: After sanitization, no javascript: or data: scheme links remain.

    **Validates: Requirements 5.11, 18.4**
    """
    result = sanitize_html(html)
    # Check for javascript: scheme
    assert "javascript:" not in result.lower(), (
        f"javascript: scheme found in sanitized output: {result!r}"
    )
    # Check for data: scheme in href/src attributes
    data_href_pattern = re.compile(r'(?:href|src)\s*=\s*["\']?\s*data:', re.IGNORECASE)
    assert not data_href_pattern.search(result), (
        f"data: scheme found in href/src in sanitized output: {result!r}"
    )


@given(
    tag=st.sampled_from(SAFE_TAG_NAMES),
    content=safe_text,
)
@settings(max_examples=200, deadline=None)
def test_property15_safe_markup_preserved(tag: str, content: str) -> None:
    """Property 15: Safe structural markup (headings, paragraphs, lists) is preserved.

    **Validates: Requirements 5.11, 18.4**
    """
    html = f"<{tag}>{content}</{tag}>"
    result = sanitize_html(html)
    # The safe tag should be present in the output
    assert f"<{tag}>" in result, (
        f"Safe tag <{tag}> was removed from output: {result!r}"
    )
    assert f"</{tag}>" in result, (
        f"Safe closing tag </{tag}> was removed from output: {result!r}"
    )
    # The content should be preserved
    assert content in result, (
        f"Content '{content}' was removed from output: {result!r}"
    )


@given(
    href=safe_href_strategy,
    text=safe_text,
)
@settings(max_examples=200, deadline=None)
def test_property15_safe_links_preserved(href: str, text: str) -> None:
    """Property 15: Links with http/https scheme are preserved after sanitization.

    **Validates: Requirements 5.11, 18.4**
    """
    html = f'<a href="{href}">{text}</a>'
    result = sanitize_html(html)
    # The anchor tag should remain
    assert "<a " in result, (
        f"Safe anchor tag was removed from output: {result!r}"
    )
    # The text content should be preserved
    assert text in result, (
        f"Link text '{text}' was removed from output: {result!r}"
    )
    # The href should be preserved (it's safe)
    assert href in result, (
        f"Safe href '{href}' was removed from output: {result!r}"
    )


# ===========================================================================
# Property 16: URL Validation for Crawling
# ===========================================================================


@given(url=valid_url_strategy)
@settings(max_examples=200, deadline=None)
def test_property16_valid_http_https_urls_accepted(url: str) -> None:
    """Property 16: URLs with http/https scheme and valid hostname are accepted.

    **Validates: Requirements 5.3**
    """
    assert validate_url(url) is True, (
        f"Valid URL was rejected: {url!r}"
    )


@given(url=invalid_scheme_url_strategy)
@settings(max_examples=200, deadline=None)
def test_property16_invalid_schemes_rejected(url: str) -> None:
    """Property 16: URLs with non-http/https schemes are rejected.

    **Validates: Requirements 5.3**
    """
    assert validate_url(url) is False, (
        f"URL with invalid scheme was accepted: {url!r}"
    )


@given(s=malformed_string_strategy)
@settings(max_examples=200, deadline=None)
def test_property16_malformed_strings_rejected(s: str) -> None:
    """Property 16: Strings without a valid URL scheme are rejected.

    **Validates: Requirements 5.3**
    """
    assert validate_url(s) is False, (
        f"Malformed string was accepted as valid URL: {s!r}"
    )


@given(scheme=st.sampled_from(["javascript", "data", "vbscript"]))
@settings(max_examples=50, deadline=None)
def test_property16_dangerous_schemes_rejected(scheme: str) -> None:
    """Property 16: Dangerous schemes (javascript:, data:, vbscript:) are rejected.

    **Validates: Requirements 5.3**
    """
    url = f"{scheme}:alert(1)"
    assert validate_url(url) is False, (
        f"Dangerous scheme URL was accepted: {url!r}"
    )


def test_property16_empty_and_none_rejected() -> None:
    """Property 16: Empty strings and None-like values are rejected.

    **Validates: Requirements 5.3**
    """
    assert validate_url("") is False
    assert validate_url(None) is False  # type: ignore[arg-type]
    assert validate_url("   ") is False


@given(
    scheme=st.sampled_from(["http", "https"]),
    path=valid_path_strategy,
)
@settings(max_examples=100, deadline=None)
def test_property16_scheme_without_hostname_rejected(scheme: str, path: str) -> None:
    """Property 16: URLs with valid scheme but no hostname are rejected.

    **Validates: Requirements 5.3**
    """
    # http:// with no host
    url = f"{scheme}://{path}"
    # Only reject if there's truly no valid netloc
    # When path starts with "/" it becomes just scheme://path with no host
    if not path or path.startswith("/"):
        assert validate_url(url) is False, (
            f"URL without hostname was accepted: {url!r}"
        )
