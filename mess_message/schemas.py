from typing import Optional

from pydantic import BaseModel


class NewMessage(BaseModel):
    chat_id: int
    sender_username: str
    text: str


class Message(BaseModel):
    chat_id: int
    sender_username: str
    text: str
    created_at: Optional[float] = None

    class Config:
        from_attributes = True
        strict = True


class NewChat(BaseModel):
    name: str
    creator_username: str
    member_usernames: list[str]
    first_message: str


class Chat(BaseModel):
    id: int
    name: str
    member_usernames: list[str]
    messages: list[Message]


class SearchChatResults(BaseModel):
    chats: list[Chat]
