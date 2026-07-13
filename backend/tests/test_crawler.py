"""Unit tests for the URL crawler module.

Tests URL validation, HTML text extraction, and crawl behavior.
Validates: Requirements 5.3
"""

import pytest

from app.research.crawler import (
    CrawlResult,
    HTMLTextExtractor,
    extract_text_from_html,
    validate_url,
)


# ---------------------------------------------------------------------------
# URL Validation Tests
# ---------------------------------------------------------------------------


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_valid_http_url(self) -> None:
        assert validate_url("http://example.com") is True

    def test_valid_https_url(self) -> None:
        assert validate_url("https://example.com") is True

    def test_valid_url_with_path(self) -> None:
        assert validate_url("https://example.com/path/to/page") is True

    def test_valid_url_with_query(self) -> None:
        assert validate_url("https://example.com/search?q=test") is True

    def test_valid_url_with_port(self) -> None:
        assert validate_url("http://example.com:8080/api") is True

    def test_valid_url_with_subdomain(self) -> None:
        assert validate_url("https://www.sub.example.com") is True

    def test_rejects_ftp_scheme(self) -> None:
        assert validate_url("ftp://example.com/file") is False

    def test_rejects_file_scheme(self) -> None:
        assert validate_url("file:///etc/passwd") is False

    def test_rejects_javascript_scheme(self) -> None:
        assert validate_url("javascript:alert(1)") is False

    def test_rejects_data_scheme(self) -> None:
        assert validate_url("data:text/html,<h1>hi</h1>") is False

    def test_rejects_empty_string(self) -> None:
        assert validate_url("") is False

    def test_rejects_none(self) -> None:
        assert validate_url(None) is False  # type: ignore

    def test_rejects_relative_path(self) -> None:
        assert validate_url("/path/to/page") is False

    def test_rejects_no_scheme(self) -> None:
        assert validate_url("example.com") is False

    def test_rejects_scheme_only(self) -> None:
        assert validate_url("http://") is False

    def test_rejects_whitespace(self) -> None:
        assert validate_url("   ") is False

    def test_rejects_just_scheme_colon(self) -> None:
        assert validate_url("https:") is False


# ---------------------------------------------------------------------------
# HTML Text Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractTextFromHtml:
    """Tests for extract_text_from_html function."""

    def test_simple_html(self) -> None:
        html = "<html><body><p>Hello World</p></body></html>"
        result = extract_text_from_html(html)
        assert "Hello World" in result

    def test_strips_script_content(self) -> None:
        html = "<p>Good</p><script>alert('xss')</script><p>Also Good</p>"
        result = extract_text_from_html(html)
        assert "Good" in result
        assert "alert" not in result
        assert "Also Good" in result

    def test_strips_style_content(self) -> None:
        html = "<p>Text</p><style>.hidden{display:none}</style>"
        result = extract_text_from_html(html)
        assert "Text" in result
        assert "hidden" not in result

    def test_empty_input(self) -> None:
        assert extract_text_from_html("") == ""

    def test_plain_text_passthrough(self) -> None:
        result = extract_text_from_html("Just plain text")
        assert "Just plain text" in result

    def test_nested_tags(self) -> None:
        html = "<div><p><strong>Bold</strong> normal</p></div>"
        result = extract_text_from_html(html)
        assert "Bold" in result
        assert "normal" in result

    def test_strips_head_content(self) -> None:
        html = "<html><head><title>Title</title></head><body><p>Body</p></body></html>"
        result = extract_text_from_html(html)
        assert "Body" in result
        assert "Title" not in result


# ---------------------------------------------------------------------------
# CrawlResult Tests
# ---------------------------------------------------------------------------


class TestCrawlResult:
    """Tests for the CrawlResult dataclass."""

    def test_default_values(self) -> None:
        result = CrawlResult(url="https://example.com")
        assert result.url == "https://example.com"
        assert result.content == ""
        assert result.status_code == 0
        assert result.success is False
        assert result.error == ""

    def test_success_result(self) -> None:
        result = CrawlResult(
            url="https://example.com",
            content="Page content",
            status_code=200,
            success=True,
        )
        assert result.success is True
        assert result.content == "Page content"
        assert result.status_code == 200
