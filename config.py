"""
Конфигурация для FastAPI приложения
"""

import os
from pathlib import Path
from typing import List

# Определяем базовую директорию проекта
BASE_DIR = Path(__file__).parent.parent


class Settings:
    """Настройки приложения"""

    # API настройки
    API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # JWT настройки
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your_secret_key_change_in_production")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    # CORS настройки
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5176",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "https://aibot-78b5d.web.app/",
        "https://38d73c447ab1.ngrok-free.app",
        "http://38d73c447ab1.ngrok-free.app"
    ]

    # Добавляем origins из переменной окружения
    if env_origins := os.getenv("ALLOWED_ORIGINS"):
        ALLOWED_ORIGINS.extend(env_origins.split(","))

    # База данных (для будущего использования)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./school_assistant.db")

    # Telegram Bot (для будущего использования)
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # AI Chat настройки
    MAX_CHAT_HISTORY: int = int(os.getenv("MAX_CHAT_HISTORY", "50"))
    MAX_AI_CHAT_HISTORY: int = int(os.getenv("MAX_AI_CHAT_HISTORY", "100"))
    AI_RESPONSE_DELAY_MIN: float = float(os.getenv("AI_RESPONSE_DELAY_MIN", "0.5"))
    AI_RESPONSE_DELAY_MAX: float = float(os.getenv("AI_RESPONSE_DELAY_MAX", "2.0"))

    # Logging настройки
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Rate limiting
    RATE_LIMIT_CALLS: int = int(os.getenv("RATE_LIMIT_CALLS", "100"))
    RATE_LIMIT_PERIOD: int = int(os.getenv("RATE_LIMIT_PERIOD", "60"))

    # Mock data настройки
    ENABLE_MOCK_DATA: bool = os.getenv("ENABLE_MOCK_DATA", "true").lower() == "true"
    MOCK_USER_ID: int = int(os.getenv("MOCK_USER_ID", "123456789"))


# Создаем экземпляр настроек
settings = Settings()


# Функции для проверки конфигурации
def validate_settings():
    """Проверка корректности настроек"""
    errors = []

    if not settings.SECRET_KEY or settings.SECRET_KEY == "your_secret_key_change_in_production":
        if not settings.DEBUG:
            errors.append("SECRET_KEY должен быть изменен в продакшене")

    if settings.API_PORT < 1 or settings.API_PORT > 65535:
        errors.append("API_PORT должен быть между 1 и 65535")

    if settings.ACCESS_TOKEN_EXPIRE_MINUTES < 1:
        errors.append("ACCESS_TOKEN_EXPIRE_MINUTES должен быть больше 0")

    return errors


def get_app_info():
    """Получение информации о приложении"""
    return {
        "app_name": "School Assistant API",
        "version": "1.0.0",
        "environment": "development" if settings.DEBUG else "production",
        "api_host": settings.API_HOST,
        "api_port": settings.API_PORT,
        "cors_origins_count": len(settings.ALLOWED_ORIGINS),
        "mock_data_enabled": settings.ENABLE_MOCK_DATA
    }