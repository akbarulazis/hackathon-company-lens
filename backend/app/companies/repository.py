"""Company repository layer.

Database operations for company search (pg_trgm fuzzy + prefix matching),
company retrieval, and case-insensitive duplicate checking.
No business logic — only data access via SQLAlchemy async sessions.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.companies.models import CompanyProfile


async def search_companies(
    session: AsyncSession,
    query: str,
    limit: int = 10,
) -> list[tuple[CompanyProfile, float]]:
    """Search companies using pg_trgm similarity combined with prefix matching.

    Uses the similarity() function from pg_trgm for fuzzy matching,
    combined with ILIKE prefix matching for typeahead support.
    Results are ranked by similarity score descending.

    Args:
        session: Async database session.
        query: Search query string (must be at least 2 chars).
        limit: Maximum number of results to return (default 10).

    Returns:
        List of tuples (CompanyProfile, similarity_score) ordered by
        similarity descending.
    """
    # pg_trgm similarity score
    similarity_score = func.similarity(
        CompanyProfile.name, query
    ).label("similarity")

    # Combine fuzzy matching (similarity > 0) with prefix matching (ILIKE)
    prefix_pattern = f"{query}%"
    stmt = (
        select(CompanyProfile, similarity_score)
        .where(
            or_(
                func.similarity(CompanyProfile.name, query) > 0,
                CompanyProfile.name.ilike(prefix_pattern),
            )
        )
        .order_by(similarity_score.desc())
        .limit(limit)
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [(row[0], float(row[1])) for row in rows]


async def get_company_by_id(
    session: AsyncSession, company_id: int
) -> CompanyProfile | None:
    """Fetch a company profile by primary key ID."""
    result = await session.execute(
        select(CompanyProfile).where(CompanyProfile.id == company_id)
    )
    return result.scalar_one_or_none()


async def find_company_by_name_case_insensitive(
    session: AsyncSession, name: str
) -> CompanyProfile | None:
    """Find an existing company by case-insensitive exact name match.

    Used for duplicate checking before research initiation.

    Args:
        session: Async database session.
        name: Company name to check (compared case-insensitively).

    Returns:
        The existing CompanyProfile if a match is found, None otherwise.
    """
    result = await session.execute(
        select(CompanyProfile).where(
            func.lower(CompanyProfile.name) == func.lower(name)
        )
    )
    return result.scalar_one_or_none()


async def create_company(
    session: AsyncSession,
    name: str,
) -> CompanyProfile:
    """Create a new company profile with pending status.

    Args:
        session: Async database session.
        name: Company name.

    Returns:
        The created CompanyProfile instance.
    """
    company = CompanyProfile(name=name)
    session.add(company)
    await session.flush()
    return company
