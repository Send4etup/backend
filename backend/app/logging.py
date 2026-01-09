"""
Простая настройка логирования для ТоварищБот
Пример использования в main.py вашего FastAPI приложения
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging():
    """
    Настройка логирования с записью в файл и вывод в консоль
    """
    # Создаем папку для логов если её нет
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Имя файла лога с текущей датой
    log_file = log_dir / f"tovarishbot_{datetime.now().strftime('%Y%m%d')}.log"

    # Формат логов - как будут выглядеть записи
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Настройка корневого логгера
    logging.basicConfig(
        level=logging.INFO,  # Минимальный уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format=log_format,
        datefmt=date_format,
        handlers=[
            # Запись в файл
            logging.FileHandler(
                log_file,
                encoding='utf-8'  # Важно для кириллицы!
            ),
        ]
    )

    # Получаем логгер для использования в приложении
    logger = logging.getLogger("tovarishbot")
    logger.info(f"🚀 Логирование настроено. Файл: {log_file}")

    return logger