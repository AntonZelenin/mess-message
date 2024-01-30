from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect

from mess_message import schemas, sender
from mess_message import repository
from mess_message.managers import ConnectionManager

app = FastAPI()
conn_manager = ConnectionManager()


@app.middleware("http")
async def make_sure_user_id_is_present(request: Request, call_next):
    x_user_id = request.headers.get("x-user-id")
    if x_user_id is None:
        return {"message": "Unauthorized"}, 401
    return await call_next(request)


@app.websocket("/ws/message/v1/messages")
async def message_socket(websocket: WebSocket, message: schemas.Message):
    user_id = websocket.headers.get("x-user-id")
    await conn_manager.connect(user_id, websocket)

    try:
        message = await repository.create_message(
            chat_id=message.chat_id,
            sender_id=user_id,
            text=message.text,
        )
        # todo it should be async
        sender.send_message(message)
    except WebSocketDisconnect:
        conn_manager.disconnect(user_id, websocket)


@app.get("/api/message/v1/messages")
async def get_messages(chat_id: int, number: int = 10) -> list[schemas.Message]:
    return await repository.get_messages(chat_id=chat_id, number=number)
