"""Graph service layer.

Business logic for relationship graph operations:
- get_graph(): depth-limited BFS traversal from a center company
- create_edge(): manual edge creation with duplicate prevention
- find_warm_path(): BFS shortest path from prospect to nearest Client
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.companies.models import ClientStatus, CompanyProfile, RelationType
from app.graph import repository as graph_repo
from app.graph.schemas import (
    EdgeCreate,
    GraphEdge,
    GraphNode,
    GraphResponse,
    WarmPathResponse,
)


async def get_graph(
    session: AsyncSession,
    company_id: int,
    depth: int = 1,
) -> GraphResponse:
    """Get the relationship graph centered on a company using BFS.

    Performs depth-limited BFS traversal with:
    - Default depth: 1
    - Maximum depth: 3
    - Maximum nodes per response: 50

    Args:
        session: Async database session.
        company_id: Center company ID.
        depth: Traversal depth (default 1, max 3).

    Returns:
        GraphResponse with nodes, edges, and center_node_id.

    Raises:
        HTTPException: If the company doesn't exist or depth is invalid.
    """
    # Validate company exists
    company = await session.get(CompanyProfile, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    # Clamp depth to valid range
    depth = max(1, min(depth, 3))

    # Perform BFS traversal
    nodes, edges = await graph_repo.get_neighbors_at_depth(
        session, company_id, max_depth=depth, max_nodes=50
    )

    # Convert to response models
    graph_nodes = [
        GraphNode(
            id=node.id,
            name=node.name,
            client_status=node.client_status,
            status=node.status,
        )
        for node in nodes
    ]

    graph_edges = [
        GraphEdge(
            id=edge.id,
            source_id=edge.source_id,
            target_id=edge.target_id,
            relation_type=edge.relation_type,
            origin=edge.origin,
            confidence=edge.confidence,
        )
        for edge in edges
    ]

    return GraphResponse(
        nodes=graph_nodes,
        edges=graph_edges,
        center_node_id=company_id,
    )


async def create_edge(
    session: AsyncSession,
    edge_data: EdgeCreate,
) -> GraphEdge:
    """Create a manual relationship edge with duplicate prevention.

    Validates that no duplicate edge exists with the same type, same
    direction, and same companies before creating.

    Args:
        session: Async database session.
        edge_data: Edge creation request data.

    Returns:
        The created GraphEdge.

    Raises:
        HTTPException: If source/target don't exist or duplicate edge exists.
    """
    # Validate source company exists
    source = await session.get(CompanyProfile, edge_data.source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source company not found",
        )

    # Validate target company exists
    target = await session.get(CompanyProfile, edge_data.target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target company not found",
        )

    # Check for duplicate edge (same type, same direction, same companies)
    is_duplicate = await graph_repo.check_duplicate_edge(
        session,
        edge_data.source_id,
        edge_data.target_id,
        edge_data.relation_type,
    )
    if is_duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A relationship of this type already exists between these companies in this direction",
        )

    # Create the edge
    edge = await graph_repo.create_edge(
        session,
        edge_data.source_id,
        edge_data.target_id,
        edge_data.relation_type,
    )

    return GraphEdge(
        id=edge.id,
        source_id=edge.source_id,
        target_id=edge.target_id,
        relation_type=edge.relation_type,
        origin=edge.origin,
        confidence=edge.confidence,
    )


async def find_warm_path(
    session: AsyncSession,
    company_id: int,
) -> WarmPathResponse:
    """Find the shortest warm path from a prospect to the nearest Client.

    Uses BFS to find the shortest path (maximum 4 edges) from the
    given company to the nearest company with ClientStatus="Client".

    Args:
        session: Async database session.
        company_id: The prospect company ID.

    Returns:
        WarmPathResponse with path details or unavailability indication.

    Raises:
        HTTPException: If the company doesn't exist.
    """
    # Validate company exists
    company = await session.get(CompanyProfile, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    # If the company is already a Client, no warm path needed
    if company.client_status == ClientStatus.client:
        return WarmPathResponse(
            path=[
                GraphNode(
                    id=company.id,
                    name=company.name,
                    client_status=company.client_status,
                    status=company.status,
                )
            ],
            edges=[],
            path_length=0,
            available=True,
        )

    # Perform BFS to find warm path
    result = await graph_repo.find_warm_path_bfs(session, company_id, max_hops=4)

    if result is None:
        return WarmPathResponse(available=False)

    path_node_ids, path_edges = result

    # Fetch full node details for path
    path_nodes = []
    for node_id in path_node_ids:
        node = await session.get(CompanyProfile, node_id)
        if node:
            path_nodes.append(
                GraphNode(
                    id=node.id,
                    name=node.name,
                    client_status=node.client_status,
                    status=node.status,
                )
            )

    graph_edges = [
        GraphEdge(
            id=edge.id,
            source_id=edge.source_id,
            target_id=edge.target_id,
            relation_type=edge.relation_type,
            origin=edge.origin,
            confidence=edge.confidence,
        )
        for edge in path_edges
    ]

    return WarmPathResponse(
        path=path_nodes,
        edges=graph_edges,
        path_length=len(path_edges),
        available=True,
    )
