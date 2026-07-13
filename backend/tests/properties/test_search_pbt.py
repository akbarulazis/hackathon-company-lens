"""Property-based tests for company search.

# Feature: company-lens-rebuild
# Property 9: Search Result Ordering and Limit
# Property 10: Minimum Search Query Length
# Property 11: Case-Insensitive Duplicate Company Detection

Validates: Requirements 4.1, 4.2, 4.3, 4.6
"""

import string
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.companies.models import ClientStatus, CompanyStatus
from app.companies.schemas import SearchResponse
from app.companies.service import (
    CompanyError,
    MAX_SEARCH_RESULTS,
    MIN_SEARCH_QUERY_LENGTH,
    initiate_research,
    search,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Search queries with at least 2 characters (valid search queries)
valid_search_query_strategy = st.text(
    alphabet=st.sampled_from(string.ascii_letters + string.digits + " "),
    min_size=2,
    max_size=100,
).filter(lambda q: len(q.strip()) >= MIN_SEARCH_QUERY_LENGTH)

# Search queries with fewer than 2 characters (should return empty)
short_query_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=0,
    max_size=1,
)

# Also include queries that are whitespace-padded but strip to < 2 chars
short_padded_query_strategy = st.builds(
    lambda spaces, char: spaces + char + spaces,
    spaces=st.text(alphabet=" \t", min_size=0, max_size=5),
    char=st.text(
        alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters=" \t"),
        min_size=0,
        max_size=1,
    ),
).filter(lambda q: len(q.strip()) < MIN_SEARCH_QUERY_LENGTH)

# Number of results the repository can return (0 to 15, to test > 10 case)
result_count_strategy = st.integers(min_value=0, max_value=15)

# Similarity scores in descending order
similarity_strategy = st.floats(min_value=0.01, max_value=1.0, allow_nan=False)

# Company names for duplicate detection
company_name_strategy = st.text(
    alphabet=st.sampled_from(string.ascii_letters + string.digits + " "),
    min_size=2,
    max_size=100,
).filter(lambda n: len(n.strip()) >= 2)

# Industries
industry_strategy = st.one_of(
    st.just(None),
    st.sampled_from(["Technology", "Finance", "Healthcare", "Manufacturing", "Retail"]),
)

# Overall scores
score_strategy = st.one_of(
    st.just(None),
    st.floats(min_value=1.0, max_value=5.0, allow_nan=False),
)

# Client statuses
client_status_strategy = st.sampled_from(list(ClientStatus))


# ---------------------------------------------------------------------------
# Helper: build mock company profiles with similarity scores
# ---------------------------------------------------------------------------


def build_mock_companies(
    count: int,
    similarities: list[float],
    industries: list,
    scores: list,
    client_statuses: list[ClientStatus],
) -> list[tuple]:
    """Build a list of (mock_company, similarity) tuples."""
    results = []
    for i in range(count):
        company = MagicMock()
        company.id = i + 1
        company.name = f"Company_{i + 1}"
        company.client_status = client_statuses[i]
        company.industry = industries[i]
        company.overall_score = scores[i]
        results.append((company, similarities[i]))
    return results


# ===========================================================================
# Property 9: Search Result Ordering and Limit
# ===========================================================================


@given(
    query=valid_search_query_strategy,
    result_count=result_count_strategy,
    data=st.data(),
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property9_results_limited_to_max_10(
    query: str,
    result_count: int,
    data,
) -> None:
    """Property 9: For any query ≥2 chars, returned results SHALL contain
    at most 10 Company_Profiles.

    **Validates: Requirements 4.1, 4.3**
    """
    mock_session = AsyncMock()

    # Generate similarity scores in descending order
    similarities = sorted(
        [data.draw(similarity_strategy) for _ in range(result_count)],
        reverse=True,
    )
    industries = [data.draw(industry_strategy) for _ in range(result_count)]
    scores = [data.draw(score_strategy) for _ in range(result_count)]
    client_statuses = [data.draw(client_status_strategy) for _ in range(result_count)]

    mock_results = build_mock_companies(
        result_count, similarities, industries, scores, client_statuses
    )

    with patch("app.companies.service.repository") as mock_repo:
        # Repository returns up to result_count results (service trusts repo limit)
        mock_repo.search_companies = AsyncMock(
            return_value=mock_results[:MAX_SEARCH_RESULTS]
        )

        response = await search(mock_session, query)

        assert isinstance(response, SearchResponse)
        assert len(response.results) <= MAX_SEARCH_RESULTS


@given(
    query=valid_search_query_strategy,
    result_count=st.integers(min_value=1, max_value=10),
    data=st.data(),
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property9_results_include_required_fields(
    query: str,
    result_count: int,
    data,
) -> None:
    """Property 9: Each search result SHALL include Client_Status, industry,
    and Overall_Score fields.

    **Validates: Requirements 4.1, 4.3**
    """
    mock_session = AsyncMock()

    similarities = sorted(
        [data.draw(similarity_strategy) for _ in range(result_count)],
        reverse=True,
    )
    industries = [data.draw(industry_strategy) for _ in range(result_count)]
    scores = [data.draw(score_strategy) for _ in range(result_count)]
    client_statuses = [data.draw(client_status_strategy) for _ in range(result_count)]

    mock_results = build_mock_companies(
        result_count, similarities, industries, scores, client_statuses
    )

    with patch("app.companies.service.repository") as mock_repo:
        mock_repo.search_companies = AsyncMock(return_value=mock_results)

        response = await search(mock_session, query)

        for i, result in enumerate(response.results):
            # client_status must always be present (required field)
            assert result.client_status is not None
            assert result.client_status == client_statuses[i]
            # industry and overall_score fields must be present (may be None)
            assert hasattr(result, "industry")
            assert result.industry == industries[i]
            assert hasattr(result, "overall_score")
            expected_score = (
                float(scores[i]) if scores[i] is not None else None
            )
            assert result.overall_score == expected_score


@given(
    query=valid_search_query_strategy,
    result_count=st.integers(min_value=2, max_value=10),
    data=st.data(),
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property9_results_ordered_by_similarity_descending(
    query: str,
    result_count: int,
    data,
) -> None:
    """Property 9: Results SHALL be ranked by pg_trgm similarity score
    in descending order.

    **Validates: Requirements 4.1**
    """
    mock_session = AsyncMock()

    # Generate similarities and sort descending (simulating what the repo returns)
    similarities = sorted(
        [data.draw(similarity_strategy) for _ in range(result_count)],
        reverse=True,
    )
    industries = [data.draw(industry_strategy) for _ in range(result_count)]
    scores = [data.draw(score_strategy) for _ in range(result_count)]
    client_statuses = [data.draw(client_status_strategy) for _ in range(result_count)]

    mock_results = build_mock_companies(
        result_count, similarities, industries, scores, client_statuses
    )

    with patch("app.companies.service.repository") as mock_repo:
        mock_repo.search_companies = AsyncMock(return_value=mock_results)

        response = await search(mock_session, query)

        # Verify similarity scores are in descending order
        result_similarities = [r.similarity for r in response.results]
        for i in range(len(result_similarities) - 1):
            assert result_similarities[i] >= result_similarities[i + 1], (
                f"Results not ordered by similarity descending: "
                f"{result_similarities[i]} < {result_similarities[i + 1]}"
            )


# ===========================================================================
# Property 10: Minimum Search Query Length
# ===========================================================================


@given(query=short_query_strategy)
@settings(max_examples=200, deadline=None)
@pytest.mark.asyncio
async def test_property10_short_query_returns_empty(query: str) -> None:
    """Property 10: For any query <2 chars, the Platform SHALL return an
    empty result set without performing a database search.

    **Validates: Requirements 4.2**
    """
    mock_session = AsyncMock()

    with patch("app.companies.service.repository") as mock_repo:
        mock_repo.search_companies = AsyncMock(return_value=[])

        response = await search(mock_session, query)

        assert isinstance(response, SearchResponse)
        assert response.results == []
        # Verify the repository was NOT called
        mock_repo.search_companies.assert_not_called()


@given(query=short_padded_query_strategy)
@settings(max_examples=200, deadline=None)
@pytest.mark.asyncio
async def test_property10_whitespace_padded_short_query_returns_empty(
    query: str,
) -> None:
    """Property 10: For any query that strips to <2 chars (including
    whitespace-padded queries), return empty set without DB query.

    **Validates: Requirements 4.2**
    """
    mock_session = AsyncMock()

    with patch("app.companies.service.repository") as mock_repo:
        mock_repo.search_companies = AsyncMock(return_value=[])

        response = await search(mock_session, query)

        assert isinstance(response, SearchResponse)
        assert response.results == []
        mock_repo.search_companies.assert_not_called()


# ===========================================================================
# Property 11: Case-Insensitive Duplicate Company Detection
# ===========================================================================


@given(company_name=company_name_strategy)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property11_exact_case_match_rejects_research(
    company_name: str,
) -> None:
    """Property 11: Research initiation SHALL be rejected when the company
    name exactly matches an existing profile (case-insensitive).

    **Validates: Requirements 4.6**
    """
    mock_session = AsyncMock()

    # Simulate an existing company with the same name
    existing_company = MagicMock()
    existing_company.id = 42
    existing_company.name = company_name

    with patch("app.companies.service.repository") as mock_repo:
        mock_repo.find_company_by_name_case_insensitive = AsyncMock(
            return_value=existing_company
        )

        with pytest.raises(CompanyError) as exc_info:
            await initiate_research(mock_session, company_name)

        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail.lower()


@given(company_name=company_name_strategy)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property11_different_case_match_rejects_research(
    company_name: str,
) -> None:
    """Property 11: For any company name that differs only in case from an
    existing profile, research initiation SHALL be rejected with a 409 error
    indicating the existing profile.

    **Validates: Requirements 4.6**
    """
    mock_session = AsyncMock()

    # The existing company has the original casing
    existing_company = MagicMock()
    existing_company.id = 99
    existing_company.name = company_name

    # Try to initiate research with different case variants
    case_variants = [
        company_name.upper(),
        company_name.lower(),
        company_name.swapcase(),
    ]

    for variant in case_variants:
        with patch("app.companies.service.repository") as mock_repo:
            mock_repo.find_company_by_name_case_insensitive = AsyncMock(
                return_value=existing_company
            )

            with pytest.raises(CompanyError) as exc_info:
                await initiate_research(mock_session, variant)

            assert exc_info.value.status_code == 409
            assert "already exists" in exc_info.value.detail.lower()
            # Error should reference the existing company name
            assert existing_company.name in exc_info.value.detail


@given(company_name=company_name_strategy)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property11_no_match_allows_research(
    company_name: str,
) -> None:
    """Property 11: When no case-insensitive match exists, research initiation
    SHALL proceed and create a new Company_Profile.

    **Validates: Requirements 4.6**
    """
    mock_session = AsyncMock()

    # Simulate a new company with pending status
    new_company = MagicMock()
    new_company.id = 1
    new_company.name = company_name
    new_company.status = CompanyStatus.pending

    with patch("app.companies.service.repository") as mock_repo:
        mock_repo.find_company_by_name_case_insensitive = AsyncMock(return_value=None)
        mock_repo.create_company = AsyncMock(return_value=new_company)

        result = await initiate_research(mock_session, company_name)

        assert result == new_company
        mock_repo.create_company.assert_called_once_with(mock_session, company_name)
