"""
WebSocket Connection & Real-Time Broadcast Manager.

Why WebSockets:
Automated CCTV recognition operates asynchronously in real time. Instead of the browser 
polling the server every 2 seconds with HTTP GET requests (which wastes server bandwidth 
and adds latency), WebSockets maintain a persistent full-duplex TCP channel. Whenever 
the recognition pipeline identifies a face or flags a spoof attempt, the event is 
instantly pushed to the teacher's dashboard in <50 milliseconds.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket

logger = logging.getLogger("api.websocket")


class WebSocketManager:
    """
    Manages active WebSocket connections grouped by classroom_id or global channel.
    """

    def __init__(self):
        # Maps classroom_id -> Set of active WebSocket connections
        self._classroom_connections: Dict[int, Set[WebSocket]] = {}
        # Global connections that receive events for all classrooms (e.g., Principal/Admin view)
        self._global_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, classroom_id: Optional[int] = None) -> None:
        """
        Accepts and registers a new WebSocket client.
        """
        await websocket.accept()
        if classroom_id is not None:
            if classroom_id not in self._classroom_connections:
                self._classroom_connections[classroom_id] = set()
            self._classroom_connections[classroom_id].add(websocket)
            logger.info(f"[WS] Client connected to Classroom #{classroom_id} channel.")
        else:
            self._global_connections.add(websocket)
            logger.info("[WS] Client connected to Global Dashboard channel.")

    def disconnect(self, websocket: WebSocket, classroom_id: Optional[int] = None) -> None:
        """
        Removes a disconnected WebSocket client.
        """
        if classroom_id is not None and classroom_id in self._classroom_connections:
            self._classroom_connections[classroom_id].discard(websocket)
            if not self._classroom_connections[classroom_id]:
                del self._classroom_connections[classroom_id]
            logger.info(f"[WS] Client disconnected from Classroom #{classroom_id}.")
        else:
            self._global_connections.discard(websocket)
            logger.info("[WS] Client disconnected from Global channel.")

    async def broadcast_to_classroom(self, classroom_id: int, message: Dict[str, Any]) -> None:
        """
        Pushes a JSON message to all clients listening to a specific classroom channel,
        as well as global dashboard clients.
        """
        # Convert non-serializable objects (e.g. datetime) if needed
        serialized_msg = json.dumps(message, default=str)

        recipients = set(self._global_connections)
        if classroom_id in self._classroom_connections:
            recipients.update(self._classroom_connections[classroom_id])

        disconnected = []
        for ws in recipients:
            try:
                await ws.send_text(serialized_msg)
            except Exception as exc:
                logger.warning(f"[WS] Failed to send message to client ({exc}). Marking for disconnect.")
                disconnected.append(ws)

        for dead_ws in disconnected:
            self._global_connections.discard(dead_ws)
            if classroom_id in self._classroom_connections:
                self._classroom_connections[classroom_id].discard(dead_ws)

    async def broadcast_global(self, message: Dict[str, Any]) -> None:
        """
        Pushes a JSON message to every connected client across all classrooms.
        """
        serialized_msg = json.dumps(message, default=str)
        all_clients = set(self._global_connections)
        for room_set in self._classroom_connections.values():
            all_clients.update(room_set)

        disconnected = []
        for ws in all_clients:
            try:
                await ws.send_text(serialized_msg)
            except Exception:
                disconnected.append(ws)

        for dead_ws in disconnected:
            self._global_connections.discard(dead_ws)
            for room_set in self._classroom_connections.values():
                room_set.discard(dead_ws)


# Global singleton instance
ws_manager = WebSocketManager()
