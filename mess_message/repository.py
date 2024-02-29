from typing import Sequence, Optional

from fastapi import Depends
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from mess_message.db import get_session
from mess_message.models.chat import Message, Chat, ChatMember, UnreadMessage


class Repository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_message(self, chat_id: int, sender_username: str, text: str) -> Message:
        message = Message(
            chat_id=chat_id,
            sender_username=sender_username,
            text=text,
        )
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)

        await self.add_to_unread_messages(message)

        return message

    async def add_to_unread_messages(self, message: Message):
        chat_members = (await self.session.scalars(
            select(ChatMember.username)
            .filter(ChatMember.chat_id == message.chat_id, ChatMember.username != message.sender_username)
        )).all()

        self.session.add_all(
            [UnreadMessage(chat_id=message.chat_id, message_id=message.id, username=username) for username in chat_members]
        )
        await self.session.commit()

    async def filter_read_messages(self, messages: Sequence[Message], username: str) -> Sequence[Message]:
        return (await self.session.scalars(
            select(UnreadMessage.message_id)
            .filter(
                UnreadMessage.message_id.in_([message.id for message in messages]),
                UnreadMessage.username == username,
            )
        )).all()

    async def get_messages(self, chat_id: int, number: int = 10) -> Sequence[Message]:
        return (await self.session.scalars(select(Message).filter_by(chat_id=chat_id).limit(number))).all()

    async def chat_exists(self, chat_name: str) -> bool:
        return (await self.session.scalars(select(Chat).filter_by(name=chat_name))).first() is not None

    async def create_chat(self, name: str) -> Chat:
        chat = Chat(
            name=name,
        )
        self.session.add(chat)
        await self.session.commit()
        await self.session.refresh(chat)

        return chat

    async def get_chat(self, chat_id: int) -> Optional[Chat]:
        return (await self.session.scalars(select(Chat).filter_by(id=chat_id))).first()

    async def add_chat_members(self, chat_id: int, member_usernames: Sequence[str]):
        chat_members = [ChatMember(chat_id=chat_id, username=username) for username in member_usernames]
        self.session.add_all(chat_members)
        await self.session.commit()

    async def get_chat_members(self, chat_id: int) -> Sequence[ChatMember]:
        return (await self.session.scalars(select(ChatMember).filter_by(chat_id=chat_id))).all()

    async def is_user_in_chat(self, username: str, chat_id: int) -> bool:
        return (
            await self.session.scalars(
                select(ChatMember).filter_by(chat_id=chat_id, username=username))).first() is not None

    async def delete_chat(self, chat_id: int):
        chat = await self.session.scalar(select(Chat).filter_by(id=chat_id))
        await self.session.delete(chat)
        await self.session.commit()

    async def get_chats_by_username(self, num_of_chats: int, username: str) -> Sequence:
        # todo indices?
        res = await self.session.execute(
            select(ChatMember.chat_id)
            .where(ChatMember.username == username)
        )
        user_chat_ids = res.scalars().all()

        result = await self.session.execute(
            select(Message.chat_id, Message.created_at)
            .where(Message.chat_id.in_(user_chat_ids))
            .order_by(Message.created_at)
            .distinct()
            .limit(num_of_chats)
        )
        recent_chat_ids = result.scalars().all()

        result = await self.session.execute(
            select(Chat.id, Chat.name, ChatMember.username).
            join(ChatMember, ChatMember.chat_id == Chat.id).
            where(Chat.id.in_(recent_chat_ids))
        )
        return result.mappings().all()

    async def get_chats_messages(self, chat_ids: list, num_of_messages: int = 100) -> Sequence[Message]:
        ranked_messages_subq = (
            select(
                Message.id,
                func.rank().over(
                    partition_by=Message.chat_id,
                    order_by=Message.created_at.asc()
                ).label('rank')
            )
            .filter(Message.chat_id.in_(chat_ids))
            .subquery()
        )

        limited_messages_query = (
            select(Message)
            .join(ranked_messages_subq,
                  ranked_messages_subq.c.id == Message.id)
            .filter(ranked_messages_subq.c.rank <= num_of_messages)
            .order_by(Message.chat_id, Message.created_at.asc())
        )

        result = await self.session.execute(limited_messages_query)
        return result.scalars().all()

    async def read_all_messages(self, chat_id: int, username: str):
        stmt = (
            delete(UnreadMessage)
            .where(
                (UnreadMessage.username == username) & (UnreadMessage.chat_id == chat_id)
            )
        )

        await self.session.execute(stmt)
        await self.session.commit()


def get_repository(session: AsyncSession = Depends(get_session)) -> Repository:
    return Repository(session)
