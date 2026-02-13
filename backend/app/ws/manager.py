"""
WebSocket connection manager for real-time nudge delivery.
"""

from fastapi import WebSocket
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections for real-time nudge delivery."""

    def __init__(self):
        # Map of user_id -> WebSocket connection
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"WebSocket connected: user={user_id} | Total: {len(self.active_connections)}")

    def disconnect(self, user_id: str):
        """Remove a WebSocket connection."""
        self.active_connections.pop(user_id, None)
        logger.info(f"WebSocket disconnected: user={user_id} | Total: {len(self.active_connections)}")

    async def send_nudge(self, user_id: str, nudge_data: dict) -> bool:
        """Send a nudge to a specific user via WebSocket."""
        websocket = self.active_connections.get(user_id)
        if websocket:
            try:
                await websocket.send_json(nudge_data)
                logger.info(f"Nudge sent to user={user_id}: {nudge_data.get('nudge_type', 'unknown')}")
                return True
            except Exception as e:
                logger.error(f"Failed to send nudge to user={user_id}: {e}")
                self.disconnect(user_id)
                return False
        else:
            logger.warning(f"No active WebSocket for user={user_id}")
            return False

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected users."""
        disconnected = []
        for user_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(user_id)
        for user_id in disconnected:
            self.disconnect(user_id)

    def is_connected(self, user_id: str) -> bool:
        """Check if a user has an active WebSocket connection."""
        return user_id in self.active_connections

    def get_connected_users(self) -> list[str]:
        """Get list of currently connected user IDs."""
        return list(self.active_connections.keys())


# Singleton manager
ws_manager = ConnectionManager()
