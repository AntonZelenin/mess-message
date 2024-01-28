from pydantic import BaseModel


class Message(BaseModel):
    chat_id: int
    user_id: str
    text: str
