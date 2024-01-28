from mess_message.db import session
from mess_message.models.chat import Message


def create_message(chat_id: int, user_id: str, text: str) -> Message:
    message = Message(
        chat_id=chat_id,
        user_id=user_id,
        text=text,
    )
    session.add(message)
    session.commit()

    return message