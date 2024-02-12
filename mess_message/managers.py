import asyncio

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections = {}
        self.lock = asyncio.Lock()

    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        await self._add(username, websocket)

    async def disconnect(self, username: str, websocket: WebSocket):
        async with self.lock:
            if username in self.active_connections:
                self.active_connections[username].remove(websocket)

    async def send_personal_message(self, recipient_username: str, message: str):
        async with self.lock:
            if recipient_username in self.active_connections:
                for connection in self.active_connections[recipient_username]:
                    await connection.send_text(message)

    async def _add(self, username: str, websocket: WebSocket):
        async with self.lock:
            if username not in self.active_connections:
                self.active_connections[username] = []

            self.active_connections[username].append(websocket)
