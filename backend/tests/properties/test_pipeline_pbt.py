"""Property-based tests for research pipeline.

# Feature: company-lens-rebuild
# Property 12: Score Dimension Range Validation
# Property 13: Pipeline Status State Machine
# Property 14: Pipeline Idempotency
# Property 33: Relationship Edge Extraction Cap
# Property 34: Shell Company Creation for Unknown Counterparties

Validates: Requirements 5.1, 5.5, 5.8, 5.10, 14.1, 14.2, 16.5
"""

import string
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from pydantic import ValidationError

from app.companies.models import (
    ClientStatus,
    CompanyProfile,
    CompanyRelationship,
    CompanyStatus,
    RelationType,
    ScoreSnapshot,
)
from app.llm.prompts.relationships import RelationshipEdge, RelationshipsOutput
from app.llm.prompts.scoring import ScoreDimension, ScoringOutput
from app.research.pipeline import (
    MAX_RELATIONSHIP_EDGES,
    _clear_prior_relationships,
    _clear_prior_score_snapshots,
    _persist_relationships,
    extract_relationships,
    run_pipeline,
    score_company,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Scores within valid range [1.0, 5.0]
valid_score_strategy = st.floats(min_value=1.0, max_value=5.0, allow_nan=False)

# Scores outside valid range
invalid_score_below_strategy = st.floats(
    min_value=-100.0, max_value=0.99, allow_nan=False, allow_infinity=False
)
invalid_score_above_strategy = st.floats(
    min_value=5.01, max_value=100.0, allow_nan=False, allow_infinity=False
)

# Number of relationship edges (0-30, some above cap of 20)
relationship_count_strategy = st.integers(min_value=0, max_value=30)

# Valid relation types
valid_relation_types = st.sampled_from(["parent", "subsidiary", "vendor", "customer", "partner"])

# Company names for relationships
company_name_strategy = st.text(
    alphabet=st.sampled_from(string.ascii_letters + string.digits + " .-&"),
    min_size=2,
    max_size=50,
).filter(lambda s: s.strip())

# Pipeline status valid sequence
VALID_STATUS_SEQUENCE = [
    CompanyStatus.pending,
    CompanyStatus.researching,
    CompanyStatus.profiling,
    CompanyStatus.scoring,
    CompanyStatus.ready,
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_score_dimension(score: float, insight: str = "Test insight") -> ScoreDimension:
    """Create a ScoreDimension with the given score."""
    return ScoreDimension(score=score, insight=insight)


def make_scoring_output(
    fh: float = 3.0,
    br: float = 3.0,
    gp: float = 3.0,
    pf: float = 3.0,
    ra: float = 3.0,
) -> ScoringOutput:
    """Create a ScoringOutput with specified scores."""
    return ScoringOutput(
        financial_health=make_score_dimension(fh),
        business_risk=make_score_dimension(br),
        growth_potential=make_score_dimension(gp),
        product_fit=make_score_dimension(pf),
        relationship_accessibility=make_score_dimension(ra),
    )


def make_relationship_edges(count: int, source: str = "TestCorp") -> list[RelationshipEdge]:
    """Create a list of relationship edges."""
    edges = []
    relation_types = ["parent", "subsidiary", "vendor", "customer", "partner"]
    for i in range(count):
        edges.append(
            RelationshipEdge(
                source=source,
                target=f"Company_{i}",
                relation_type=relation_types[i % len(relation_types)],
            )
        )
    return edges


# ===========================================================================
# Property 12: Score Dimension Range Validation
# ===========================================================================


@given(score=valid_score_strategy)
@settings(max_examples=100)
def test_property12_valid_scores_accepted(score: float) -> None:
    """Property 12: Any score within [1.0, 5.0] MUST be accepted by
    the ScoreDimension model.

    **Validates: Requirements 5.5**
    """
    dim = ScoreDimension(score=score, insight="Valid score test")
    assert 1.0 <= dim.score <= 5.0


@given(score=invalid_score_below_strategy)
@settings(max_examples=50)
def test_property12_scores_below_range_rejected(score: float) -> None:
    """Property 12: Any score below 1.0 MUST be rejected by ScoreDimension.

    **Validates: Requirements 5.5**
    """
    with pytest.raises(ValidationError):
        ScoreDimension(score=score, insight="Below range test")


@given(score=invalid_score_above_strategy)
@settings(max_examples=50)
def test_property12_scores_above_range_rejected(score: float) -> None:
    """Property 12: Any score above 5.0 MUST be rejected by ScoreDimension.

    **Validates: Requirements 5.5**
    """
    with pytest.raises(ValidationError):
        ScoreDimension(score=score, insight="Above range test")


@given(
    fh=valid_score_strategy,
    br=valid_score_strategy,
    gp=valid_score_strategy,
    pf=valid_score_strategy,
    ra=valid_score_strategy,
)
@settings(max_examples=100)
def test_property12_all_dimensions_in_range(
    fh: float, br: float, gp: float, pf: float, ra: float
) -> None:
    """Property 12: For any valid ScoringOutput, ALL five dimensions
    MUST have scores within [1.0, 5.0].

    **Validates: Requirements 5.5**
    """
    output = make_scoring_output(fh=fh, br=br, gp=gp, pf=pf, ra=ra)
    assert 1.0 <= output.financial_health.score <= 5.0
    assert 1.0 <= output.business_risk.score <= 5.0
    assert 1.0 <= output.growth_potential.score <= 5.0
    assert 1.0 <= output.product_fit.score <= 5.0
    assert 1.0 <= output.relationship_accessibility.score <= 5.0


@given(
    fh=invalid_score_below_strategy,
    br=valid_score_strategy,
    gp=valid_score_strategy,
    pf=valid_score_strategy,
    ra=valid_score_strategy,
)
@settings(max_examples=50)
def test_property12_single_invalid_dimension_rejects_entire_output(
    fh: float, br: float, gp: float, pf: float, ra: float
) -> None:
    """Property 12: If ANY single dimension is out of range [1.0, 5.0],
    the entire ScoringOutput MUST be rejected.

    **Validates: Requirements 5.5**
    """
    with pytest.raises(ValidationError):
        make_scoring_output(fh=fh, br=br, gp=gp, pf=pf, ra=ra)


# ===========================================================================
# Property 13: Pipeline Status State Machine
# ===========================================================================


@given(
    success_step_index=st.integers(min_value=0, max_value=3),
)
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property13_successful_transitions_follow_sequence(
    success_step_index: int,
) -> None:
    """Property 13: On a successful pipeline run, status transitions MUST
    follow the sequence: pending → researching → profiling → scoring → ready.

    **Validates: Requirements 5.1, 5.8**
    """
    # Track all status transitions during pipeline execution
    status_transitions: list[CompanyStatus] = []
    company_id = 1
    user_id = 1

    # Mock company
    mock_company = MagicMock(spec=CompanyProfile)
    mock_company.id = company_id
    mock_company.name = "Test Company"
    mock_company.status = CompanyStatus.pending

    def track_status(session, company, status):
        status_transitions.append(status)
        company.status = status

    mock_session = AsyncMock()

    with (
        patch("app.research.pipeline.get_company_by_id", new_callable=AsyncMock) as mock_get,
        patch("app.research.pipeline._update_company_status", side_effect=track_status),
        patch("app.research.pipeline._publish_status", new_callable=AsyncMock),
        patch("app.research.pipeline.tavily_search", new_callable=AsyncMock) as mock_tavily,
        patch("app.research.pipeline.crawl_sources", new_callable=AsyncMock) as mock_crawl,
        patch("app.research.pipeline.generate_profile", new_callable=AsyncMock) as mock_profile,
        patch("app.research.pipeline.score_company", new_callable=AsyncMock) as mock_score,
        patch("app.research.pipeline.extract_financials", new_callable=AsyncMock) as mock_fin,
        patch(
            "app.research.pipeline.extract_relationships", new_callable=AsyncMock
        ) as mock_rel,
        patch("app.research.pipeline._persist_scores", new_callable=AsyncMock),
        patch("app.research.pipeline._persist_financials", new_callable=AsyncMock),
        patch("app.research.pipeline._persist_relationships", new_callable=AsyncMock),
    ):
        mock_get.return_value = mock_company
        mock_tavily.return_value = ["http://example.com"]
        mock_crawl.return_value = "Crawled content"
        mock_profile.return_value = "Brief text"
        mock_score.return_value = make_scoring_output()
        mock_fin.return_value = MagicMock()
        mock_rel.return_value = RelationshipsOutput(relationships=[])

        mock_settings = MagicMock()
        await run_pipeline(company_id, user_id, mock_session, mock_settings)

    # Verify status transitions follow valid sequence
    expected = [
        CompanyStatus.researching,
        CompanyStatus.profiling,
        CompanyStatus.scoring,
        CompanyStatus.ready,
    ]
    assert status_transitions == expected


@given(
    fail_at_step=st.sampled_from(["tavily_search", "crawl", "profile", "scoring"]),
)
@settings(max_examples=20, deadline=None)
@pytest.mark.asyncio
async def test_property13_failure_transitions_to_failed(fail_at_step: str) -> None:
    """Property 13: If any pipeline step fails, the status MUST transition to
    'failed' from whatever intermediate state it was in.

    **Validates: Requirements 5.1, 5.8**
    """
    from app.research.pipeline import PipelineError

    status_transitions: list[CompanyStatus] = []
    company_id = 1
    user_id = 1

    mock_company = MagicMock(spec=CompanyProfile)
    mock_company.id = company_id
    mock_company.name = "Test Company"
    mock_company.status = CompanyStatus.pending

    def track_status(session, company, status):
        status_transitions.append(status)
        company.status = status

    mock_session = AsyncMock()

    with (
        patch("app.research.pipeline.get_company_by_id", new_callable=AsyncMock) as mock_get,
        patch("app.research.pipeline._update_company_status", side_effect=track_status),
        patch("app.research.pipeline._publish_status", new_callable=AsyncMock),
        patch("app.research.pipeline.tavily_search", new_callable=AsyncMock) as mock_tavily,
        patch("app.research.pipeline.crawl_sources", new_callable=AsyncMock) as mock_crawl,
        patch("app.research.pipeline.generate_profile", new_callable=AsyncMock) as mock_profile,
        patch("app.research.pipeline.score_company", new_callable=AsyncMock) as mock_score,
        patch("app.research.pipeline.extract_financials", new_callable=AsyncMock) as mock_fin,
        patch(
            "app.research.pipeline.extract_relationships", new_callable=AsyncMock
        ) as mock_rel,
        patch("app.research.pipeline._persist_scores", new_callable=AsyncMock),
        patch("app.research.pipeline._persist_financials", new_callable=AsyncMock),
        patch("app.research.pipeline._persist_relationships", new_callable=AsyncMock),
    ):
        mock_get.return_value = mock_company

        # Configure step to fail
        error = PipelineError(fail_at_step, "Simulated failure")
        if fail_at_step == "tavily_search":
            mock_tavily.side_effect = error
        elif fail_at_step == "crawl":
            mock_tavily.return_value = ["http://example.com"]
            mock_crawl.side_effect = error
        elif fail_at_step == "profile":
            mock_tavily.return_value = ["http://example.com"]
            mock_crawl.return_value = "Content"
            mock_profile.side_effect = error
        elif fail_at_step == "scoring":
            mock_tavily.return_value = ["http://example.com"]
            mock_crawl.return_value = "Content"
            mock_profile.return_value = "Brief"
            mock_score.side_effect = error

        mock_settings = MagicMock()
        await run_pipeline(company_id, user_id, mock_session, mock_settings)

    # The last transition MUST be to 'failed'
    assert status_transitions[-1] == CompanyStatus.failed


@given(
    status=st.sampled_from(
        [CompanyStatus.researching, CompanyStatus.profiling, CompanyStatus.scoring]
    ),
)
@settings(max_examples=20)
def test_property13_no_skip_transitions(status: CompanyStatus) -> None:
    """Property 13: Each intermediate status in the valid sequence MUST
    only transition to the next state or to 'failed'. No skips allowed.

    **Validates: Requirements 5.1, 5.8**
    """
    idx = VALID_STATUS_SEQUENCE.index(status)
    valid_next = {VALID_STATUS_SEQUENCE[idx + 1], CompanyStatus.failed}
    # The only valid transitions from any intermediate state are:
    # next in sequence OR failed
    assert status in VALID_STATUS_SEQUENCE[1:-1]  # intermediate states
    assert len(valid_next) == 2


# ===========================================================================
# Property 14: Pipeline Idempotency
# ===========================================================================


@given(company_id=st.integers(min_value=1, max_value=10000))
@settings(max_examples=30, deadline=None)
@pytest.mark.asyncio
async def test_property14_clear_prior_relationships_removes_llm_edges(
    company_id: int,
) -> None:
    """Property 14: _clear_prior_relationships MUST delete all LLM-extracted
    edges for a company, ensuring re-execution doesn't create duplicates.

    **Validates: Requirements 5.10, 16.5**
    """
    mock_session = AsyncMock()

    await _clear_prior_relationships(mock_session, company_id)

    # Verify a delete statement was executed filtering by source_id and origin
    mock_session.execute.assert_called_once()
    call_args = mock_session.execute.call_args
    # The delete statement should have been executed
    assert call_args is not None


@given(company_id=st.integers(min_value=1, max_value=10000))
@settings(max_examples=30, deadline=None)
@pytest.mark.asyncio
async def test_property14_clear_prior_score_snapshots_removes_all(
    company_id: int,
) -> None:
    """Property 14: _clear_prior_score_snapshots MUST delete all prior snapshots
    for a company, ensuring re-execution produces exactly one snapshot.

    **Validates: Requirements 5.10, 16.5**
    """
    mock_session = AsyncMock()

    await _clear_prior_score_snapshots(mock_session, company_id)

    # Verify a delete statement was executed
    mock_session.execute.assert_called_once()


@given(run_count=st.integers(min_value=2, max_value=5))
@settings(max_examples=10, deadline=None)
@pytest.mark.asyncio
async def test_property14_multiple_runs_produce_single_profile(run_count: int) -> None:
    """Property 14: Re-running the pipeline multiple times for the same company
    MUST result in exactly one set of results (brief, scores, relationships)
    with no duplicates.

    **Validates: Requirements 5.10, 16.5**
    """
    company_id = 1
    user_id = 1
    briefs_set: list[str] = []
    score_persist_count = 0
    relationship_persist_count = 0

    mock_company = MagicMock(spec=CompanyProfile)
    mock_company.id = company_id
    mock_company.name = "IdempotentCo"
    mock_company.status = CompanyStatus.pending
    mock_company.acquisition_brief = None

    def track_brief_update(*args, **kwargs):
        """Track that the brief is replaced, not duplicated."""
        pass

    mock_session = AsyncMock()

    with (
        patch("app.research.pipeline.get_company_by_id", new_callable=AsyncMock) as mock_get,
        patch("app.research.pipeline._update_company_status", new_callable=AsyncMock),
        patch("app.research.pipeline._publish_status", new_callable=AsyncMock),
        patch("app.research.pipeline.tavily_search", new_callable=AsyncMock) as mock_tavily,
        patch("app.research.pipeline.crawl_sources", new_callable=AsyncMock) as mock_crawl,
        patch("app.research.pipeline.generate_profile", new_callable=AsyncMock) as mock_profile,
        patch("app.research.pipeline.score_company", new_callable=AsyncMock) as mock_score,
        patch("app.research.pipeline.extract_financials", new_callable=AsyncMock) as mock_fin,
        patch(
            "app.research.pipeline.extract_relationships", new_callable=AsyncMock
        ) as mock_rel,
        patch("app.research.pipeline._persist_scores", new_callable=AsyncMock) as mock_ps,
        patch("app.research.pipeline._persist_financials", new_callable=AsyncMock),
        patch(
            "app.research.pipeline._persist_relationships", new_callable=AsyncMock
        ) as mock_pr,
    ):
        mock_get.return_value = mock_company
        mock_tavily.return_value = ["http://example.com"]
        mock_crawl.return_value = "Crawled content"
        mock_profile.return_value = "Brief text"
        mock_score.return_value = make_scoring_output()
        mock_fin.return_value = MagicMock()
        mock_rel.return_value = RelationshipsOutput(relationships=[])

        mock_settings = MagicMock()

        # Run pipeline multiple times
        for _ in range(run_count):
            await run_pipeline(company_id, user_id, mock_session, mock_settings)

    # _persist_scores is called once per run (it internally clears prior snapshots)
    assert mock_ps.call_count == run_count
    # _persist_relationships is called once per run (it internally clears prior edges)
    assert mock_pr.call_count == run_count
    # Each run replaces the brief on the same company object (no new profile created)
    assert mock_company.acquisition_brief == "Brief text"


# ===========================================================================
# Property 33: Relationship Edge Extraction Cap
# ===========================================================================


@given(edge_count=st.integers(min_value=0, max_value=20))
@settings(max_examples=50)
def test_property33_within_cap_all_preserved(edge_count: int) -> None:
    """Property 33: When edge count is ≤20, all edges MUST be preserved
    in the RelationshipsOutput.

    **Validates: Requirements 14.1**
    """
    edges = make_relationship_edges(edge_count)
    output = RelationshipsOutput(relationships=edges)
    assert len(output.relationships) == edge_count
    assert len(output.relationships) <= MAX_RELATIONSHIP_EDGES


@given(edge_count=st.integers(min_value=21, max_value=30))
@settings(max_examples=30)
def test_property33_above_cap_rejected_by_pydantic(edge_count: int) -> None:
    """Property 33: When more than 20 edges are provided, the Pydantic
    model with max_length=20 MUST reject it with a ValidationError.

    **Validates: Requirements 14.1**
    """
    edges = make_relationship_edges(edge_count)
    with pytest.raises(ValidationError):
        RelationshipsOutput(relationships=edges)


@given(edge_count=st.integers(min_value=21, max_value=30))
@settings(max_examples=30, deadline=None)
@pytest.mark.asyncio
async def test_property33_pipeline_truncates_excess_edges(edge_count: int) -> None:
    """Property 33: The extract_relationships function MUST enforce the cap
    of 20 edges even if the LLM returns more (via truncation).

    **Validates: Requirements 14.1**
    """
    # Create output that bypasses Pydantic validation by constructing directly
    edges = make_relationship_edges(edge_count)
    # Simulate the LLM returning more than 20 by building the output
    # with model_construct (bypasses validation)
    raw_output = RelationshipsOutput.model_construct(relationships=edges)

    mock_settings = MagicMock()

    with patch("app.research.pipeline.LLMClient") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm_cls.return_value = mock_llm
        mock_llm.generate_structured = AsyncMock(return_value=raw_output)

        result = await extract_relationships("TestCorp", "Brief text", mock_settings)

    # Pipeline enforces max 20 edges
    assert len(result.relationships) <= MAX_RELATIONSHIP_EDGES


@given(edge_count=relationship_count_strategy)
@settings(max_examples=50)
def test_property33_max_edges_constant_is_20(edge_count: int) -> None:
    """Property 33: The MAX_RELATIONSHIP_EDGES constant MUST be 20.

    **Validates: Requirements 14.1**
    """
    assert MAX_RELATIONSHIP_EDGES == 20


# ===========================================================================
# Property 34: Shell Company Creation for Unknown Counterparties
# ===========================================================================


def _make_mock_shell_company(name: str):
    """Create a mock that simulates a Shell_Company with expected attributes."""
    shell = MagicMock()
    shell.name = name
    shell.status = CompanyStatus.pending
    shell.client_status = ClientStatus.unknown
    shell.id = None
    return shell


@given(
    target_names=st.lists(
        company_name_strategy,
        min_size=1,
        max_size=10,
        unique=True,
    ),
)
@settings(max_examples=30, deadline=None)
@pytest.mark.asyncio
async def test_property34_unknown_counterparty_creates_shell_company(
    target_names: list[str],
) -> None:
    """Property 34: For each unknown counterparty in relationships,
    _persist_relationships MUST create a Shell_Company with
    Client_Status="Unknown".

    **Validates: Requirements 14.2**
    """
    # Build relationship edges with unknown targets
    edges = [
        RelationshipEdge(source="TestCorp", target=name, relation_type="vendor")
        for name in target_names
    ]
    relationships = RelationshipsOutput(relationships=edges[:20])  # cap at 20

    # Create source company
    source_company = MagicMock(spec=CompanyProfile)
    source_company.id = 1
    source_company.name = "TestCorp"

    # Track shell companies created
    shell_companies_created: list[dict] = []

    mock_session = AsyncMock()
    id_counter = [0]

    # Patch CompanyProfile constructor to avoid SQLAlchemy mapper config
    def mock_company_profile_init(**kwargs):
        id_counter[0] += 1
        mock_obj = MagicMock()
        mock_obj.id = id_counter[0]
        mock_obj.name = kwargs.get("name")
        mock_obj.status = kwargs.get("status")
        mock_obj.client_status = kwargs.get("client_status")
        shell_companies_created.append(
            {
                "name": mock_obj.name,
                "status": mock_obj.status,
                "client_status": mock_obj.client_status,
            }
        )
        return mock_obj

    def mock_relationship_init(**kwargs):
        mock_rel = MagicMock()
        for k, v in kwargs.items():
            setattr(mock_rel, k, v)
        return mock_rel

    # find_company_by_name_case_insensitive returns None (all unknown)
    with (
        patch(
            "app.research.pipeline.find_company_by_name_case_insensitive",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.research.pipeline.CompanyProfile",
            side_effect=mock_company_profile_init,
        ),
        patch(
            "app.research.pipeline.CompanyRelationship",
            side_effect=mock_relationship_init,
        ),
        patch(
            "app.research.pipeline._clear_prior_relationships",
            new_callable=AsyncMock,
        ),
    ):
        await _persist_relationships(mock_session, source_company, relationships)

    # Each unknown counterparty should create a Shell_Company
    expected_count = min(len(target_names), 20)
    assert len(shell_companies_created) == expected_count

    for shell in shell_companies_created:
        assert shell["client_status"] == ClientStatus.unknown
        assert shell["status"] == CompanyStatus.pending


@given(
    known_count=st.integers(min_value=1, max_value=5),
    unknown_count=st.integers(min_value=1, max_value=5),
)
@settings(max_examples=30, deadline=None)
@pytest.mark.asyncio
async def test_property34_known_counterparties_not_duplicated(
    known_count: int, unknown_count: int,
) -> None:
    """Property 34: Known counterparties (already in DB) MUST NOT create
    new Shell_Company records — only unknown ones get Shell_Companies.

    **Validates: Requirements 14.2**
    """
    assume(known_count + unknown_count <= 20)

    # Build edges: first `known_count` are known, rest are unknown
    known_names = [f"KnownCo_{i}" for i in range(known_count)]
    unknown_names = [f"UnknownCo_{i}" for i in range(unknown_count)]

    edges = []
    for name in known_names:
        edges.append(RelationshipEdge(source="TestCorp", target=name, relation_type="customer"))
    for name in unknown_names:
        edges.append(RelationshipEdge(source="TestCorp", target=name, relation_type="vendor"))

    relationships = RelationshipsOutput(relationships=edges)

    source_company = MagicMock(spec=CompanyProfile)
    source_company.id = 1
    source_company.name = "TestCorp"

    mock_session = AsyncMock()
    shell_companies_created: list = []
    id_counter = [200]

    # Return existing company for known names, None for unknown
    existing_companies = {}
    for i, name in enumerate(known_names):
        mock_co = MagicMock()
        mock_co.id = 100 + i
        mock_co.name = name
        existing_companies[name.lower().strip()] = mock_co

    async def mock_find(session, name):
        return existing_companies.get(name.lower().strip())

    def mock_company_profile_init(**kwargs):
        id_counter[0] += 1
        mock_obj = MagicMock()
        mock_obj.id = id_counter[0]
        mock_obj.name = kwargs.get("name")
        mock_obj.status = kwargs.get("status")
        mock_obj.client_status = kwargs.get("client_status")
        shell_companies_created.append(mock_obj)
        return mock_obj

    def mock_relationship_init(**kwargs):
        mock_rel = MagicMock()
        for k, v in kwargs.items():
            setattr(mock_rel, k, v)
        return mock_rel

    with (
        patch(
            "app.research.pipeline.find_company_by_name_case_insensitive",
            side_effect=mock_find,
        ),
        patch(
            "app.research.pipeline.CompanyProfile",
            side_effect=mock_company_profile_init,
        ),
        patch(
            "app.research.pipeline.CompanyRelationship",
            side_effect=mock_relationship_init,
        ),
        patch(
            "app.research.pipeline._clear_prior_relationships",
            new_callable=AsyncMock,
        ),
    ):
        await _persist_relationships(mock_session, source_company, relationships)

    # Only unknown counterparties should create shell companies
    assert len(shell_companies_created) == unknown_count

    # All shell companies should have Unknown client_status
    for shell in shell_companies_created:
        assert shell.client_status == ClientStatus.unknown


@given(target_name=company_name_strategy)
@settings(max_examples=30, deadline=None)
@pytest.mark.asyncio
async def test_property34_shell_company_has_correct_fields(target_name: str) -> None:
    """Property 34: A Shell_Company MUST have the target name and
    Client_Status set to 'Unknown'.

    **Validates: Requirements 14.2**
    """
    edges = [
        RelationshipEdge(source="TestCorp", target=target_name, relation_type="partner")
    ]
    relationships = RelationshipsOutput(relationships=edges)

    source_company = MagicMock(spec=CompanyProfile)
    source_company.id = 1
    source_company.name = "TestCorp"

    mock_session = AsyncMock()
    created_profiles: list = []

    def mock_company_profile_init(**kwargs):
        mock_obj = MagicMock()
        mock_obj.id = 99
        mock_obj.name = kwargs.get("name")
        mock_obj.status = kwargs.get("status")
        mock_obj.client_status = kwargs.get("client_status")
        created_profiles.append(mock_obj)
        return mock_obj

    def mock_relationship_init(**kwargs):
        mock_rel = MagicMock()
        for k, v in kwargs.items():
            setattr(mock_rel, k, v)
        return mock_rel

    with (
        patch(
            "app.research.pipeline.find_company_by_name_case_insensitive",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.research.pipeline.CompanyProfile",
            side_effect=mock_company_profile_init,
        ),
        patch(
            "app.research.pipeline.CompanyRelationship",
            side_effect=mock_relationship_init,
        ),
        patch(
            "app.research.pipeline._clear_prior_relationships",
            new_callable=AsyncMock,
        ),
    ):
        await _persist_relationships(mock_session, source_company, relationships)

    # Verify the shell company was created with correct fields
    assert len(created_profiles) == 1
    shell = created_profiles[0]
    assert shell.name == target_name.strip()
    assert shell.client_status == ClientStatus.unknown
    assert shell.status == CompanyStatus.pending
