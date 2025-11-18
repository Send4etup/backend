# app/tasks/image_cleanup_task.py
"""
Фоновая задача для автоматической очистки старых изображений
Запускается каждый день в 3:00 утра
"""
import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class ImageCleanupTask:
    """Планировщик очистки старых изображений"""

    def __init__(self, image_service, cleanup_days: int = 30):
        """
        Args:
            image_service: Экземпляр ImageService
            cleanup_days: Удалять изображения старше N дней (по умолчанию 30)
        """
        self.image_service = image_service
        self.cleanup_days = cleanup_days
        self.scheduler = AsyncIOScheduler()
        self.is_running = False

    async def cleanup_job(self):
        """
        Задача очистки - выполняется по расписанию
        """
        try:
            logger.info(f"🧹 Starting scheduled image cleanup (>{self.cleanup_days} days old)")

            result = await self.image_service.cleanup_old_images(days=self.cleanup_days)

            logger.info(
                f"✅ Cleanup completed!\n"
                f"   Deleted: {result['deleted_count']} files\n"
                f"   Freed: {result['freed_space_mb']} MB"
            )

        except Exception as e:
            logger.error(f"❌ Error in cleanup job: {e}")

    def start(self):
        """
        Запуск планировщика
        Очистка будет выполняться каждый день в 3:00 утра
        """
        if self.is_running:
            logger.warning("⚠️ Cleanup scheduler already running")
            return

        try:
            # Добавляем задачу в расписание (каждый день в 3:00)
            self.scheduler.add_job(
                self.cleanup_job,
                CronTrigger(hour=3, minute=0),  # 03:00 каждый день
                id='image_cleanup',
                name='Clean up old generated images',
                replace_existing=True
            )

            self.scheduler.start()
            self.is_running = True

            logger.info(
                f"✅ Image cleanup scheduler started\n"
                f"   Schedule: Daily at 03:00\n"
                f"   Cleanup threshold: >{self.cleanup_days} days"
            )

        except Exception as e:
            logger.error(f"❌ Failed to start cleanup scheduler: {e}")

    def stop(self):
        """Остановка планировщика"""
        if not self.is_running:
            return

        try:
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            logger.info("✅ Image cleanup scheduler stopped")

        except Exception as e:
            logger.error(f"❌ Error stopping cleanup scheduler: {e}")

    async def manual_cleanup(self) -> dict:
        """
        Ручной запуск очистки (для админов/тестирования)

        Returns:
            Результат очистки
        """
        logger.info("🧹 Manual cleanup triggered")
        return await self.cleanup_job()

