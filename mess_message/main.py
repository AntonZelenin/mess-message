from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from mess_message import schemas, sender
from mess_message import repository
from mess_message.db import get_session
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
async def message_socket(websocket: WebSocket, session: AsyncSession = Depends(get_session)):
    # todo middleware or depends to check user id header?
    user_id = websocket.headers.get("x-user-id")
    await conn_manager.connect(user_id, websocket)

    try:
        data = await websocket.receive_text()
        message = schemas.Message.model_validate_json(data)
        message_ = await repository.create_message(
            session,
            chat_id=message.chat_id,
            sender_id=user_id,
            text=message.text,
        )
        # todo it should be async
        sender.send_message(message_)
    except WebSocketDisconnect:
        await conn_manager.disconnect(user_id, websocket)


@app.get("/api/message/v1/messages")
async def get_messages(
        chat_id: int, number: int = 10, session: AsyncSession = Depends(get_session),
) -> list[schemas.Message]:
    return list(await repository.get_messages(session, chat_id=chat_id, number=number))
