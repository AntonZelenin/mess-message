from typing import Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mess_message import schemas, sender
from mess_message import repository
from mess_message.db import get_session
from mess_message.managers import ConnectionManager
from mess_message.schemas import SearchChatResults

app = FastAPI()
conn_manager = ConnectionManager()


@app.middleware('http')
async def make_sure_username_is_present(request: Request, call_next):
    # todo it's duplicate
    x_username = request.headers.get('x-username')
    if x_username is None:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return await call_next(request)


@app.post('/api/message/v1/chats')
async def create_chat(
        chat: schemas.NewChat,
        x_username: str = Header(...),
        session: AsyncSession = Depends(get_session),
):
    if await repository.chat_exists(session, chat.name):
        raise HTTPException(status_code=409, detail='Chat already exists')

    chat_db = await repository.create_chat(session, chat.name)

    try:
        await repository.add_chat_members(session, chat_db.id, [x_username] + list(chat.member_usernames))
    except Exception as e:
        await repository.delete_chat(session, chat_db.id)
        raise e

    return {'message': 'Chat created', 'chat': chat}


@app.websocket('/ws/message/v1/messages')
async def message_socket(websocket: WebSocket, session: AsyncSession = Depends(get_session)):
    username = websocket.headers.get('x-username')
    # todo make conn_manager context manager, and maybe a dependency?
    await conn_manager.connect(username, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            message = schemas.NewMessage.model_validate_json(data)

            if username != message.sender_username:
                # todo this message will not be shown, it's not http
                # todo logger
                raise HTTPException(status_code=403)
            if not await repository.is_user_in_chat(session, username, message.chat_id):
                # todo this message will not be shown, it's not http
                # todo log that someone tried to send a message to a chat they are not in
                raise HTTPException(status_code=403)

            message_ = await repository.create_message(
                session,
                chat_id=message.chat_id,
                sender_username=username,
                text=message.text,
            )
            # todo it should be async
            sender.send_message(message_)
    except WebSocketDisconnect:
        await conn_manager.disconnect(username, websocket)
        raise
    except Exception as e:
        # It's a good practice to handle exceptions to close the WebSocket connection cleanly
        await websocket.close(code=1011)  # Internal Error
        raise e


@app.get('/api/message/v1/chats')
async def get_chats(
        username_like: Optional[str] = None,
        num_of_chats: int = 20,
        session: AsyncSession = Depends(get_session),
        x_username: str = Header(...),
) -> SearchChatResults:
    if username_like == "":
        return SearchChatResults(chats=[])

    username = username_like or x_username
    res = list(await repository.get_chats_by_username(session, num_of_chats, username))

    chats = {}
    for row in res:
        if row["id"] not in chats:
            chats[row["id"]] = schemas.Chat(id=row["id"], name=row["name"], member_usernames=[], messages=[])

        chats[row["id"]].member_usernames.append(row["username"])

    messages = await repository.get_chats_messages(session, [chat.id for chat in chats.values()])

    for message in messages:
        chats[message.chat_id].message.append(message)

    return SearchChatResults(chats=list(chats.values()))
