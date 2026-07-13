"""WebSocket endpoint for real-time notifications.

Authenticates connections via JWT token in query parameter.
Replays missed events on reconnection and forwards new events
from the user's Redis Pub/Sub channel.
"""

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt

from app.config import get_settings
from app.notifications.manager import get_notification_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# WebSocket close codes
WS_CLOSE_POLICY_VIOLATION = 1008


def _decode_ws_token(token: str) -> int | None:
    """Decode a JWT token and extract the user_id (subject).

    Returns the user_id as int if valid, None otherwise.
    This is a lightweight validation — full user verification
    (checking user exists in DB, etc.) will be added in task 3.5.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        sub = payload.get("sub")
        if sub is None:
            return None
        return int(sub)
    except (JWTError, ValueError, TypeError):
        return None


@router.websocket("/api/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    """Per-user authenticated WebSocket channel.

    Connect: ws://host/api/ws?token={jwt}

    Authentication:
    - Validates JWT from query parameter
    - Closes with code 1008 (Policy Violation) if token is invalid/missing

    On connection:
    - Replays any events stored within the 5-minute TTL window
    - Forwards new events from the user's Redis Pub/Sub channel

    The connection stays open until the client disconnects or an error occurs.
    """
    # Reject if no token provided
    if not token:
        await websocket.close(code=WS_CLOSE_POLICY_VIOLATION)
        return

    # Validate JWT
    user_id = _decode_ws_token(token)
    if user_id is None:
        await websocket.close(code=WS_CLOSE_POLICY_VIOLATION)
        return

    # Accept the WebSocket connection
    await websocket.accept()

    manager = get_notification_manager()

    try:
        # Register connection
        await manager.connect(user_id, websocket)

        # Replay missed events from the 5-minute TTL window
        await manager.replay_missed_events(user_id, websocket)

        # Keep connection alive — listen for client messages (ping/pong, close)
        while True:
            # Wait for any incoming message (keeps connection alive)
            # Client can send ping or close; we just need to keep the loop running
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected: user_id=%d", user_id)
    except Exception:
        logger.exception("WebSocket error for user_id=%d", user_id)
    finally:
        await manager.disconnect(user_id, websocket)
