from typing import Optional

from pydantic import BaseModel


class Message(BaseModel):
    chat_id: int
    sender_id: str
    text: str
    created_at: Optional[float] = None

    class Config:
        from_attributes = True
        strict = True


class Chat(BaseModel):
    id: int
    name: Optional[str]
    member_ids: list[str]
    messages: list[Message]

    class Config:
        from_attributes = True
        strict = True
