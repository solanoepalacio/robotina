import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Enum, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from robotina.db import Base


class Platform(enum.Enum):
    TELEGRAM = "telegram"


class MessageRole(enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("platform", "chat_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)
    chat_id: Mapped[str] = mapped_column(String, nullable=False)
    household_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    messages: Mapped[list["StoredMessage"]] = relationship(back_populates="conversation")


class StoredMessage(Base):
    __tablename__ = "stored_messages"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String, ForeignKey("conversations.id"), nullable=False)
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    platform_message_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
