"""Property-based tests for chat message persistence.

# Feature: company-lens-rebuild
# Property 25: Chat Message Persistence

Validates: Requirements 11.5
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Workspace IDs
workspace_id_strategy = st.integers(min_value=1, max_value=100_000)

# User IDs
user_id_strategy = st.integers(min_value=1, max_value=100_000)

# Message content: realistic text strings (non-empty, various lengths)
message_content_strategy = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?'-\n"
    ),
    min_size=1,
    max_size=2000,
)

# Role strategy (only "user" and "assistant" are valid)
role_strategy = st.sampled_from(["user", "assistant"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_chat_message(
    msg_id: int,
    workspace_id: int,
    user_id: int,
    role: str,
    content: str,
    created_at: datetime,
):
    """Create a mock ChatMessage object with specified attributes."""
    msg = MagicMock()
    msg.id = msg_id
    msg.workspace_id = workspace_id
    msg.user_id = user_id
    msg.role = role
    msg.content = content
    msg.created_at = created_at
    return msg


def make_chat_message_factory():
    """Create a factory that produces mock ChatMessage objects, simulating
    the real ChatMessage constructor without triggering SQLAlchemy mapper.

    Returns a tuple of (factory_mock, captured_messages) where captured_messages
    is a list that collects all instantiated mock messages.
    """
    captured = []

    def factory(**kwargs):
        msg = MagicMock()
        msg.workspace_id = kwargs.get("workspace_id")
        msg.user_id = kwargs.get("user_id")
        msg.role = kwargs.get("role")
        msg.content = kwargs.get("content")
        msg.created_at = None  # Would be set by DB server_default
        captured.append(msg)
        return msg

    return factory, captured


# ===========================================================================
# Property 25: Chat Message Persistence
# ===========================================================================


@given(
    workspace_id=workspace_id_strategy,
    user_id=user_id_strategy,
    user_content=message_content_strategy,
    assistant_content=message_content_strategy,
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property25_persist_message_stores_correct_role(
    workspace_id: int,
    user_id: int,
    user_content: str,
    assistant_content: str,
) -> None:
    """Property 25: For any chat interaction, both user and assistant messages
    SHALL be persisted with the correct role ("user" / "assistant").

    **Validates: Requirements 11.5**
    """
    factory, captured = make_chat_message_factory()

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    with patch("app.chatbot.repository.ChatMessage", side_effect=factory):
        from app.chatbot.repository import persist_message

        # Persist user message
        user_msg = await persist_message(
            session=mock_session,
            workspace_id=workspace_id,
            user_id=user_id,
            role="user",
            content=user_content,
        )

        # Persist assistant message
        assistant_msg = await persist_message(
            session=mock_session,
            workspace_id=workspace_id,
            user_id=user_id,
            role="assistant",
            content=assistant_content,
        )

    # Verify roles are correct
    assert user_msg.role == "user"
    assert assistant_msg.role == "assistant"

    # Verify both messages were captured with correct roles
    assert len(captured) == 2
    assert captured[0].role == "user"
    assert captured[1].role == "assistant"


@given(
    workspace_id=workspace_id_strategy,
    user_id=user_id_strategy,
    user_content=message_content_strategy,
    assistant_content=message_content_strategy,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property25_persist_message_stores_correct_content(
    workspace_id: int,
    user_id: int,
    user_content: str,
    assistant_content: str,
) -> None:
    """Property 25: For any chat interaction, both messages SHALL be persisted
    with their exact original content preserved.

    **Validates: Requirements 11.5**
    """
    factory, captured = make_chat_message_factory()

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    with patch("app.chatbot.repository.ChatMessage", side_effect=factory):
        from app.chatbot.repository import persist_message

        # Persist user message
        user_msg = await persist_message(
            session=mock_session,
            workspace_id=workspace_id,
            user_id=user_id,
            role="user",
            content=user_content,
        )

        # Persist assistant message
        assistant_msg = await persist_message(
            session=mock_session,
            workspace_id=workspace_id,
            user_id=user_id,
            role="assistant",
            content=assistant_content,
        )

    # Verify content is preserved exactly
    assert user_msg.content == user_content
    assert assistant_msg.content == assistant_content


@given(
    workspace_id=workspace_id_strategy,
    user_id=user_id_strategy,
    user_content=message_content_strategy,
    assistant_content=message_content_strategy,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property25_persist_message_correct_workspace_association(
    workspace_id: int,
    user_id: int,
    user_content: str,
    assistant_content: str,
) -> None:
    """Property 25: For any chat interaction, both messages SHALL be associated
    with the correct workspace.

    **Validates: Requirements 11.5**
    """
    factory, captured = make_chat_message_factory()

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    with patch("app.chatbot.repository.ChatMessage", side_effect=factory):
        from app.chatbot.repository import persist_message

        # Persist user message
        user_msg = await persist_message(
            session=mock_session,
            workspace_id=workspace_id,
            user_id=user_id,
            role="user",
            content=user_content,
        )

        # Persist assistant message
        assistant_msg = await persist_message(
            session=mock_session,
            workspace_id=workspace_id,
            user_id=user_id,
            role="assistant",
            content=assistant_content,
        )

    # Both messages must be associated with the correct workspace
    assert user_msg.workspace_id == workspace_id
    assert assistant_msg.workspace_id == workspace_id


@given(
    workspace_id=workspace_id_strategy,
    user_id=user_id_strategy,
    num_interactions=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property25_get_history_returns_chronological_order(
    workspace_id: int,
    user_id: int,
    num_interactions: int,
) -> None:
    """Property 25: get_history SHALL return messages in chronological order
    (oldest first), maintaining the ordering user -> assistant for each
    interaction pair.

    **Validates: Requirements 11.5**
    """
    from app.chatbot.repository import get_history

    # Create mock messages in chronological order (user, assistant pairs)
    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    messages = []
    for i in range(num_interactions):
        # User message
        user_msg = make_mock_chat_message(
            msg_id=i * 2 + 1,
            workspace_id=workspace_id,
            user_id=user_id,
            role="user",
            content=f"User question {i}",
            created_at=base_time + timedelta(minutes=i * 2),
        )
        messages.append(user_msg)

        # Assistant response (comes after user message)
        assistant_msg = make_mock_chat_message(
            msg_id=i * 2 + 2,
            workspace_id=workspace_id,
            user_id=user_id,
            role="assistant",
            content=f"Assistant response {i}",
            created_at=base_time + timedelta(minutes=i * 2 + 1),
        )
        messages.append(assistant_msg)

    # get_history queries DESC then reverses, so mock the DB returning DESC order
    messages_desc = list(reversed(messages))

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = messages_desc
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await get_history(session=mock_session, workspace_id=workspace_id)

    # Result should be in chronological order (oldest first)
    assert len(result) == num_interactions * 2

    # Verify chronological ordering: each message's created_at <= next message's
    for i in range(len(result) - 1):
        assert result[i].created_at <= result[i + 1].created_at, (
            f"Messages not in chronological order at index {i}: "
            f"{result[i].created_at} > {result[i + 1].created_at}"
        )

    # Verify alternating roles: user, assistant, user, assistant...
    for i in range(0, len(result), 2):
        assert result[i].role == "user", (
            f"Expected 'user' at index {i}, got '{result[i].role}'"
        )
        assert result[i + 1].role == "assistant", (
            f"Expected 'assistant' at index {i+1}, got '{result[i + 1].role}'"
        )


@given(
    workspace_id=workspace_id_strategy,
    user_id=user_id_strategy,
    user_content=message_content_strategy,
    assistant_content=message_content_strategy,
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property25_user_message_created_before_assistant(
    workspace_id: int,
    user_id: int,
    user_content: str,
    assistant_content: str,
) -> None:
    """Property 25: In any chat interaction, the user message SHALL be persisted
    before the assistant message (chronological ordering guaranteed by sequential
    persist_message calls — user message always has earlier created_at).

    **Validates: Requirements 11.5**
    """
    call_order = []
    factory_calls = []

    def factory(**kwargs):
        msg = MagicMock()
        msg.workspace_id = kwargs.get("workspace_id")
        msg.user_id = kwargs.get("user_id")
        msg.role = kwargs.get("role")
        msg.content = kwargs.get("content")
        factory_calls.append(msg)
        return msg

    mock_session = AsyncMock()

    def track_add(obj):
        call_order.append(obj.role)

    mock_session.add = track_add
    mock_session.flush = AsyncMock()

    with patch("app.chatbot.repository.ChatMessage", side_effect=factory):
        from app.chatbot.repository import persist_message

        # Persist user message first (as the service does)
        user_msg = await persist_message(
            session=mock_session,
            workspace_id=workspace_id,
            user_id=user_id,
            role="user",
            content=user_content,
        )

        # Then persist assistant message
        assistant_msg = await persist_message(
            session=mock_session,
            workspace_id=workspace_id,
            user_id=user_id,
            role="assistant",
            content=assistant_content,
        )

    # User message is always added first (guaranteeing earlier created_at)
    assert call_order == ["user", "assistant"]
    # The service always persists user message before assistant
    assert user_msg.role == "user"
    assert assistant_msg.role == "assistant"


@given(
    workspace_id=workspace_id_strategy,
    user_id=user_id_strategy,
    messages_data=st.lists(
        st.tuples(role_strategy, message_content_strategy),
        min_size=1,
        max_size=20,
    ),
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property25_all_messages_persist_with_correct_workspace(
    workspace_id: int,
    user_id: int,
    messages_data: list[tuple[str, str]],
) -> None:
    """Property 25: For any sequence of messages persisted to a workspace,
    ALL messages SHALL be associated with that specific workspace_id.

    **Validates: Requirements 11.5**
    """
    captured = []

    def factory(**kwargs):
        msg = MagicMock()
        msg.workspace_id = kwargs.get("workspace_id")
        msg.user_id = kwargs.get("user_id")
        msg.role = kwargs.get("role")
        msg.content = kwargs.get("content")
        captured.append(msg)
        return msg

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    with patch("app.chatbot.repository.ChatMessage", side_effect=factory):
        from app.chatbot.repository import persist_message

        for role, content in messages_data:
            await persist_message(
                session=mock_session,
                workspace_id=workspace_id,
                user_id=user_id,
                role=role,
                content=content,
            )

    # Every persisted message must have the correct workspace_id
    assert len(captured) == len(messages_data)
    for msg in captured:
        assert msg.workspace_id == workspace_id


@given(
    workspace_id=workspace_id_strategy,
    user_id=user_id_strategy,
    limit=st.integers(min_value=1, max_value=100),
    total_messages=st.integers(min_value=0, max_value=50),
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property25_get_history_respects_limit(
    workspace_id: int,
    user_id: int,
    limit: int,
    total_messages: int,
) -> None:
    """Property 25: get_history SHALL return at most `limit` messages,
    even if more messages exist in the workspace.

    **Validates: Requirements 11.5**
    """
    from app.chatbot.repository import get_history

    # Create mock messages (simulate DB returning at most `limit` messages)
    returned_count = min(total_messages, limit)
    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    messages_desc = [
        make_mock_chat_message(
            msg_id=i + 1,
            workspace_id=workspace_id,
            user_id=user_id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"Message {i}",
            created_at=base_time + timedelta(minutes=returned_count - 1 - i),
        )
        for i in range(returned_count)
    ]

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = messages_desc
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await get_history(
        session=mock_session, workspace_id=workspace_id, limit=limit
    )

    # Result should not exceed limit
    assert len(result) <= limit
    # Result should be the number actually available (up to limit)
    assert len(result) == returned_count
