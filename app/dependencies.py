# app/dependencies.py
"""
FastAPI Dependencies для сервисов
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.user_service import UserService
from app.services.chat_service import ChatService
from app.services.file_service import FileService
from app.models import User
import logging

logger = logging.getLogger(__name__)

# Схема авторизации
security = HTTPBearer(auto_error=False)

# Временное решение для мока авторизации
MOCK_USER_ID = "mock_user_123"


class ServiceContainer:
    """Контейнер для сервисов"""

    def __init__(self, db: Session):
        self.db = db
        self.user_service = UserService(db)
        self.chat_service = ChatService(db)
        self.file_service = FileService(db)


def get_services(db: Session = Depends(get_db)) -> ServiceContainer:
    """Dependency для получения всех сервисов"""
    return ServiceContainer(db)


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Dependency для UserService"""
    return UserService(db)


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    """Dependency для ChatService"""
    return ChatService(db)


def get_file_service(db: Session = Depends(get_db)) -> FileService:
    """Dependency для FileService"""
    return FileService(db)


async def get_current_user(
        services: ServiceContainer = Depends(get_services),
        token: Optional[str] = Depends(security)
) -> User:
    """
    Получение текущего пользователя
    ВРЕМЕННО: возвращает mock пользователя
    TODO: реализовать полную JWT авторизацию
    """

    # ВРЕМЕННОЕ РЕШЕНИЕ: создаем/получаем тестового пользователя
    try:
        user = services.user_service.user_repo.get_by_telegram_id(123456789)

        if not user:
            # Создаем тестового пользователя
            user = await services.user_service.authenticate_or_create_user({
                'telegram_id': 123456789,
                'username': 'test_user',
                'first_name': 'Test',
                'last_name': 'User'
            })
            logger.info("Mock user created for testing")

        return user

    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


def require_tokens(min_tokens: int = 1):
    """Decorator для проверки наличия токенов у пользователя"""

    async def check_tokens(
            user: User = Depends(get_current_user),
            user_service: UserService = Depends(get_user_service)
    ):
        if not user_service.user_repo.check_tokens_available(user.user_id, min_tokens):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Insufficient tokens. Required: {min_tokens}, available: {user.tokens_balance}"
            )
        return user

    return check_tokens
