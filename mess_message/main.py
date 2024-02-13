from typing import Optional, Sequence

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException

from mess_message import schemas, sender, logger
from mess_message.managers import ConnectionManager
from mess_message.models.chat import Message
from mess_message.repository import get_repository, Repository
from mess_message.schemas import SearchChatResults, Chat

logger_ = logger.get_logger(__name__, stdout=True)

app = FastAPI()
conn_manager = ConnectionManager()


@app.middleware('http')
async def ensure_username_is_present(request: Request, call_next):
    x_username = request.headers.get('x-username')
    if x_username is None:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return await call_next(request)


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
                logger_.error(f'username in message does not match username in headers: {username}, {message.sender_username}')
                # todo this message will not be shown, it's not http
                # todo logger
                raise HTTPException(status_code=403)
            if not await repository.is_user_in_chat(username, message.chat_id):
                logger_.error(f'user {username} is not in chat {message.chat_id}')
                # todo this message will not be shown, it's not http
                # todo log that someone tried to send a message to a chat they are not in
                raise HTTPException(status_code=403)

            db_message = await repository.save_message(
                chat_id=message.chat_id,
                sender_username=username,
                text=message.text,
            )
            message = schemas.Message(
                chat_id=db_message.chat_id,
                sender_username=db_message.sender_username,
                text=db_message.text,
                is_read=False,
                created_at=db_message.created_at,
            )
            chat_members = await repository.get_chat_members(message.chat_id)
            await sender.send_message(message, chat_members, conn_manager)
    except WebSocketDisconnect as e:
        logger_.info(f'websocket disconnected: {username}, code {e.code}: {e.reason}')
        await conn_manager.disconnect(username, websocket)
    except Exception as e:
        logger_.exception(f'websocket error: {username}, {e}')
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
                is_read=message not in unread_messages,
                created_at=message.created_at,
            )
        )

    return SearchChatResults(chats=list(chats.values()))


@app.post('/api/message/v1/chats')
async def create_chat(
        new_chat: schemas.NewChat,
        x_username: str = Header(...),
        repository: Repository = Depends(get_repository),
) -> Chat:
    chat_db = await repository.create_chat(new_chat.name)

    try:
        await repository.add_chat_members(chat_db.id, list(new_chat.member_usernames))
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
                is_read=message not in unread_messages,
                created_at=message.created_at,
            )
            for message in messages
        ]
    )


@app.post('/api/message/v1/chats/{chat_id}/read')
async def mark_chat_as_read(
        chat_id: int,
        x_username: str = Header(...),
        repository: Repository = Depends(get_repository),
):
    if not await repository.is_user_in_chat(x_username, chat_id):
        raise HTTPException(status_code=403, detail='User is not in chat')

    await repository.read_all_messages(chat_id, x_username)
    return {"message": "ok"}
