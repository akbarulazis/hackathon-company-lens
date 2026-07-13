"""Prompt template for extracting structured financial fields from an acquisition brief.

Extracts: founded_year, headquarters, employee_count, annual_revenue,
funding_total, market_cap, company_website, linkedin_url, ticker, industry.
"""

from pydantic import BaseModel, Field


class ExtractionOutput(BaseModel):
    """Structured output for financial field extraction.

    All fields are optional since not all information may be available
    in the source content.
    """

    founded_year: int | None = Field(
        default=None, description="Year the company was founded (e.g. 2015)"
    )
    headquarters: str | None = Field(
        default=None, description="City and country of headquarters (e.g. 'Jakarta, Indonesia')"
    )
    employee_count: int | None = Field(
        default=None, description="Approximate number of employees"
    )
    annual_revenue: str | None = Field(
        default=None,
        description="Annual revenue as a string with currency (e.g. '$50M', 'IDR 1.2T')",
    )
    funding_total: str | None = Field(
        default=None,
        description="Total funding raised as a string with currency (e.g. '$120M')",
    )
    market_cap: str | None = Field(
        default=None,
        description="Market capitalization as a string with currency (e.g. '$2.5B')",
    )
    company_website: str | None = Field(
        default=None, description="Official company website URL"
    )
    linkedin_url: str | None = Field(
        default=None, description="LinkedIn company page URL"
    )
    ticker: str | None = Field(
        default=None, description="Stock ticker symbol (e.g. 'BBCA.JK', 'AAPL')"
    )
    industry: str | None = Field(
        default=None,
        description="Primary industry classification (e.g. 'Financial Services', 'Technology')",
    )


def build_extraction_system_prompt() -> str:
    """Return the system prompt for financial field extraction."""
    return (
        "You are a precise data extraction assistant. Your job is to extract "
        "structured financial and company profile fields from research text.\n\n"
        "Rules:\n"
        "- Extract only information explicitly stated in the text\n"
        "- Use null for any field where information is not available or unclear\n"
        "- For revenue/funding/market_cap: include currency symbol and magnitude "
        "(e.g. '$50M', 'IDR 1.2T')\n"
        "- For founded_year: extract only the 4-digit year as an integer\n"
        "- For employee_count: extract approximate headcount as an integer\n"
        "- For URLs: include full URL with https:// prefix\n"
        "- Do NOT fabricate or estimate values — only extract what is clearly stated"
    )


def build_extraction_prompt(acquisition_brief: str) -> str:
    """Build the user prompt for financial field extraction.

    Args:
        acquisition_brief: The generated acquisition brief markdown text.

    Returns:
        Formatted prompt string ready to send to the LLM.
    """
    return (
        "Extract the following structured fields from this acquisition research brief. "
        "Return null for any field where the information is not clearly stated.\n\n"
        "Fields to extract:\n"
        "- founded_year (integer)\n"
        "- headquarters (city, country)\n"
        "- employee_count (integer)\n"
        "- annual_revenue (string with currency)\n"
        "- funding_total (string with currency)\n"
        "- market_cap (string with currency)\n"
        "- company_website (URL)\n"
        "- linkedin_url (URL)\n"
        "- ticker (stock symbol)\n"
        "- industry (classification)\n\n"
        "---\n\n"
        f"{acquisition_brief}\n\n"
        "---\n\n"
        "Extract the fields now."
    )
