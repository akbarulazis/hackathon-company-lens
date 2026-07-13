"""Workspace repository layer.

Provides database operations for workspaces, workspace-company associations,
and cascade delete logic. No business logic — only data access.
"""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.chatbot.models import ChatMessage
from app.companies.models import CompanyProfile
from app.documents.models import TextChunk
from app.workspaces.models import ComparisonReport, Workspace, WorkspaceCompany


async def get_workspace_by_id(
    session: AsyncSession, workspace_id: int
) -> Workspace | None:
    """Fetch a workspace by primary key."""
    result = await session.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    return result.scalar_one_or_none()


async def get_workspace_by_id_and_user(
    session: AsyncSession, workspace_id: int, user_id: int
) -> Workspace | None:
    """Fetch a workspace by ID only if owned by the given user."""
    result = await session.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_workspace_by_name_and_user(
    session: AsyncSession, name: str, user_id: int
) -> Workspace | None:
    """Fetch a workspace by name for a specific user (duplicate check)."""
    result = await session.execute(
        select(Workspace).where(
            Workspace.name == name,
            Workspace.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def list_workspaces_for_user(
    session: AsyncSession, user_id: int
) -> list[Workspace]:
    """List all workspaces owned by a user."""
    result = await session.execute(
        select(Workspace)
        .where(Workspace.user_id == user_id)
        .order_by(Workspace.created_at.desc())
    )
    return list(result.scalars().all())


async def get_workspace_company_count(
    session: AsyncSession, workspace_id: int
) -> int:
    """Count the number of companies in a workspace."""
    result = await session.execute(
        select(func.count())
        .select_from(WorkspaceCompany)
        .where(WorkspaceCompany.workspace_id == workspace_id)
    )
    return result.scalar_one()


async def create_workspace(
    session: AsyncSession,
    user_id: int,
    name: str,
    company_limit: int,
) -> Workspace:
    """Create a new workspace."""
    workspace = Workspace(
        user_id=user_id,
        name=name,
        company_limit=company_limit,
    )
    session.add(workspace)
    await session.flush()
    return workspace


async def update_workspace_name(
    session: AsyncSession, workspace: Workspace, name: str
) -> Workspace:
    """Update the name of an existing workspace."""
    workspace.name = name
    await session.flush()
    return workspace


async def delete_workspace(session: AsyncSession, workspace: Workspace) -> None:
    """Delete a workspace and cascade-delete related data.

    Removes: workspace-company associations, text chunks scoped to workspace,
    chat messages, and comparison reports.
    The workspace itself is deleted last.
    Company profiles are preserved (they may belong to other workspaces).
    """
    workspace_id = workspace.id

    # Delete text chunks scoped to this workspace
    await session.execute(
        delete(TextChunk).where(TextChunk.workspace_id == workspace_id)
    )

    # Delete chat messages for this workspace
    await session.execute(
        delete(ChatMessage).where(ChatMessage.workspace_id == workspace_id)
    )

    # Delete comparison reports for this workspace
    await session.execute(
        delete(ComparisonReport).where(ComparisonReport.workspace_id == workspace_id)
    )

    # Delete workspace-company associations
    await session.execute(
        delete(WorkspaceCompany).where(WorkspaceCompany.workspace_id == workspace_id)
    )

    # Delete the workspace itself
    await session.delete(workspace)
    await session.flush()


async def get_workspace_company(
    session: AsyncSession, workspace_id: int, company_id: int
) -> WorkspaceCompany | None:
    """Check if a company is already in a workspace."""
    result = await session.execute(
        select(WorkspaceCompany).where(
            WorkspaceCompany.workspace_id == workspace_id,
            WorkspaceCompany.company_id == company_id,
        )
    )
    return result.scalar_one_or_none()


async def add_company_to_workspace(
    session: AsyncSession, workspace_id: int, company_id: int
) -> WorkspaceCompany:
    """Add a company to a workspace."""
    association = WorkspaceCompany(
        workspace_id=workspace_id,
        company_id=company_id,
    )
    session.add(association)
    await session.flush()
    return association


async def remove_company_from_workspace(
    session: AsyncSession, workspace_id: int, company_id: int
) -> None:
    """Remove a company from a workspace."""
    await session.execute(
        delete(WorkspaceCompany).where(
            WorkspaceCompany.workspace_id == workspace_id,
            WorkspaceCompany.company_id == company_id,
        )
    )
    await session.flush()


async def get_workspace_companies(
    session: AsyncSession, workspace_id: int
) -> list[tuple[CompanyProfile, WorkspaceCompany]]:
    """Get all companies in a workspace with their association data."""
    result = await session.execute(
        select(CompanyProfile, WorkspaceCompany)
        .join(
            WorkspaceCompany,
            CompanyProfile.id == WorkspaceCompany.company_id,
        )
        .where(WorkspaceCompany.workspace_id == workspace_id)
        .order_by(WorkspaceCompany.added_at.desc())
    )
    return list(result.tuples().all())
