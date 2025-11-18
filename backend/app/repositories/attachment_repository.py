# app/repositories/attachment_repository.py
"""
Репозиторий для работы с файлами
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import Attachment
from app.repositories.base_repository import BaseRepository


class AttachmentRepository(BaseRepository[Attachment]):
    """Репозиторий для файловых вложений"""

    def __init__(self, db: Session):
        super().__init__(Attachment, db)

    def get_user_files(self, user_id: str, limit: int = 50) -> List[Attachment]:
        """Получение файлов пользователя"""
        return (self.db.query(Attachment)
                .filter(Attachment.user_id == user_id)
                .order_by(Attachment.uploaded_at.desc())
                .limit(limit)
                .all())

    def get_message_attachments(self, message_id: int) -> List[Attachment]:
        """Получение вложений сообщения"""
        return (self.db.query(Attachment)
                .filter(Attachment.message_id == message_id)
                .all())

    def create_attachment(self, user_id: str, file_name: str, file_path: str,
                          file_type: str, file_size: int,
                          message_id: Optional[int] = None) -> Attachment:
        """Создание нового вложения"""
        return self.create(
            user_id=user_id,
            message_id=message_id,
            file_name=file_name,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size
        )

    def get_files_to_cleanup(self, hours_old: int = 24) -> List[Attachment]:
        """Получение файлов для очистки"""
        from datetime import datetime, timedelta
        cutoff_time = datetime.now() - timedelta(hours=hours_old)

        return (self.db.query(Attachment)
                .filter(Attachment.uploaded_at < cutoff_time)
                .all())

    def delete_attachment(self, file_id: str) -> bool:
        """Удаление вложения"""
        return self.delete(file_id)