from typing import Optional, Sequence

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException

from mess_message import schemas, sender
from mess_message.managers import ConnectionManager
from mess_message.models.chat import Message
from mess_message.repository import get_repository, Repository
from mess_message.schemas import SearchChatResults, Chat

app = FastAPI()
conn_manager = ConnectionManager()


@app.middleware('http')
async def ensure_username_is_present(request: Request, call_next):
    x_username = request.headers.get('x-username')
    if x_username is None:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return await call_next(request)


@app.post('/api/message/v1/chats')
async def create_chat(
        new_chat: schemas.NewChat,
        x_username: str = Header(...),
        repository: Repository = Depends(get_repository),
) -> Chat:
    if await repository.chat_exists(new_chat.name):
        raise HTTPException(status_code=409, detail='Chat already exists')

    chat_db = await repository.create_chat(new_chat.name)

    try:
        await repository.add_chat_members(chat_db.id, [x_username] + list(new_chat.member_usernames))
        await repository.save_message(chat_db.id, x_username, new_chat.first_message)
    except Exception as e:
        await repository.delete_chat(chat_db.id)
        raise e

    messages = await repository.get_chats_messages([chat_db.id])
    unread_messages = await repository.filter_read_messages(messages, x_username)

    return Chat(
        id=chat_db.id,
        name=chat_db.name,
        member_usernames=new_chat.member_usernames,
        messages=[
            schemas.Message(
                chat_id=message.chat_id,
                sender_username=message.sender_username,
                text=message.text,
                is_read=message in unread_messages,
                created_at=message.created_at,
            )
            for message in messages
        ]
    )


@app.websocket('/ws/message/v1/messages')
async def message_socket(websocket: WebSocket, repository: Repository = Depends(get_repository)):
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
            if not await repository.is_user_in_chat(username, message.chat_id):
                # todo this message will not be shown, it's not http
                # todo log that someone tried to send a message to a chat they are not in
                raise HTTPException(status_code=403)

            message_ = await repository.save_message(
                chat_id=message.chat_id,
                sender_username=username,
                text=message.text,
            )
            await sender.send_message(message_, repository, conn_manager)
    except WebSocketDisconnect:
        await conn_manager.disconnect(username, websocket)
        # raise
    except Exception as e:
        await websocket.close(code=1011)
        raise e


@app.get('/api/message/v1/chats')
async def get_chats(
        username_like: Optional[str] = None,
        num_of_chats: int = 20,
        repository: Repository = Depends(get_repository),
        x_username: str = Header(...),
) -> SearchChatResults:
    if username_like == "":
        return SearchChatResults(chats=[])

    username = username_like or x_username
    res = list(await repository.get_chats_by_username(num_of_chats, username))

    chats: dict[int, Chat] = {}
    for row in res:
        if row["id"] not in chats:
            chats[row["id"]] = Chat(id=row["id"], name=row["name"], member_usernames=[], messages=[])

        chats[row["id"]].member_usernames.append(row["username"])

    messages: Sequence[Message] = await repository.get_chats_messages([chat.id for chat in chats.values()])
    unread_messages = await repository.filter_read_messages(messages, x_username)

    for message in messages:
        chats[message.chat_id].messages.append(
            schemas.Message(
                chat_id=message.chat_id,
                sender_username=message.sender_username,
                text=message.text,
                is_read=message in unread_messages,
                created_at=message.created_at,
            )
        )

    return SearchChatResults(chats=list(chats.values()))
