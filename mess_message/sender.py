from typing import Sequence

from mess_message.managers import ConnectionManager
from mess_message.models.chat import ChatMember
from mess_message.schemas import Message


async def send_message(message: Message, chat_members: Sequence[ChatMember], connection_manager: ConnectionManager):
    for member in chat_members:
        if member.username != message.sender_username:
            await connection_manager.send_personal_message(member.username, message.model_dump_json())

    message.is_read = True
    await connection_manager.send_personal_message(message.sender_username, message.model_dump_json())
