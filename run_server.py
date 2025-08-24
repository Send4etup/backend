#!/usr/bin/env python3
"""
Скрипт для запуска FastAPI сервера School Assistant API
"""

import sys
import uvicorn
import logging
from pathlib import Path

# Добавляем текущую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent))

from main import app
from config import settings
from middleware import setup_middleware
from utils import mock_db

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("school_assistant.log")
    ]
)

logger = logging.getLogger(__name__)


def setup_application():
    """Настройка приложения перед запуском"""
    logger.info("🔧 Настройка приложения...")

    # Настраиваем middleware
    setup_middleware(app)

    # Создаем резервную копию данных
    mock_db.create_backup()

    logger.info("✅ Приложение настроено успешно")


def print_startup_info():
    """Вывод информации о запуске"""
    print("\n" + "=" * 60)
    print("🚀 School Assistant API")
    print("=" * 60)
    print(f"📍 Сервер: http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"📚 API Docs: http://{settings.API_HOST}:{settings.API_PORT}/docs")
    print(f"🔍 ReDoc: http://{settings.API_HOST}:{settings.API_PORT}/redoc")
    print(f"🏥 Health: http://{settings.API_HOST}:{settings.API_PORT}/")
    print(f"📊 System Info: http://{settings.API_HOST}:{settings.API_PORT}/api/system/info")
    print("=" * 60)
    print("🔑 Тестовые данные:")
    print("   Telegram ID: 123456789")
    print("   Имя: Иванов Иван")
    print("   Токен формат: mock_token_*")
    print("=" * 60)
    print("🎯 Доступные эндпоинты:")
    print("   Authentication: /api/auth/*")
    print("   Users: /api/users/*")
    print("   Education: /api/education/*")
    print("   Ideas: /api/ideas/*")
    print("   Statistics: /api/statistics")
    print("   Leaderboard: /api/leaderboard")
    print("=" * 60)
    print("📝 Логи сохраняются в: school_assistant.log")
    print("🔄 Режим разработки:", "включен" if settings.DEBUG else "отключен")
    print("=" * 60)


def main():
    """Главная функция запуска"""
    try:
        print_startup_info()
        setup_application()

        logger.info(f"🌟 Запуск сервера на {settings.API_HOST}:{settings.API_PORT}")
        logger.info(f"🔧 Режим разработки: {settings.DEBUG}")

        # Запуск сервера
        uvicorn.run(
            "main:app",
            host=settings.API_HOST,
            port=settings.API_PORT,
            reload=settings.DEBUG,
            log_level="info" if settings.DEBUG else "warning",
            access_log=settings.DEBUG,
            reload_excludes=["*.log", "*.db"] if settings.DEBUG else None
        )

    except KeyboardInterrupt:
        logger.info("⏹️ Получен сигнал остановки")
        print("\n🛑 Сервер остановлен пользователем")

    except Exception as e:
        logger.error(f"❌ Ошибка при запуске сервера: {e}")
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)

    finally:
        logger.info("🔄 Завершение работы приложения")


if __name__ == "__main__":
    main()  # !/usr/bin/env python3
"""
Скрипт для запуска FastAPI сервера
"""

import uvicorn
from main import app

if __name__ == "__main__":
    print("🚀 Запуск School Assistant API...")
    print("📍 Сервер будет доступен по адресу: http://127.0.0.1:8000")
    print("📚 Документация API: http://127.0.0.1:8000/docs")
    print("🔍 Альтернативная документация: http://127.0.0.1:8000/redoc")
    print()

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,  # Автоперезагрузка при изменении кода
        log_level="info"
    )