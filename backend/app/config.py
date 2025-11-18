# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tovarishbot.db")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
    APP_NAME = "ТоварищБот"
    APP_VERSION = "2.0.0"
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
    UPLOAD_DIR = "uploads"
    MAX_FILE_SIZE = 50 * 1024 * 1024
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    DEFAULT_USER_TOKENS = 5
    TOKEN_PRICE = 0.002

settings = Settings()
