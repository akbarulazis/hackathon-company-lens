"""Chatbot API router.

Provides REST endpoints for submitting chat messages and retrieving
conversation history within a workspace. All endpoints require
authentication and workspace ownership verification.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.chatbot import repository as chat_repo
from app.chatbot.schemas import (
    ChatHistoryResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatResponse,
)
from app.chatbot.service import process_message
from app.config import Settings
from app.dependencies import get_cached_settings, get_db
from app.workspaces.service import WorkspaceError, get_workspace

router = APIRouter(prefix="/api/workspaces", tags=["chatbot"])


@router.post(
    "/{workspace_id}/chat",
    response_model=ChatResponse,
)
async def submit_chat_message(
    workspace_id: int,
    data: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_cached_settings),
) -> ChatResponse:
    """Submit a chat message and receive an AI-generated response.

    The response is also streamed via WebSocket (chat.token events)
    for real-time display. This endpoint returns the complete response
    once generation is finished.

    Requires workspace ownership. Returns 404 if workspace not found
    or not owned by the authenticated user.
    """
    # Verify workspace ownership
    try:
        await get_workspace(session, workspace_id, current_user.id)
    except WorkspaceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    # Process the message through RAG pipeline
    response_text = await process_message(
        session=session,
        workspace_id=workspace_id,
        user_id=current_user.id,
        message=data.message,
        settings=settings,
    )

    return ChatResponse(response=response_text)


@router.get(
    "/{workspace_id}/chat/history",
    response_model=ChatHistoryResponse,
)
async def get_chat_history(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ChatHistoryResponse:
    """Retrieve conversation history for a workspace.

    Returns up to 50 most recent messages in chronological order.
    Requires workspace ownership. Returns 404 if workspace not found
    or not owned by the authenticated user.
    """
    # Verify workspace ownership
    try:
        await get_workspace(session, workspace_id, current_user.id)
    except WorkspaceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    messages = await chat_repo.get_history(session, workspace_id)

    return ChatHistoryResponse(
        messages=[
            ChatMessageResponse(
                id=msg.id,
                workspace_id=msg.workspace_id,
                user_id=msg.user_id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
            )
            for msg in messages
        ]
    )
