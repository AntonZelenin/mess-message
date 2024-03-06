from typing import Optional

from pydantic import BaseModel


class NewMessage(BaseModel):
    chat_id: int
    sender_id: str
    text: str


class Message(BaseModel):
    chat_id: int
    sender_id: str
    text: str
    is_read: bool
    created_at: float


class NewChat(BaseModel):
    name: Optional[str]
    member_ids: list[str]
    first_message: str


class Chat(BaseModel):
    id: int
    name: Optional[str]
    member_ids: list[str]
    messages: list[Message]


class SearchChatResults(BaseModel):
    chats: list[Chat]
