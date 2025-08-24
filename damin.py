# main.py
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid
import asyncio
import random
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv

from ai_service import get_ai_service, AIService

load_dotenv()
AIService()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="School Assistant API", version="1.0.0")

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Схема авторизации (опционально)
security = HTTPBearer(auto_error=False)

# Временное хранилище
chat_storage = {}
user_storage = {}

# Создаем тестового пользователя по умолчанию
DEFAULT_USER = {
    "id": 1,
    "telegram_id": 123456789,
    "name": "Test User",
    "current_points": 0,
    "total_points": 0,
    "level": 1,
    "created_at": datetime.now().isoformat()
}
user_storage[1] = DEFAULT_USER


# Pydantic модели
class TelegramAuthRequest(BaseModel):
    telegram_id: Optional[int] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    initData: Optional[str] = None
    user: Optional[Dict[str, Any]] = None


class SendMessageRequest(BaseModel):
    message: str
    tool_type: Optional[str] = None
    chat_id: Optional[str] = None


class AIResponseRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = {}


class CreateChatRequest(BaseModel):
    title: Optional[str] = "Новый чат"


class CreateToolChatRequest(BaseModel):
    tool_type: str
    tool_title: str
    description: Optional[str] = None


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    school_name: Optional[str] = None
    class_name: Optional[str] = None


# Модели ответов
class AuthResponse(BaseModel):
    token: str
    user: Dict[str, Any]


class MessageResponse(BaseModel):
    message_id: str
    chat_id: str
    status: str
    timestamp: str


class AIResponse(BaseModel):
    message: str
    response_id: str
    timestamp: str


# Вспомогательные функции
def generate_mock_token(telegram_id: int) -> str:
    return f"mock_token_{telegram_id}_{int(datetime.now().timestamp())}"


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Получение текущего пользователя (без проверки токена)"""
    # Просто возвращаем тестового пользователя
    return DEFAULT_USER


async def get_gpt_response(message: str, context: Dict[str, Any] = {}) -> str:
    """Получить ответ от GPT или fallback"""
    ai_service = get_ai_service()

    if ai_service is None:
        # Если GPT недоступен, используем статичные ответы
        print("AI сервис не запустился!")
        return await simulate_ai_response(message, context)

    try:
        # Получаем историю чата для контекста
        chat_id = context.get('chat_id')
        chat_history = []

        if chat_id and chat_id in chat_storage:
            chat_history = chat_storage[chat_id]["messages"]

        # Вызываем GPT
        response = await ai_service.get_response(message, context, chat_history)
        return response

    except Exception as e:
        logger.error(f"GPT error, falling back to static response: {e}")
        return await simulate_ai_response(message, context)


async def simulate_ai_response(message: str, context: Dict[str, Any] = {}) -> str:
    """Статичная симуляция ИИ (fallback)"""
    await asyncio.sleep(random.uniform(0.5, 1.0))  # Короткая задержка для fallback

    tool_type = context.get('tool_type')

    # Упрощенные fallback ответы
    if tool_type == 'create_image':
        return f"🎨 (Режим fallback) Понял! Хотите создать изображение: '{message}'. Опишите подробнее стиль и детали!"
    elif tool_type == 'coding':
        return f"💻 (Режим fallback) Отличная задача по программированию! '{message}' - давайте разберем пошагово."
    elif tool_type == 'brainstorm':
        return f"💡 (Режим fallback) Супер тема для мозгового штурма: '{message}'! Вот несколько направлений для размышлений..."
    elif tool_type == 'excuse':
        return f"😅 (Режим fallback) Нужна отмазка для '{message}'? Придумываю креативное объяснение!"
    else:
        return f"🤖 (Режим fallback) Интересный вопрос! По теме '{message}' могу предложить несколько идей..."


# АВТОРИЗАЦИЯ (упрощенная)
@app.post("/api/auth/telegram", response_model=AuthResponse)
async def simple_auth():
    try:
        token = "simple_token_123"  # Простой токен

        logger.info(f"User authenticated: {DEFAULT_USER['id']}")

        return AuthResponse(token=token, user=DEFAULT_USER)

    except Exception as e:
        logger.error(f"Auth error: {e}")
        raise HTTPException(status_code=400, detail="Authentication failed")


# ПОЛЬЗОВАТЕЛЬ
@app.get("/api/user/profile")
async def get_user_profile(user=Depends(get_current_user)):
    """Получение профиля пользователя"""
    return user


@app.patch("/api/user/profile")
async def update_user_profile(
        profile_data: UserProfileUpdate,
        user=Depends(get_current_user)
):
    """Обновление профиля пользователя"""
    user_id = user["id"]

    # Обновляем данные
    if profile_data.name:
        user["name"] = profile_data.name
    if profile_data.school_name:
        user["school_name"] = profile_data.school_name
    if profile_data.class_name:
        user["class_name"] = profile_data.class_name

    user["updated_at"] = datetime.now().isoformat()
    user_storage[user_id] = user

    return user


# ЧАТ
@app.post("/api/chat/send", response_model=MessageResponse)
async def send_message(
        request: SendMessageRequest,
        user=Depends(get_current_user)
):
    """Отправка сообщения в чат"""
    message_id = str(uuid.uuid4())
    chat_id = request.chat_id or str(uuid.uuid4())

    # Создаем чат если не существует
    if chat_id not in chat_storage:
        chat_storage[chat_id] = {
            "chat_id": chat_id,
            "user_id": user["id"],
            "tool_type": request.tool_type,  # Сохраняем тип инструмента
            "created_at": datetime.now().isoformat(),
            "messages": []
        }

    # Сохраняем сообщение
    message_data = {
        "message_id": message_id,
        "chat_id": chat_id,
        "user_id": user["id"],
        "message": request.message,
        "tool_type": request.tool_type,  # Сохраняем тип в сообщении
        "type": "user",
        "timestamp": datetime.now().isoformat()
    }

    chat_storage[chat_id]["messages"].append(message_data)

    logger.info(f"Message sent to chat {chat_id}: {request.message[:50]}...")

    return MessageResponse(
        message_id=message_id,
        chat_id=chat_id,
        status="sent",
        timestamp=message_data["timestamp"]
    )


@app.post("/api/chat/ai-response", response_model=AIResponse)
async def get_ai_response(
        request: AIResponseRequest,
        user=Depends(get_current_user)
):
    """Получение ответа от ИИ"""
    try:
        # Генерируем ответ от GPT
        ai_message = await get_gpt_response(request.message, request.context)

        response_id = str(uuid.uuid4())
        chat_id = request.context.get("chat_id")
        tool_type = request.context.get("tool_type")

        # Сохраняем ответ в чат если есть chat_id
        if chat_id and chat_id in chat_storage:
            ai_response_data = {
                "message_id": response_id,
                "chat_id": chat_id,
                "user_id": user["id"],
                "message": ai_message,
                "tool_type": tool_type,
                "type": "assistant",
                "timestamp": datetime.now().isoformat()
            }
            chat_storage[chat_id]["messages"].append(ai_response_data)

        logger.info(f"AI response generated for user {user['id']}, tool_type: {tool_type}")

        return AIResponse(
            message=ai_message,
            response_id=response_id,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"AI response error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate AI response")


@app.get("/api/chat/history")
async def get_chat_history(
        chat_id: Optional[str] = None,
        limit: int = 20,
        user=Depends(get_current_user)
):
    """Получение истории чатов"""
    user_id = user["id"]

    if chat_id:
        # Возвращаем конкретный чат
        if chat_id in chat_storage and chat_storage[chat_id]["user_id"] == user_id:
            chat = chat_storage[chat_id]
            return chat["messages"][-limit:] if chat["messages"] else []
        else:
            return []
    else:
        # Возвращаем список чатов пользователя
        user_chats = []
        for chat_id, chat_data in chat_storage.items():
            if chat_data["user_id"] == user_id:
                last_message = chat_data["messages"][-1] if chat_data["messages"] else None

                chat_info = {
                    "chat_id": chat_id,
                    "title": chat_data.get("title", f"Чат {chat_id[:8]}..."),
                    "last_message": last_message["message"] if last_message else None,
                    "last_message_time": last_message["timestamp"] if last_message else chat_data["created_at"],
                    "message_count": len(chat_data["messages"])
                }
                user_chats.append(chat_info)

        # Сортируем по времени последнего сообщения
        user_chats.sort(key=lambda x: x["last_message_time"], reverse=True)

        return user_chats[:limit]


@app.post("/api/chat/create")
async def create_new_chat(
        request: CreateChatRequest,
        user=Depends(get_current_user)
):
    """Создание нового чата"""
    chat_id = str(uuid.uuid4())

    chat_data = {
        "chat_id": chat_id,
        "user_id": user["id"],
        "title": request.title,
        "created_at": datetime.now().isoformat(),
        "messages": []
    }

    chat_storage[chat_id] = chat_data

    logger.info(f"New chat created: {chat_id} by user {user['id']}")

    return {"chat_id": chat_id, "title": request.title, "status": "created"}


@app.post("/api/chat/create-tool")
async def create_tool_chat(
        request: CreateToolChatRequest,
        user=Depends(get_current_user)
):
    """Создание чата для инструмента"""
    chat_id = str(uuid.uuid4())

    chat_data = {
        "chat_id": chat_id,
        "user_id": user["id"],
        "title": request.tool_title,
        "tool_type": request.tool_type,
        "description": request.description,
        "created_at": datetime.now().isoformat(),
        "messages": []
    }

    # Добавляем начальное сообщение с описанием инструмента, если оно есть
    if request.description:
        initial_message = {
            "message_id": str(uuid.uuid4()),
            "chat_id": chat_id,
            "user_id": user["id"],
            "message": request.description,
            "type": "assistant",
            "is_tool_description": True,
            "timestamp": datetime.now().isoformat()
        }
        chat_data["messages"].append(initial_message)

    chat_storage[chat_id] = chat_data

    logger.info(f"Tool chat created: {chat_id} for tool: {request.tool_type} by user {user['id']}")

    return {
        "chat_id": chat_id,
        "tool_type": request.tool_type,
        "tool_title": request.tool_title,
        "status": "created"
    }


# СИСТЕМНЫЕ ЭНДПОИНТЫ
@app.get("/")
async def health_check():
    """Проверка состояния сервера"""
    ai_service = get_ai_service()
    gpt_status = "available" if ai_service else "unavailable"

    if ai_service:
        try:
            gpt_healthy = await ai_service.health_check()
            gpt_status = "healthy" if gpt_healthy else "error"
        except:
            gpt_status = "error"

    return {
        "status": "ok",
        "message": "School Assistant API is running",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "gpt_status": gpt_status,
        "stats": {
            "users": len(user_storage),
            "chats": len(chat_storage)
        }
    }


@app.get("/api/system/info")
async def get_system_info():
    """Информация о системе"""
    total_messages = sum(len(chat["messages"]) for chat in chat_storage.values())

    return {
        "api_name": "School Assistant API",
        "version": "1.0.0",
        "status": "running",
        "statistics": {
            "total_users": len(user_storage),
            "total_chats": len(chat_storage),
            "total_messages": total_messages
        },
        "endpoints": {
            "auth": "/api/auth/telegram",
            "profile": "/api/user/profile",
            "chat_send": "/api/chat/send",
            "chat_ai": "/api/chat/ai-response",
            "chat_history": "/api/chat/history"
        }
    }


# DEBUG ЭНДПОИНТЫ (только для разработки)
@app.get("/api/debug/storage")
async def debug_get_storage():
    """DEBUG: Просмотр всего хранилища"""
    return {
        "users": user_storage,
        "chats": {k: {**v, "messages": len(v["messages"])} for k, v in chat_storage.items()}
    }


@app.delete("/api/debug/clear")
async def debug_clear_storage():
    """DEBUG: Очистка хранилища"""
    chat_storage.clear()
    user_storage.clear()
    return {"status": "cleared", "message": "All data cleared"}


if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting School Assistant API...")
    print("📍 Server: http://127.0.0.1:8000")
    print("📚 API Docs: http://127.0.0.1:8000/docs")

    uvicorn.run(app, host="127.0.0.1", port=3213)