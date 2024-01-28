from fastapi import status, Header, HTTPException


async def check_user(x_user_id: str = Header(None)):
    if x_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
