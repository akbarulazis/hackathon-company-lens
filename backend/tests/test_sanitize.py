"""Unit tests for the HTML/Markdown sanitizer.

Tests that dangerous elements are removed while safe markup is preserved.
Validates: Requirements 5.11, 18.4
"""

import pytest

from app.middleware.sanitize import sanitize_html


# ---------------------------------------------------------------------------
# Dangerous Element Removal Tests
# ---------------------------------------------------------------------------


class TestDangerousElementRemoval:
    """Tests that dangerous HTML elements are stripped."""

    def test_removes_script_tags(self) -> None:
        html = "<p>Hello</p><script>alert('xss')</script><p>World</p>"
        result = sanitize_html(html)
        assert "<script" not in result
        assert "alert" not in result
        assert "Hello" in result
        assert "World" in result

    def test_removes_script_with_attributes(self) -> None:
        html = '<script type="text/javascript" src="evil.js"></script>'
        result = sanitize_html(html)
        assert "<script" not in result
        assert "evil.js" not in result

    def test_removes_style_tags(self) -> None:
        html = "<p>Text</p><style>.hidden{display:none}</style>"
        result = sanitize_html(html)
        assert "<style" not in result
        assert "display:none" not in result
        assert "Text" in result

    def test_removes_iframe_tags(self) -> None:
        html = '<p>Content</p><iframe src="http://evil.com"></iframe>'
        result = sanitize_html(html)
        assert "<iframe" not in result
        assert "evil.com" not in result
        assert "Content" in result

    def test_removes_onclick_handler(self) -> None:
        html = '<p onclick="alert(1)">Click me</p>'
        result = sanitize_html(html)
        assert "onclick" not in result
        assert "alert" not in result
        assert "Click me" in result

    def test_removes_onload_handler(self) -> None:
        html = '<img onload="steal()" src="https://example.com/img.png">'
        result = sanitize_html(html)
        assert "onload" not in result
        assert "steal" not in result

    def test_removes_onerror_handler(self) -> None:
        html = '<img onerror="alert(1)" src="x">'
        result = sanitize_html(html)
        assert "onerror" not in result
        assert "alert" not in result

    def test_removes_onmouseover_handler(self) -> None:
        html = '<a onmouseover="evil()" href="https://safe.com">Link</a>'
        result = sanitize_html(html)
        assert "onmouseover" not in result
        assert "evil" not in result
        assert "Link" in result

    def test_removes_javascript_href(self) -> None:
        html = '<a href="javascript:alert(1)">Click</a>'
        result = sanitize_html(html)
        assert "javascript:" not in result
        assert "Click" in result

    def test_removes_javascript_href_mixed_case(self) -> None:
        html = '<a href="JavaScript:alert(1)">Click</a>'
        result = sanitize_html(html)
        assert "JavaScript:" not in result.lower()

    def test_removes_javascript_href_with_spaces(self) -> None:
        html = '<a href="  javascript:alert(1)">Click</a>'
        result = sanitize_html(html)
        assert "javascript:" not in result.lower()

    def test_removes_data_href(self) -> None:
        html = '<a href="data:text/html,<script>alert(1)</script>">Click</a>'
        result = sanitize_html(html)
        assert "data:" not in result

    def test_removes_vbscript_href(self) -> None:
        html = '<a href="vbscript:msgbox">Click</a>'
        result = sanitize_html(html)
        assert "vbscript:" not in result

    def test_removes_object_tag(self) -> None:
        html = '<object data="evil.swf"></object><p>Safe</p>'
        result = sanitize_html(html)
        assert "<object" not in result
        assert "Safe" in result

    def test_removes_embed_tag(self) -> None:
        html = '<embed src="evil.swf"><p>Safe</p>'
        result = sanitize_html(html)
        assert "<embed" not in result
        assert "Safe" in result

    def test_removes_form_tag(self) -> None:
        html = '<form action="/steal"><input type="text"></form><p>Safe</p>'
        result = sanitize_html(html)
        assert "<form" not in result
        assert "Safe" in result

    def test_removes_nested_scripts(self) -> None:
        html = "<div><script>nested();</script></div>"
        result = sanitize_html(html)
        assert "<script" not in result
        assert "nested" not in result


# ---------------------------------------------------------------------------
# Safe Markup Preservation Tests
# ---------------------------------------------------------------------------


class TestSafeMarkupPreservation:
    """Tests that safe HTML elements are preserved."""

    def test_preserves_headings(self) -> None:
        for level in range(1, 7):
            html = f"<h{level}>Heading {level}</h{level}>"
            result = sanitize_html(html)
            assert f"<h{level}>" in result
            assert f"Heading {level}" in result
            assert f"</h{level}>" in result

    def test_preserves_paragraphs(self) -> None:
        html = "<p>This is a paragraph.</p>"
        result = sanitize_html(html)
        assert "<p>" in result
        assert "This is a paragraph." in result
        assert "</p>" in result

    def test_preserves_unordered_lists(self) -> None:
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        result = sanitize_html(html)
        assert "<ul>" in result
        assert "<li>" in result
        assert "Item 1" in result
        assert "Item 2" in result

    def test_preserves_ordered_lists(self) -> None:
        html = "<ol><li>First</li><li>Second</li></ol>"
        result = sanitize_html(html)
        assert "<ol>" in result
        assert "<li>" in result
        assert "First" in result

    def test_preserves_tables(self) -> None:
        html = "<table><tr><th>Header</th></tr><tr><td>Cell</td></tr></table>"
        result = sanitize_html(html)
        assert "<table>" in result
        assert "<th>" in result
        assert "<td>" in result
        assert "Header" in result
        assert "Cell" in result

    def test_preserves_safe_links(self) -> None:
        html = '<a href="https://example.com">Safe Link</a>'
        result = sanitize_html(html)
        assert "<a" in result
        assert "https://example.com" in result
        assert "Safe Link" in result

    def test_preserves_http_links(self) -> None:
        html = '<a href="http://example.com">HTTP Link</a>'
        result = sanitize_html(html)
        assert "http://example.com" in result

    def test_preserves_bold(self) -> None:
        html = "<strong>Bold text</strong>"
        result = sanitize_html(html)
        assert "<strong>" in result
        assert "Bold text" in result

    def test_preserves_italic(self) -> None:
        html = "<em>Italic text</em>"
        result = sanitize_html(html)
        assert "<em>" in result
        assert "Italic text" in result

    def test_preserves_code_blocks(self) -> None:
        html = "<pre><code>print('hello')</code></pre>"
        result = sanitize_html(html)
        assert "<pre>" in result
        assert "<code>" in result
        assert "print('hello')" in result

    def test_preserves_blockquote(self) -> None:
        html = "<blockquote>A quote</blockquote>"
        result = sanitize_html(html)
        assert "<blockquote>" in result
        assert "A quote" in result

    def test_preserves_images_with_safe_src(self) -> None:
        html = '<img src="https://example.com/img.png" alt="Image">'
        result = sanitize_html(html)
        assert "<img" in result
        assert "https://example.com/img.png" in result


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests for the sanitizer."""

    def test_empty_string(self) -> None:
        assert sanitize_html("") == ""

    def test_plain_text(self) -> None:
        text = "Just plain text without HTML"
        result = sanitize_html(text)
        assert text in result

    def test_mixed_safe_and_dangerous(self) -> None:
        html = (
            '<h1>Title</h1>'
            '<script>evil()</script>'
            '<p onclick="bad()">Content</p>'
            '<a href="javascript:void(0)">Link</a>'
            '<a href="https://safe.com">Safe</a>'
        )
        result = sanitize_html(html)
        assert "<h1>" in result
        assert "Title" in result
        assert "<script" not in result
        assert "evil" not in result
        assert "onclick" not in result
        assert "javascript:" not in result
        assert "https://safe.com" in result
        assert "Safe" in result

    def test_markdown_embedded_html(self) -> None:
        """Markdown may contain embedded HTML that needs sanitization."""
        content = (
            "# Title\n\n"
            "Some markdown text.\n\n"
            '<script>alert("xss")</script>\n\n'
            "<p>Embedded paragraph</p>\n"
        )
        result = sanitize_html(content)
        assert "<script" not in result
        assert "alert" not in result
        assert "Title" in result
        assert "Embedded paragraph" in result

    def test_preserves_entities(self) -> None:
        html = "<p>Less &lt; Greater &gt; Amp &amp;</p>"
        result = sanitize_html(html)
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result

    def test_multiple_event_handlers_on_same_tag(self) -> None:
        html = '<div onclick="a()" onmouseover="b()" onload="c()">Text</div>'
        result = sanitize_html(html)
        assert "onclick" not in result
        assert "onmouseover" not in result
        assert "onload" not in result
        assert "Text" in result
