"""Prompt template for generating an acquisition research brief.

Takes a company name and crawled web content, produces a sanitized
markdown acquisition brief not exceeding 50,000 characters.
"""

MAX_BRIEF_CHARS = 50_000


def build_research_brief_system_prompt() -> str:
    """Return the system prompt for research brief generation."""
    return (
        "You are an expert corporate banking analyst producing acquisition research briefs. "
        "Your output is used by Relationship Managers to evaluate potential corporate clients. "
        "Write in clear, professional markdown. Structure the brief with appropriate headings, "
        "bullet points, and tables where relevant.\n\n"
        "Rules:\n"
        "- Output MUST be sanitized markdown (no HTML script tags, no event handlers, "
        "no javascript: links)\n"
        "- Output MUST NOT exceed 50,000 characters\n"
        "- Include sections: Executive Summary, Company Overview, Business Model, "
        "Financial Profile, Market Position, Key Risks, Growth Indicators, "
        "Key Relationships & Partnerships\n"
        "- If information is unavailable, note it explicitly rather than fabricating data\n"
        "- Focus on facts relevant to banking acquisition decisions"
    )


def build_research_brief_prompt(company_name: str, crawled_content: str) -> str:
    """Build the user prompt for research brief generation.

    Args:
        company_name: Name of the company being researched.
        crawled_content: Concatenated text content from crawled web sources.

    Returns:
        Formatted prompt string ready to send to the LLM.
    """
    # Truncate crawled content to leave room for the prompt itself
    max_content_len = 80_000
    if len(crawled_content) > max_content_len:
        crawled_content = crawled_content[:max_content_len] + "\n\n[Content truncated]"

    return (
        f"Generate a comprehensive acquisition research brief for **{company_name}**.\n\n"
        f"Below is the crawled web content gathered from multiple sources about this company. "
        f"Synthesize this information into a well-structured markdown brief.\n\n"
        f"---\n\n"
        f"## Source Content\n\n"
        f"{crawled_content}\n\n"
        f"---\n\n"
        f"Generate the acquisition brief now. Remember: sanitized markdown only, "
        f"no more than {MAX_BRIEF_CHARS:,} characters."
    )
