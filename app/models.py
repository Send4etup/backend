# app/models.py (ИСПРАВЛЕННАЯ ВЕРСИЯ)
"""
SQLAlchemy модели для БД с relationships - ИСПРАВЛЕНИЕ КОНФЛИКТА METADATA
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class User(Base):
    """Модель пользователя"""
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

    # Relationships
    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(user_id={self.user_id}, telegram_id={self.telegram_id}, subscription={self.subscription_type})>"

    @property
    def full_name(self):
        """Полное имя пользователя"""
        parts = [self.first_name, self.last_name]
        return " ".join(part for part in parts if part)

    @property
    def display_name(self):
        """Отображаемое имя пользователя"""
        return self.full_name or self.username or f"User {self.telegram_id}"

    def has_tokens(self, required: int = 1) -> bool:
        """Проверка наличия токенов"""
        return self.tokens_balance >= required

    def get_subscription_limits(self) -> dict:
        """Получение лимитов текущей подписки"""
        limits = {
            "free": {
                "daily_tokens": 5,
                "max_file_size_mb": 10,
                "max_files_per_message": 3,
                "features": ["basic_chat", "image_generation"]
            },
            "basic": {
                "daily_tokens": 80,
                "max_file_size_mb": 25,
                "max_files_per_message": 5,
                "features": ["basic_chat", "image_generation", "document_analysis", "coding_help"]
            },
            "pro": {
                "daily_tokens": 300,
                "max_file_size_mb": 50,
                "max_files_per_message": 10,
                "features": ["all_features", "priority_support", "advanced_ai"]
            },
            "mega": {
                "daily_tokens": 620,
                "max_file_size_mb": 100,
                "max_files_per_message": 15,
                "features": ["all_features", "premium_support", "advanced_ai", "early_access"]
            }
        }
        return limits.get(self.subscription_type, limits["free"])


class Chat(Base):
    """Модель чата"""
    __tablename__ = "chats"

    chat_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    type = Column(String, default="general")  # general, image, coding, brainstorm, excuse, make_notes
    title = Column(String, nullable=False)

    # Статистика
    messages_count = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)

    # Временные метки
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="chats")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan", order_by="Message.created_at")

    def __repr__(self):
        return f"<Chat(chat_id={self.chat_id}, title={self.title}, type={self.type})>"

    @property
    def last_message(self):
        """Последнее сообщение в чате"""
        return self.messages[-1] if self.messages else None

    @property
    def last_activity(self):
        """Время последней активности"""
        return self.last_message.created_at if self.last_message else self.created_at

    def get_chat_type_display(self) -> str:
        """Отображаемое название типа чата"""
        type_names = {
            "general": "Общий чат",
            "image": "Создание изображений",
            "coding": "Помощь с кодом",
            "brainstorm": "Мозговой штурм",
            "excuse": "Генератор отмазок",
            "make_notes": "Создание заметок",
            "explain_topic": "Объяснение темы",
            "exam_prep": "Подготовка к экзаменам",
            "solve_homework": "Решение заданий",
            "write_essay": "Написание работ",
            "psychology": "Психологическая поддержка"
        }
        return type_names.get(self.type, self.type.title())


class Message(Base):
    """Модель сообщения"""
    __tablename__ = "messages"

    message_id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String, ForeignKey("chats.chat_id"), nullable=False)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)

    role = Column(String, nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    tokens_count = Column(Integer, default=0)

    # ИСПРАВЛЕНО: переименовано metadata -> message_metadata
    message_metadata = Column(JSON, nullable=True)  # Дополнительная информация

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    chat = relationship("Chat", back_populates="messages")
    user = relationship("User", back_populates="messages")
    attachments = relationship("Attachment", back_populates="message", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Message(message_id={self.message_id}, role={self.role}, chat_id={self.chat_id})>"

    @property
    def content_preview(self, max_length: int = 100) -> str:
        """Превью содержимого сообщения"""
        if len(self.content) <= max_length:
            return self.content
        return self.content[:max_length] + "..."

    @property
    def has_attachments(self) -> bool:
        """Есть ли вложения в сообщении"""
        return len(self.attachments) > 0

    def get_role_display(self) -> str:
        """Отображаемое название роли"""
        role_names = {
            "user": "Пользователь",
            "assistant": "ТоварищБот",
            "system": "Система"
        }
        return role_names.get(self.role, self.role.title())


class Attachment(Base):
    """Модель файлового вложения"""
    __tablename__ = "attachments"

    file_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(Integer, ForeignKey("messages.message_id"), nullable=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)

    # Информация о файле
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # MIME type
    file_size = Column(Integer, nullable=False)  # В байтах

    # Дополнительные метаданные
    original_name = Column(String, nullable=True)  # Оригинальное имя файла
    file_hash = Column(String, nullable=True)  # Хеш для дедупликации
    thumbnail_path = Column(String, nullable=True)  # Путь к превью для изображений

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    message = relationship("Message", back_populates="attachments")
    user = relationship("User", back_populates="attachments")

    def __repr__(self):
        return f"<Attachment(file_id={self.file_id}, file_name={self.file_name}, file_type={self.file_type})>"

    @property
    def file_size_mb(self) -> float:
        """Размер файла в МБ"""
        return round(self.file_size / (1024 * 1024), 2)

    @property
    def is_image(self) -> bool:
        """Является ли файл изображением"""
        image_types = {'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'}
        return self.file_type in image_types

    @property
    def is_document(self) -> bool:
        """Является ли файл документом"""
        document_types = {
            'application/pdf', 'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain', 'application/rtf', 'text/csv',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        return self.file_type in document_types

    @property
    def is_audio(self) -> bool:
        """Является ли файл аудио"""
        audio_types = {
            'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/wave',
            'audio/x-wav', 'audio/m4a', 'audio/mp4', 'audio/aac',
            'audio/webm', 'audio/ogg', 'audio/vorbis'
        }
        return self.file_type in audio_types

    def get_file_category(self) -> str:
        """Категория файла для отображения"""
        if self.is_image:
            return "image"
        elif self.is_document:
            return "document"
        elif self.is_audio:
            return "audio"
        else:
            return "file"

    def get_file_icon(self) -> str:
        """Иконка для типа файла"""
        category = self.get_file_category()
        icons = {
            "image": "🖼️",
            "document": "📄",
            "audio": "🎵",
            "file": "📎"
        }
        return icons.get(category, "📎")