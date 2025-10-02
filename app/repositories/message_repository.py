# app/repositories/message_repository.py
from typing import List
from sqlalchemy.orm import Session

from app.main import logger
from app.models import Message
from app.repositories.base_repository import BaseRepository

class MessageRepository(BaseRepository[Message]):
    def __init__(self, db: Session):
        super().__init__(Message, db)

    def get_last_message(self, chat_id: str) -> Message:
        return (self.db.query(Message)
                .filter(Message.chat_id == chat_id)
                .filter(Message.role == "user")
                .order_by(Message.created_at.desc())
                .first())

    def get_chat_messages(self, chat_id: str, user_id: str, limit: int = 50) -> List[Message]:
        return (self.db.query(Message)
                .filter(Message.user_id == user_id)
                .filter(Message.chat_id == chat_id)
                .order_by(Message.created_at.desc())
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

    def delete_by_chat_id(self, chat_id: str):
        """Удаление всех сообщений чата"""
        try:
            self.db.query(Message).filter(Message.chat_id == chat_id).delete()
            self.db.commit()
        except Exception as e:
            logger.error(f"Error deleting messages for chat {chat_id}: {e}")
            self.db.rollback()
            raise