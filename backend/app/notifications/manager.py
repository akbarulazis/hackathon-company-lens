"""WebSocket connection manager with Redis Pub/Sub per-user channels.

Manages active WebSocket connections per user and uses Redis Pub/Sub
to deliver typed events. Events are also stored in a Redis list with
a 5-minute TTL for replay on reconnection.
"""

import asyncio
import json
import logging
from collections import defaultdict

from fastapi import WebSocket
from redis.asyncio import Redis

from app.notifications.events import WebSocketEvent

logger = logging.getLogger(__name__)

# Redis key patterns
CHANNEL_PREFIX = "ws:user:"
EVENTS_PREFIX = "ws:events:"
EVENT_TTL_SECONDS = 300  # 5 minutes


class ConnectionManager:
    """Manages per-user WebSocket connections backed by Redis Pub/Sub.

    Each user gets a dedicated Redis Pub/Sub channel. Events published
    to the channel are forwarded to all active WebSocket connections
    for that user. Events are also stored in a Redis list for replay
    on reconnection (5-minute TTL).
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._subscriber_tasks: dict[int, asyncio.Task] = {}

    @property
    def active_connections(self) -> dict[int, set[WebSocket]]:
        """Expose active connections (read-only access for testing)."""
        return self._connections

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        """Register a WebSocket connection for a user.

        Adds the connection to the active set. If this is the first
        connection for the user, starts a Redis subscriber task.
        """
        self._connections[user_id].add(websocket)
        logger.info("WebSocket connected for user_id=%d (total=%d)", user_id, len(self._connections[user_id]))

        # Start subscriber if not already running for this user
        if user_id not in self._subscriber_tasks or self._subscriber_tasks[user_id].done():
            task = asyncio.create_task(self._subscribe_and_forward(user_id))
            self._subscriber_tasks[user_id] = task

    async def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        """Remove a WebSocket connection for a user.

        If this was the last connection for the user, cancels the
        Redis subscriber task.
        """
        self._connections[user_id].discard(websocket)
        logger.info("WebSocket disconnected for user_id=%d (remaining=%d)", user_id, len(self._connections[user_id]))

        # Cancel subscriber if no more connections for this user
        if not self._connections[user_id]:
            del self._connections[user_id]
            task = self._subscriber_tasks.pop(user_id, None)
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def publish(self, user_id: int, event: WebSocketEvent) -> None:
        """Publish a typed event to a user's channel.

        Serializes the event as JSON, publishes to the user's Redis
        Pub/Sub channel, and stores it in a Redis list for replay
        on reconnection (5-minute TTL).
        """
        channel = f"{CHANNEL_PREFIX}{user_id}"
        events_key = f"{EVENTS_PREFIX}{user_id}"
        payload = event.model_dump_json()

        # Publish to Pub/Sub channel for immediate delivery
        await self._redis.publish(channel, payload)

        # Store in list for replay on reconnection (LPUSH + EXPIRE)
        await self._redis.lpush(events_key, payload)
        await self._redis.expire(events_key, EVENT_TTL_SECONDS)

        logger.debug("Published event type=%s to user_id=%d", event.type, user_id)

    async def get_missed_events(self, user_id: int) -> list[str]:
        """Retrieve stored events for replay on reconnection.

        Returns all events in the user's Redis list (within 5-min TTL).
        Events are returned in chronological order (oldest first).
        """
        events_key = f"{EVENTS_PREFIX}{user_id}"
        # LRANGE returns newest first (LPUSH), so reverse for chronological order
        events = await self._redis.lrange(events_key, 0, -1)
        return list(reversed(events))

    async def replay_missed_events(self, user_id: int, websocket: WebSocket) -> None:
        """Send any stored events to a newly connected WebSocket.

        Replays events from the Redis list that were published during
        the disconnection period (up to 5 minutes).
        """
        events = await self.get_missed_events(user_id)
        for event_payload in events:
            try:
                await websocket.send_text(event_payload)
            except Exception:
                logger.warning("Failed to replay event to user_id=%d", user_id)
                break

    async def _subscribe_and_forward(self, user_id: int) -> None:
        """Subscribe to a user's Redis Pub/Sub channel and forward events.

        Runs as a background asyncio task. Listens on the user's
        channel and forwards each message to all active WebSocket
        connections for that user.
        """
        channel = f"{CHANNEL_PREFIX}{user_id}"
        pubsub = self._redis.pubsub()

        try:
            await pubsub.subscribe(channel)
            logger.info("Subscribed to Redis channel %s", channel)

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")

                # Forward to all active connections for this user
                connections = self._connections.get(user_id, set()).copy()
                disconnected = set()

                for ws in connections:
                    try:
                        await ws.send_text(data)
                    except Exception:
                        disconnected.add(ws)

                # Clean up any broken connections
                for ws in disconnected:
                    self._connections[user_id].discard(ws)

        except asyncio.CancelledError:
            logger.info("Subscriber cancelled for user_id=%d", user_id)
        except Exception:
            logger.exception("Subscriber error for user_id=%d", user_id)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()


# Module-level singleton (initialized when the app starts)
_manager: ConnectionManager | None = None


def get_notification_manager() -> ConnectionManager:
    """Get the global notification manager instance.

    Raises RuntimeError if the manager has not been initialized.
    """
    if _manager is None:
        raise RuntimeError(
            "NotificationManager not initialized. "
            "Call init_notification_manager() during app startup."
        )
    return _manager


def init_notification_manager(redis: Redis) -> ConnectionManager:
    """Initialize the global notification manager with a Redis connection."""
    global _manager
    _manager = ConnectionManager(redis)
    return _manager
