import asyncio

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections = {}
        self.lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        await self._add(user_id, websocket)

    async def disconnect(self, user_id: str, websocket: WebSocket):
        async with self.lock:
            if user_id in self.active_connections:
                self.active_connections[user_id].remove(websocket)

    # async def send_personal_message(self, recipient_user_id: str, message: str):
    #     async with self.lock:
    #         if recipient_user_id in self.active_connections:
    #             for connection in self.active_connections[recipient_user_id]:
    #                 await connection.send_text(message)

    async def _add(self, user_id: str, websocket: WebSocket):
        async with self.lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = []

            self.active_connections[user_id].append(websocket)
