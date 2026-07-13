"""Portfolio repository with CRUD for snapshots and suggestion queue.

Provides database operations for PortfolioSnapshot (get by company_id,
get latest, get history) and PortfolioSuggestion (list pending, resolve).
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.companies.models import CompanyProfile
from app.portfolio.models import PortfolioSnapshot, PortfolioSuggestion


async def get_latest_snapshot(
    session: AsyncSession, company_id: int
) -> PortfolioSnapshot | None:
    """Get the most recent portfolio snapshot for a company.

    Args:
        session: Async database session.
        company_id: The company's ID.

    Returns:
        The latest PortfolioSnapshot or None if no snapshots exist.
    """
    stmt = (
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.company_id == company_id)
        .order_by(PortfolioSnapshot.as_of_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_snapshot_history(
    session: AsyncSession, company_id: int
) -> list[PortfolioSnapshot]:
    """Get all portfolio snapshots for a company, ordered by date descending.

    Args:
        session: Async database session.
        company_id: The company's ID.

    Returns:
        List of PortfolioSnapshot records ordered newest first.
    """
    stmt = (
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.company_id == company_id)
        .order_by(PortfolioSnapshot.as_of_date.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_company_by_id(
    session: AsyncSession, company_id: int
) -> CompanyProfile | None:
    """Get a company by ID.

    Args:
        session: Async database session.
        company_id: The company's ID.

    Returns:
        CompanyProfile or None.
    """
    stmt = select(CompanyProfile).where(CompanyProfile.id == company_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_pending_suggestions(
    session: AsyncSession,
) -> list[PortfolioSuggestion]:
    """List all pending portfolio suggestions for manual resolution.

    Returns suggestions ordered by creation date descending (newest first).

    Args:
        session: Async database session.

    Returns:
        List of pending PortfolioSuggestion records.
    """
    stmt = (
        select(PortfolioSuggestion)
        .where(PortfolioSuggestion.status == "pending")
        .order_by(PortfolioSuggestion.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_suggestion_by_id(
    session: AsyncSession, suggestion_id: int
) -> PortfolioSuggestion | None:
    """Get a single suggestion by ID.

    Args:
        session: Async database session.
        suggestion_id: The suggestion's ID.

    Returns:
        PortfolioSuggestion or None.
    """
    stmt = select(PortfolioSuggestion).where(PortfolioSuggestion.id == suggestion_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def resolve_suggestion(
    session: AsyncSession,
    suggestion_id: int,
    resolution: str,
    company_id: int | None = None,
) -> PortfolioSuggestion | None:
    """Resolve a pending suggestion (accept or reject).

    If accepted with a company_id, links the suggestion to that company.
    Updates the status to 'accepted' or 'rejected'.

    Args:
        session: Async database session.
        suggestion_id: The suggestion's ID.
        resolution: Either 'accepted' or 'rejected'.
        company_id: The company to link to (required for 'accepted').

    Returns:
        Updated PortfolioSuggestion or None if not found.
    """
    suggestion = await get_suggestion_by_id(session, suggestion_id)
    if suggestion is None:
        return None

    if suggestion.status != "pending":
        return suggestion

    suggestion.status = resolution
    if company_id is not None:
        suggestion.matched_company_id = company_id

    session.add(suggestion)
    await session.flush()
    return suggestion
