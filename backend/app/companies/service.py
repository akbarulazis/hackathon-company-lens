"""Company service layer.

Business logic for company search, detail retrieval, duplicate checking,
and research initiation. Enforces search constraints (min 2 chars, max 10 results)
and case-insensitive duplicate prevention.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.companies import repository
from app.companies.models import CompanyProfile
from app.companies.schemas import (
    CompanyDetailResponse,
    DuplicateCheckResult,
    SearchResponse,
    SearchResult,
)

# Search constraints
MIN_SEARCH_QUERY_LENGTH = 2
MAX_SEARCH_RESULTS = 10


class CompanyError(Exception):
    """Base company error with status code and detail message."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def search(session: AsyncSession, query: str) -> SearchResponse:
    """Search companies by name with fuzzy and prefix matching.

    Returns an empty result set without performing a database search
    if the query is fewer than 2 characters. Sets can_research=True
    when no matches are found.

    Args:
        session: Async database session.
        query: Search query string.

    Returns:
        SearchResponse with results (max 10) and can_research flag.
    """
    # Strip whitespace for length check
    cleaned_query = query.strip()

    # Return empty result set without DB query if query < 2 chars
    if len(cleaned_query) < MIN_SEARCH_QUERY_LENGTH:
        return SearchResponse(results=[], can_research=False, query=cleaned_query)

    # Perform fuzzy search with pg_trgm + prefix matching
    results = await repository.search_companies(
        session, cleaned_query, limit=MAX_SEARCH_RESULTS
    )

    # Build search result items with required fields
    search_results = [
        SearchResult(
            id=company.id,
            name=company.name,
            client_status=company.client_status,
            industry=company.industry,
            overall_score=float(company.overall_score) if company.overall_score is not None else None,
            similarity=similarity,
        )
        for company, similarity in results
    ]

    # Set can_research flag when no matches found
    can_research = len(search_results) == 0

    return SearchResponse(
        results=search_results,
        can_research=can_research,
        query=cleaned_query,
    )


async def get_company_detail(
    session: AsyncSession, company_id: int
) -> CompanyDetailResponse:
    """Get full company profile detail by ID.

    Args:
        session: Async database session.
        company_id: Company primary key ID.

    Returns:
        CompanyDetailResponse with full profile data.

    Raises:
        CompanyError(404): If company not found.
    """
    company = await repository.get_company_by_id(session, company_id)
    if not company:
        raise CompanyError(status_code=404, detail="Company not found")

    return CompanyDetailResponse.model_validate(company)


async def check_duplicate(session: AsyncSession, company_name: str) -> DuplicateCheckResult:
    """Perform case-insensitive duplicate check for a company name.

    Args:
        session: Async database session.
        company_name: The company name to check.

    Returns:
        DuplicateCheckResult indicating whether a match exists.
    """
    existing = await repository.find_company_by_name_case_insensitive(
        session, company_name
    )

    if existing:
        return DuplicateCheckResult(
            is_duplicate=True,
            existing_company_id=existing.id,
            existing_company_name=existing.name,
        )

    return DuplicateCheckResult(is_duplicate=False)


async def initiate_research(
    session: AsyncSession, company_name: str
) -> CompanyProfile:
    """Initiate research for a new company.

    Performs a case-insensitive name match against existing profiles.
    If a match is found, rejects the request with an error indicating
    the existing profile rather than creating a duplicate.

    Args:
        session: Async database session.
        company_name: Name of the company to research.

    Returns:
        The newly created CompanyProfile (with pending status).

    Raises:
        CompanyError(409): If a company with the same name already exists
            (case-insensitive match).
    """
    # Case-insensitive duplicate check
    existing = await repository.find_company_by_name_case_insensitive(
        session, company_name
    )

    if existing:
        raise CompanyError(
            status_code=409,
            detail=f"Company '{existing.name}' already exists (id={existing.id}). "
            f"Cannot initiate duplicate research.",
        )

    # Create new company profile with pending status
    company = await repository.create_company(session, company_name)
    return company
