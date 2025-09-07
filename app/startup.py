# app/startup.py
"""
Инициализация приложения при запуске
"""
from app.database import init_database
from app.services.ai_service import get_ai_service
import logging

logger = logging.getLogger(__name__)


async def startup_event():
    """События при запуске приложения"""
    logger.info("🚀 Starting ТоварищБот Backend...")

    # 1. Инициализируем базу данных
    logger.info("📊 Initializing database...")
    db_success = init_database()

    if not db_success:
        logger.error("❌ Failed to initialize database")
        raise Exception("Database initialization failed")

    # 2. Проверяем ИИ сервис
    logger.info("🤖 Checking AI service...")
    ai_service = get_ai_service()

    if ai_service:
        try:
            health_ok = await ai_service.health_check()
            if health_ok:
                logger.info("✅ AI service is healthy")
            else:
                logger.warning("⚠️ AI service health check failed")
        except Exception as e:
            logger.warning(f"⚠️ AI service error: {e}")
    else:
        logger.warning("⚠️ AI service not available")

    # 3. Создаем необходимые директории
    from pathlib import Path
    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)
    logger.info(f"📁 Upload directory ready: {upload_dir.absolute()}")

    logger.info("✅ ТоварищБот Backend started successfully!")


async def shutdown_event():
    """События при завершении приложения"""
    logger.info("🛑 Shutting down ТоварищБот Backend...")

    # Здесь можно добавить очистку ресурсов

    logger.info("✅ ТоварищБот Backend shutdown complete!")