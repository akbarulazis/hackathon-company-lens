"""Graph API router.

Provides endpoints for relationship graph queries,
manual edge creation, and warm path computation.
All endpoints require authentication via get_current_user dependency.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.dependencies import get_db
from app.graph.schemas import EdgeCreate, GraphEdge, GraphResponse, WarmPathResponse
from app.graph.service import create_edge, find_warm_path, get_graph

router = APIRouter(prefix="/api/companies", tags=["graph"])


@router.get(
    "/{company_id}/graph",
    response_model=GraphResponse,
)
async def get_company_graph(
    company_id: int,
    depth: int = Query(default=1, ge=1, le=3, description="BFS traversal depth (1-3)"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GraphResponse:
    """Get the relationship graph centered on a company.

    Performs depth-limited BFS traversal returning nodes and edges.
    Default depth is 1, maximum depth is 3, and at most 50 nodes
    are returned per response.
    """
    return await get_graph(session, company_id, depth)


@router.post(
    "/{company_id}/graph/edges",
    response_model=GraphEdge,
    status_code=201,
)
async def create_graph_edge(
    company_id: int,
    edge_data: EdgeCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GraphEdge:
    """Create a manual relationship edge.

    Validates that no duplicate edge of the same type exists between
    the same two companies in the same direction before creating.
    """
    return await create_edge(session, edge_data)


@router.get(
    "/{company_id}/warm-path",
    response_model=WarmPathResponse,
)
async def get_warm_path(
    company_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WarmPathResponse:
    """Compute the warm path from a company to the nearest Client.

    Uses BFS to find the shortest path (maximum 4 edges) from
    the given company to the nearest company with ClientStatus="Client".
    Returns available=False if no path exists within 4 hops.
    """
    return await find_warm_path(session, company_id)
