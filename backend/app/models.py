# app/models.py
"""
SQLAlchemy модели для БД ТоварищБота
Включает основные модели + экзаменационную систему + голосовой режим
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, JSON, Float, Date, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
from datetime import datetime
import pytz
import uuid
import enum

MoscowTZ = pytz.timezone("Europe/Moscow")


# =====================================================
# ОСНОВНЫЕ МОДЕЛИ
# =====================================================

class UserType(str, enum.Enum):
    """
    Тип пользователя в образовательной системе
    """
    SCHOOLER = "schooler"  # Школьник
    STUDENT = "student"

class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_id = Column(Integer, unique=True, nullable=False)

    about_user = Column(String, nullable=True)

    # Токены и подписка
    subscription_type = Column(String, default="free")  # free, basic, pro, mega
    tokens_balance = Column(Integer, default=5)
    tokens_used = Column(Integer, default=0)

    user_type = Column(
        Enum(UserType),
        nullable=True,
        comment="Тип пользователя: schooler (школьник) или student (студент)"
    )

    grade = Column(Integer, nullable=True, comment="Класс/курс ученика (1-11 для школы, 1-6 для вуза)")

    # Временные метки
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(MoscowTZ))
    last_activity = Column(DateTime(timezone=True), default=lambda: datetime.now(MoscowTZ))

    is_active = Column(Boolean, default=True)

    # Relationships - Основные
    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="user", cascade="all, delete-orphan")

    # Relationships - Экзамены и голосовой режим
    exam_settings = relationship("ExamSettings", back_populates="user", cascade="all, delete-orphan")
    task_attempts = relationship("UserTaskAttempt", back_populates="user", cascade="all, delete-orphan")
    exam_progress = relationship("ExamProgress", back_populates="user", cascade="all, delete-orphan")
    exam_stats = relationship("ExamStats", back_populates="user", cascade="all, delete-orphan", uselist=False)
    voice_settings = relationship("VoiceSettings", back_populates="user", cascade="all, delete-orphan", uselist=False)

    def __repr__(self):
        return f"<User(user_id={self.user_id}, telegram_id={self.telegram_id}, subscription={self.subscription_type})>"

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

    assistant_thread_id = Column(String, nullable=True, default=None)

    # Статистика
    messages_count = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)

    # Временные метки
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(MoscowTZ),
                        onupdate=lambda: datetime.now(MoscowTZ))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(MoscowTZ),
                        onupdate=lambda: datetime.now(MoscowTZ))

    # Relationships
    user = relationship("User", back_populates="chats")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan",
                            order_by="Message.created_at")

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
    tool_type = Column(String, nullable=True, default="general")
    content = Column(Text, nullable=False)
    tokens_count = Column(Integer, default=0)

    message_metadata = Column(JSON, nullable=True)  # Дополнительная информация

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(MoscowTZ))

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

    extracted_text = Column(String, nullable=True)

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


class GeneratedImage(Base):
    """
    Модель для сгенерированных DALL-E изображений
    Сохраняет изображения локально для обхода CORS и истечения ссылок OpenAI
    """
    __tablename__ = "generated_images"

    image_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    chat_id = Column(String, ForeignKey("chats.chat_id"), nullable=True)
    message_id = Column(Integer, ForeignKey("messages.message_id"), nullable=True)

    # Информация об изображении
    original_url = Column(String, nullable=False)  # Оригинальная ссылка от OpenAI
    local_path = Column(String, nullable=False)  # Локальный путь к сохранённому файлу
    file_name = Column(String, nullable=False)  # Имя файла
    file_size = Column(Integer, nullable=True)  # Размер в байтах

    # Промпты
    user_prompt = Column(Text, nullable=False)  # Оригинальный промпт пользователя
    revised_prompt = Column(Text, nullable=True)  # Улучшенный промпт от DALL-E

    # Параметры генерации
    model = Column(String, default="dall-e-2")  # dall-e-2 или dall-e-3
    size = Column(String, default="1024x1024")  # Размер изображения
    quality = Column(String, default="standard")  # standard или hd
    style = Column(String, nullable=True)  # vivid или natural (только для DALL-E 3)

    # Временные метки
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(MoscowTZ))
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Когда истекает оригинальная ссылка OpenAI
    downloaded_at = Column(DateTime(timezone=True), nullable=True)  # Когда файл скачан локально

    # Статус
    is_downloaded = Column(Boolean, default=False)  # Скачан ли файл локально
    download_error = Column(Text, nullable=True)  # Ошибка при скачивании (если была)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    chat = relationship("Chat", foreign_keys=[chat_id])
    message = relationship("Message", foreign_keys=[message_id])

    def __repr__(self):
        return f"<GeneratedImage(image_id={self.image_id}, user_id={self.user_id}, is_downloaded={self.is_downloaded})>"

    @property
    def file_size_mb(self) -> float:
        """Размер файла в МБ"""
        if not self.file_size:
            return 0.0
        return round(self.file_size / (1024 * 1024), 2)

    @property
    def is_expired(self) -> bool:
        """Истекла ли оригинальная ссылка OpenAI"""
        if not self.expires_at:
            return False
        return datetime.now(MoscowTZ) > self.expires_at

    @property
    def local_url(self) -> str:
        """URL для доступа к локальному файлу"""
        return f"/api/images/generated/{self.image_id}"

    def get_display_info(self) -> dict:
        """Информация для отображения в UI"""
        return {
            "image_id": self.image_id,
            "local_url": self.local_url,
            "original_url": self.original_url if not self.is_expired else None,
            "user_prompt": self.user_prompt,
            "revised_prompt": self.revised_prompt,
            "size": self.size,
            "model": self.model,
            "created_at": self.created_at.isoformat(),
            "is_downloaded": self.is_downloaded,
            "file_size_mb": self.file_size_mb
        }


# =====================================================
# МОДЕЛИ ДЛЯ ЭКЗАМЕНАЦИОННОЙ СИСТЕМЫ
# =====================================================

class ExamSettings(Base):
    """
    Настройки подготовки к экзамену
    Пользователь может создавать несколько настроек
    """
    __tablename__ = "exam_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)

    exam_type = Column(String, nullable=False)  # 'ОГЭ' или 'ЕГЭ'
    exam_date = Column(Date, nullable=True)  # Общая дата экзамена

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(MoscowTZ))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(MoscowTZ),
                        onupdate=lambda: datetime.now(MoscowTZ))

    # Relationships
    user = relationship("User", back_populates="exam_settings")
    subjects = relationship("ExamSubject", back_populates="exam_settings", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ExamSettings(id={self.id}, user_id={self.user_id}, exam_type={self.exam_type})>"


class ExamSubject(Base):
    """
    Предметы для сдачи с целевыми баллами и текущим прогрессом
    """
    __tablename__ = "exam_subjects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    exam_settings_id = Column(Integer, ForeignKey("exam_settings.id", ondelete="CASCADE"), nullable=False)

    subject_id = Column(String, nullable=False)  # 'математика', 'русский язык', и т.д.
    target_score = Column(Integer, nullable=True)  # Целевой балл
    current_score = Column(Integer, default=0)  # Текущая степень подготовки (0-100)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(MoscowTZ))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(MoscowTZ),
                        onupdate=lambda: datetime.now(MoscowTZ))

    # Relationships
    exam_settings = relationship("ExamSettings", back_populates="subjects")

    def __repr__(self):
        return f"<ExamSubject(id={self.id}, subject={self.subject_id}, target={self.target_score}, current={self.current_score})>"

    @property
    def progress_percentage(self):
        """Процент прогресса подготовки"""
        if not self.target_score or self.target_score == 0:
            return 0
        return min(100, int((self.current_score / self.target_score) * 100))


class ExamTask(Base):
    """
    База заданий для подготовки к экзаменам
    Общая база, которую используют все пользователи
    """
    __tablename__ = "exam_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)

    subject_id = Column(String, nullable=False)  # Предмет
    exam_type = Column(String, nullable=False)  # 'ОГЭ' или 'ЕГЭ'
    task_number = Column(Integer, nullable=True)  # Номер задания (например, № 13)
    difficulty = Column(String, nullable=False)  # 'easy', 'medium', 'hard'

    question_text = Column(Text, nullable=False)  # Условие задания
    answer_type = Column(String, nullable=False)  # 'text', 'number', 'single_choice', 'multiple_choice'
    answer_options = Column(Text, nullable=True)  # JSON массив вариантов ответа
    correct_answer = Column(Text, nullable=False)  # Правильный ответ
    explanation = Column(Text, nullable=True)  # Подробный разбор

    points = Column(Integer, default=1)  # Баллы за задание
    estimated_time = Column(Integer, nullable=True)  # Время (в минутах)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(MoscowTZ))
    is_active = Column(Boolean, default=True)  # Активно ли задание

    # Relationships
    attempts = relationship("UserTaskAttempt", back_populates="task", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ExamTask(id={self.id}, subject={self.subject_id}, type={self.exam_type}, difficulty={self.difficulty})>"


class UserTaskAttempt(Base):
    """
    История выполненных заданий пользователем
    """
    __tablename__ = "user_task_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("exam_tasks.id", ondelete="CASCADE"), nullable=False)

    user_answer = Column(Text, nullable=False)  # Ответ пользователя
    is_correct = Column(Boolean, nullable=False)  # Правильно или нет

    # Денормализация для быстрой аналитики
    subject_id = Column(String, nullable=False)
    exam_type = Column(String, nullable=False)
    difficulty = Column(String, nullable=False)

    time_spent = Column(Integer, nullable=True)  # Время в секундах
    attempted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(MoscowTZ))

    # Relationships
    user = relationship("User", back_populates="task_attempts")
    task = relationship("ExamTask", back_populates="attempts")

    def __repr__(self):
        return f"<UserTaskAttempt(id={self.id}, user_id={self.user_id}, correct={self.is_correct})>"


class ExamProgress(Base):
    """
    Ежедневный прогресс пользователя
    """
    __tablename__ = "exam_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)

    date = Column(Date, nullable=False)  # Дата
    is_completed = Column(Boolean, default=False)  # Выполнена ли дневная норма
    tasks_completed = Column(Integer, default=0)  # Количество выполненных заданий

    # Relationships
    user = relationship("User", back_populates="exam_progress")

    def __repr__(self):
        return f"<ExamProgress(id={self.id}, user_id={self.user_id}, date={self.date}, completed={self.is_completed})>"


class ExamStats(Base):
    """
    Общая статистика пользователя по экзаменам
    """
    __tablename__ = "exam_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, unique=True)


    total_points = Column(Integer, default=0)  # Всего баллов
    tasks_solved = Column(Integer, default=0)  # Всего заданий
    tasks_correct = Column(Integer, default=0)  # Правильных заданий

    streak_days = Column(Integer, default=0)  # Текущая серия дней
    best_streak = Column(Integer, default=0)  # Лучшая серия

    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(MoscowTZ))

    # Relationships
    user = relationship("User", back_populates="exam_stats")

    def __repr__(self):
        return f"<ExamStats(user_id={self.user_id}, points={self.total_points}, streak={self.streak_days})>"

    @property
    def accuracy_percentage(self):
        """Процент правильных ответов"""
        if self.tasks_solved == 0:
            return 0
        return int((self.tasks_correct / self.tasks_solved) * 100)


# =====================================================
# МОДЕЛИ ДЛЯ ГОЛОСОВОГО РЕЖИМА
# =====================================================

class VoiceSettings(Base):
    """
    Настройки голосового режима
    """
    __tablename__ = "voice_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, unique=True)

    speech_speed = Column(String, default='normal')  # 'slow', 'normal', 'fast'
    voice_bot = Column(String, default='neuro')  # 'nastya', 'sergey', 'neuro', 'alex'
    communication_style = Column(String, default='default')  # 'default', 'mentor', 'classmate', и т.д.
    background_music = Column(String, default='lofi')  # 'lofi', 'chillpop', 'nature', 'silence'
    music_volume = Column(Integer, default=39)  # 0-100

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(MoscowTZ))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(MoscowTZ),
                        onupdate=lambda: datetime.now(MoscowTZ))

    # Relationships
    user = relationship("User", back_populates="voice_settings")

    def __repr__(self):
        return f"<VoiceSettings(user_id={self.user_id}, voice={self.voice_bot}, style={self.communication_style})>"