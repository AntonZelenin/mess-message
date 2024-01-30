from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

aengine = create_async_engine('sqlite:///mess-chats.db')
asession = AsyncSession(bind=aengine)
