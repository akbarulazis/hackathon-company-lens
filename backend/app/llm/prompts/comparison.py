"""Prompt template for generating side-by-side company comparisons.

Takes 2-3 company profiles and produces an HTML-formatted semantic
comparison covering key business attributes, financial metrics,
score dimensions, and a recommendation summary.
"""

from typing import Any


def build_comparison_system_prompt() -> str:
    """Return the system prompt for company comparison generation."""
    return (
        "You are an expert corporate banking analyst generating side-by-side company "
        "comparisons for relationship managers. Your output helps RMs decide which "
        "prospect to prioritize for acquisition.\n\n"
        "Output Requirements:\n"
        "- Generate the comparison as clean HTML (no markdown, no code fences)\n"
        "- Use a structured table layout comparing companies across dimensions\n"
        "- Include sections: Executive Summary, Key Metrics Comparison, "
        "Score Analysis, Strategic Fit, and Recommendation\n"
        "- Use semantic HTML: <h2>, <h3>, <table>, <p>, <ul>, <strong>\n"
        "- Do NOT include <html>, <head>, <body>, or <style> tags\n"
        "- Do NOT include script tags or event handler attributes\n"
        "- Keep the comparison concise but insightful (aim for 1500-3000 words)\n"
        "- Highlight the strongest candidate in the recommendation section\n"
    )


def build_comparison_prompt(companies: list[Any]) -> str:
    """Build the user prompt for comparing 2-3 companies.

    Args:
        companies: List of CompanyProfile instances (2-3 companies).

    Returns:
        Formatted prompt string with company data ready for LLM.
    """
    company_sections = []

    for i, company in enumerate(companies, 1):
        section = (
            f"### Company {i}: {company.name}\n"
            f"- Industry: {company.industry or 'Unknown'}\n"
            f"- Headquarters: {company.headquarters or 'Unknown'}\n"
            f"- Founded: {company.founded_year or 'Unknown'}\n"
            f"- Employees: {company.employee_count or 'Unknown'}\n"
            f"- Annual Revenue: {_format_revenue_for_prompt(company.annual_revenue)}\n"
            f"- Funding Total: {_format_revenue_for_prompt(company.funding_total)}\n"
            f"- Market Cap: {_format_revenue_for_prompt(company.market_cap)}\n"
            f"- Website: {company.company_website or 'N/A'}\n"
            f"- Ticker: {company.ticker or 'N/A'}\n\n"
            f"Scores (1.0-5.0 scale):\n"
            f"- Financial Health: {_score_str(company.financial_health)}\n"
            f"- Business Risk: {_score_str(company.business_risk)}\n"
            f"- Growth Potential: {_score_str(company.growth_potential)}\n"
            f"- Product Fit: {_score_str(company.product_fit)}\n"
            f"- Relationship Accessibility: {_score_str(company.relationship_accessibility)}\n"
            f"- Overall Score: {_score_str(company.overall_score)}\n"
        )

        # Include acquisition brief if available
        if company.acquisition_brief:
            # Truncate to keep prompt manageable and comparison fast
            brief = company.acquisition_brief[:2000]
            section += f"\nAcquisition Brief (excerpt):\n{brief}\n"

        company_sections.append(section)

    companies_text = "\n---\n\n".join(company_sections)

    return (
        f"Compare the following {len(companies)} companies side by side for "
        "a corporate banking relationship manager evaluating acquisition targets.\n\n"
        f"{companies_text}\n\n"
        "---\n\n"
        "Generate a comprehensive HTML comparison covering:\n"
        "1. Executive Summary (brief overview of each company)\n"
        "2. Key Metrics Comparison (table with financial and operational metrics)\n"
        "3. Score Analysis (analysis of score differences across all 5 dimensions)\n"
        "4. Strategic Fit (which company aligns best with typical banking products)\n"
        "5. Recommendation (which company to prioritize and why)\n"
    )


def _format_revenue_for_prompt(value: Any) -> str:
    """Format a revenue/monetary value for the prompt."""
    if value is None:
        return "N/A"
    try:
        num = float(value)
        if num >= 1_000_000_000:
            return f"${num / 1_000_000_000:.1f}B"
        elif num >= 1_000_000:
            return f"${num / 1_000_000:.1f}M"
        elif num >= 1_000:
            return f"${num / 1_000:.1f}K"
        else:
            return f"${num:,.0f}"
    except (TypeError, ValueError):
        return "N/A"


def _score_str(value: Any) -> str:
    """Format a score value for the prompt."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "N/A"
