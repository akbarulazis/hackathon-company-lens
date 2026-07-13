"""Comparison service layer.

Business logic for initiating and executing company comparisons.
Validates preconditions (company count, status, workspace ownership),
calls the LLM for semantic comparison, and implements a fallback
static HTML table on LLM failure.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.companies.models import CompanyProfile, CompanyStatus
from app.config import Settings
from app.llm.client import LLMClient, LLMClientError
from app.llm.prompts.comparison import (
    build_comparison_prompt,
    build_comparison_system_prompt,
)
from app.workspaces.models import ComparisonReport, Workspace, WorkspaceCompany

logger = logging.getLogger(__name__)


class ComparisonError(Exception):
    """Base comparison error with status code and message."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def initiate(
    session: AsyncSession,
    workspace_id: int,
    company_ids: list[int],
    user_id: int,
) -> ComparisonReport:
    """Validate preconditions and create a pending comparison report.

    Validates:
    - Exactly 2-3 company IDs (422 otherwise)
    - Workspace exists and is owned by user (404 otherwise)
    - All companies have status "ready" (409 with list of non-ready companies)

    Args:
        session: Async database session.
        workspace_id: ID of the workspace containing the companies.
        company_ids: List of 2-3 company IDs to compare.
        user_id: ID of the user initiating the comparison.

    Returns:
        The created ComparisonReport (with html_content=None initially).

    Raises:
        ComparisonError(422): If company_ids count is not 2 or 3.
        ComparisonError(404): If workspace not found or not owned by user.
        ComparisonError(409): If any company does not have status "ready".
    """
    # Validate company count (also enforced by schema, but defense-in-depth)
    if len(company_ids) < 2 or len(company_ids) > 3:
        raise ComparisonError(
            status_code=422,
            detail="Comparison requires exactly 2 or 3 companies",
        )

    # Validate workspace ownership
    result = await session.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.user_id == user_id,
        )
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise ComparisonError(
            status_code=404,
            detail="Workspace not found",
        )

    # Validate all companies exist, are in workspace, and have status "ready"
    result = await session.execute(
        select(CompanyProfile).where(CompanyProfile.id.in_(company_ids))
    )
    companies = list(result.scalars().all())

    # Check all companies exist
    found_ids = {c.id for c in companies}
    missing_ids = set(company_ids) - found_ids
    if missing_ids:
        raise ComparisonError(
            status_code=404,
            detail=f"Companies not found: {sorted(missing_ids)}",
        )

    # Check all companies are in the workspace
    result = await session.execute(
        select(WorkspaceCompany.company_id).where(
            WorkspaceCompany.workspace_id == workspace_id,
            WorkspaceCompany.company_id.in_(company_ids),
        )
    )
    workspace_company_ids = set(result.scalars().all())
    not_in_workspace = set(company_ids) - workspace_company_ids
    if not_in_workspace:
        raise ComparisonError(
            status_code=404,
            detail=f"Companies not in workspace: {sorted(not_in_workspace)}",
        )

    # Check all companies have status "ready"
    non_ready = [
        {"id": c.id, "name": c.name, "status": c.status.value}
        for c in companies
        if c.status != CompanyStatus.ready
    ]
    if non_ready:
        names = [f"{c['name']} (status: {c['status']})" for c in non_ready]
        raise ComparisonError(
            status_code=409,
            detail=f"Companies not ready for comparison: {', '.join(names)}",
        )

    # Create pending comparison report
    report = ComparisonReport(
        workspace_id=workspace_id,
        company_ids=company_ids,
        html_content=None,
        is_fallback=False,
    )
    session.add(report)
    await session.flush()

    return report


async def execute_comparison(
    session: AsyncSession,
    report_id: int,
    settings: Settings,
) -> ComparisonReport:
    """Execute the LLM comparison and persist the result.

    Loads the comparison report, fetches company data, invokes the LLM
    to generate a semantic comparison in HTML format, and persists the result.
    On LLM failure, generates a fallback static HTML table.

    Args:
        session: Async database session.
        report_id: ID of the ComparisonReport to populate.
        settings: Application settings (for LLM client).

    Returns:
        The updated ComparisonReport with html_content populated.
    """
    # Load the report
    result = await session.execute(
        select(ComparisonReport).where(ComparisonReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise ComparisonError(
            status_code=404,
            detail=f"Comparison report not found: id={report_id}",
        )

    # Load company data
    company_ids = report.company_ids
    result = await session.execute(
        select(CompanyProfile).where(CompanyProfile.id.in_(company_ids))
    )
    companies = list(result.scalars().all())

    # Sort companies in the same order as requested
    id_to_company = {c.id: c for c in companies}
    companies_ordered = [id_to_company[cid] for cid in company_ids if cid in id_to_company]

    # Attempt LLM comparison
    try:
        llm_client = LLMClient(settings)
        system_prompt = build_comparison_system_prompt()
        user_prompt = build_comparison_prompt(companies_ordered)

        html_content = await llm_client.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=8192,
        )

        report.html_content = html_content
        report.is_fallback = False

    except LLMClientError as e:
        logger.warning(
            "LLM comparison failed for report_id=%d, generating fallback: %s",
            report_id,
            e,
        )
        # Generate fallback static HTML table
        report.html_content = _generate_fallback_html(companies_ordered)
        report.is_fallback = True

    await session.flush()
    return report


def _generate_fallback_html(companies: list[Any]) -> str:
    """Generate a static HTML comparison table as fallback.

    Compares structured fields (name, industry, revenue, employees)
    and all five score dimensions for the given companies.

    Args:
        companies: List of CompanyProfile instances.

    Returns:
        HTML string with a comparison table.
    """
    # Build header row
    headers = ["Metric"] + [_escape_html(c.name) for c in companies]
    header_row = "".join(f"<th>{h}</th>" for h in headers)

    # Define rows to compare
    rows: list[tuple[str, list[str]]] = [
        ("Industry", [_escape_html(c.industry or "N/A") for c in companies]),
        ("Annual Revenue", [_format_revenue(c.annual_revenue) for c in companies]),
        ("Employee Count", [_format_number(c.employee_count) for c in companies]),
        ("Financial Health", [_format_score(c.financial_health) for c in companies]),
        ("Business Risk", [_format_score(c.business_risk) for c in companies]),
        ("Growth Potential", [_format_score(c.growth_potential) for c in companies]),
        ("Product Fit", [_format_score(c.product_fit) for c in companies]),
        (
            "Relationship Accessibility",
            [_format_score(c.relationship_accessibility) for c in companies],
        ),
        ("Overall Score", [_format_score(c.overall_score) for c in companies]),
    ]

    # Build table body
    body_rows = ""
    for label, values in rows:
        cells = f"<td><strong>{label}</strong></td>"
        cells += "".join(f"<td>{v}</td>" for v in values)
        body_rows += f"<tr>{cells}</tr>"

    return (
        '<div class="comparison-fallback">'
        "<h2>Company Comparison</h2>"
        "<p><em>AI-generated comparison unavailable. Showing structured data comparison.</em></p>"
        '<table class="comparison-table" border="1" cellpadding="8" cellspacing="0">'
        f"<thead><tr>{header_row}</tr></thead>"
        f"<tbody>{body_rows}</tbody>"
        "</table>"
        "</div>"
    )


def _escape_html(text: str) -> str:
    """Escape HTML special characters in a string."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _format_revenue(value: Any) -> str:
    """Format revenue as a readable string."""
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


def _format_number(value: Any) -> str:
    """Format a number with comma separators."""
    if value is None:
        return "N/A"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "N/A"


def _format_score(value: Any) -> str:
    """Format a score value to one decimal place."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.1f}/5.0"
    except (TypeError, ValueError):
        return "N/A"
