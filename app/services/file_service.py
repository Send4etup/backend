# app/services/file_service.py
"""
Сервис для работы с файлами
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.repositories.attachment_repository import AttachmentRepository
from app.repositories.user_repository import UserRepository
from app.models import Attachment
from pathlib import Path
import uuid
import logging

logger = logging.getLogger(__name__)


class FileService:
    """Сервис для работы с файлами"""

    def __init__(self, db: Session):
        self.db = db
        self.attachment_repo = AttachmentRepository(db)
        self.user_repo = UserRepository(db)

    def save_file(self, user_id: str, file_name: str, file_path: str,
                  file_type: str, file_size: int, message_id: Optional[int] = None) -> Attachment:
        """Сохранение файла в БД"""
        # Проверяем существование пользователя
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")

        # Проверяем лимиты подписки
        subscription_limits = self._get_subscription_limits(user.subscription_type)
        max_file_size = subscription_limits["max_file_size"] * 1024 * 1024  # MB to bytes

        if file_size > max_file_size:
            raise ValueError(f"File too large: {file_size} > {max_file_size}")

        attachment = self.attachment_repo.create_attachment(
            user_id=user_id,
            file_name=file_name,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
            message_id=message_id
        )

        logger.info(f"File saved: {attachment.file_id} for user {user_id}")
        return attachment

    def get_user_files(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Получение файлов пользователя"""
        attachments = self.attachment_repo.get_user_files(user_id, limit)

        return [
            {
                "file_id": att.file_id,
                "file_name": att.file_name,
                "file_type": att.file_type,
                "file_size": att.file_size,
                "uploaded_at": att.uploaded_at.isoformat(),
                "message_id": att.message_id
            }
            for att in attachments
        ]

    def get_file_info(self, file_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Получение информации о файле"""
        attachment = self.attachment_repo.get_by_id(file_id)

        if not attachment or attachment.user_id != user_id:
            return None

        return {
            "file_id": attachment.file_id,
            "file_name": attachment.file_name,
            "file_path": attachment.file_path,
            "file_type": attachment.file_type,
            "file_size": attachment.file_size,
            "uploaded_at": attachment.uploaded_at.isoformat(),
            "message_id": attachment.message_id
        }

    def delete_file(self, file_id: str, user_id: str) -> bool:
        """Удаление файла"""
        attachment = self.attachment_repo.get_by_id(file_id)

        if not attachment or attachment.user_id != user_id:
            return False

        # Удаляем файл с диска
        try:
            file_path = Path(attachment.file_path)
            if file_path.exists():
                file_path.unlink()

            # Удаляем превью если есть
            thumb_path = file_path.parent / f"thumb_{file_path.name}"
            if thumb_path.exists():
                thumb_path.unlink()
        except Exception as e:
            logger.error(f"Error deleting file from disk: {e}")

        # Удаляем из БД
        success = self.attachment_repo.delete_attachment(file_id)
        logger.info(f"File deleted: {file_id} by user {user_id}")
        return success

    def cleanup_old_files(self, hours_old: int = 24) -> int:
        """Очистка старых файлов"""
        old_attachments = self.attachment_repo.get_files_to_cleanup(hours_old)
        deleted_count = 0

        for attachment in old_attachments:
            try:
                # Удаляем файл с диска
                file_path = Path(attachment.file_path)
                if file_path.exists():
                    file_path.unlink()

                # Удаляем из БД
                self.attachment_repo.delete_attachment(attachment.file_id)
                deleted_count += 1

            except Exception as e:
                logger.error(f"Error during cleanup of {attachment.file_id}: {e}")

        logger.info(f"Cleanup completed: {deleted_count} files deleted")
        return deleted_count

    def _get_subscription_limits(self, subscription_type: str) -> Dict[str, int]:
        """Получение лимитов подписки"""
        limits = {
            "free": {"max_file_size": 10},
            "basic": {"max_file_size": 25},
            "pro": {"max_file_size": 50},
            "mega": {"max_file_size": 100}
        }
        return limits.get(subscription_type, limits["free"])