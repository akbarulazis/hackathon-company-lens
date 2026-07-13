"""Unit tests for the comparison module.

Tests the comparison service validation logic, fallback HTML generation,
schemas, and worker integration.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from pydantic import ValidationError

from app.comparison.schemas import CompareRequest, ComparisonReportResponse
from app.comparison.service import (
    ComparisonError,
    _generate_fallback_html,
    _escape_html,
    _format_revenue,
    _format_number,
    _format_score,
)
from app.llm.prompts.comparison import (
    build_comparison_prompt,
    build_comparison_system_prompt,
)


# --- Schema tests ---


class TestCompareRequest:
    """Tests for CompareRequest schema validation."""

    def test_valid_two_companies(self):
        req = CompareRequest(company_ids=[1, 2])
        assert req.company_ids == [1, 2]

    def test_valid_three_companies(self):
        req = CompareRequest(company_ids=[1, 2, 3])
        assert req.company_ids == [1, 2, 3]

    def test_too_few_companies_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            CompareRequest(company_ids=[1])
        assert "too_short" in str(exc_info.value) or "min_length" in str(exc_info.value)

    def test_empty_list_raises(self):
        with pytest.raises(ValidationError):
            CompareRequest(company_ids=[])

    def test_too_many_companies_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            CompareRequest(company_ids=[1, 2, 3, 4])
        assert "too_long" in str(exc_info.value) or "max_length" in str(exc_info.value)

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            CompareRequest()


class TestComparisonReportResponse:
    """Tests for ComparisonReportResponse schema."""

    def test_valid_response(self):
        resp = ComparisonReportResponse(
            id=1,
            workspace_id=1,
            company_ids=[1, 2],
            html_content="<h1>Compare</h1>",
            is_fallback=False,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        assert resp.id == 1
        assert resp.is_fallback is False

    def test_null_html_content(self):
        resp = ComparisonReportResponse(
            id=1,
            workspace_id=1,
            company_ids=[1, 2],
            html_content=None,
            is_fallback=True,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        assert resp.html_content is None


# --- Fallback HTML generation tests ---


class TestFallbackHtml:
    """Tests for the fallback HTML table generator."""

    def _make_company(self, **kwargs):
        """Create a mock company profile for testing."""
        company = MagicMock()
        company.name = kwargs.get("name", "Test Corp")
        company.industry = kwargs.get("industry", "Technology")
        company.annual_revenue = kwargs.get("annual_revenue", 1_000_000)
        company.employee_count = kwargs.get("employee_count", 100)
        company.financial_health = kwargs.get("financial_health", 4.2)
        company.business_risk = kwargs.get("business_risk", 3.1)
        company.growth_potential = kwargs.get("growth_potential", 4.5)
        company.product_fit = kwargs.get("product_fit", 3.8)
        company.relationship_accessibility = kwargs.get("relationship_accessibility", 2.9)
        company.overall_score = kwargs.get("overall_score", 3.7)
        return company

    def test_generates_html_with_two_companies(self):
        companies = [
            self._make_company(name="Company A"),
            self._make_company(name="Company B"),
        ]
        html = _generate_fallback_html(companies)

        assert "<table" in html
        assert "Company A" in html
        assert "Company B" in html
        assert "comparison-table" in html

    def test_generates_html_with_three_companies(self):
        companies = [
            self._make_company(name="Alpha"),
            self._make_company(name="Beta"),
            self._make_company(name="Gamma"),
        ]
        html = _generate_fallback_html(companies)

        assert "Alpha" in html
        assert "Beta" in html
        assert "Gamma" in html

    def test_includes_all_score_dimensions(self):
        companies = [
            self._make_company(name="A"),
            self._make_company(name="B"),
        ]
        html = _generate_fallback_html(companies)

        assert "Financial Health" in html
        assert "Business Risk" in html
        assert "Growth Potential" in html
        assert "Product Fit" in html
        assert "Relationship Accessibility" in html
        assert "Overall Score" in html

    def test_includes_structured_fields(self):
        companies = [
            self._make_company(name="A"),
            self._make_company(name="B"),
        ]
        html = _generate_fallback_html(companies)

        assert "Industry" in html
        assert "Annual Revenue" in html
        assert "Employee Count" in html

    def test_handles_none_values(self):
        companies = [
            self._make_company(
                name="No Data",
                industry=None,
                annual_revenue=None,
                employee_count=None,
                financial_health=None,
            ),
            self._make_company(name="Full Data"),
        ]
        html = _generate_fallback_html(companies)

        assert "N/A" in html
        assert "No Data" in html

    def test_escapes_html_in_names(self):
        companies = [
            self._make_company(name="<script>alert('xss')</script>"),
            self._make_company(name="Normal Co"),
        ]
        html = _generate_fallback_html(companies)

        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_includes_fallback_notice(self):
        companies = [
            self._make_company(name="A"),
            self._make_company(name="B"),
        ]
        html = _generate_fallback_html(companies)

        assert "unavailable" in html.lower()


# --- Helper function tests ---


class TestHelpers:
    """Tests for formatting helper functions."""

    def test_escape_html(self):
        assert _escape_html("<script>") == "&lt;script&gt;"
        assert _escape_html('"hello"') == "&quot;hello&quot;"
        assert _escape_html("a & b") == "a &amp; b"

    def test_format_revenue_billions(self):
        assert _format_revenue(5_000_000_000) == "$5.0B"

    def test_format_revenue_millions(self):
        assert _format_revenue(2_500_000) == "$2.5M"

    def test_format_revenue_thousands(self):
        assert _format_revenue(50_000) == "$50.0K"

    def test_format_revenue_small(self):
        assert _format_revenue(500) == "$500"

    def test_format_revenue_none(self):
        assert _format_revenue(None) == "N/A"

    def test_format_number(self):
        assert _format_number(1000) == "1,000"
        assert _format_number(1000000) == "1,000,000"
        assert _format_number(None) == "N/A"

    def test_format_score(self):
        assert _format_score(4.2) == "4.2/5.0"
        assert _format_score(None) == "N/A"
        assert _format_score(1.0) == "1.0/5.0"


# --- Prompt template tests ---


class TestPromptTemplates:
    """Tests for comparison LLM prompt templates."""

    def _make_company(self, **kwargs):
        company = MagicMock()
        company.name = kwargs.get("name", "Test Corp")
        company.industry = kwargs.get("industry", "Tech")
        company.headquarters = kwargs.get("headquarters", "NYC")
        company.founded_year = kwargs.get("founded_year", 2010)
        company.employee_count = kwargs.get("employee_count", 500)
        company.annual_revenue = kwargs.get("annual_revenue", 10_000_000)
        company.funding_total = kwargs.get("funding_total", 5_000_000)
        company.market_cap = kwargs.get("market_cap", None)
        company.company_website = kwargs.get("company_website", "https://test.com")
        company.ticker = kwargs.get("ticker", None)
        company.financial_health = kwargs.get("financial_health", 3.5)
        company.business_risk = kwargs.get("business_risk", 2.8)
        company.growth_potential = kwargs.get("growth_potential", 4.1)
        company.product_fit = kwargs.get("product_fit", 3.2)
        company.relationship_accessibility = kwargs.get("relationship_accessibility", 3.9)
        company.overall_score = kwargs.get("overall_score", 3.5)
        company.acquisition_brief = kwargs.get("acquisition_brief", "A brief.")
        return company

    def test_system_prompt_contains_key_instructions(self):
        prompt = build_comparison_system_prompt()
        assert "HTML" in prompt
        assert "corporate banking" in prompt.lower()
        assert "script" in prompt.lower()

    def test_user_prompt_includes_company_names(self):
        companies = [
            self._make_company(name="Alpha Inc"),
            self._make_company(name="Beta LLC"),
        ]
        prompt = build_comparison_prompt(companies)
        assert "Alpha Inc" in prompt
        assert "Beta LLC" in prompt

    def test_user_prompt_includes_scores(self):
        companies = [
            self._make_company(name="A", financial_health=4.5),
            self._make_company(name="B", financial_health=2.1),
        ]
        prompt = build_comparison_prompt(companies)
        assert "4.5" in prompt
        assert "2.1" in prompt

    def test_user_prompt_includes_all_companies_for_three(self):
        companies = [
            self._make_company(name="First"),
            self._make_company(name="Second"),
            self._make_company(name="Third"),
        ]
        prompt = build_comparison_prompt(companies)
        assert "First" in prompt
        assert "Second" in prompt
        assert "Third" in prompt
        assert "3 companies" in prompt
