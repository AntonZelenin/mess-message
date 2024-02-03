import httpx

from mess_message import settings


async def get_user_ids_by_username(usernames: list[str]) -> dict:
    # todo make sure all usernames are valid
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f'{settings.get_settings().user_service_url}/api/user/v1/users/ids',
            json={'usernames': usernames},
        )
        return response.json()['user_ids']
