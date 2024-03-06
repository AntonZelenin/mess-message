from typing import Sequence, Optional

from fastapi import Depends
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from mess_message.db import get_session
from mess_message.models.chat import Message, Chat, ChatMember, UnreadMessage


class Repository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_message(self, chat_id: int, sender_id: str, text: str) -> Message:
        message = Message(
            chat_id=chat_id,
            sender_id=sender_id,
            text=text,
        )
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)

        await self.add_to_unread_messages(message)

        return message

    async def add_to_unread_messages(self, message: Message):
        chat_members = (await self.session.scalars(
            select(ChatMember.user_id)
            .filter(ChatMember.chat_id == message.chat_id, ChatMember.user_id != message.sender_id)
        )).all()

        self.session.add_all(
            [UnreadMessage(chat_id=message.chat_id, message_id=message.id, user_id=user_id) for user_id in chat_members]
        )
        await self.session.commit()

    async def filter_read_messages(self, messages: Sequence[Message], user_id: str) -> Sequence[Message]:
        return (await self.session.scalars(
            select(UnreadMessage.message_id)
            .filter(
                UnreadMessage.message_id.in_([message.id for message in messages]),
                UnreadMessage.user_id == user_id,
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

    async def add_chat_members(self, chat_id: int, member_user_ids: Sequence[str]):
        chat_members = [ChatMember(chat_id=chat_id, user_id=user_id) for user_id in member_user_ids]
        self.session.add_all(chat_members)
        await self.session.commit()

    async def get_chat_members(self, chat_id: int) -> Sequence[ChatMember]:
        return (await self.session.scalars(select(ChatMember).filter_by(chat_id=chat_id))).all()

    async def is_user_in_chat(self, user_id: str, chat_id: int) -> bool:
        return (
            await self.session.scalars(
                select(ChatMember).filter_by(chat_id=chat_id, user_id=user_id))).first() is not None

    async def delete_chat(self, chat_id: int):
        await self.session.execute(
            delete(UnreadMessage).where(UnreadMessage.chat_id == chat_id)
        )
        await self.session.execute(
            delete(Message).where(Message.chat_id == chat_id)
        )
        await self.session.commit()

        await self.session.execute(
            delete(ChatMember).where(ChatMember.chat_id == chat_id)
        )
        await self.session.commit()

        chat = await self.session.scalar(select(Chat).filter_by(id=chat_id))
        await self.session.delete(chat)
        await self.session.commit()

    async def get_chats_by_user_id(self, num_of_chats: int, user_id: str) -> Sequence:
        # todo indices?
        res = await self.session.execute(
            select(ChatMember.chat_id)
            .where(ChatMember.user_id == user_id)
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
            select(Chat.id, Chat.name, ChatMember.user_id).
            join(ChatMember, ChatMember.chat_id == Chat.id).
            where(Chat.id.in_(recent_chat_ids))
        )
        return result.mappings().all()

    async def get_chat_messages(self, chat_id: int, num_of_messages: int = 100) -> Sequence[Message]:
        return await self.get_chats_messages([chat_id], num_of_messages)

    async def get_chats_messages(self, chat_ids: list[int], num_of_messages: int = 100) -> Sequence[Message]:
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

    async def read_all_messages(self, chat_id: int, user_id: str):
        stmt = (
            delete(UnreadMessage)
            .where(
                (UnreadMessage.user_id == user_id) & (UnreadMessage.chat_id == chat_id)
            )
        )

        await self.session.execute(stmt)
        await self.session.commit()


def get_repository(session: AsyncSession = Depends(get_session)) -> Repository:
    return Repository(session)
