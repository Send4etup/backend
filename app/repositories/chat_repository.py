# app/repositories/chat_repository.py
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import Chat
from app.repositories.base_repository import BaseRepository

class ChatRepository(BaseRepository[Chat]):
    def __init__(self, db: Session):
        super().__init__(Chat, db)

    def get_user_chats(self, user_id: str, limit: int = 3) -> List[Chat]:
        return (self.db.query(Chat)
                .filter(Chat.user_id == user_id)
                .filter(Chat.messages_count > 0)
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

    def get_user_chats_paginated(self, user_id: str, limit: int = 10, offset: int = 0) -> List[Chat]:
        """Получение чатов пользователя с пагинацией"""
        return (self.db.query(Chat)
                .filter(Chat.user_id == user_id)
                .filter(Chat.messages_count > 0)
                .order_by(Chat.updated_at.desc())
                .offset(offset)
                .limit(limit)
                .all())

    def cleanup_empty_chats(self, hours_old: int = 24) -> int:
        """
        Удаление чатов без сообщений старше указанного времени
        Возвращает количество удаленных чатов
        """
        from datetime import datetime, timedelta
        from app.models import Message

        cutoff_time = datetime.now() - timedelta(hours=hours_old)

        try:
            # Находим чаты старше cutoff_time без сообщений
            empty_chats = (
                self.db.query(Chat)
                .outerjoin(Message, Chat.chat_id == Message.chat_id)
                .filter(Chat.created_at < cutoff_time)
                .filter(Message.message_id.is_(None))  # Нет связанных сообщений
                .all()
            )

            deleted_count = len(empty_chats)

            # Удаляем найденные пустые чаты
            for chat in empty_chats:
                self.db.delete(chat)

            self.db.commit()

            return deleted_count

        except Exception as e:
            self.db.rollback()
            return 0