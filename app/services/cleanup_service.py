# cleanup_service.py
import os
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
import glob

logger = logging.getLogger(__name__)


class CleanupService:
    """Сервис для автоматической очистки старых файлов"""

    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = Path(upload_dir)
        self.cleanup_interval = 3600  # 1 час
        self.file_max_age = 24 * 3600  # 24 часа
        self.is_running = False
        self.cleanup_task = None

    async def start_cleanup_scheduler(self):
        """Запуск планировщика очистки"""
        if self.is_running:
            return

        self.is_running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Cleanup scheduler started")

    async def stop_cleanup_scheduler(self):
        """Остановка планировщика очистки"""
        self.is_running = False
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Cleanup scheduler stopped")

    async def _cleanup_loop(self):
        """Основной цикл очистки"""
        while self.is_running:
            try:
                await self.cleanup_old_files()
                await asyncio.sleep(self.cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)  # Ждем минуту при ошибке

    async def cleanup_old_files(self):
        """Удаление старых файлов"""
        if not self.upload_dir.exists():
            return

        cleanup_count = 0
        cleanup_size = 0
        cutoff_time = datetime.now() - timedelta(seconds=self.file_max_age)

        try:
            # Проходим по всем пользовательским директориям
            for user_dir in self.upload_dir.iterdir():
                if not user_dir.is_dir():
                    continue

                # Удаляем старые файлы пользователя
                for file_path in user_dir.iterdir():
                    if file_path.is_file():
                        # Проверяем возраст файла
                        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)

                        if file_time < cutoff_time:
                            file_size = file_path.stat().st_size
                            try:
                                file_path.unlink()
                                cleanup_count += 1
                                cleanup_size += file_size
                                logger.debug(f"Cleaned up old file: {file_path}")
                            except Exception as e:
                                logger.warning(f"Failed to remove old file {file_path}: {e}")

                # Удаляем пустые директории пользователей
                try:
                    if not any(user_dir.iterdir()):
                        user_dir.rmdir()
                        logger.debug(f"Removed empty user directory: {user_dir}")
                except Exception as e:
                    logger.debug(f"Could not remove directory {user_dir}: {e}")

        except Exception as e:
            logger.error(f"Error during file cleanup: {e}")

        if cleanup_count > 0:
            size_mb = cleanup_size / (1024 * 1024)
            logger.info(f"Cleaned up {cleanup_count} old files ({size_mb:.1f} MB)")

    async def cleanup_specific_files(self, file_ids: List[str], file_storage: Dict):
        """Удаление конкретных файлов по ID"""
        cleanup_count = 0

        for file_id in file_ids:
            if file_id in file_storage:
                file_data = file_storage[file_id]
                file_path = Path(file_data.get('file_path', ''))

                try:
                    if file_path.exists():
                        file_path.unlink()
                        cleanup_count += 1
                        logger.debug(f"Cleaned up specific file: {file_path}")

                    # Удаляем превью если есть
                    thumb_path = file_path.parent / f"thumb_{file_path.name}"
                    if thumb_path.exists():
                        thumb_path.unlink()
                        logger.debug(f"Cleaned up thumbnail: {thumb_path}")

                    # Удаляем из storage
                    del file_storage[file_id]

                except Exception as e:
                    logger.warning(f"Failed to cleanup file {file_id}: {e}")

        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} specific files")

    async def emergency_cleanup(self, max_size_mb: float = 1000):
        """Экстренная очистка при превышении лимита места"""
        if not self.upload_dir.exists():
            return

        total_size = 0
        file_list = []

        # Собираем информацию о всех файлах
        for file_path in self.upload_dir.rglob("*"):
            if file_path.is_file():
                stat = file_path.stat()
                file_list.append({
                    'path': file_path,
                    'size': stat.st_size,
                    'mtime': stat.st_mtime
                })
                total_size += stat.st_size

        current_size_mb = total_size / (1024 * 1024)

        if current_size_mb <= max_size_mb:
            return

        logger.warning(f"Emergency cleanup triggered: {current_size_mb:.1f} MB > {max_size_mb} MB")

        # Сортируем по времени модификации (старые первыми)
        file_list.sort(key=lambda x: x['mtime'])

        # Удаляем старые файлы пока не достигнем целевого размера
        target_size = max_size_mb * 0.8 * 1024 * 1024  # 80% от лимита
        current_size = total_size
        cleanup_count = 0

        for file_info in file_list:
            if current_size <= target_size:
                break

            try:
                file_info['path'].unlink()
                current_size -= file_info['size']
                cleanup_count += 1
            except Exception as e:
                logger.warning(f"Failed to remove file during emergency cleanup: {e}")

        final_size_mb = current_size / (1024 * 1024)
        logger.info(f"Emergency cleanup completed: {cleanup_count} files removed, "
                    f"{final_size_mb:.1f} MB remaining")

    def get_storage_stats(self) -> Dict:
        """Получение статистики хранилища"""
        if not self.upload_dir.exists():
            return {'total_files': 0, 'total_size_mb': 0, 'user_count': 0}

        total_files = 0
        total_size = 0
        user_dirs = 0

        for item in self.upload_dir.rglob("*"):
            if item.is_file():
                total_files += 1
                total_size += item.stat().st_size

        for item in self.upload_dir.iterdir():
            if item.is_dir():
                user_dirs += 1

        return {
            'total_files': total_files,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'user_count': user_dirs,
            'upload_dir': str(self.upload_dir)
        }


# Глобальный экземпляр сервиса очистки
cleanup_service = None


def get_cleanup_service() -> CleanupService:
    """Получить экземпляр сервиса очистки"""
    global cleanup_service
    if cleanup_service is None:
        cleanup_service = CleanupService()
    return cleanup_service