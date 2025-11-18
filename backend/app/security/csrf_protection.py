# app/security/csrf_protection.py
"""
CSRF защита для ТоварищБот
Предотвращает атаки межсайтовой подделки запросов
"""
import os
import secrets
import logging
from fastapi_csrf_protect import CsrfProtect
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class CsrfSettings(BaseModel):
    """Настройки CSRF защиты"""

    # Секретный ключ для подписи токенов
    secret_key: str = os.getenv("CSRF_SECRET_KEY", secrets.token_urlsafe(32))

    # Настройки cookie
    cookie_name: str = "csrf_token"
    cookie_max_age: int = 3600  # 1 час
    cookie_samesite: str = "lax"  # Защита от CSRF
    # cookie_secure: bool = True
    cookie_secure: bool = os.getenv("ENVIRONMENT") == "production"  # HTTPS в продакшене
    cookie_httponly: bool = False  # Frontend должен читать для отправки в headers
    cookie_domain: str = None  # Автоматически определяется

    # Настройки заголовка
    header_name: str = "X-CSRF-Token"
    header_type: str = "header"  # form | header | both

    # Время жизни токена
    token_lifetime: int = 3600  # 1 час в секундах


@CsrfProtect.load_config
def get_csrf_config():
    """Загрузка конфигурации CSRF для FastAPI-CSRF-Protect"""
    return CsrfSettings()


def init_csrf_protection():
    """
    Инициализация CSRF защиты при запуске приложения
    Проверяет наличие секретного ключа и создает его при необходимости
    """
    settings = CsrfSettings()

    # Проверяем наличие секретного ключа
    if not os.getenv("CSRF_SECRET_KEY"):
        csrf_key = secrets.token_urlsafe(32)
        logger.warning(
            f"🔑 CSRF_SECRET_KEY не найден в переменных окружения. "
            f"Используется временный ключ. "
            f"Добавьте в .env: CSRF_SECRET_KEY={csrf_key}"
        )
    else:
        logger.info("✅ CSRF защита инициализирована с секретным ключом из переменных окружения")

    # Логируем настройки (без секретного ключа)
    logger.info(f"CSRF настройки:")
    logger.info(f"  Cookie name: {settings.cookie_name}")
    logger.info(f"  Cookie secure: {settings.cookie_secure}")
    logger.info(f"  Cookie samesite: {settings.cookie_samesite}")
    logger.info(f"  Header name: {settings.header_name}")
    logger.info(f"  Token lifetime: {settings.token_lifetime}s")

    return settings


def validate_csrf_token_manually(token: str, cookie_token: str) -> bool:
    """
    Ручная валидация CSRF токена (если нужна дополнительная проверка)
    """
    if not token or not cookie_token:
        return False

    # Простая проверка на совпадение
    return token == cookie_token


def get_csrf_error_response():
    """Стандартная ошибка CSRF для единообразия"""
    return {
        "error": "CSRF_TOKEN_INVALID",
        "message": "CSRF токен недействителен или отсутствует",
        "code": "SECURITY_VIOLATION",
        "details": {
            "required_header": "X-CSRF-Token",
            "how_to_fix": "Получите CSRF токен через GET /api/security/csrf-token и отправьте его в заголовке X-CSRF-Token"
        }
    }