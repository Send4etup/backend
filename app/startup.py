# app/startup.py
"""
Инициализация приложения при запуске
"""
from app.config import settings
from app.services.telegram_validator import init_telegram_validator
from app.database import init_database
from app.services.ai_service import get_ai_service
import logging
import os


logger = logging.getLogger(__name__)


async def startup_event():
    """
    Инициализация приложения с безопасным Telegram валидатором
    """
    logger.info("🚀 Starting ТоварищБот API...")

    try:
        # 1. Проверяем обязательные переменные окружения
        bot_token = settings.TELEGRAM_BOT_TOKEN
        if not bot_token:
            logger.error("❌ TELEGRAM_BOT_TOKEN not found in environment variables!")
            logger.error("Please add TELEGRAM_BOT_TOKEN to your .env file")
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required for secure authentication")

        # 2. Инициализируем Telegram валидатор
        try:
            init_telegram_validator(bot_token)
            logger.info("✅ Telegram validator initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Telegram validator: {e}")
            raise RuntimeError(f"Telegram validator initialization failed: {e}")

        # 3. Проверяем другие важные настройки
        if not settings.SECRET_KEY or settings.SECRET_KEY == "your-secret-key":
            logger.warning("⚠️ Using default SECRET_KEY - change it in production!")

        if not settings.OPENAI_API_KEY:
            logger.warning("⚠️ OPENAI_API_KEY not configured - AI features will be limited")

        # 4. Создаем директории для файлов
        from pathlib import Path
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(exist_ok=True)
        logger.info(f"📁 Upload directory ready: {upload_dir}")

        # 5. Инициализируем базу данных
        try:
            from app.database import create_database
            create_database()
            logger.info("✅ Database initialized successfully")
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            raise RuntimeError(f"Database setup failed: {e}")

        # 6. Проверяем доступность AI сервиса
        try:
            from app.services.ai_service import get_ai_service
            ai_service = get_ai_service()
            if ai_service:
                health_check = await ai_service.health_check()
                if health_check:
                    logger.info("✅ AI service is healthy")
                else:
                    logger.warning("⚠️ AI service health check failed")
            else:
                logger.warning("⚠️ AI service not available")
        except Exception as e:
            logger.warning(f"⚠️ AI service check failed: {e}")

        # 7. Логируем успешную инициализацию
        environment = os.getenv("ENVIRONMENT", "development")
        logger.info(f"🎯 Environment: {environment}")
        logger.info("✅ Application startup completed successfully")

        # 8. Показываем статус безопасности
        logger.info("🔐 Security features enabled:")
        logger.info("   - Telegram HMAC-SHA256 validation")
        logger.info("   - JWT token authentication")
        logger.info("   - CORS protection")
        logger.info("   - Request rate limiting")

    except Exception as e:
        logger.error(f"❌ CRITICAL: Application startup failed: {e}")
        logger.error("Application cannot start safely. Exiting...")
        raise SystemExit(1)


# Функция для проверки конфигурации безопасности при старте
def validate_security_config():
    """
    Проверка критически важных настроек безопасности
    """
    issues = []

    # Проверяем токен бота
    if not settings.TELEGRAM_BOT_TOKEN:
        issues.append("TELEGRAM_BOT_TOKEN not configured")

    # Проверяем SECRET_KEY
    if not settings.SECRET_KEY or settings.SECRET_KEY == "your-secret-key":
        issues.append("SECRET_KEY using default value (insecure)")

    # Проверяем переменную окружения
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        # Дополнительные проверки для production
        if settings.SECRET_KEY == "your-secret-key":
            issues.append("Production SECRET_KEY must be changed")

        if not settings.OPENAI_API_KEY:
            issues.append("OPENAI_API_KEY required for production")

    if issues:
        logger.error("❌ Security configuration issues found:")
        for issue in issues:
            logger.error(f"   - {issue}")

        if environment == "production":
            raise RuntimeError("Security issues prevent production startup")
        else:
            logger.warning("⚠️ Development mode: some security issues ignored")

    return len(issues) == 0


async def shutdown_event():
    """События при завершении приложения"""
    logger.info("🛑 Shutting down ТоварищБот Backend...")

    # Здесь можно добавить очистку ресурсов

    logger.info("✅ ТоварищБот Backend shutdown complete!")