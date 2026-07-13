"""Graph repository layer.

Database operations for relationship graph traversal (BFS),
edge CRUD, and duplicate edge checking.
No business logic — only data access via SQLAlchemy async sessions.
"""

from collections import deque

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.companies.models import (
    ClientStatus,
    CompanyProfile,
    CompanyRelationship,
    RelationType,
)


async def get_edges_for_company(
    session: AsyncSession, company_id: int
) -> list[CompanyRelationship]:
    """Get all relationship edges where the company is source or target.

    Args:
        session: Async database session.
        company_id: The company to find edges for.

    Returns:
        List of CompanyRelationship edges connected to the company.
    """
    stmt = select(CompanyRelationship).where(
        or_(
            CompanyRelationship.source_id == company_id,
            CompanyRelationship.target_id == company_id,
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_neighbors_at_depth(
    session: AsyncSession,
    company_id: int,
    max_depth: int = 1,
    max_nodes: int = 50,
) -> tuple[list[CompanyProfile], list[CompanyRelationship]]:
    """Perform BFS traversal from a center node up to max_depth levels.

    Uses a queue-based BFS approach starting from the center node,
    expanding up to max_depth levels, collecting all nodes and edges
    encountered (capped at max_nodes).

    Args:
        session: Async database session.
        company_id: Starting company ID for the BFS.
        max_depth: Maximum depth to traverse (default 1, max 3).
        max_nodes: Maximum number of nodes to return (default 50).

    Returns:
        Tuple of (nodes, edges) discovered during BFS traversal.
    """
    visited_node_ids: set[int] = {company_id}
    collected_edge_ids: set[int] = set()
    collected_edges: list[CompanyRelationship] = []

    # BFS queue: (node_id, current_depth)
    queue: deque[tuple[int, int]] = deque([(company_id, 0)])

    while queue and len(visited_node_ids) <= max_nodes:
        current_id, current_depth = queue.popleft()

        if current_depth >= max_depth:
            continue

        # Fetch edges for the current node
        edges = await get_edges_for_company(session, current_id)

        for edge in edges:
            # Collect edge if not already seen
            if edge.id not in collected_edge_ids:
                collected_edge_ids.add(edge.id)
                collected_edges.append(edge)

            # Determine neighbor
            neighbor_id = (
                edge.target_id if edge.source_id == current_id else edge.source_id
            )

            # Add neighbor if not visited and within node limit
            if neighbor_id not in visited_node_ids:
                if len(visited_node_ids) >= max_nodes:
                    break
                visited_node_ids.add(neighbor_id)
                queue.append((neighbor_id, current_depth + 1))

    # Fetch all node profiles
    if visited_node_ids:
        stmt = select(CompanyProfile).where(CompanyProfile.id.in_(visited_node_ids))
        result = await session.execute(stmt)
        nodes = list(result.scalars().all())
    else:
        nodes = []

    return nodes, collected_edges


async def check_duplicate_edge(
    session: AsyncSession,
    source_id: int,
    target_id: int,
    relation_type: RelationType,
) -> bool:
    """Check if a duplicate edge exists (same type, same direction, same companies).

    Args:
        session: Async database session.
        source_id: Source company ID.
        target_id: Target company ID.
        relation_type: The relationship type.

    Returns:
        True if a duplicate exists, False otherwise.
    """
    stmt = select(CompanyRelationship).where(
        and_(
            CompanyRelationship.source_id == source_id,
            CompanyRelationship.target_id == target_id,
            CompanyRelationship.relation_type == relation_type,
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def create_edge(
    session: AsyncSession,
    source_id: int,
    target_id: int,
    relation_type: RelationType,
) -> CompanyRelationship:
    """Create a new relationship edge between two companies.

    Args:
        session: Async database session.
        source_id: Source company ID.
        target_id: Target company ID.
        relation_type: The relationship type.

    Returns:
        The created CompanyRelationship instance.
    """
    edge = CompanyRelationship(
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        origin="manual",
        confidence=1.0,
    )
    session.add(edge)
    await session.flush()
    return edge


async def find_warm_path_bfs(
    session: AsyncSession,
    start_company_id: int,
    max_hops: int = 4,
) -> tuple[list[int], list[CompanyRelationship]] | None:
    """BFS from a company to the nearest Client within max_hops edges.

    Traverses the relationship graph from the starting company until
    finding a company with ClientStatus.client. Returns the path
    (sequence of node IDs) and edges along that path.

    Args:
        session: Async database session.
        start_company_id: The starting prospect company ID.
        max_hops: Maximum number of edges to traverse (default 4).

    Returns:
        Tuple of (path_node_ids, path_edges) if a Client is found,
        None if no warm path exists within max_hops.
    """
    # BFS queue: each item is (current_node_id, path_of_node_ids, path_of_edges)
    queue: deque[tuple[int, list[int], list[CompanyRelationship]]] = deque(
        [(start_company_id, [start_company_id], [])]
    )
    visited: set[int] = {start_company_id}

    while queue:
        current_id, path_nodes, path_edges = queue.popleft()

        # Check depth limit (number of edges in path)
        if len(path_edges) >= max_hops:
            continue

        # Fetch edges for current node
        edges = await get_edges_for_company(session, current_id)

        for edge in edges:
            # Determine neighbor
            neighbor_id = (
                edge.target_id if edge.source_id == current_id else edge.source_id
            )

            if neighbor_id in visited:
                continue

            visited.add(neighbor_id)

            new_path_nodes = path_nodes + [neighbor_id]
            new_path_edges = path_edges + [edge]

            # Check if neighbor is a Client
            neighbor = await session.get(CompanyProfile, neighbor_id)
            if neighbor and neighbor.client_status == ClientStatus.client:
                return new_path_nodes, new_path_edges

            # Only continue if we haven't exceeded max hops
            if len(new_path_edges) < max_hops:
                queue.append((neighbor_id, new_path_nodes, new_path_edges))

    return None
