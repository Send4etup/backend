import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # База данных
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tovarishbot.db")

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # Приложение
    APP_NAME = "ТоварищБот"
    APP_VERSION = "1.0.0"
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")

    # Пути
    UPLOAD_DIR = "uploads"
    LOG_DIR = "logs"
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    # Токены и лимиты
    DEFAULT_USER_TOKENS = 5
    TOKEN_PRICE = 0.002


settings = Settings()