# app/services/user_service.py (ИСПРАВЛЕННАЯ ВЕРСИЯ)
"""
Сервис для работы с пользователями
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import logging

from app.models import User
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class UserService:
    """Сервис для бизнес-логики пользователей"""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    async def authenticate_or_create_user(self, telegram_data: Dict[str, Any]) -> User:
        """Авторизация или создание пользователя"""
        telegram_id = telegram_data.get('telegram_id') or telegram_data.get('id')

        if not telegram_id:
            raise ValueError("Telegram ID is required")

        # Ищем существующего пользователя
        user = self.user_repo.get_by_telegram_id(telegram_id)

        if user:
            # Обновляем активность
            self.user_repo.update(user.user_id, last_activity=func.now())
            logger.info(f"User authenticated: {user.user_id}")
            return user

        # Создаем нового пользователя
        user = self.user_repo.create_user(
            telegram_id=telegram_id,
            username=telegram_data.get('username'),
            first_name=telegram_data.get('first_name'),
            last_name=telegram_data.get('last_name')
        )

        logger.info(f"New user created: {user.user_id}")
        return user

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получение профиля пользователя"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return None

        return {
            "user_id": user.user_id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "subscription_type": user.subscription_type,
            "tokens_balance": user.tokens_balance,
            "tokens_used": user.tokens_used,
            "created_at": user.created_at.isoformat(),
            "last_activity": user.last_activity.isoformat(),
            "is_active": user.is_active
        }

    def use_tokens(self, user_id: str, tokens_count: int) -> bool:
        """Использование токенов пользователем"""
        if not self.user_repo.check_tokens_available(user_id, tokens_count):
            logger.warning(f"Insufficient tokens for user {user_id}: required {tokens_count}")
            return False

        updated_user = self.user_repo.update_tokens(user_id, tokens_count)
        logger.info(f"Tokens used: {tokens_count} by user {user_id}")
        return updated_user is not None

    def get_subscription_limits(self, subscription_type: str) -> Dict[str, int]:
        """Получение лимитов подписки"""
        limits = {
            "free": {"daily_tokens": 5, "max_file_size": 10},
            "basic": {"daily_tokens": 80, "max_file_size": 25},
            "pro": {"daily_tokens": 300, "max_file_size": 50},
            "mega": {"daily_tokens": 620, "max_file_size": 100}
        }
        return limits.get(subscription_type, limits["free"])