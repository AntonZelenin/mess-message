from datetime import datetime, timezone

from sqlalchemy import Integer, String, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import mapped_column, Mapped

from mess_message.models import Base


class Chat(Base):
    __tablename__ = 'chats'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class ChatMember(Base):
    __tablename__ = 'chat_members'

    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey('chats.id'))
    user_id: Mapped[str] = mapped_column(String(32))

    __table_args__ = (
        PrimaryKeyConstraint('chat_id', 'user_id'),
    )


class Message(Base):
    __tablename__ = 'messages'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey('chats.id'))
    sender_id: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), default=datetime.now(timezone.utc).isoformat())
