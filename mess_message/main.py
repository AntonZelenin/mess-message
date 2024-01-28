from fastapi import FastAPI, Request

from mess_message import schemas, sender
from mess_message import repository

app = FastAPI()


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    x_user_id = request.headers.get("x-user-id")
    if x_user_id is None:
        return {"message": "Unauthorized"}, 401
    return await call_next(request)


@app.post("/api/v1/messages")
async def send_message(message: schemas.Message):
    message = repository.create_message(
        chat_id=message.chat_id,
        user_id=message.user_id,
        text=message.text,
    )
    sender.send_message(message)
