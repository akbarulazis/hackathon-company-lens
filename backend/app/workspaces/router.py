"""Workspace API router.

Provides REST endpoints for workspace CRUD operations and
company management within workspaces. All endpoints require
authentication via JWT bearer token.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.dependencies import get_db
from app.workspaces.schemas import (
    AddCompanyRequest,
    WorkspaceCreate,
    WorkspaceDetail,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.workspaces.service import (
    WorkspaceError,
    add_company,
    create_workspace,
    delete_workspace,
    get_workspace,
    list_workspaces,
    remove_company,
    update_workspace,
)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.get(
    "",
    response_model=list[WorkspaceResponse],
)
async def list_user_workspaces(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[WorkspaceResponse]:
    """List all workspaces owned by the authenticated user."""
    return await list_workspaces(session, current_user.id)


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_workspace(
    data: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    """Create a new workspace for the authenticated user."""
    try:
        return await create_workspace(session, current_user.id, data)
    except WorkspaceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceDetail,
)
async def get_workspace_detail(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkspaceDetail:
    """Get workspace detail with companies. Returns 404 if not found or not owned."""
    try:
        return await get_workspace(session, workspace_id, current_user.id)
    except WorkspaceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.put(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
)
async def update_user_workspace(
    workspace_id: int,
    data: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    """Update workspace name. Returns 404 if not found or not owned."""
    try:
        return await update_workspace(session, workspace_id, current_user.id, data)
    except WorkspaceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user_workspace(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a workspace with cascade. Returns 404 if not found or not owned."""
    try:
        await delete_workspace(session, workspace_id, current_user.id)
    except WorkspaceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post(
    "/{workspace_id}/companies",
    response_model=WorkspaceDetail,
)
async def add_company_to_workspace(
    workspace_id: int,
    data: AddCompanyRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkspaceDetail:
    """Add a company to a workspace.

    Returns 404 if workspace/company not found.
    Returns 409 if company already in workspace.
    Returns 422 if company limit exceeded.
    """
    try:
        return await add_company(session, workspace_id, data.company_id, current_user.id)
    except WorkspaceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.delete(
    "/{workspace_id}/companies/{company_id}",
    response_model=WorkspaceDetail,
)
async def remove_company_from_workspace(
    workspace_id: int,
    company_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkspaceDetail:
    """Remove a company from a workspace. Returns 404 if not found."""
    try:
        return await remove_company(session, workspace_id, company_id, current_user.id)
    except WorkspaceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
