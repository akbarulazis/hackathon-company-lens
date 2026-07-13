"""Prompt template for scoring a company across five dimensions.

Takes an acquisition brief and produces:
- Numeric scores (1.0-5.0) with insights for 5 dimensions
- Revenue/profit projections if the bank acquires this company as a client
- Overall verdict with recommendation
"""

from pydantic import BaseModel, Field


class ScoreDimension(BaseModel):
    """A single score dimension with value and reasoning."""

    score: float = Field(ge=1.0, le=5.0, description="Score between 1.0 and 5.0")
    insight: str = Field(description="2-4 sentence explanation citing specific facts from the brief")


class RevenueProjection(BaseModel):
    """Projected revenue/profit if this company becomes a bank client."""

    estimated_loan_size: str = Field(description="Estimated lending facility size (e.g. 'IDR 500B - 1T')")
    estimated_annual_interest_income: str = Field(description="Estimated annual interest income to the bank")
    estimated_fee_income: str = Field(description="Estimated annual fee-based income (trade, cash mgmt, etc.)")
    estimated_total_annual_revenue: str = Field(description="Total estimated annual revenue to the bank")
    product_mix: str = Field(description="Recommended product mix: which bank products to offer and why")
    assumptions: str = Field(description="Key assumptions behind the estimates (interest rate, utilization, etc.)")
    payback_assessment: str = Field(description="How quickly the relationship pays back acquisition cost")


class ScoringOutput(BaseModel):
    """Structured output for the scoring LLM call."""

    financial_health: ScoreDimension = Field(
        description="Assessment of financial stability, revenue, profitability"
    )
    business_risk: ScoreDimension = Field(
        description="Assessment of operational, market, and regulatory risks (5=LOW risk)"
    )
    growth_potential: ScoreDimension = Field(
        description="Assessment of market opportunity, expansion potential, future banking wallet"
    )
    product_fit: ScoreDimension = Field(
        description="Assessment of fit with bank's product offerings (lending, trade, cash mgmt)"
    )
    relationship_accessibility: ScoreDimension = Field(
        description="Assessment of how winnable the relationship is"
    )
    overall_insight: str = Field(
        description="3-5 sentence verdict: pursue now / monitor / deprioritize, lead product, first thing to verify"
    )
    revenue_projection: RevenueProjection = Field(
        description="Estimated revenue/profit to the bank if this company is acquired as a client"
    )


def build_scoring_system_prompt() -> str:
    """Return the system prompt for company scoring."""
    return (
        "You are a senior corporate banking analyst scoring companies for acquisition "
        "potential. You evaluate companies across five dimensions on a scale of 1.0 to 5.0 "
        "AND project the revenue this company could generate for the bank as a client.\n\n"
        "Scoring Guidelines:\n"
        "- 1.0-2.0: Poor/High risk — significant concerns, likely not worth pursuing\n"
        "- 2.0-3.0: Below average — notable weaknesses, monitor only\n"
        "- 3.0-4.0: Good — solid opportunity with manageable risks\n"
        "- 4.0-5.0: Excellent — strong prospect, pursue actively\n\n"
        "Dimensions:\n"
        "- financial_health: Revenue stability, profitability, balance sheet strength, "
        "debt capacity, cash flow adequacy. Cite specific numbers.\n"
        "- business_risk: INVERTED scale (5 = LOW risk). Market concentration, "
        "regulatory exposure, competitive threats, litigation.\n"
        "- growth_potential: Future banking wallet — capex plans, expansion, "
        "new markets, M&A activity creating loan demand.\n"
        "- product_fit: Breadth of bank products needed (lending KI/KMK, trade finance, "
        "cash management, payroll, FX, SCF). More products = higher score.\n"
        "- relationship_accessibility: How winnable — existing bank relationships, "
        "whether locked into competitors, public procurement accessibility.\n\n"
        "Revenue Projection Rules:\n"
        "- Base estimates on the company's revenue, assets, and business model\n"
        "- For lending: assume 8-12% interest rate on working capital, 9-11% on investment loans\n"
        "- For trade finance: assume 0.5-1.5% fee on trade volume\n"
        "- For cash management: assume fee based on transaction volume and float\n"
        "- State all assumptions explicitly\n"
        "- Be conservative — use lower bound of ranges\n\n"
        "Each insight MUST cite specific facts/numbers from the brief. Generic insights are useless."
    )


def build_scoring_prompt(acquisition_brief: str) -> str:
    """Build the user prompt for company scoring."""
    return (
        "Based on the following acquisition research brief, provide:\n"
        "1. Scores (1.0-5.0) with evidence-based insights for all 5 dimensions\n"
        "2. An overall verdict (pursue/monitor/deprioritize) with recommended lead product\n"
        "3. Revenue projection: what this company could generate for the bank annually\n\n"
        "---\n\n"
        f"{acquisition_brief}\n\n"
        "---\n\n"
        "Score and project now."
    )
