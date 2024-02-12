from sqlalchemy.ext.asyncio import AsyncSession

from mess_message import repository
from mess_message.managers import ConnectionManager
from mess_message.models.chat import Message


async def send_message(message: Message, session: AsyncSession, connection_manager: ConnectionManager):
    chat_members = await repository.get_chat_members(session, message.chat_id)
    for member in chat_members:
        await connection_manager.send_personal_message(member.username, message.json())
