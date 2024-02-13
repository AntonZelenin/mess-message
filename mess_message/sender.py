from mess_message.managers import ConnectionManager
from mess_message.models.chat import Message
from mess_message.repository import Repository


async def send_message(message: Message, repository: Repository, connection_manager: ConnectionManager):
    chat_members = await repository.get_chat_members(message.chat_id)
    for member in chat_members:
        await connection_manager.send_personal_message(member.username, message.json())
