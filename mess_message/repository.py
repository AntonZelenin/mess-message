from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from mess_message.models.chat import Message, Chat, ChatMember


async def create_message(session: AsyncSession, chat_id: int, sender_id: str, text: str) -> Message:
    message = Message(
        chat_id=chat_id,
        sender_id=sender_id,
        text=text,
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)

    return message


async def get_messages(session: AsyncSession, chat_id: int, number: int = 10) -> Sequence[Message]:
    return (await session.scalars(select(Message).filter_by(chat_id=chat_id).limit(number))).all()


async def chat_exists(session: AsyncSession, chat_name: str) -> bool:
    return (await session.scalars(select(Chat).filter_by(name=chat_name))).first() is not None


async def create_chat(session: AsyncSession, name: str) -> Chat:
    chat = Chat(
        name=name,
    )
    session.add(chat)
    await session.commit()
    await session.refresh(chat)

    return chat


async def add_chat_members(session: AsyncSession, chat_id: int, user_ids: Sequence[str]):
    chat_members = [ChatMember(chat_id=chat_id, user_id=user_id) for user_id in user_ids]
    session.add_all(chat_members)
    await session.commit()


async def is_user_in_chat(session: AsyncSession, user_id: str, chat_id: int) -> bool:
    return (await session.scalars(select(ChatMember).filter_by(chat_id=chat_id, user_id=user_id))).first() is not None


async def delete_chat(session: AsyncSession, chat_id: int) -> None:
    chat = await session.scalar(select(Chat).filter_by(id=chat_id))
    await session.delete(chat)
    await session.commit()


async def get_chats(session: AsyncSession, num_of_chats: int, user_id: str) -> Sequence[Chat]:
    result = await session.execute(
        select(Chat).
        join(Chat.chat_members).  # Assuming chat_members is properly defined as a relationship
        where(ChatMember.user_id == user_id).
        options(joinedload(Chat.chat_members)).  # Correctly load the chat members
        limit(num_of_chats)
    )
    return result.scalars().unique().all()
