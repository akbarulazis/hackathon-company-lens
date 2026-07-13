"""Tests for the WebSocket notification system.

Tests cover:
- Event schema creation and serialization
- ConnectionManager operations (connect, disconnect, publish, replay)
- WebSocket endpoint authentication (JWT validation)
- Event storage with TTL for missed delivery
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.notifications.events import (
    EVENT_TYPES,
    ChatTokenEvent,
    ComparisonResultEvent,
    ComparisonStatusEvent,
    DocumentStatusEvent,
    ResearchStatusEvent,
    ToastEvent,
    ToastLevel,
)
from app.notifications.manager import (
    CHANNEL_PREFIX,
    EVENT_TTL_SECONDS,
    EVENTS_PREFIX,
    ConnectionManager,
)


class TestEventSchemas:
    """Test typed event schema creation and serialization."""

    def test_research_status_event_has_required_fields(self):
        event = ResearchStatusEvent(
            company_id=1,
            status="researching",
            message="Crawling web sources",
        )
        assert event.type == "research.status"
        assert event.company_id == 1
        assert event.status == "researching"
        assert event.message == "Crawling web sources"
        assert event.timestamp is not None

    def test_research_status_event_serializes_to_json(self):
        event = ResearchStatusEvent(
            company_id=42,
            status="profiling",
            message="Generating acquisition brief",
            timestamp="2024-01-15T10:30:00Z",
        )
        data = json.loads(event.model_dump_json())
        assert data["type"] == "research.status"
        assert data["company_id"] == 42
        assert data["status"] == "profiling"
        assert data["message"] == "Generating acquisition brief"
        assert data["timestamp"] == "2024-01-15T10:30:00Z"

    def test_comparison_status_event(self):
        event = ComparisonStatusEvent(
            workspace_id=5,
            report_id=10,
            status="processing",
        )
        assert event.type == "comparison.status"
        assert event.workspace_id == 5
        assert event.report_id == 10
        assert event.status == "processing"

    def test_comparison_result_event(self):
        event = ComparisonResultEvent(
            workspace_id=3,
            report_id=7,
        )
        assert event.type == "comparison.result"
        assert event.workspace_id == 3
        assert event.report_id == 7

    def test_document_status_event_without_message(self):
        event = DocumentStatusEvent(
            document_id=1,
            company_id=2,
            status="processing",
        )
        assert event.type == "document.status"
        assert event.document_id == 1
        assert event.company_id == 2
        assert event.status == "processing"
        assert event.message is None

    def test_document_status_event_with_message(self):
        event = DocumentStatusEvent(
            document_id=1,
            company_id=2,
            status="failed",
            message="PDF extraction failed",
        )
        assert event.message == "PDF extraction failed"

    def test_chat_token_event(self):
        event = ChatTokenEvent(
            workspace_id=4,
            token="Hello",
            done=False,
        )
        assert event.type == "chat.token"
        assert event.workspace_id == 4
        assert event.token == "Hello"
        assert event.done is False

    def test_chat_token_event_done(self):
        event = ChatTokenEvent(
            workspace_id=4,
            token="",
            done=True,
        )
        assert event.done is True

    def test_toast_event_info(self):
        event = ToastEvent(
            level=ToastLevel.INFO,
            message="Research started",
        )
        assert event.type == "toast"
        assert event.level == ToastLevel.INFO
        assert event.message == "Research started"

    def test_toast_event_error(self):
        event = ToastEvent(
            level=ToastLevel.ERROR,
            message="Pipeline failed",
        )
        assert event.level == ToastLevel.ERROR

    def test_toast_event_success(self):
        event = ToastEvent(level=ToastLevel.SUCCESS, message="Done")
        assert event.level == ToastLevel.SUCCESS

    def test_toast_event_warning(self):
        event = ToastEvent(level=ToastLevel.WARNING, message="Slow")
        assert event.level == ToastLevel.WARNING

    def test_all_event_types_are_registered(self):
        assert "research.status" in EVENT_TYPES
        assert "comparison.status" in EVENT_TYPES
        assert "comparison.result" in EVENT_TYPES
        assert "document.status" in EVENT_TYPES
        assert "chat.token" in EVENT_TYPES
        assert "toast" in EVENT_TYPES
        assert len(EVENT_TYPES) == 6


class TestConnectionManager:
    """Test ConnectionManager operations with mocked Redis."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.publish = AsyncMock(return_value=1)
        redis.lpush = AsyncMock()
        redis.expire = AsyncMock()
        redis.lrange = AsyncMock(return_value=[])
        # Mock pubsub
        pubsub = AsyncMock()
        pubsub.subscribe = AsyncMock()
        pubsub.unsubscribe = AsyncMock()
        pubsub.aclose = AsyncMock()
        pubsub.listen = MagicMock(return_value=AsyncIteratorMock([]))
        redis.pubsub = MagicMock(return_value=pubsub)
        return redis

    @pytest.fixture
    def manager(self, mock_redis):
        return ConnectionManager(mock_redis)

    @pytest.fixture
    def mock_websocket(self):
        ws = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    async def test_connect_adds_websocket_to_connections(self, manager, mock_websocket):
        await manager.connect(1, mock_websocket)
        assert mock_websocket in manager.active_connections[1]

    async def test_connect_multiple_websockets_for_same_user(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await manager.connect(1, ws1)
        await manager.connect(1, ws2)
        assert ws1 in manager.active_connections[1]
        assert ws2 in manager.active_connections[1]
        assert len(manager.active_connections[1]) == 2

    async def test_disconnect_removes_websocket(self, manager, mock_websocket):
        await manager.connect(1, mock_websocket)
        await manager.disconnect(1, mock_websocket)
        assert 1 not in manager.active_connections

    async def test_disconnect_keeps_other_connections(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await manager.connect(1, ws1)
        await manager.connect(1, ws2)
        await manager.disconnect(1, ws1)
        assert ws2 in manager.active_connections[1]
        assert ws1 not in manager.active_connections[1]

    async def test_publish_sends_to_redis_channel(self, manager, mock_redis):
        event = ResearchStatusEvent(
            company_id=1,
            status="researching",
            message="Starting",
            timestamp="2024-01-15T10:30:00Z",
        )
        await manager.publish(42, event)

        channel = f"{CHANNEL_PREFIX}42"
        mock_redis.publish.assert_called_once_with(channel, event.model_dump_json())

    async def test_publish_stores_event_in_list(self, manager, mock_redis):
        event = ToastEvent(level=ToastLevel.INFO, message="Hello")
        await manager.publish(7, event)

        events_key = f"{EVENTS_PREFIX}7"
        mock_redis.lpush.assert_called_once_with(events_key, event.model_dump_json())

    async def test_publish_sets_ttl_on_events_list(self, manager, mock_redis):
        event = ToastEvent(level=ToastLevel.SUCCESS, message="Done")
        await manager.publish(7, event)

        events_key = f"{EVENTS_PREFIX}7"
        mock_redis.expire.assert_called_once_with(events_key, EVENT_TTL_SECONDS)

    async def test_get_missed_events_returns_chronological_order(self, manager, mock_redis):
        # Redis LRANGE returns newest first (from LPUSH)
        mock_redis.lrange.return_value = ["event3", "event2", "event1"]
        events = await manager.get_missed_events(5)
        # Should be reversed to chronological order
        assert events == ["event1", "event2", "event3"]

    async def test_get_missed_events_empty_when_no_events(self, manager, mock_redis):
        mock_redis.lrange.return_value = []
        events = await manager.get_missed_events(5)
        assert events == []

    async def test_replay_missed_events_sends_to_websocket(self, manager, mock_redis, mock_websocket):
        mock_redis.lrange.return_value = ['{"type":"toast","level":"info","message":"hi"}']
        await manager.replay_missed_events(1, mock_websocket)
        mock_websocket.send_text.assert_called_once_with('{"type":"toast","level":"info","message":"hi"}')

    async def test_replay_missed_events_stops_on_send_error(self, manager, mock_redis):
        ws = AsyncMock()
        ws.send_text = AsyncMock(side_effect=Exception("connection closed"))
        mock_redis.lrange.return_value = ["event1", "event2"]
        # Should not raise, just stop
        await manager.replay_missed_events(1, ws)

    async def test_event_ttl_is_300_seconds(self):
        assert EVENT_TTL_SECONDS == 300


class TestWebSocketAuthentication:
    """Test JWT authentication for WebSocket connections."""

    def test_decode_valid_token(self):
        """Valid JWT with 'sub' claim returns user_id."""
        from jose import jwt as jose_jwt

        secret = "test-secret"
        token = jose_jwt.encode({"sub": "42"}, secret, algorithm="HS256")

        with patch("app.notifications.router.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(SECRET_KEY=secret)
            from app.notifications.router import _decode_ws_token
            result = _decode_ws_token(token)

        assert result == 42

    def test_decode_invalid_token_returns_none(self):
        """Invalid JWT returns None."""
        with patch("app.notifications.router.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(SECRET_KEY="test-secret")
            from app.notifications.router import _decode_ws_token
            result = _decode_ws_token("invalid.token.here")

        assert result is None

    def test_decode_token_missing_sub_returns_none(self):
        """JWT without 'sub' claim returns None."""
        from jose import jwt as jose_jwt

        secret = "test-secret"
        token = jose_jwt.encode({"user": "42"}, secret, algorithm="HS256")

        with patch("app.notifications.router.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(SECRET_KEY=secret)
            from app.notifications.router import _decode_ws_token
            result = _decode_ws_token(token)

        assert result is None

    def test_decode_token_wrong_secret_returns_none(self):
        """JWT signed with wrong secret returns None."""
        from jose import jwt as jose_jwt

        token = jose_jwt.encode({"sub": "42"}, "wrong-secret", algorithm="HS256")

        with patch("app.notifications.router.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(SECRET_KEY="correct-secret")
            from app.notifications.router import _decode_ws_token
            result = _decode_ws_token(token)

        assert result is None

    def test_decode_empty_token_returns_none(self):
        """Empty string token returns None."""
        with patch("app.notifications.router.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(SECRET_KEY="test-secret")
            from app.notifications.router import _decode_ws_token
            result = _decode_ws_token("")

        assert result is None


class AsyncIteratorMock:
    """Mock for async iterator (Redis pubsub.listen())."""

    def __init__(self, items):
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration
