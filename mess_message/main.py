from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException

from mess_message import schemas, sender, logger
from mess_message.managers import ConnectionManager
from mess_message.repository import get_repository, Repository
from mess_message.schemas import SearchChatResults, Chat

logger_ = logger.get_logger(__name__, stdout=True)

app = FastAPI()
conn_manager = ConnectionManager()


@app.middleware('http')
async def validate_headers(request: Request, call_next):
    if request.headers.get('x-user-id') is None:
        logger_.error('x-user-id header is missing')
        raise HTTPException(status_code=401)
    if request.headers.get('x-username') is None:
        logger_.error('x-username header is missing')
        raise HTTPException(status_code=401)
    return await call_next(request)


@app.websocket('/ws/message/v1/messages')
async def message_socket(websocket: WebSocket, repository: Repository = Depends(get_repository)):
    user_id = websocket.headers.get('x-user-id')
    # todo make conn_manager context manager, and maybe a dependency?
    await conn_manager.connect(user_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            message = schemas.NewMessage.model_validate_json(data)

            if user_id != message.sender_id:
                logger_.error(f'user id in message does not match user id in headers: {user_id}, {message.sender_id}')
                # todo this message will not be shown, it's not http
                # todo logger
                raise HTTPException(status_code=403)
            if not await repository.is_user_in_chat(user_id, message.chat_id):
                logger_.error(f'user {user_id} is not in chat {message.chat_id}')
                # todo this message will not be shown, it's not http
                # todo log that someone tried to send a message to a chat they are not in
                raise HTTPException(status_code=403)

            db_message = await repository.save_message(
                chat_id=message.chat_id,
                sender_id=user_id,
                text=message.text,
            )
            message = schemas.Message(
                chat_id=db_message.chat_id,
                sender_id=db_message.sender_id,
                text=db_message.text,
                is_read=False,
                created_at=db_message.created_at,
            )
            chat_members = await repository.get_chat_members(message.chat_id)
            await sender.send_message(message, chat_members, conn_manager)
    except WebSocketDisconnect as e:
        logger_.info(f'websocket disconnected: {user_id}, code {e.code}: {e.reason}')
        await conn_manager.disconnect(user_id, websocket)
    except Exception as e:
        logger_.exception(f'websocket error: {user_id}, {e}')
        await websocket.close(code=1011)
        raise e


@app.get('/api/message/v1/chats/{chat_id}')
async def get_chat(
        chat_id: int,
        x_user_id: str = Header(...),
        repository: Repository = Depends(get_repository),
) -> Chat:
    if not await repository.is_user_in_chat(x_user_id, chat_id):
        raise HTTPException(status_code=403, detail='User is not in chat')

    chat = await repository.get_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail='Chat not found')

    messages = await repository.get_chat_messages(chat_id)
    unread_messages = await repository.filter_read_messages(messages, x_user_id)

    return Chat(
        id=chat_id,
        name=chat.name,
        member_ids=[chat_member.user_id for chat_member in chat.chat_members],
        messages=[
            schemas.Message(
                chat_id=message.chat_id,
                sender_id=message.sender_id,
                text=message.text,
                is_read=message.id not in unread_messages,
                created_at=message.created_at,
            )
            for message in messages
        ]
    )


@app.get('/api/message/v1/chats')
async def get_chats(
        num_of_chats: int = 20,
        repository: Repository = Depends(get_repository),
        x_user_id: str = Header(...),
) -> SearchChatResults:
    res = list(await repository.get_chats_by_user_id(num_of_chats, x_user_id))

    chats: dict[int, Chat] = {}
    for row in res:
        if row["id"] not in chats:
            chats[row["id"]] = Chat(id=row["id"], name=row["name"], member_ids=[], messages=[])

        chats[row["id"]].member_ids.append(row["user_id"])

    messages = await repository.get_chats_messages([chat.id for chat in chats.values()])
    unread_messages = await repository.filter_read_messages(messages, x_user_id)

    for message in messages:
        chats[message.chat_id].messages.append(
            schemas.Message(
                chat_id=message.chat_id,
                sender_id=message.sender_id,
                text=message.text,
                is_read=message.id not in unread_messages,
                created_at=message.created_at,
            )
        )

    return SearchChatResults(chats=list(chats.values()))


@app.post('/api/message/v1/chats')
async def create_chat(
        new_chat: schemas.NewChat,
        x_user_id: str = Header(...),
        repository: Repository = Depends(get_repository),
) -> Chat:
    chat_db = await repository.create_chat(new_chat.name)

    try:
        await repository.add_chat_members(chat_db.id, list(new_chat.member_ids))
        await repository.save_message(chat_db.id, x_user_id, new_chat.first_message)
    except Exception as e:
        logger_.exception(f'error creating chat: {e}')
        await repository.delete_chat(chat_db.id)
        raise e

    db_messages = await repository.get_chats_messages([chat_db.id])
    chat_members = await repository.get_chat_members(chat_db.id)

    first_message = schemas.Message(
        chat_id=db_messages[0].chat_id,
        sender_id=db_messages[0].sender_id,
        text=db_messages[0].text,
        is_read=False,
        created_at=db_messages[0].created_at,
    )
    # todo why I cannot use chat_db.chat_members here? it argues on greenlet.. something related to async
    await sender.send_message(first_message, chat_members, conn_manager)

    return Chat(
        id=chat_db.id,
        name=chat_db.name,
        member_ids=new_chat.member_ids,
        messages=[
            schemas.Message(
                chat_id=message.chat_id,
                sender_id=message.sender_id,
                text=message.text,
                is_read=True,
                created_at=message.created_at,
            )
            for message in db_messages
        ]
    )


@app.post('/api/message/v1/chats/{chat_id}/read')
async def mark_chat_as_read(
        chat_id: int,
        x_user_id: str = Header(...),
        repository: Repository = Depends(get_repository),
):
    if not await repository.is_user_in_chat(x_user_id, chat_id):
        raise HTTPException(status_code=403, detail='User is not in chat')

    await repository.read_all_messages(chat_id, x_user_id)
    return {"message": "ok"}
