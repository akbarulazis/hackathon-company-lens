"""Chatbot repository layer.

Provides database operations for persisting and retrieving chat messages
per workspace. No business logic — only data access.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chatbot.models import ChatMessage


async def persist_message(
    session: AsyncSession,
    workspace_id: int,
    user_id: int,
    role: str,
    content: str,
) -> ChatMessage:
    """Persist a single chat message (user or assistant).

    Args:
        session: Async SQLAlchemy session.
        workspace_id: The workspace this message belongs to.
        user_id: The user who initiated the conversation.
        role: Message role — "user" or "assistant".
        content: The message text content.

    Returns:
        The persisted ChatMessage instance.
    """
    message = ChatMessage(
        workspace_id=workspace_id,
        user_id=user_id,
        role=role,
        content=content,
    )
    session.add(message)
    await session.flush()
    return message


async def get_history(
    session: AsyncSession,
    workspace_id: int,
    limit: int = 50,
) -> list[ChatMessage]:
    """Retrieve chat history for a workspace, ordered chronologically.

    Returns the most recent messages up to the limit, sorted by
    creation time ascending (oldest first) for display.

    Args:
        session: Async SQLAlchemy session.
        workspace_id: The workspace to retrieve history for.
        limit: Maximum number of messages to return (default 50).

    Returns:
        List of ChatMessage objects in chronological order.
    """
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.workspace_id == workspace_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    messages = list(result.scalars().all())
    # Reverse to get chronological order (oldest first)
    messages.reverse()
    return messages


async def get_recent_messages(
    session: AsyncSession,
    workspace_id: int,
    limit: int = 5,
) -> list[ChatMessage]:
    """Retrieve the most recent chat messages for context building.

    Used to provide conversation history to the LLM for continuity.
    Returns messages in chronological order (oldest first).

    Args:
        session: Async SQLAlchemy session.
        workspace_id: The workspace to retrieve messages for.
        limit: Maximum number of recent messages (default 5).

    Returns:
        List of the most recent ChatMessage objects in chronological order.
    """
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.workspace_id == workspace_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    messages = list(result.scalars().all())
    # Reverse to get chronological order (oldest first)
    messages.reverse()
    return messages
