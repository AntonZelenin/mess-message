from mess_message.db import asession
from mess_message.models.chat import Message


async def create_message(chat_id: int, sender_id: str, text: str) -> Message:
    message = Message(
        chat_id=chat_id,
        sender_id=sender_id,
        text=text,
    )
    asession.add(message)
    await asession.commit()

    return message


async def get_messages(chat_id: int, number: int = 10) -> list[Message]:
    messages = await asession.query(Message).filter_by(chat_id=chat_id).limit(number)
    return messages.all()
