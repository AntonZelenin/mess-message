from typing import Optional

from pydantic import BaseModel


class Message(BaseModel):
    chat_id: int
    text: str

    class Config:
        from_attributes = True
        strict = True


class Chat(BaseModel):
    chat_id: int
    name: Optional[str]
    member_usernames: list[str]
    messages: list[Message]

    class Config:
        from_attributes = True
        strict = True
