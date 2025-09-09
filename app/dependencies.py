# app/dependencies.py - ВРЕМЕННАЯ ПРОСТАЯ ВЕРСИЯ

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from app.database import get_db
import logging

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


class ServiceContainer:
    def __init__(self, db: Session):
        self.db = db
        from app.services.user_service import UserService
        from app.services.chat_service import ChatService
        from app.services.file_service import FileService

        self.user_service = UserService(db)
        self.chat_service = ChatService(db)
        self.file_service = FileService(db)


def get_services(db: Session = Depends(get_db)) -> ServiceContainer:
    return ServiceContainer(db)


async def get_current_user(
        services: ServiceContainer = Depends(get_services),
        token: Optional[str] = Depends(security)
):
    """
    🚀 ВРЕМЕННАЯ ПРОСТАЯ АВТОРИЗАЦИЯ ДЛЯ РАЗРАБОТКИ
    Всегда возвращает одного и того же тестового пользователя
    """
    from app.models import User

    logger.info("🔐 Using SIMPLE auth mode")

    # Создаем простой объект пользователя
    class SimpleUser:
        def __init__(self):
            self.user_id = "dev_user_123"
            self.telegram_id = 123456789
            self.username = "dev_user"
            self.display_name = "Development User"
            self.subscription_type = "free"
            self.tokens_balance = 1000

        def get_subscription_limits(self):
            return {
                "max_requests_per_day": 1000,
                "max_tokens_per_request": 4000,
                "max_file_size_mb": 50
            }

    logger.info("✅ Simple user created successfully")
    return SimpleUser()


def require_tokens(min_tokens: int = 1):
    """
    🚀 ВРЕМЕННАЯ ПРОСТАЯ ПРОВЕРКА ТОКЕНОВ
    Просто пропускает всех пользователей
    """

    def check_tokens(
            user=Depends(get_current_user),
            services: ServiceContainer = Depends(get_services)
    ):
        logger.info(f"✅ Token check passed for user: {getattr(user, 'user_id', 'unknown')}")
        return user

    return check_tokens


# ====================================================================
# ОРИГИНАЛЬНЫЙ КОД (ЗАКОММЕНТИРОВАН ДЛЯ ВОССТАНОВЛЕНИЯ)
# ====================================================================

"""
# ОРИГИНАЛЬНАЯ ВЕРСИЯ get_current_user:

async def get_current_user_ORIGINAL(
        services: ServiceContainer = Depends(get_services),
        token: Optional[str] = Depends(security)
):
    from app.models import User
    try:
        user = services.user_service.user_repo.get_by_telegram_id(123456789)
        if not user:
            user = await services.user_service.authenticate_or_create_user({
                'telegram_id': 123456789,
                'username': 'test_user',
                'first_name': 'Test',
                'last_name': 'User'
            })
        return user
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")

# ОРИГИНАЛЬНАЯ ВЕРСИЯ require_tokens:

def require_tokens_ORIGINAL(min_tokens: int = 1):
    def check_tokens(
            user = Depends(get_current_user),
            services: ServiceContainer = Depends(get_services)
    ):
        try:
            if hasattr(services.user_service.user_repo, 'check_tokens_available'):
                if not services.user_service.user_repo.check_tokens_available(user.user_id, min_tokens):
                    raise HTTPException(status_code=402, detail=f"Insufficient tokens")
        except:
            pass  # Пропускаем если метод не реализован
        return user

    return check_tokens
"""