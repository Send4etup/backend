# quick_fix.py - Скрипт для быстрого исправления проекта
"""
Быстрое исправление структуры проекта
"""
import os
from pathlib import Path


def create_directories():
    """Создание необходимых директорий"""
    directories = [
        "app",
        "app/services",
        "app/repositories",
        "uploads"
    ]

    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Created directory: {directory}")


def create_init_files():
    """Создание __init__.py файлов"""
    init_files = [
        "app/__init__.py",
        "app/services/__init__.py",
        "app/repositories/__init__.py"
    ]

    for init_file in init_files:
        Path(init_file).touch()
        print(f"✅ Created: {init_file}")


def create_config_file():
    """Создание app/config.py"""
    config_content = '''# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tovarishbot.db")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
    APP_NAME = "ТоварищБот"
    APP_VERSION = "2.0.0"
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
    UPLOAD_DIR = "uploads"
    MAX_FILE_SIZE = 50 * 1024 * 1024
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    DEFAULT_USER_TOKENS = 5
    TOKEN_PRICE = 0.002

settings = Settings()
'''

    Path("../app/config.py").write_text(config_content, encoding='utf-8')
    print("✅ Created: app/config.py")


def create_database_file():
    """Создание app/database.py"""
    database_content = '''# app/database.py
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings
import logging

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def create_database():
    """Создание всех таблиц в БД"""
    try:
        from app.models import User, Chat, Message, Attachment
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        return False

def init_database():
    """Инициализация БД при запуске приложения"""
    return create_database()

def get_db():
    """Получение сессии БД для FastAPI endpoints"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def get_db_session():
    """Получение сессии БД для сервисов"""
    return SessionLocal()
'''

    Path("../app/database.py").write_text(database_content, encoding='utf-8')
    print("✅ Created: app/database.py")


def create_base_repository():
    """Создание базового репозитория"""
    base_repo_content = '''# app/repositories/base_repository.py
from typing import Generic, TypeVar, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.database import Base
import logging

logger = logging.getLogger(__name__)
ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType], db: Session):
        self.model = model
        self.db = db

    def create(self, **kwargs) -> ModelType:
        try:
            obj = self.model(**kwargs)
            self.db.add(obj)
            self.db.commit()
            self.db.refresh(obj)
            return obj
        except SQLAlchemyError as e:
            self.db.rollback()
            raise

    def get_by_id(self, id: Any) -> Optional[ModelType]:
        # Простая реализация - ищем по первичному ключу
        return self.db.query(self.model).filter(
            list(self.model.__table__.primary_key.columns)[0] == id
        ).first()
'''

    Path("../app/repositories/base_repository.py").write_text(base_repo_content, encoding='utf-8')
    print("✅ Created: app/repositories/base_repository.py")


def create_user_repository():
    """Создание репозитория пользователей"""
    user_repo_content = '''# app/repositories/user_repository.py
from typing import Optional
from sqlalchemy.orm import Session
from app.models import User
from app.repositories.base_repository import BaseRepository

class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session):
        super().__init__(User, db)

    def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.telegram_id == telegram_id).first()

    def create_user(self, telegram_id: int, **kwargs) -> User:
        return self.create(
            telegram_id=telegram_id,
            tokens_balance=kwargs.get('tokens_balance', 5),
            subscription_type=kwargs.get('subscription_type', 'free'),
            **kwargs
        )

    def check_tokens_available(self, user_id: str, required_tokens: int = 1) -> bool:
        user = self.get_by_id(user_id)
        return user and user.tokens_balance >= required_tokens

    def update_tokens(self, user_id: str, tokens_used: int) -> Optional[User]:
        user = self.get_by_id(user_id)
        if not user:
            return None

        user.tokens_used += tokens_used
        user.tokens_balance = max(0, user.tokens_balance - tokens_used)
        self.db.commit()
        self.db.refresh(user)
        return user
'''

    Path("../app/repositories/user_repository.py").write_text(user_repo_content, encoding='utf-8')
    print("✅ Created: app/repositories/user_repository.py")


def create_chat_repository():
    """Создание репозитория чатов"""
    chat_repo_content = '''# app/repositories/chat_repository.py
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import Chat
from app.repositories.base_repository import BaseRepository

class ChatRepository(BaseRepository[Chat]):
    def __init__(self, db: Session):
        super().__init__(Chat, db)

    def get_user_chats(self, user_id: str, limit: int = 10) -> List[Chat]:
        return (self.db.query(Chat)
                .filter(Chat.user_id == user_id)
                .order_by(Chat.updated_at.desc())
                .limit(limit)
                .all())

    def create_chat(self, user_id: str, title: str, chat_type: str = "general") -> Chat:
        return self.create(
            user_id=user_id,
            title=title,
            type=chat_type,
            messages_count=0,
            tokens_used=0
        )
'''

    Path("../app/repositories/chat_repository.py").write_text(chat_repo_content, encoding='utf-8')
    print("✅ Created: app/repositories/chat_repository.py")


def create_message_repository():
    """Создание репозитория сообщений"""
    message_repo_content = '''# app/repositories/message_repository.py
from typing import List
from sqlalchemy.orm import Session
from app.models import Message
from app.repositories.base_repository import BaseRepository

class MessageRepository(BaseRepository[Message]):
    def __init__(self, db: Session):
        super().__init__(Message, db)

    def get_chat_messages(self, chat_id: str, limit: int = 50) -> List[Message]:
        return (self.db.query(Message)
                .filter(Message.chat_id == chat_id)
                .order_by(Message.created_at.asc())
                .limit(limit)
                .all())

    def create_message(self, chat_id: str, user_id: str, role: str, 
                      content: str, tokens_count: int = 0) -> Message:
        return self.create(
            chat_id=chat_id,
            user_id=user_id,
            role=role,
            content=content,
            tokens_count=tokens_count
        )
'''

    Path("../app/repositories/message_repository.py").write_text(message_repo_content, encoding='utf-8')
    print("✅ Created: app/repositories/message_repository.py")


def create_chat_service():
    """Создание сервиса чатов"""
    chat_service_content = '''# app/services/chat_service.py
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.repositories.chat_repository import ChatRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.user_repository import UserRepository
from app.models import Chat, Message
import logging

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, db: Session):
        self.db = db
        self.chat_repo = ChatRepository(db)
        self.message_repo = MessageRepository(db)
        self.user_repo = UserRepository(db)

    def create_chat(self, user_id: str, title: str, chat_type: str = "general") -> Chat:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")

        chat = self.chat_repo.create_chat(user_id, title, chat_type)
        logger.info(f"Chat created: {chat.chat_id} for user {user_id}")
        return chat

    def send_message(self, chat_id: str, user_id: str, content: str, 
                    role: str = "user", tokens_count: int = 0) -> Message:
        chat = self.chat_repo.get_by_id(chat_id)
        if not chat:
            raise ValueError(f"Chat not found: {chat_id}")

        if chat.user_id != user_id:
            raise ValueError(f"Access denied to chat {chat_id}")

        message = self.message_repo.create_message(
            chat_id, user_id, role, content, tokens_count
        )

        # Обновляем статистику чата
        chat.messages_count += 1
        chat.tokens_used += tokens_count
        self.db.commit()

        return message

    def get_user_chats(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        chats = self.chat_repo.get_user_chats(user_id, limit)

        result = []
        for chat in chats:
            result.append({
                "chat_id": chat.chat_id,
                "title": chat.title,
                "type": chat.type,
                "messages_count": chat.messages_count,
                "tokens_used": chat.tokens_used,
                "created_at": chat.created_at.isoformat(),
                "updated_at": chat.updated_at.isoformat()
            })

        return result

    def get_chat_for_ai_context(self, chat_id: str) -> List[Dict[str, str]]:
        messages = self.message_repo.get_chat_messages(chat_id, 20)

        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
'''

    Path("../app/services/chat_service.py").write_text(chat_service_content, encoding='utf-8')
    print("✅ Created: app/services/chat_service.py")


def main():
    """Основная функция исправления"""
    print("🔧 Исправление структуры проекта...")

    create_directories()
    create_init_files()
    create_config_file()
    create_database_file()
    create_base_repository()
    create_user_repository()
    create_chat_repository()
    create_message_repository()
    create_chat_service()

    print("\n✅ Структура проекта исправлена!")
    print("📝 Теперь замените содержимое app/models.py на исправленную версию")
    print("🚀 После этого запустите: python migrate_to_sqlite.py")


if __name__ == "__main__":
    main()