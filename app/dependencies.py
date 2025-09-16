# app/dependencies.py - ВРЕМЕННАЯ ПРОСТАЯ ВЕРСИЯ

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from app.auth import JWTManager
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
    Безопасное получение текущего пользователя через JWT
    """
    from app.models import User

    logger.info("🔐 Authenticating user with JWT token")
    logger.info(token)

    # Проверяем наличие токена
    if not token or not token.credentials:
        logger.error("❌ No token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        # Декодируем и проверяем JWT токен
        payload = JWTManager.verify_token(token.credentials)

        telegram_id = payload.get("telegram_id")
        user_id = payload.get("user_id")

        if not telegram_id or not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )

        logger.info(f"🔍 Looking for user: {user_id} (telegram_id: {telegram_id})")

        # Ищем пользователя в БД
        user = services.user_service.user_repo.get_by_id(user_id)

        if not user:
            logger.error(f"❌ User not found in database: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        # Дополнительная проверка telegram_id
        if user.telegram_id != telegram_id:
            logger.error(f"❌ Telegram ID mismatch for user: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token data mismatch"
            )

        # Проверяем активность пользователя
        if not user.is_active:
            logger.warning(f"⚠️ Inactive user attempted access: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive"
            )

        logger.info(f"✅ User authenticated successfully: {user.user_id}")

        # Обновляем время последней активности
        from datetime import datetime, timezone, timedelta
        msk = timezone(timedelta(hours=3))
        services.user_service.user_repo.update_time_activity(
            user.user_id,
            last_activity=datetime.now(msk)
        )

        return user

    except HTTPException:
        # Пропускаем HTTPException дальше
        raise
    except Exception as e:
        logger.error(f"❌ Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


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