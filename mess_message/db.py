from sqlalchemy import create_engine
from sqlalchemy.orm import Session


# engine = create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')
engine = create_engine('sqlite:///mess-chats.db')
session = Session(bind=engine)
