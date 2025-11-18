# app/repositories/user_repository.py
from datetime import datetime
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
        # Извлекаем конфликтующие параметры
        tokens_balance = kwargs.pop('tokens_balance', 5)
        subscription_type = kwargs.pop('subscription_type', 'free')

        return self.create(
            telegram_id=telegram_id,
            tokens_balance=tokens_balance,
            subscription_type=subscription_type,
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

    def update_time_activity(self, user_id: str, last_activity: datetime) -> Optional[User]:
        user = self.get_by_id(user_id)
        user.last_activity = last_activity

        self.db.commit()
        self.db.refresh(user)

        return
