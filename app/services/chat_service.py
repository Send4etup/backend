# app/services/chat_service.py
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.repositories.chat_repository import ChatRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.user_repository import UserRepository
from app.repositories.attachment_repository import AttachmentRepository
from app.models import Chat, Message
import logging

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, db: Session):
        self.db = db
        self.chat_repo = ChatRepository(db)
        self.message_repo = MessageRepository(db)
        self.user_repo = UserRepository(db)
        self.attachments_repo = AttachmentRepository(db)

    def create_chat(self, user_id: str, title: str, chat_type: str = "general") -> Chat:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")

        chat = self.chat_repo.create_chat(user_id, title, chat_type)
        logger.info(f"Chat created: {chat.chat_id} for user {user_id}")
        return chat

    def send_message(self, chat_id: str, user_id: str, content: str, role: str = "user", tokens_count: int = 0) -> Message:
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

            last_message = self.message_repo.get_last_message(chat.chat_id)

            logger.info('Search last message: %s', last_message)

            result.append({
                "chat_id": chat.chat_id,
                "title": chat.title,
                "type": chat.type,
                "messages_count": chat.messages_count,
                "last_message": last_message.content,
                "tokens_used": chat.tokens_used,
                "created_at": chat.created_at.isoformat(),
                "updated_at": chat.updated_at.isoformat()
            })

        logger.info(f"User {user_id} has {len(result)} chats")

        return result

    def get_chat_for_ai_context(self, chat_id: str) -> List[Dict[str, str]]:
        messages = self.message_repo.get_chat_messages(chat_id, 20)

        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        # messages_data = services.chat_service.get_chat_history(chat_id, user.user_id, limit)

    def get_chat_history(self, chat_id: str, user_id, limit: int = 10) -> List[Message]:

        messages = self.message_repo.get_chat_messages(chat_id, user_id, limit)

        for msg in messages:
            attachments = self.attachments_repo.get_message_attachments(msg.message_id)

            if attachments:
                msg.attachments = attachments
            logger.info(f"Message {msg.chat_id} has {len(msg.attachments)} attachments")

        logger.info(f"User {user_id} has {len(messages)} messages")

        return messages