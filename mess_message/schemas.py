from pydantic import BaseModel


class Message(BaseModel):
    chat_id: int
    text: str

    class Config:
        from_attributes = True
        strict = True
