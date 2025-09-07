from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, JSON, Float
from sqlalchemy.sql import func
from app.database import Base
import uuid


# Модель пользователя
class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)

    # Токены и подписка
    subscription_type = Column(String, default="free")  # free, basic, pro, mega
    tokens_balance = Column(Integer, default=5)
    tokens_used = Column(Integer, default=0)

    # Временные метки
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now())

    is_active = Column(Boolean, default=True)


# Модель чата
class Chat(Base):
    __tablename__ = "chats"

    chat_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.user_id"))
    type = Column(String, default="general")  # general, image, coding, etc.
    title = Column(String)

    messages_count = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


# Модель сообщения
class Message(Base):
    __tablename__ = "messages"

    message_id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String, ForeignKey("chats.chat_id"))
    user_id = Column(String, ForeignKey("users.user_id"))

    role = Column(String)  # user, assistant, system
    content = Column(Text)
    tokens_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# Модель файла
class Attachment(Base):
    __tablename__ = "attachments"

    file_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(Integer, ForeignKey("messages.message_id"), nullable=True)
    user_id = Column(String, ForeignKey("users.user_id"))

    file_name = Column(String)
    file_path = Column(String)
    file_type = Column(String)  # image, document, audio
    file_size = Column(Integer)

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())