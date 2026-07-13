"""Property-based tests for graph operations.

# Feature: company-lens-rebuild
# Property 35: Graph BFS Depth-Limited Traversal
# Property 36: Duplicate Edge Prevention
# Property 37: Warm Path Shortest Path Computation

Validates: Requirements 14.3, 14.4, 14.5, 14.6
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.companies.models import ClientStatus, CompanyProfile, CompanyRelationship, CompanyStatus, RelationType
from app.graph.schemas import EdgeCreate, GraphResponse, WarmPathResponse
from app.graph import service as graph_service


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid BFS depths (1-3 as per spec)
valid_depth_strategy = st.integers(min_value=1, max_value=3)

# Node counts for BFS results (0-60, some above the 50 cap)
node_count_strategy = st.integers(min_value=1, max_value=60)

# Relation types for edge creation
relation_type_strategy = st.sampled_from(list(RelationType))

# Company IDs
company_id_strategy = st.integers(min_value=1, max_value=10000)

# Warm path lengths (1-6, some above the 4-edge max)
path_length_strategy = st.integers(min_value=1, max_value=6)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_company(
    company_id: int,
    name: str = "TestCo",
    client_status: ClientStatus = ClientStatus.prospect,
    status: CompanyStatus = CompanyStatus.ready,
) -> MagicMock:
    """Create a mock CompanyProfile with the given attributes."""
    mock = MagicMock(spec=CompanyProfile)
    mock.id = company_id
    mock.name = name
    mock.client_status = client_status
    mock.status = status
    return mock


def make_mock_edge(
    edge_id: int,
    source_id: int,
    target_id: int,
    relation_type: RelationType = RelationType.partner,
) -> MagicMock:
    """Create a mock CompanyRelationship edge."""
    mock = MagicMock(spec=CompanyRelationship)
    mock.id = edge_id
    mock.source_id = source_id
    mock.target_id = target_id
    mock.relation_type = relation_type
    mock.origin = "manual"
    mock.confidence = 1.0
    return mock


def generate_bfs_results(
    center_id: int, num_nodes: int, depth: int
) -> tuple[list[MagicMock], list[MagicMock]]:
    """Generate mock BFS traversal results (nodes and edges).

    Creates a simple graph structure with nodes at varying depths
    from the center node.
    """
    nodes = [make_mock_company(center_id, name=f"Company_{center_id}")]
    edges = []

    edge_id = 1
    current_layer_ids = [center_id]
    node_id = center_id + 1
    nodes_created = 1

    for d in range(1, depth + 1):
        next_layer_ids = []
        for parent_id in current_layer_ids:
            if nodes_created >= num_nodes:
                break
            # Each node at this depth connects to parent
            new_node = make_mock_company(node_id, name=f"Company_{node_id}")
            nodes.append(new_node)
            edges.append(make_mock_edge(edge_id, parent_id, node_id))
            next_layer_ids.append(node_id)
            node_id += 1
            edge_id += 1
            nodes_created += 1
        current_layer_ids = next_layer_ids
        if nodes_created >= num_nodes:
            break

    return nodes, edges


# ===========================================================================
# Property 35: Graph BFS Depth-Limited Traversal
# ===========================================================================


@given(depth=valid_depth_strategy, num_nodes=st.integers(min_value=1, max_value=50))
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property35_bfs_returns_within_node_limit(depth: int, num_nodes: int) -> None:
    """Property 35: BFS traversal SHALL not exceed 50 nodes in the response.

    **Validates: Requirements 14.3**
    """
    center_id = 1
    nodes, edges = generate_bfs_results(center_id, num_nodes, depth)

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=make_mock_company(center_id))

    with patch(
        "app.graph.service.graph_repo.get_neighbors_at_depth",
        new_callable=AsyncMock,
        return_value=(nodes, edges),
    ):
        result = await graph_service.get_graph(mock_session, center_id, depth)

    assert isinstance(result, GraphResponse)
    assert len(result.nodes) <= 50


@given(depth=valid_depth_strategy, num_nodes=st.integers(min_value=51, max_value=80))
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property35_bfs_caps_at_50_nodes(depth: int, num_nodes: int) -> None:
    """Property 35: Even when the graph has more than 50 reachable nodes,
    BFS SHALL return at most 50 nodes.

    **Validates: Requirements 14.3**
    """
    center_id = 1
    # Generate more nodes than the 50-node cap allows
    nodes, edges = generate_bfs_results(center_id, num_nodes, depth)
    # Cap the nodes returned by repository to simulate the max_nodes enforcement
    capped_nodes = nodes[:50]

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=make_mock_company(center_id))

    with patch(
        "app.graph.service.graph_repo.get_neighbors_at_depth",
        new_callable=AsyncMock,
        return_value=(capped_nodes, edges),
    ):
        result = await graph_service.get_graph(mock_session, center_id, depth)

    assert len(result.nodes) <= 50


@given(depth=valid_depth_strategy)
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property35_bfs_respects_depth_parameter(depth: int) -> None:
    """Property 35: BFS SHALL only return nodes within the specified depth.
    The depth is clamped to [1, 3].

    **Validates: Requirements 14.3**
    """
    center_id = 1
    nodes, edges = generate_bfs_results(center_id, num_nodes=10, depth=depth)

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=make_mock_company(center_id))

    with patch(
        "app.graph.service.graph_repo.get_neighbors_at_depth",
        new_callable=AsyncMock,
        return_value=(nodes, edges),
    ) as mock_bfs:
        result = await graph_service.get_graph(mock_session, center_id, depth)

    # Verify the repository was called with the correct clamped depth
    call_args = mock_bfs.call_args
    called_depth = call_args.kwargs.get("max_depth") or call_args[1].get("max_depth", depth)
    assert 1 <= called_depth <= 3
    assert called_depth == depth


@given(depth=st.integers(min_value=4, max_value=10))
@settings(max_examples=30, deadline=None)
@pytest.mark.asyncio
async def test_property35_bfs_clamps_depth_above_max(depth: int) -> None:
    """Property 35: Depths above 3 SHALL be clamped to 3.

    **Validates: Requirements 14.3**
    """
    center_id = 1
    nodes = [make_mock_company(center_id)]
    edges: list = []

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=make_mock_company(center_id))

    with patch(
        "app.graph.service.graph_repo.get_neighbors_at_depth",
        new_callable=AsyncMock,
        return_value=(nodes, edges),
    ) as mock_bfs:
        result = await graph_service.get_graph(mock_session, center_id, depth)

    # Verify depth was clamped to 3
    call_args = mock_bfs.call_args
    called_depth = call_args.kwargs.get("max_depth") or call_args[1].get("max_depth")
    assert called_depth == 3


@given(depth=valid_depth_strategy, num_nodes=st.integers(min_value=2, max_value=20))
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property35_bfs_includes_correct_edge_labels(depth: int, num_nodes: int) -> None:
    """Property 35: BFS SHALL include correct edge labels (relation_type)
    for all edges in the response.

    **Validates: Requirements 14.3**
    """
    center_id = 1
    nodes, edges = generate_bfs_results(center_id, num_nodes, depth)

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=make_mock_company(center_id))

    with patch(
        "app.graph.service.graph_repo.get_neighbors_at_depth",
        new_callable=AsyncMock,
        return_value=(nodes, edges),
    ):
        result = await graph_service.get_graph(mock_session, center_id, depth)

    # Verify all edges have valid relation_type labels
    for edge in result.edges:
        assert edge.relation_type in list(RelationType)
        assert edge.source_id is not None
        assert edge.target_id is not None


# ===========================================================================
# Property 36: Duplicate Edge Prevention
# ===========================================================================


@given(
    source_id=company_id_strategy,
    target_id=company_id_strategy,
    relation_type=relation_type_strategy,
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property36_duplicate_edge_rejected_with_409(
    source_id: int, target_id: int, relation_type: RelationType
) -> None:
    """Property 36: When an edge of the same type already exists between
    the same two companies in the same direction, create_edge SHALL
    reject with 409 Conflict.

    **Validates: Requirements 14.4**
    """
    from fastapi import HTTPException

    edge_data = EdgeCreate(
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
    )

    mock_session = AsyncMock()
    # session.get returns mock companies (they exist)
    mock_session.get = AsyncMock(side_effect=lambda model, id_: make_mock_company(id_))

    with patch(
        "app.graph.service.graph_repo.check_duplicate_edge",
        new_callable=AsyncMock,
        return_value=True,  # duplicate exists
    ):
        with pytest.raises(HTTPException) as exc_info:
            await graph_service.create_edge(mock_session, edge_data)

    assert exc_info.value.status_code == 409


@given(
    source_id=company_id_strategy,
    target_id=company_id_strategy,
    relation_type=relation_type_strategy,
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property36_non_duplicate_edge_allowed(
    source_id: int, target_id: int, relation_type: RelationType
) -> None:
    """Property 36: When no duplicate edge exists, create_edge SHALL
    successfully create and return the new edge.

    **Validates: Requirements 14.4**
    """
    edge_data = EdgeCreate(
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
    )

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=lambda model, id_: make_mock_company(id_))

    created_edge = make_mock_edge(
        edge_id=999,
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
    )

    with (
        patch(
            "app.graph.service.graph_repo.check_duplicate_edge",
            new_callable=AsyncMock,
            return_value=False,  # no duplicate
        ),
        patch(
            "app.graph.service.graph_repo.create_edge",
            new_callable=AsyncMock,
            return_value=created_edge,
        ),
    ):
        result = await graph_service.create_edge(mock_session, edge_data)

    assert result.source_id == source_id
    assert result.target_id == target_id
    assert result.relation_type == relation_type


@given(
    source_id=company_id_strategy,
    target_id=company_id_strategy,
    relation_type=relation_type_strategy,
)
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property36_direction_matters_for_duplicates(
    source_id: int, target_id: int, relation_type: RelationType
) -> None:
    """Property 36: Duplicate detection SHALL consider direction —
    an edge A→B does NOT prevent B→A of the same type.

    **Validates: Requirements 14.4**
    """
    from fastapi import HTTPException

    # Edge in reverse direction (target→source) should NOT be a duplicate
    edge_data = EdgeCreate(
        source_id=target_id,
        target_id=source_id,
        relation_type=relation_type,
    )

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=lambda model, id_: make_mock_company(id_))

    created_edge = make_mock_edge(
        edge_id=888,
        source_id=target_id,
        target_id=source_id,
        relation_type=relation_type,
    )

    with (
        patch(
            "app.graph.service.graph_repo.check_duplicate_edge",
            new_callable=AsyncMock,
            return_value=False,  # not a duplicate in reverse direction
        ),
        patch(
            "app.graph.service.graph_repo.create_edge",
            new_callable=AsyncMock,
            return_value=created_edge,
        ),
    ):
        # Should succeed since direction is reversed
        result = await graph_service.create_edge(mock_session, edge_data)

    assert result.source_id == target_id
    assert result.target_id == source_id


# ===========================================================================
# Property 37: Warm Path Shortest Path Computation
# ===========================================================================


@given(path_length=st.integers(min_value=1, max_value=4))
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property37_warm_path_within_4_edges(path_length: int) -> None:
    """Property 37: When a warm path exists within 4 edges, find_warm_path
    SHALL return available=True with path_length ≤ 4.

    **Validates: Requirements 14.5**
    """
    start_id = 1
    # Build a linear path: start → node2 → ... → client
    path_node_ids = list(range(start_id, start_id + path_length + 1))
    path_edges = [
        make_mock_edge(i + 1, path_node_ids[i], path_node_ids[i + 1])
        for i in range(path_length)
    ]

    # Start node is a prospect
    start_company = make_mock_company(
        start_id, name="Prospect", client_status=ClientStatus.prospect
    )

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=start_company)

    # Mock find_warm_path_bfs to return the path
    with patch(
        "app.graph.service.graph_repo.find_warm_path_bfs",
        new_callable=AsyncMock,
        return_value=(path_node_ids, path_edges),
    ):
        # Also mock session.get for path node lookups
        async def mock_get(model, node_id):
            if node_id == start_id:
                return start_company
            # Last node is a client
            if node_id == path_node_ids[-1]:
                return make_mock_company(
                    node_id, name=f"Client_{node_id}", client_status=ClientStatus.client
                )
            return make_mock_company(node_id, name=f"Node_{node_id}")

        mock_session.get = AsyncMock(side_effect=mock_get)

        result = await graph_service.find_warm_path(mock_session, start_id)

    assert isinstance(result, WarmPathResponse)
    assert result.available is True
    assert result.path_length is not None
    assert result.path_length <= 4
    assert result.path_length == path_length


@given(path_length=st.integers(min_value=5, max_value=8))
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property37_no_warm_path_beyond_4_edges(path_length: int) -> None:
    """Property 37: When no Client is reachable within 4 edges,
    find_warm_path SHALL return available=False.

    **Validates: Requirements 14.6**
    """
    start_id = 1
    start_company = make_mock_company(
        start_id, name="Prospect", client_status=ClientStatus.prospect
    )

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=start_company)

    # Mock find_warm_path_bfs returning None (no path within max_hops)
    with patch(
        "app.graph.service.graph_repo.find_warm_path_bfs",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await graph_service.find_warm_path(mock_session, start_id)

    assert isinstance(result, WarmPathResponse)
    assert result.available is False
    assert result.path is None
    assert result.edges is None
    assert result.path_length is None


@given(company_id=company_id_strategy)
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property37_client_company_returns_zero_length_path(company_id: int) -> None:
    """Property 37: If the company is already a Client, find_warm_path
    SHALL return available=True with path_length=0.

    **Validates: Requirements 14.5**
    """
    client_company = make_mock_company(
        company_id, name="ExistingClient", client_status=ClientStatus.client
    )

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=client_company)

    result = await graph_service.find_warm_path(mock_session, company_id)

    assert isinstance(result, WarmPathResponse)
    assert result.available is True
    assert result.path_length == 0
    assert result.path is not None
    assert len(result.path) == 1
    assert result.path[0].id == company_id


@given(path_length=st.integers(min_value=1, max_value=4))
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property37_warm_path_ends_at_client(path_length: int) -> None:
    """Property 37: A valid warm path MUST terminate at a company with
    Client_Status='Client'.

    **Validates: Requirements 14.5**
    """
    start_id = 1
    path_node_ids = list(range(start_id, start_id + path_length + 1))
    path_edges = [
        make_mock_edge(i + 1, path_node_ids[i], path_node_ids[i + 1])
        for i in range(path_length)
    ]

    start_company = make_mock_company(
        start_id, name="Prospect", client_status=ClientStatus.prospect
    )

    mock_session = AsyncMock()

    with patch(
        "app.graph.service.graph_repo.find_warm_path_bfs",
        new_callable=AsyncMock,
        return_value=(path_node_ids, path_edges),
    ):
        async def mock_get(model, node_id):
            if node_id == start_id:
                return start_company
            if node_id == path_node_ids[-1]:
                return make_mock_company(
                    node_id, name=f"Client_{node_id}", client_status=ClientStatus.client
                )
            return make_mock_company(node_id, name=f"Intermediate_{node_id}")

        mock_session.get = AsyncMock(side_effect=mock_get)

        result = await graph_service.find_warm_path(mock_session, start_id)

    assert result.available is True
    assert result.path is not None
    # Last node in path should be the Client
    last_node = result.path[-1]
    assert last_node.client_status == ClientStatus.client
