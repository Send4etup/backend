# app/security/cors_config.py
"""
Безопасная конфигурация CORS для ТоварищБот
Предотвращает CSRF атаки через правильные настройки доменов
"""
import os
from typing import List


class CORSConfig:
    """Конфигурация CORS с безопасными настройками"""

    @staticmethod
    def get_allowed_origins() -> List[str]:
        """Получение разрешенных доменов из переменных окружения и предустановленных"""

        # Читаем из переменной окружения
        env_origins = os.getenv("ALLOWED_ORIGINS", "")
        custom_origins = [origin.strip() for origin in env_origins.split(",") if origin.strip()]

        # Продакшен домены (замените на ваши реальные домены)
        production_origins = [
            "https://tovarishbot.ru",
            "https://webapp.tovarishbot.ru",
            "https://admin.tovarishbot.ru"
        ]

        # Домены для разработки
        development_origins = [
            "http://localhost:3000",
            "http://localhost:5173",  # Vite dev server
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://localhost:8080",  # Дополнительные порты
            "http://127.0.0.1:8080",
            "https://bfd990ebf425.ngrok-free.app"
        ]

        # Telegram WebApp домены
        telegram_origins = [
            "https://web.telegram.org",
            "https://webk.telegram.org",
            "https://webz.telegram.org"
        ]

        env = os.getenv("ENVIRONMENT", "development")

        if env == "production":
            # В продакшене используем только продакшн и телеграм домены + кастомные
            allowed = production_origins + telegram_origins + custom_origins
        else:
            # В разработке добавляем localhost домены
            allowed = production_origins + development_origins + telegram_origins + custom_origins

        # Удаляем дубликаты и пустые строки
        return list(set([origin for origin in allowed if origin]))

    @staticmethod
    def get_allowed_methods() -> List[str]:
        """Разрешенные HTTP методы"""
        return ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]

    @staticmethod
    def get_allowed_headers() -> List[str]:
        """Разрешенные заголовки"""
        return [
            "Authorization",
            "Content-Type",
            "X-Requested-With",
            "Accept",
            "Origin",
            "User-Agent",
            "X-CSRF-Token"
        ]

    @staticmethod
    def get_expose_headers() -> List[str]:
        """Заголовки, доступные frontend"""
        return [
            "Content-Length",
            "Content-Type"
        ]

    @staticmethod
    def is_development() -> bool:
        """Проверка режима разработки"""
        return os.getenv("ENVIRONMENT", "development") != "production"