from pydantic import BaseModel


class Message(BaseModel):
    chat_id: int
    text: str

    class Config:
        orm_mode = True
