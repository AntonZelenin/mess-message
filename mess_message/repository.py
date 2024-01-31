from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mess_message.models.chat import Message


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
