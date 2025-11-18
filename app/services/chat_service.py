# app/services/chat_service.py
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.repositories.chat_repository import ChatRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.user_repository import UserRepository
from app.repositories.attachment_repository import AttachmentRepository
from app.models import Chat, Message, Attachment
import logging
import os
from app.services.ai.ai_service import AIService

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

    async def send_message(self, chat_id: str, user_id: str, content: str, role: str = "user",
                           tokens_count: int = 0, tool_type: str = 'general') -> Message:
        chat = self.chat_repo.get_by_id(chat_id)
        if not chat:
            raise ValueError(f"Chat not found: {chat_id}")

        if chat.user_id != user_id:
            raise ValueError(f"Access denied to chat {chat_id}")

        logger.info("Sending message")

        if chat.messages_count == 0 and content:
            try:
                from app.services.ai import get_ai_service

                ai_service = get_ai_service()
                if ai_service:
                    chat.title = await ai_service.get_chat_title(
                        chat_id=chat_id,
                        prompt=content,
                        tool_type=chat.type
                    )
                    logger.info(f"AI-generated title: '{chat.title}'")
                else:
                    # Фолбэк: простое название
                    words = content.strip().split()[:5]
                    chat.title = " ".join(words)[:50]
            except Exception as e:
                logger.error(f"AI title generation failed: {e}")
                # Фолбэк при ошибке
                words = content.strip().split()[:5]
                chat.title = " ".join(words)[:50]

            self.db.commit()

        # Создаем сообщение
        message = self.message_repo.create_message(
            chat_id, user_id, role, content, tokens_count, tool_type
        )

        # Обновляем статистику чата
        chat.messages_count += 1
        chat.tokens_used += tokens_count
        self.db.commit()

        return message

    def get_user_chats(self, user_id: str, limit: int = 3) -> List[Dict[str, Any]]:
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

    def get_user_chats_with_pagination(self, user_id: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """Получение чатов пользователя с пагинацией"""
        chats = self.chat_repo.get_user_chats_paginated(user_id, limit, offset)

        result = []
        for chat in chats:
            # Получаем последнее сообщение
            last_message = self.message_repo.get_last_message(chat.chat_id)

            result.append({
                "chat_id": chat.chat_id,
                "title": chat.title,
                "type": chat.type,
                "messages_count": chat.messages_count,
                "tokens_used": chat.tokens_used,
                "created_at": chat.created_at.isoformat(),
                "updated_at": chat.updated_at.isoformat(),
                "last_message": last_message.content if last_message else None
            })

        return result

    def get_chat_for_ai_context(self, chat_id: str, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Получение истории чата для AI с информацией о файлах

        Args:
            chat_id: ID чата
            limit: Количество последних сообщений (по умолчанию 20)
            user_id: ID пользователя

        Returns:
            Список сообщений с файлами
        """
        messages = self.message_repo.get_chat_messages(chat_id, user_id, limit)
        messages = list(reversed(messages))

        logger.info(f"Chat {chat_id} has {len(messages)} messages")

        result = []
        for msg in messages:
            # Получаем файлы для каждого сообщения
            attachments = self.attachments_repo.get_message_attachments(msg.message_id)

            # Базовая структура сообщения
            message_data = {
                "role": msg.role,
                "content": msg.content
            }

            # Добавляем информацию о файлах, если они есть
            if attachments:
                files_list = []  # ← Создаем отдельный список
                for att in attachments:
                    file_dict = {
                        "file_id": str(att.file_id),  # ← Явное приведение к str
                        "original_name": str(att.file_name),  # ← Явное приведение к str
                        "file_type": str(att.file_type),  # ← Явное приведение к str
                        "file_size": int(att.file_size),  # ← Явное приведение к int
                        "extracted_text": str(att.extracted_text) if att.extracted_text else None
                    }
                    files_list.append(file_dict)

                message_data["files"] = files_list  # ← Присваиваем список
                logger.info(f"History of chat {msg.chat_id} has {len(attachments)} attachments")

            result.append(message_data)

        logger.info(f"Retrieved {len(result)} messages for AI context, chat_id={chat_id}")
        return result

    def get_chat_history(self, chat_id: str, user_id, limit: int = 50) -> List[Message]:

        messages = self.message_repo.get_chat_messages(chat_id, user_id, limit)
        messages = list(reversed(messages))

        for msg in messages:
            attachments = self.attachments_repo.get_message_attachments(msg.message_id)

            if attachments:
                msg.attachments = attachments
            logger.info(f"Message {msg.message_id} has {len(msg.attachments)} attachments")

        logger.info(f"User {user_id} has {len(messages)} messages")

        return messages


    def get_chat(self, chat_id: str, user_id: str):
        """Получение чата по ID с проверкой владельца"""
        chat = self.chat_repo.get_by_id(chat_id)

        if not chat or chat.user_id != user_id:
            return None

        return chat


    def update_chat_title(self, chat_id: str, user_id: str, new_title: str) -> bool:
        """Обновление названия чата"""
        try:
            chat = self.chat_repo.get_by_id(chat_id)

            if not chat or chat.user_id != user_id:
                return False

            chat.title = new_title
            # chat.updated_at = datetime.now()
            self.db.commit()

            return True

        except Exception as e:
            logger.error(f"Error updating chat title: {e}")
            self.db.rollback()
            return False


    def delete_chat(self, chat_id: str, user_id: str) -> bool:
        """Удаление чата и всех связанных данных"""
        try:
            chat = self.chat_repo.get_by_id(chat_id)

            if not chat or chat.user_id != user_id:
                return False

            # Удаляем все сообщения чата
            self.message_repo.delete_by_chat_id(chat_id)

            # Удаляем все вложения чата
            attachments = self.db.query(Attachment).filter(
                Attachment.message_id.in_(
                    self.db.query(Message.message_id).filter(Message.chat_id == chat_id)
                )
            ).all()

            # Удаляем файлы с диска
            for attachment in attachments:
                try:
                    if os.path.exists(attachment.file_path):
                        os.remove(attachment.file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete file {attachment.file_path}: {e}")

            # Удаляем записи о вложениях
            for attachment in attachments:
                self.db.delete(attachment)

            # Удаляем сам чат
            self.db.delete(chat)
            self.db.commit()

            logger.info(f"Chat {chat_id} deleted successfully with all related data")
            return True

        except Exception as e:
            logger.error(f"Error deleting chat: {e}")
            self.db.rollback()
            return False

    def cleanup_empty_chats(self, hours_old: int = 24) -> int:
        """Очистка пустых чатов старше указанного времени"""
        try:
            return self.chat_repo.cleanup_empty_chats(hours_old)
        except Exception as e:
            logger.error(f"Error during empty chats cleanup: {e}")
            return 0

    def get_user_chat_statistics(self, user_id: str) -> Dict[str, Any]:
        """
        Получение статистики чатов пользователя
        """
        try:
            # Общее количество чатов
            total_chats = self.db.query(Chat).filter(Chat.user_id == user_id).count()

            # Общее количество сообщений
            total_messages = self.db.query(Message).join(Chat).filter(
                Chat.user_id == user_id
            ).count()

            # Количество загруженных файлов
            files_uploaded = self.db.query(Attachment).filter(
                Attachment.user_id == user_id
            ).count()

            # Популярные типы чатов
            chat_types = self.db.query(Chat.type, func.count(Chat.id)).filter(
                Chat.user_id == user_id
            ).group_by(Chat.type).all()

            favorite_tools = [{"tool": tool, "count": count} for tool, count in chat_types]

            return {
                "total_chats": total_chats,
                "total_messages": total_messages,
                "files_uploaded": files_uploaded,
                "favorite_tools": favorite_tools
            }
        except Exception as e:
            logger.error(f"Error getting chat statistics: {e}")
            return {}

    def get_recent_user_activity(self, user_id: str, limit: int = 5) -> List[Dict]:
        """
        Получение последней активности пользователя
        """
        try:
            recent_messages = self.db.query(Message).join(Chat).filter(
                Chat.user_id == user_id,
                Message.role == 'user'
            ).order_by(Message.created_at.desc()).limit(limit).all()

            activity = []
            for msg in recent_messages:
                chat = self.db.query(Chat).filter(Chat.chat_id == msg.chat_id).first()
                activity.append({
                    "type": "message",
                    "chat_title": chat.title if chat else "Неизвестный чат",
                    "content": msg.content[:100] + "..." if len(msg.content) > 100 else msg.content,
                    "timestamp": msg.created_at.isoformat(),
                    "chat_id": msg.chat_id
                })

            return activity
        except Exception as e:
            logger.error(f"Error getting recent activity: {e}")
            return []