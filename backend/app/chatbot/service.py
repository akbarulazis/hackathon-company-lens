"""Chatbot service layer.

Orchestrates the RAG chatbot flow: checks workspace state, generates
query embeddings, retrieves similar chunks, invokes the LLM with context,
persists messages, and streams response tokens via WebSocket.
"""

import logging

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.chatbot import repository as chat_repo
from app.chatbot.embeddings import generate_embeddings, search_similar_chunks
from app.config import Settings
from app.llm.client import LLMClientError
from app.llm.prompts.chatbot import (
    build_chatbot_prompt,
    build_chatbot_system_prompt,
)
from app.notifications.events import ChatTokenEvent
from app.notifications.manager import get_notification_manager
from app.workspaces.repository import get_workspace_company_count

logger = logging.getLogger(__name__)

CANNED_NO_COMPANIES = (
    "This workspace doesn't have any companies yet. "
    "Add companies to your workspace first, and I'll be able to answer "
    "questions about them based on their research data."
)

LLM_ERROR_MESSAGE = (
    "I'm sorry, but I'm temporarily unable to generate a response. "
    "Please try again in a moment."
)

DEFAULT_MODEL = "gpt-4o-mini"


async def process_message(
    session: AsyncSession,
    workspace_id: int,
    user_id: int,
    message: str,
    settings: Settings,
) -> str:
    """Process a user chat message with RAG retrieval and LLM generation.

    Flow:
    1. Check if workspace has companies (canned response if not)
    2. Persist the user message
    3. Generate embedding for the user's question
    4. Search similar chunks in the workspace
    5. Retrieve last 5 messages for conversation history
    6. Invoke LLM with streaming, publishing tokens via WebSocket
    7. Persist the assistant response

    Args:
        session: Async SQLAlchemy session.
        workspace_id: The workspace to query against.
        user_id: The authenticated user's ID.
        message: The user's question text.
        settings: Application settings (API keys, etc).

    Returns:
        The complete assistant response text.
    """
    # Step 1: Check if workspace has companies
    company_count = await get_workspace_company_count(session, workspace_id)
    if company_count == 0:
        # Persist user message and canned response
        await chat_repo.persist_message(
            session, workspace_id, user_id, "user", message
        )
        await chat_repo.persist_message(
            session, workspace_id, user_id, "assistant", CANNED_NO_COMPANIES
        )
        # Stream the canned response via WebSocket
        await _stream_text_via_websocket(
            user_id, workspace_id, CANNED_NO_COMPANIES
        )
        return CANNED_NO_COMPANIES

    # Step 2: Persist user message
    await chat_repo.persist_message(
        session, workspace_id, user_id, "user", message
    )

    # Step 3: Generate query embedding
    try:
        embeddings = await generate_embeddings([message], settings)
        query_embedding = embeddings[0]
    except Exception:
        logger.exception("Failed to generate query embedding")
        await chat_repo.persist_message(
            session, workspace_id, user_id, "assistant", LLM_ERROR_MESSAGE
        )
        await _stream_text_via_websocket(
            user_id, workspace_id, LLM_ERROR_MESSAGE
        )
        return LLM_ERROR_MESSAGE

    # Step 4: Search similar chunks
    context_chunks = await search_similar_chunks(
        session, query_embedding, workspace_id
    )

    # Step 5: Get recent chat history (last 5 messages before the current one)
    chat_history = await chat_repo.get_recent_messages(
        session, workspace_id, limit=5
    )
    # Exclude the message we just persisted (last item) from history context
    # since it's the current question
    if chat_history and chat_history[-1].role == "user" and chat_history[-1].content == message:
        chat_history = chat_history[:-1]

    # Step 6: Build prompts and invoke LLM with streaming
    system_prompt = build_chatbot_system_prompt()
    user_prompt = build_chatbot_prompt(message, context_chunks, chat_history)

    try:
        response_text = await _stream_llm_response(
            settings=settings,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            user_id=user_id,
            workspace_id=workspace_id,
        )
    except Exception:
        logger.exception("LLM generation failed for workspace_id=%d", workspace_id)
        await chat_repo.persist_message(
            session, workspace_id, user_id, "assistant", LLM_ERROR_MESSAGE
        )
        await _stream_text_via_websocket(
            user_id, workspace_id, LLM_ERROR_MESSAGE
        )
        return LLM_ERROR_MESSAGE

    # Step 7: Persist assistant response
    await chat_repo.persist_message(
        session, workspace_id, user_id, "assistant", response_text
    )

    return response_text


async def _stream_llm_response(
    settings: Settings,
    system_prompt: str,
    user_prompt: str,
    user_id: int,
    workspace_id: int,
) -> str:
    """Stream LLM response tokens via WebSocket and return full text.

    Uses OpenAI streaming API to emit chat.token events for each
    token as it's generated, then sends a final done=True event.

    Args:
        settings: Application settings with API key.
        system_prompt: The system prompt.
        user_prompt: The user prompt with context.
        user_id: User ID for WebSocket targeting.
        workspace_id: Workspace ID for the event payload.

    Returns:
        The complete generated response text.

    Raises:
        LLMClientError: If the OpenAI API call fails.
    """
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    manager = get_notification_manager()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    collected_tokens: list[str] = []

    try:
        stream = await client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            max_tokens=2048,
            temperature=0.3,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                collected_tokens.append(token)

                # Publish token via WebSocket
                event = ChatTokenEvent(
                    workspace_id=workspace_id,
                    token=token,
                    done=False,
                )
                await manager.publish(user_id, event)

        # Send done signal
        done_event = ChatTokenEvent(
            workspace_id=workspace_id,
            token="",
            done=True,
        )
        await manager.publish(user_id, done_event)

    except Exception as e:
        logger.error("OpenAI streaming error: %s", e)
        raise LLMClientError(f"Streaming failed: {e}") from e

    return "".join(collected_tokens)


async def _stream_text_via_websocket(
    user_id: int,
    workspace_id: int,
    text: str,
) -> None:
    """Stream a pre-built text response via WebSocket as a single token + done.

    Used for canned responses and error messages that don't need
    actual LLM streaming but should still arrive via the same channel.

    Args:
        user_id: User ID for WebSocket targeting.
        workspace_id: Workspace ID for the event payload.
        text: The full text to send.
    """
    try:
        manager = get_notification_manager()
        # Send the full text as one token
        event = ChatTokenEvent(
            workspace_id=workspace_id,
            token=text,
            done=False,
        )
        await manager.publish(user_id, event)

        # Send done signal
        done_event = ChatTokenEvent(
            workspace_id=workspace_id,
            token="",
            done=True,
        )
        await manager.publish(user_id, done_event)
    except Exception:
        # Don't fail the request if WebSocket publishing fails
        logger.warning(
            "Failed to stream text via WebSocket for user_id=%d", user_id
        )
