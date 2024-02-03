from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mess_message import schemas, sender, helpers
from mess_message import repository
from mess_message.db import get_session
from mess_message.managers import ConnectionManager

app = FastAPI()
conn_manager = ConnectionManager()


# todo it's not working, probably
@app.middleware('http')
async def make_sure_user_id_is_present(request: Request, call_next):
    # todo it's duplicate
    x_user_id = request.headers.get('x-sub')
    if x_user_id is None:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return await call_next(request)


@app.post('/api/message/v1/chats')
async def create_chat(chat: schemas.Chat,  x_sub: str = Header(None), session: AsyncSession = Depends(get_session)):
    if await repository.chat_exists(session, chat.name):
        raise HTTPException(status_code=409, detail='Chat already exists')

    chat_db = await repository.create_chat(session, chat.name)

    try:
        user_ids = await helpers.user.get_user_ids_by_username(chat.member_usernames)
        await repository.add_chat_members(session, chat_db.id, [x_sub] + list(user_ids.values()))
    except Exception as e:
        await repository.delete_chat(session, chat_db.id)
        raise e

    return {'message': 'Chat created', 'chat': chat}


@app.websocket('/ws/message/v1/messages')
async def message_socket(websocket: WebSocket, session: AsyncSession = Depends(get_session)):
    user_id = websocket.headers.get('x-sub')
    # todo make conn_manager context manager, and maybe a dependency?
    await conn_manager.connect(user_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            message = schemas.Message.model_validate_json(data)

            if not await repository.is_user_in_chat(session, user_id, message.chat_id):
                raise HTTPException(status_code=403, detail='You are not in this chat')

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
    except Exception as e:
        # It's a good practice to handle exceptions to close the WebSocket connection cleanly
        await websocket.close(code=1011)  # Internal Error
        raise e


@app.get('/api/message/v1/messages')
async def get_messages(
        chat_id: int, number: int = 10, session: AsyncSession = Depends(get_session),
) -> list[schemas.Message]:
    return list(await repository.get_messages(session, chat_id=chat_id, number=number))


@app.get('/api/message/v1/chats')
async def get_chats(
        num_of_chats: int = 20,
        session: AsyncSession = Depends(get_session),
        x_sub: str = Header(None),
) -> list[schemas.Chat]:
    chat_models = list(await repository.get_recent_chats(session, num_of_chats, user_id=x_sub))
    chats = {}
    for chat in chat_models:
        if chat.name not in chats:
            chats[chat.name] = schemas.Chat(chat_id=chat.id, name=chat.name, member_usernames=[])

        chats[chat.name].member_usernames.append(chat.chat_members.user_id)

    unique_user_ids = set()
    for chat in chats.values():
        unique_user_ids.update(chat.member_usernames)

    usernames = await helpers.user.get_user_ids_by_username(list(unique_user_ids))
    for chat in chats.values():
        chat.member_usernames = [usernames[user_id] for user_id in chat.member_usernames]

    chat_ids = [chat.chat_id for chat in chats.values()]
    messages = await repository.get_chats_messages(session, chat_ids)

    for message in messages:
        chats[message.chat_id].messages.append(message)

    return list(chats.values())
