from pydantic import BaseModel


class Message(BaseModel):
    chat_id: int
    text: str

    class Config:
        from_attributes = True
        strict = True


class Chat(BaseModel):
    name: str
    member_usernames: list[str]

    class Config:
        from_attributes = True
        strict = True
