# migrate_to_sqlite.py (ИСПРАВЛЕННАЯ ВЕРСИЯ)
"""
Скрипт для миграции от in-memory хранилищ к SQLite
"""
import asyncio
import logging
from pathlib import Path
from datetime import datetime
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Теперь импортируем наши модули
try:
    from app.database import init_database, get_db_session
    from app.models import User, Chat, Message, Attachment
    from app.services.user_service import UserService
    from app.services.chat_service import ChatService
    from app.config import settings
    from sqlalchemy.sql import func
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("💡 Убедитесь что все файлы находятся в правильных папках:")
    print("   app/models.py")
    print("   app/database.py")
    print("   app/config.py")
    print("   app/services/")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseMigrator:
    """Класс для миграции данных в SQLite"""

    def __init__(self):
        self.db = get_db_session()
        self.user_service = UserService(self.db)
        self.chat_service = ChatService(self.db)

    async def migrate_sample_data(self):
        """Создание тестовых данных для демонстрации"""
        logger.info("🔄 Creating sample data...")

        try:
            # 1. Создаем тестового пользователя
            test_user = self.user_service.user_repo.create_user(
                telegram_id=123456789,
                username="test_user",
                first_name="Тест",
                last_name="Пользователь",
                subscription_type="basic",
                tokens_balance=50
            )
            logger.info(f"✅ Created test user: {test_user.user_id}")

            # 2. Создаем несколько чатов
            chats_data = [
                {"title": "Помощь с математикой", "type": "general"},
                {"title": "Генерация изображений", "type": "image"},
                {"title": "Помощь с кодом Python", "type": "coding"},
                {"title": "Подготовка к экзамену", "type": "exam_prep"},
                {"title": "Мозговой штурм проекта", "type": "brainstorm"}
            ]

            created_chats = []
            for chat_data in chats_data:
                chat = self.chat_service.create_chat(
                    test_user.user_id,
                    chat_data["title"],
                    chat_data["type"]
                )
                created_chats.append(chat)
                logger.info(f"✅ Created chat: {chat.title}")

            # 3. Добавляем сообщения в чаты
            sample_conversations = [
                {
                    "chat": created_chats[0],  # Математика
                    "messages": [
                        ("user", "Помоги решить квадратное уравнение: x² + 5x + 6 = 0"),
                        ("assistant",
                         "Конечно! Для решения квадратного уравнения x² + 5x + 6 = 0 используем формулу дискриминанта:\n\nD = b² - 4ac = 5² - 4(1)(6) = 25 - 24 = 1\n\nТак как D > 0, у уравнения есть два корня:\nx₁ = (-5 + √1) / 2 = -2\nx₂ = (-5 - √1) / 2 = -3\n\nОтвет: x = -2 или x = -3"),
                        ("user", "Спасибо! А как проверить правильность решения?"),
                        ("assistant",
                         "Отличный вопрос! Для проверки подставим найденные корни в исходное уравнение:\n\nДля x = -2: (-2)² + 5(-2) + 6 = 4 - 10 + 6 = 0 ✓\nДля x = -3: (-3)² + 5(-3) + 6 = 9 - 15 + 6 = 0 ✓\n\nОба корня дают ноль, значит решение верное!")
                    ]
                },
                {
                    "chat": created_chats[1],  # Изображения
                    "messages": [
                        ("user", "Создай изображение кота в космосе"),
                        ("assistant",
                         "Я создам для вас изображение кота в космосе! Вот промпт для генерации:\n\n'A cute orange tabby cat floating in space, wearing a tiny astronaut helmet, surrounded by stars and galaxies, digital art style, high quality, detailed'"),
                        ("user", "Можешь сделать кота более реалистичным?"),
                        ("assistant",
                         "Конечно! Вот обновленный промпт для более реалистичного изображения:\n\n'Photorealistic orange tabby cat floating in deep space, wearing detailed NASA astronaut helmet, Earth visible in background, surrounded by nebula and stars, professional photography style, 4K quality'")
                    ]
                },
                {
                    "chat": created_chats[2],  # Код Python
                    "messages": [
                        ("user", "Как создать простой веб-сервер на Python?"),
                        ("assistant",
                         "Вот несколько способов создать простой веб-сервер на Python:\n\n**1. Используя встроенный http.server:**\n```python\npython -m http.server 8000\n```\n\n**2. Используя Flask:**\n```python\nfrom flask import Flask\n\napp = Flask(__name__)\n\n@app.route('/')\ndef hello():\n    return 'Привет, мир!'\n\nif __name__ == '__main__':\n    app.run(debug=True)\n```\n\n**3. Используя FastAPI:**\n```python\nfrom fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/')\ndef read_root():\n    return {'message': 'Привет, мир!'}\n```\n\nЧто именно вас интересует?")
                    ]
                }
            ]

            for conv in sample_conversations:
                chat = conv["chat"]
                for role, content in conv["messages"]:
                    tokens = len(content.split()) // 4  # Примерный подсчет токенов
                    self.chat_service.send_message(
                        chat.chat_id,
                        test_user.user_id,
                        content,
                        role,
                        tokens
                    )

                logger.info(f"✅ Added {len(conv['messages'])} messages to chat: {chat.title}")

            logger.info("🎉 Sample data created successfully!")
            return test_user

        except Exception as e:
            logger.error(f"❌ Error creating sample data: {e}")
            self.db.rollback()
            raise
        finally:
            self.db.close()

    def verify_migration(self):
        """Проверка успешности миграции"""
        logger.info("🔍 Verifying migration...")

        try:
            db = get_db_session()

            users_count = db.query(User).count()
            chats_count = db.query(Chat).count()
            messages_count = db.query(Message).count()

            logger.info(f"📊 Migration results:")
            logger.info(f"   Users: {users_count}")
            logger.info(f"   Chats: {chats_count}")
            logger.info(f"   Messages: {messages_count}")

            if users_count > 0 and chats_count > 0 and messages_count > 0:
                logger.info("✅ Migration verified successfully!")
                return True
            else:
                logger.warning("⚠️ Migration verification failed - missing data")
                return False

        except Exception as e:
            logger.error(f"❌ Error verifying migration: {e}")
            return False
        finally:
            db.close()


async def main():
    """Основная функция миграции"""
    print("=" * 60)
    print("🚀 ТоварищБот Database Migration to SQLite")
    print("=" * 60)

    # 1. Инициализируем базу данных
    logger.info("📊 Initializing SQLite database...")

    if not init_database():
        logger.error("❌ Failed to initialize database")
        return False

    logger.info("✅ Database initialized successfully!")

    # 2. Запускаем миграцию
    migrator = DatabaseMigrator()

    try:
        # test_user = await migrator.migrate_sample_data()

        # 3. Проверяем результат
        if migrator.verify_migration():
            print("\n" + "=" * 60)
            print("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
            print("=" * 60)
            print(f"📍 Database file: {settings.DATABASE_URL}")
            # print(f"👤 Test user created: {test_user.display_name}")
            # print(f"🔑 User ID: {test_user.user_id}")
            # print(f"📱 Telegram ID: {test_user.telegram_id}")
            print("\n🚀 You can now start the FastAPI server:")
            print("   python app/main.py")
            print("   # ИЛИ")
            print("   python run_server.py")
            print("\n📚 API Documentation will be available at:")
            print("   http://127.0.0.1:3213/docs")
            print("=" * 60)
            return True
        else:
            logger.error("❌ Migration verification failed")
            return False

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)