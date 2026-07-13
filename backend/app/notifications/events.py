"""Typed event schemas for WebSocket notifications.

All events published through the WebSocket notification system must
conform to one of these schemas. Each event has a discriminator `type`
field for client-side routing.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Literal, Union

from pydantic import BaseModel, Field


class ToastLevel(str, Enum):
    """Severity levels for toast notifications."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class ResearchStatusEvent(BaseModel):
    """Emitted when the research pipeline transitions status."""

    type: Literal["research.status"] = "research.status"
    company_id: int
    status: str
    message: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


class ComparisonStatusEvent(BaseModel):
    """Emitted when a comparison job changes status."""

    type: Literal["comparison.status"] = "comparison.status"
    workspace_id: int
    report_id: int
    status: str


class ComparisonResultEvent(BaseModel):
    """Emitted when a comparison report is ready."""

    type: Literal["comparison.result"] = "comparison.result"
    workspace_id: int
    report_id: int


class DocumentStatusEvent(BaseModel):
    """Emitted when document processing transitions status."""

    type: Literal["document.status"] = "document.status"
    document_id: int
    company_id: int
    status: str
    message: str | None = None


class ChatTokenEvent(BaseModel):
    """Emitted for each streamed token from RAG chatbot."""

    type: Literal["chat.token"] = "chat.token"
    workspace_id: int
    token: str
    done: bool


class ToastEvent(BaseModel):
    """Generic toast notification for informational messages."""

    type: Literal["toast"] = "toast"
    level: ToastLevel
    message: str


# Union of all event types for type-safe handling
WebSocketEvent = Union[
    ResearchStatusEvent,
    ComparisonStatusEvent,
    ComparisonResultEvent,
    DocumentStatusEvent,
    ChatTokenEvent,
    ToastEvent,
]

# All valid event type discriminators
EVENT_TYPES = frozenset(
    {
        "research.status",
        "comparison.status",
        "comparison.result",
        "document.status",
        "chat.token",
        "toast",
    }
)
