"""Workspace service layer.

Business logic for workspace CRUD operations, company management,
and ownership enforcement. Raises appropriate HTTP-friendly errors
for validation failures.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.companies.models import CompanyProfile
from app.workspaces import repository
from app.workspaces.models import Workspace
from app.workspaces.schemas import (
    CompanyInWorkspace,
    WorkspaceCreate,
    WorkspaceDetail,
    WorkspaceResponse,
    WorkspaceUpdate,
)


class WorkspaceError(Exception):
    """Base workspace error with status code and message."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def create_workspace(
    session: AsyncSession,
    user_id: int,
    data: WorkspaceCreate,
    company_limit: int = 3,
) -> WorkspaceResponse:
    """Create a new workspace for a user.

    Validates:
    - Name is 1-100 characters (enforced by schema)
    - No duplicate name for the same user

    Raises:
        WorkspaceError(409): If a workspace with the same name exists for user.
    """
    # Check for duplicate name
    existing = await repository.get_workspace_by_name_and_user(
        session, data.name, user_id
    )
    if existing:
        raise WorkspaceError(
            status_code=409,
            detail=f"A workspace named '{data.name}' already exists",
        )

    workspace = await repository.create_workspace(
        session,
        user_id=user_id,
        name=data.name,
        company_limit=company_limit,
    )

    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        company_count=0,
        company_limit=workspace.company_limit,
        created_at=workspace.created_at,
    )


async def list_workspaces(
    session: AsyncSession, user_id: int
) -> list[WorkspaceResponse]:
    """List all workspaces owned by a user."""
    workspaces = await repository.list_workspaces_for_user(session, user_id)

    results = []
    for ws in workspaces:
        count = await repository.get_workspace_company_count(session, ws.id)
        results.append(
            WorkspaceResponse(
                id=ws.id,
                name=ws.name,
                company_count=count,
                company_limit=ws.company_limit,
                created_at=ws.created_at,
            )
        )
    return results


async def get_workspace(
    session: AsyncSession, workspace_id: int, user_id: int
) -> WorkspaceDetail:
    """Get workspace detail with companies, enforcing ownership.

    Raises:
        WorkspaceError(404): If workspace not found or not owned by user.
    """
    workspace = await repository.get_workspace_by_id_and_user(
        session, workspace_id, user_id
    )
    if not workspace:
        raise WorkspaceError(
            status_code=404,
            detail="Workspace not found",
        )

    companies_data = await repository.get_workspace_companies(session, workspace_id)
    companies = [
        CompanyInWorkspace(
            id=company.id,
            name=company.name,
            status=company.status.value,
            client_status=company.client_status.value,
            industry=company.industry,
            overall_score=float(company.overall_score) if company.overall_score else None,
            added_at=assoc.added_at,
        )
        for company, assoc in companies_data
    ]

    return WorkspaceDetail(
        id=workspace.id,
        name=workspace.name,
        company_count=len(companies),
        company_limit=workspace.company_limit,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        companies=companies,
    )


async def update_workspace(
    session: AsyncSession,
    workspace_id: int,
    user_id: int,
    data: WorkspaceUpdate,
) -> WorkspaceResponse:
    """Update a workspace name, enforcing ownership.

    Validates:
    - Ownership (404 for non-owners)
    - No duplicate name for the same user

    Raises:
        WorkspaceError(404): If workspace not found or not owned by user.
        WorkspaceError(409): If another workspace with the same name exists.
    """
    workspace = await repository.get_workspace_by_id_and_user(
        session, workspace_id, user_id
    )
    if not workspace:
        raise WorkspaceError(
            status_code=404,
            detail="Workspace not found",
        )

    # Check for duplicate name (excluding current workspace)
    existing = await repository.get_workspace_by_name_and_user(
        session, data.name, user_id
    )
    if existing and existing.id != workspace_id:
        raise WorkspaceError(
            status_code=409,
            detail=f"A workspace named '{data.name}' already exists",
        )

    workspace = await repository.update_workspace_name(session, workspace, data.name)
    count = await repository.get_workspace_company_count(session, workspace_id)

    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        company_count=count,
        company_limit=workspace.company_limit,
        created_at=workspace.created_at,
    )


async def delete_workspace(
    session: AsyncSession, workspace_id: int, user_id: int
) -> None:
    """Delete a workspace with cascade, enforcing ownership.

    Cascade deletes: workspace-company associations, text chunks scoped to
    the workspace, chat messages, and comparison reports.
    Company profiles are preserved (may belong to other workspaces).

    Raises:
        WorkspaceError(404): If workspace not found or not owned by user.
    """
    workspace = await repository.get_workspace_by_id_and_user(
        session, workspace_id, user_id
    )
    if not workspace:
        raise WorkspaceError(
            status_code=404,
            detail="Workspace not found",
        )

    await repository.delete_workspace(session, workspace)


async def add_company(
    session: AsyncSession,
    workspace_id: int,
    company_id: int,
    user_id: int,
) -> WorkspaceDetail:
    """Add a company to a workspace.

    Validates:
    - Ownership (404 for non-owners)
    - Company exists
    - Company not already in workspace (409)
    - Company limit not exceeded (422)

    Raises:
        WorkspaceError(404): If workspace or company not found.
        WorkspaceError(409): If company is already in the workspace.
        WorkspaceError(422): If adding would exceed the company limit.
    """
    workspace = await repository.get_workspace_by_id_and_user(
        session, workspace_id, user_id
    )
    if not workspace:
        raise WorkspaceError(
            status_code=404,
            detail="Workspace not found",
        )

    # Check company exists
    from sqlalchemy import select

    result = await session.execute(
        select(CompanyProfile).where(CompanyProfile.id == company_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise WorkspaceError(
            status_code=404,
            detail="Company not found",
        )

    # Check if already in workspace
    existing = await repository.get_workspace_company(session, workspace_id, company_id)
    if existing:
        raise WorkspaceError(
            status_code=409,
            detail="Company is already in this workspace",
        )

    # Check company limit
    current_count = await repository.get_workspace_company_count(session, workspace_id)
    if current_count >= workspace.company_limit:
        raise WorkspaceError(
            status_code=422,
            detail=(
                f"Workspace company limit reached. "
                f"Current: {current_count}, Maximum: {workspace.company_limit}"
            ),
        )

    await repository.add_company_to_workspace(session, workspace_id, company_id)

    # Return updated workspace detail
    return await get_workspace(session, workspace_id, user_id)


async def remove_company(
    session: AsyncSession,
    workspace_id: int,
    company_id: int,
    user_id: int,
) -> WorkspaceDetail:
    """Remove a company from a workspace.

    Validates:
    - Ownership (404 for non-owners)
    - Company is in the workspace (404 if not)

    Raises:
        WorkspaceError(404): If workspace not found or company not in workspace.
    """
    workspace = await repository.get_workspace_by_id_and_user(
        session, workspace_id, user_id
    )
    if not workspace:
        raise WorkspaceError(
            status_code=404,
            detail="Workspace not found",
        )

    # Check if company is in workspace
    existing = await repository.get_workspace_company(session, workspace_id, company_id)
    if not existing:
        raise WorkspaceError(
            status_code=404,
            detail="Company not found in this workspace",
        )

    await repository.remove_company_from_workspace(session, workspace_id, company_id)

    # Return updated workspace detail
    return await get_workspace(session, workspace_id, user_id)
