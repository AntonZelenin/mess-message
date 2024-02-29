from datetime import datetime, timezone

from sqlalchemy import Integer, String, ForeignKey, PrimaryKeyConstraint, Float
from sqlalchemy.orm import mapped_column, Mapped, relationship

from mess_message.models import Base


class Chat(Base):
    __tablename__ = 'chats'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=True)

    chat_members: Mapped['ChatMember'] = relationship("ChatMember", back_populates="chat")


class ChatMember(Base):
    __tablename__ = 'chat_members'

    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey('chats.id'))
    username: Mapped[str] = mapped_column(String(150), nullable=False)

    chat: Mapped['Chat'] = relationship("Chat", back_populates="chat_members")

    __table_args__ = (
        PrimaryKeyConstraint('chat_id', 'username', name='chat_member_pk'),
    )


class Message(Base):
    __tablename__ = 'messages'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey('chats.id'), nullable=False)
    sender_username: Mapped[str] = mapped_column(String(150), nullable=False)
    text: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[float] = mapped_column(Float, default=lambda: datetime.now(timezone.utc).timestamp())


class UnreadMessage(Base):
    __tablename__ = 'unread_messages'

    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey('chats.id'))
    message_id: Mapped[int] = mapped_column(Integer, ForeignKey('messages.id'))
    username: Mapped[str] = mapped_column(String(150), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint('message_id', 'username', name='unread_messages_pk'),
    )
