"""Chatbot request/response schemas.

Pydantic models for the chatbot endpoints including message submission
and conversation history retrieval.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    """Request body for submitting a chat message."""

    message: str = Field(..., min_length=1, max_length=2000)


class ChatMessageResponse(BaseModel):
    """Response for a single chat message."""

    id: int
    workspace_id: int
    user_id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    """Response after processing a chat message."""

    response: str


class ChatHistoryResponse(BaseModel):
    """Response containing conversation history."""

    messages: list[ChatMessageResponse]
