# app/repositories/chat_repository.py
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
