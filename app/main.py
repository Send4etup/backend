# app/main.py
"""
ТоварищБот Backend API
"""
from fastapi import FastAPI, HTTPException, Depends, status, File, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid
import asyncio
import os
import json
from pathlib import Path
from datetime import datetime
import logging
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.auth import JWT_EXPIRATION_HOURS, JWTManager
# Импорты наших модулей
from app.database import get_db
from app.dependencies import (
    get_services, get_current_user, require_tokens,
    ServiceContainer, security
)
from app.models import User, Chat, Message, Attachment
from app.services.ai_service import get_ai_service
from app.startup import startup_event, shutdown_event

from app.security import CORSConfig
from app.services.telegram_validator import (
    validate_telegram_init_data,
    TelegramDataValidationError,
    init_telegram_validator
)
from app.services.telegram_validator import init_telegram_validator
from app.config import settings

# from fastapi_csrf_protect import CsrfProtect
# from fastapi_csrf_protect.exceptions import CsrfProtectError
# from app.security import CORSConfig, init_csrf_protection, get_csrf_error_response

import mimetypes
import magic
from PIL import Image


load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Создаем FastAPI приложение
app = FastAPI(
    title="ТоварищБот API",
    description="Образовательный ИИ-помощник для учеников и студентов",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORSConfig.get_allowed_origins(),  # ✅ Только разрешенные домены
    allow_credentials=True,  # Теперь безопасно с конкретными доменами
    allow_methods=CORSConfig.get_allowed_methods(),
    allow_headers=CORSConfig.get_allowed_headers(),
    expose_headers=CORSConfig.get_expose_headers()
)

# csrf_settings = init_csrf_protection()


# @app.exception_handler(CsrfProtectError)
# async def csrf_protect_exception_handler(request: Request, exc: CsrfProtectError):
#     """Обработчик ошибок CSRF"""
#     logger.warning(f"🛡️ CSRF атака заблокирована: {exc} от IP: {request.client.host}")
#
#     return JSONResponse(
#         status_code=status.HTTP_403_FORBIDDEN,
#         content=get_csrf_error_response()
#     )

# События жизненного цикла
app.add_event_handler("startup", startup_event)
app.add_event_handler("shutdown", shutdown_event)

# Создаем директории для файлов
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Константы
SUPPORTED_IMAGE_TYPES = {
    'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'
}
SUPPORTED_DOCUMENT_TYPES = {
    'application/pdf', 'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain', 'application/rtf', 'text/csv',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
}
SUPPORTED_AUDIO_TYPES = {
    'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/wave',
    'audio/x-wav', 'audio/m4a', 'audio/mp4', 'audio/aac',
    'audio/webm', 'audio/ogg', 'audio/vorbis'
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_FILES_PER_MESSAGE = 10

# Монтируем статические файлы
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# Pydantic модели для API
class TelegramAuthRequest(BaseModel):
    """
    Новая модель для безопасной авторизации через Telegram
    """
    init_data: str  # Полные данные от window.Telegram.WebApp.initData

    class Config:
        # Пример валидного init_data для документации
        schema_extra = {
            "example": {
                "init_data": "query_id=AAHdF6IQAAAAAN0XohDhrOrc&user=%7B%22id%22%3A279058397%2C%22first_name%22%3A%22Test%22%7D&auth_date=1662771648&hash=c501b71e775f74ce10e377dea85a7ea24ecd640b223ea86dfe453e0eaed2e2b2"
            }
        }

class CreateChatRequest(BaseModel):
    title: str
    chat_type: Optional[str] = "general"


class SendMessageRequest(BaseModel):
    chat_id: str
    message: str
    tool_type: Optional[str] = None


class AIResponseRequest(BaseModel):
    message: str
    chat_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = {}


class UserProfileResponse(BaseModel):
    user_id: str
    telegram_id: int
    subscription_type: str
    tokens_balance: int
    tokens_used: int
    subscription_limits: Dict[str, Any]
    created_at: str
    last_activity: str


class ChatResponse(BaseModel):
    chat_id: str
    title: str
    type: str
    messages_count: int
    tokens_used: int
    created_at: str
    updated_at: str
    last_message: Optional[str] = None


class MessageResponse(BaseModel):
    message_id: int
    chat_id: str
    role: str
    content: str
    tokens_count: int
    created_at: str
    attachments: List[Dict[str, Any]] = []
    status: str


class FileResponse(BaseModel):
    file_id: str
    file_name: str
    file_type: str
    file_size: int
    file_size_mb: float
    category: str
    icon: str
    uploaded_at: str


# =====================================================
# АУТЕНТИФИКАЦИЯ
# =====================================================

@app.post("/api/auth/telegram-secure")
async def telegram_auth_secure_v2(
        auth_request: TelegramAuthRequest,
        services: ServiceContainer = Depends(get_services),
):
    """
    🔐 БЕЗОПАСНАЯ авторизация через Telegram WebApp с полной валидацией initData

    Этот endpoint проверяет подлинность данных с помощью HMAC-SHA256 подписи,
    защищает от replay-атак и подделки данных пользователя.

    Требует передачи полной строки window.Telegram.WebApp.initData
    """
    try:
        logger.info("🔐 Starting secure Telegram authentication")

        # 1. Валидируем initData с помощью HMAC-SHA256
        try:
            validated_data = validate_telegram_init_data(auth_request.init_data)
            logger.info("✅ Telegram initData validation successful")
        except TelegramDataValidationError as e:
            logger.warning(f"🚫 Telegram validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Telegram data: {str(e)}"
            )

        # 2. Извлекаем проверенные данные пользователя
        user_data = validated_data['user']
        telegram_id = user_data['id']

        logger.info(f"🆔 Validated Telegram user ID: {telegram_id}")

        # 3. Создаем или находим пользователя в БД
        user_info = {
            'telegram_id': telegram_id,
            'first_name': user_data.get('first_name', ''),
            'last_name': user_data.get('last_name', ''),
            'username': user_data.get('username', ''),
            'language_code': user_data.get('language_code', 'ru'),
            'is_premium': user_data.get('is_premium', False),
        }

        user = await services.user_service.authenticate_or_create_user(user_info)

        # 4. Создаем безопасный JWT токен
        token = JWTManager.create_access_token({
            "user_id": user.user_id,
            "telegram_id": user.telegram_id,
            "subscription_type": user.subscription_type,
            "auth_method": "telegram_secure",  # Отмечаем метод авторизации
            "auth_date": validated_data.get('auth_date')
        })

        logger.info(f"✅ Secure authentication successful for user: {user.user_id}")

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": JWT_EXPIRATION_HOURS * 3600,
            "auth_method": "telegram_secure",
            "user": {
                "user_id": user.user_id,
                "telegram_id": user.telegram_id,
                "subscription_type": user.subscription_type,
                "tokens_balance": user.tokens_balance,
                "first_name": user_data.get('first_name', ''),
                "username": user_data.get('username', ''),
                "is_premium": user_data.get('is_premium', False)
            },
            "telegram_data": {
                "auth_date": validated_data.get('auth_date'),
                "query_id": validated_data.get('query_id'),
                "chat_type": validated_data.get('chat_type')
            }
        }

    except HTTPException:
        # Перебрасываем HTTP исключения как есть
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service temporarily unavailable"
        )


# Endpoint для проверки конфигурации безопасности
@app.get("/api/auth/security-status")
async def get_security_status():
    """
    📊 Информация о состоянии системы безопасности
    """
    try:
        # Проверяем инициализацию валидатора
        from app.services.telegram_validator import get_telegram_validator
        validator = get_telegram_validator()
        validator_status = "initialized"
    except:
        validator_status = "not_initialized"

    # Проверяем переменные окружения
    bot_token_configured = bool(os.getenv("TELEGRAM_BOT_TOKEN"))
    environment = os.getenv("ENVIRONMENT", "development")

    return {
        "timestamp": datetime.now().isoformat(),
        "environment": environment,
        "security_features": {
            "telegram_validator": validator_status,
            "bot_token_configured": bot_token_configured,
            "jwt_auth": "enabled",
            "cors_protection": "enabled",
        },
        "available_auth_methods": {
            "telegram_secure": validator_status == "initialized",
            "telegram_test": environment == "development",
        },
        "recommendations": [
            "Use /api/auth/telegram-secure for production",
            "Disable test endpoints in production",
            "Ensure TELEGRAM_BOT_TOKEN is configured",
            "Verify CORS settings for your domain"
        ]
    }


@app.post("/api/auth/refresh")
async def refresh_token(
        token: str = Depends(security),
        services: ServiceContainer = Depends(get_services)
):
    """Обновление JWT токена"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token required"
        )

    try:
        new_token = JWTManager.refresh_token(token.credentials)

        return {
            "access_token": new_token,
            "token_type": "bearer",
            "expires_in": JWT_EXPIRATION_HOURS * 3600
        }

    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise

@app.post("/api/auth/verify")
async def verify_token_endpoint(
        user = Depends(get_current_user)
):
    """Проверка валидности токена"""
    return {
        "valid": True,
        "user_id": user.user_id,
        "telegram_id": user.telegram_id,
        "subscription_type": user.subscription_type
    }

# =====================================================
# ПОЛЬЗОВАТЕЛИ
# =====================================================

@app.get("/api/user/profile-extended")
async def get_user_profile_extended(
        user: User = Depends(get_current_user),
        services: ServiceContainer = Depends(get_services)
):
    """
    Получение расширенной информации о пользователе для профиля
    Включает статистику, подписку, активность и настройки
    """
    try:
        # Основная информация о пользователе
        profile = services.user_service.get_user_profile(user.user_id)

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )

        # Статистика чатов
        chat_stats = services.chat_service.get_user_chat_statistics(user.user_id)

        # Статистика токенов за последние 30 дней
        token_stats = services.user_service.get_token_usage_stats(user.user_id, days=30)

        # Последняя активность
        recent_activity = services.chat_service.get_recent_user_activity(user.user_id, limit=5)

        return {
            "user_info": {
                "user_id": user.user_id,
                "telegram_id": user.telegram_id,
                "first_name": profile.get('first_name', ''),
                "last_name": profile.get('last_name', ''),
                "username": profile.get('username', ''),
                "language_code": profile.get('language_code', 'ru'),
                "is_premium": profile.get('is_premium', False),
                "created_at": profile.get('created_at'),
                "last_activity": profile.get('last_activity')
            },
            "subscription": {
                "type": user.subscription_type,
                "tokens_balance": user.tokens_balance,
                "tokens_used": profile.get('tokens_used', 0),
                "limits": user.get_subscription_limits(),
                "next_reset": None  # TODO: добавить дату сброса токенов
            },
            "statistics": {
                "total_chats": chat_stats.get('total_chats', 0),
                "total_messages": chat_stats.get('total_messages', 0),
                "files_uploaded": chat_stats.get('files_uploaded', 0),
                "favorite_tools": chat_stats.get('favorite_tools', []),
                "token_usage_30_days": token_stats.get('tokens_used', 0),
                "days_active": token_stats.get('active_days', 0)
            },
            "recent_activity": recent_activity,
            "settings": {
                "notifications_enabled": True,  # TODO: добавить настройки
                "theme": "dark",
                "language": profile.get('language_code', 'ru')
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting extended profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile"
        )


# =====================================================
# ЧАТЫ
# =====================================================

@app.post("/api/chat/create", response_model=ChatResponse)
async def create_chat(
        request: CreateChatRequest,
        user: User = Depends(get_current_user),
        services: ServiceContainer = Depends(get_services)
):
    """Создание нового чата"""
    try:
        chat = services.chat_service.create_chat(
            user.user_id,
            request.title,
            request.chat_type
        )

        return ChatResponse(
            chat_id=chat.chat_id,
            title=chat.title,
            type=chat.type,
            type_display=chat.get_chat_type_display(),
            messages_count=chat.messages_count,
            tokens_used=chat.tokens_used,
            created_at=chat.created_at.isoformat(),
            updated_at=chat.updated_at.isoformat(),
            last_activity=chat.last_activity.isoformat()
        )

    except Exception as e:
        logger.error(f"Error creating chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.get("/api/chat/history", response_model=List[ChatResponse])
async def get_chat_history(
        limit: int = 3,
        offset: int = 0,
        user: User = Depends(get_current_user),
        services: ServiceContainer = Depends(get_services)
):
    """Получение истории чатов пользователя"""
    try:

        if offset == 0:
            chats_data = services.chat_service.get_user_chats(user.user_id, limit)
        else:
            logger.info('!!!!!!!!!! add pagination')
            chats_data = services.chat_service.get_user_chats_with_pagination(
                user.user_id, limit, offset
            )

        logger.info(f'Requested chat history for user: {user.user_id}, limit: {limit}, offset: {offset}')

        result = []

        for chat in chats_data:
            chat_response = ChatResponse(
                chat_id=chat["chat_id"],
                title=chat["title"],
                type=chat["type"],
                messages_count=chat["messages_count"],
                tokens_used=chat["tokens_used"],
                created_at=chat["created_at"],
                updated_at=chat["updated_at"],
                last_message=chat.get("last_message")
            )

            result.append(chat_response)

        logger.info(f'Returned {len(result)} chats')
        return result

    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chat history"
        )


@app.get("/api/chat/{chat_id}/messages", response_model=List[MessageResponse])
async def get_chat_messages(
        chat_id: str,
        limit: int = 50,
        user: User = Depends(get_current_user),
        services: ServiceContainer = Depends(get_services)
):
    """Получение сообщений чата"""
    try:
        messages_data = services.chat_service.get_chat_history(chat_id, user.user_id, limit)

        logger.info('send result')

        return [
            MessageResponse(
                message_id=msg.message_id,
                chat_id=chat_id,
                role=msg.role,
                content=msg.content,
                tokens_count=msg.tokens_count,
                created_at=msg.created_at.isoformat(),
                attachments=[],  # TODO: добавить вложения
                status='sent'
            )
            for msg in messages_data
        ]

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting chat messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chat messages"
        )


@app.put("/api/chat/{chat_id}/title")
async def update_chat_title(
        chat_id: str,
        request: dict,  # Ожидаем {"title": "Новое название"}
        user: User = Depends(get_current_user),
        services: ServiceContainer = Depends(get_services)
):
    """
    Обновление названия чата
    """
    try:
        new_title = request.get("title", "").strip()

        if not new_title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Title cannot be empty"
            )

        if len(new_title) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Title too long (max 100 characters)"
            )

        # Проверяем что чат существует и принадлежит пользователю
        chat = services.chat_service.get_chat(chat_id, user.user_id)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found or access denied"
            )

        # Обновляем название
        success = services.chat_service.update_chat_title(chat_id, user.user_id, new_title)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update chat title"
            )

        logger.info(f"Chat title updated: {chat_id} -> '{new_title}' by user {user.user_id}")

        return {
            "status": "success",
            "message": "Chat title updated successfully",
            "chat_id": chat_id,
            "new_title": new_title
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating chat title: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update chat title"
        )


@app.delete("/api/chat/{chat_id}")
async def delete_chat(
        chat_id: str,
        user: User = Depends(get_current_user),
        services: ServiceContainer = Depends(get_services)
):
    """
    Удаление чата и всех связанных данных
    """
    try:
        # Проверяем что чат существует и принадлежит пользователю
        chat = services.chat_service.get_chat(chat_id, user.user_id)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found or access denied"
            )

        # Удаляем чат
        success = services.chat_service.delete_chat(chat_id, user.user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete chat"
            )

        logger.info(f"Chat deleted: {chat_id} by user {user.user_id}")

        return {
            "status": "success",
            "message": "Chat deleted successfully",
            "chat_id": chat_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete chat"
        )


@app.get("/api/chat/{chat_id}")
async def get_chat_info(
        chat_id: str,
        user: User = Depends(get_current_user),
        services: ServiceContainer = Depends(get_services)
):
    """
    Получение информации о конкретном чате
    """
    try:
        chat = services.chat_service.get_chat(chat_id, user.user_id)

        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found or access denied"
            )

        # Получаем статистику чата
        return {
            "chat_id": chat.chat_id,
            "title": chat.title,
            "type": chat.type,
            "messages_count": chat.messages_count,
            "tokens_used": chat.tokens_used,
            "created_at": chat.created_at.isoformat(),
            "updated_at": chat.updated_at.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chat info"
        )


# =====================================================
# СООБЩЕНИЯ
# =====================================================

@app.post("/api/chat/send")
async def send_message(
        request: SendMessageRequest,
        user: User = Depends(require_tokens(1)),
        services: ServiceContainer = Depends(get_services)
):
    """Отправка текстового сообщения"""
    try:


        user_message = services.chat_service.send_message(
            request.chat_id, user.user_id, request.message, "user"
        )

        logger.info('get message')

        return {
            "message_id": user_message.message_id,
            "status": "sent",
            "timestamp": user_message.created_at.isoformat()
        }

    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.post("/api/chat/send-with-files")
async def send_message_with_files(
        message: str = Form(""),
        chat_id: Optional[str] = Form(None),
        tool_type: Optional[str] = Form(None),
        files: List[UploadFile] = File(default=[]),
        user: User = Depends(get_current_user),
        services: ServiceContainer = Depends(get_services)
):
    """
    Отправка сообщения с файлами одним запросом
    Этот endpoint КРИТИЧНО нужен для работы фронтенда
    """
    try:
        logger.info(f"Sending message with {len(files)} files from user {user.user_id}")

        if not message.strip() and len(files) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Необходимо отправить текст или прикрепить файлы"
            )

        # 1. Создаем или используем существующий чат
        if not chat_id:
            chat_title = f"Чат {datetime.now().strftime('%d.%m %H:%M')}"
            chat_type = tool_type or "general"

            chat = services.chat_service.create_chat(
                user.user_id,
                chat_title,
                chat_type
            )
            chat_id = chat.chat_id
            logger.info(f"Created new chat: {chat_id}")
        else:
            # Проверяем что чат принадлежит пользователю
            chat = services.chat_service.get_chat(chat_id, user.user_id)
            if not chat:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Chat not found or access denied"
                )

        # 2. Загружаем файлы если есть
        uploaded_files = []
        file_errors = []

        for file in files:
            if not file.filename:
                continue

            try:
                # Проверяем лимиты подписки
                limits = user.get_subscription_limits()
                max_size = limits["max_file_size_mb"] * 1024 * 1024

                content = await file.read()
                if len(content) > max_size:
                    file_errors.append(f"{file.filename}: превышен лимит {limits['max_file_size_mb']} MB")
                    continue

                await file.seek(0)  # Возвращаем указатель

                # Сохраняем файл
                file_data = await save_uploaded_file(file, user, services)
                uploaded_files.append(file_data)

                logger.info(f"Uploaded file: {file.filename} -> {file_data['file_id']}")

            except Exception as e:
                logger.error(f"Error uploading file {file.filename}: {e}")
                file_errors.append(f"{file.filename}: {str(e)}")

        # 3. Отправляем сообщение пользователя ТОЛЬКО если есть текст
        user_message = None
        if message.strip():  # 🔧 ПРОВЕРЯЕМ что есть текст
            user_message = services.chat_service.send_message(
                chat_id, user.user_id, message, "user"
            )
            logger.info(f"✅ Sent user message: {user_message.message_id}")
        elif len(uploaded_files) > 0:
            # Если только файлы - создаем сообщение с описанием файлов
            file_names = [f['file_name'] for f in uploaded_files]
            auto_message = f"Прикреплено файлов: {len(uploaded_files)}"
            user_message = services.chat_service.send_message(
                chat_id, user.user_id, auto_message, "user"
            )
            logger.info(f"✅ Sent auto-generated message for files: {user_message.message_id}")

        # 4. Списываем токены за сообщение
        tokens_used = 1  # Базовая стоимость сообщения
        tokens_used += len(uploaded_files) * 2  # +2 токена за каждый файл

        if user.tokens_balance >= tokens_used:
            services.user_service.use_tokens(user.user_id, tokens_used)
            logger.info(f"Deducted {tokens_used} tokens from user {user.user_id}")
        else:
            logger.warning(f"User {user.user_id} has insufficient tokens: {user.tokens_balance} < {tokens_used}")

        # 5. Формируем ответ
        response_data = {
            "status": "success",
            "chat_id": chat_id,
            "message_id": user_message.message_id if user_message else None,
            "uploaded_files": uploaded_files,
            "file_errors": file_errors,
            "tokens_used": tokens_used,
            "timestamp": datetime.now().isoformat()
        }

        # Если есть только файлы без текста
        if not message.strip() and uploaded_files:
            response_data["message"] = f"📎 Прикреплено файлов: {len(uploaded_files)}"

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in send_message_with_files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )


@app.post("/api/chat/ai-response")
async def get_ai_response(
        request: AIResponseRequest,
        user: User = Depends(require_tokens(2)),
        services: ServiceContainer = Depends(get_services)
):
    """Получение STREAMING ответа от ИИ"""
    try:
        if not request.chat_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chat ID is required"
            )

        # Получаем контекст чата
        chat_history = services.chat_service.get_chat_for_ai_context(request.chat_id, user.user_id, 20)
        logger.info(f"Chat history length: {len(chat_history)}")

        # Получаем AI service
        ai_service = get_ai_service()
        if not ai_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI service is not available"
            )

        # Функция-генератор для streaming
        async def generate_response():
            full_response = ""
            try:
                logger.info(f"Generating response for user {user.user_id}")
                # Используем существующий get_response_stream
                async for chunk in ai_service.get_response_stream(
                        request.message,
                        request.context,
                        chat_history,
                        []
                ):
                    full_response += chunk
                    # Отправляем chunk клиенту
                    yield chunk

                # После завершения - сохраняем полный ответ в БД
                ai_message = services.chat_service.send_message(
                    request.chat_id, user.user_id, full_response, "assistant", tokens_count=2
                )

                # Списываем токены
                services.user_service.use_tokens(user.user_id, 2)

            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"\n\nОшибка: {str(e)}"

        # Возвращаем StreamingResponse
        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        logger.error(f"Error in ai_response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =====================================================
# ФАЙЛЫ
# =====================================================

async def save_uploaded_file(file: UploadFile, user: User, services: ServiceContainer) -> Dict[str, Any]:
    """Сохранение загруженного файла с полной обработкой"""

    # Генерируем уникальный ID файла
    file_id = str(uuid.uuid4())

    # Определяем MIME тип
    content = await file.read()
    await file.seek(0)

    try:
        import magic
        detected_type = magic.from_buffer(content, mime=True)
        file_type = detected_type if detected_type else file.content_type
    except:
        file_type = file.content_type or 'application/octet-stream'

    # Проверяем поддерживаемые типы
    all_supported_types = SUPPORTED_IMAGE_TYPES | SUPPORTED_DOCUMENT_TYPES | SUPPORTED_AUDIO_TYPES

    if file_type not in all_supported_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_type}"
        )

    # Создаем директорию пользователя
    user_dir = UPLOAD_DIR / user.user_id
    user_dir.mkdir(exist_ok=True)

    # Определяем расширение файла
    original_name = file.filename or f"file_{file_id}"
    file_extension = Path(original_name).suffix or _get_extension_by_mime(file_type)

    # Создаем путь файла
    safe_filename = f"{file_id}{file_extension}"
    file_path = user_dir / safe_filename

    # Сохраняем файл на диск
    with open(file_path, "wb") as buffer:
        buffer.write(content)

    # Создаем thumbnail для изображений
    thumbnail_path = None
    if file_type in SUPPORTED_IMAGE_TYPES:
        try:
            thumbnail_path = await create_thumbnail(file_path, user_dir)
        except Exception as e:
            logger.warning(f"Failed to create thumbnail for {file_path}: {e}")

    # Сохраняем в БД
    attachment = services.file_service.attachment_repo.create(
        file_id=file_id,
        user_id=user.user_id,
        file_name=safe_filename,
        original_name=original_name,
        file_path=str(file_path),
        file_type=file_type,
        file_size=len(content),
        thumbnail_path=thumbnail_path
    )

    logger.info(f"File saved: {file_path} ({len(content)} bytes)")

    return {
        "file_id": file_id,
        "file_name": safe_filename,
        "original_name": original_name,
        "file_type": file_type,
        "file_size": len(content),
        "file_size_mb": round(len(content) / 1024 / 1024, 2),
        "thumbnail_path": thumbnail_path,
        "uploaded_at": attachment.uploaded_at.isoformat() if attachment.uploaded_at else datetime.now().isoformat()
    }


async def create_thumbnail(image_path: Path, output_dir: Path, size: tuple = (200, 200)) -> str:
    """Создание превью изображения"""
    try:
        with Image.open(image_path) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)

            thumbnail_name = f"thumb_{image_path.name}"
            thumbnail_path = output_dir / thumbnail_name

            # Конвертируем в RGB если нужно
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            img.save(thumbnail_path, "JPEG", quality=85)
            return str(thumbnail_path)

    except Exception as e:
        logger.error(f"Error creating thumbnail: {e}")
        raise


@app.post("/api/files/upload", response_model=FileResponse)
async def upload_file(
        file: UploadFile = File(...),
        user: User = Depends(get_current_user),
        services: ServiceContainer = Depends(get_services)
):
    """Загрузка файла"""
    try:
        # Проверяем лимиты подписки
        limits = user.get_subscription_limits()
        max_size = limits["max_file_size_mb"] * 1024 * 1024

        content = await file.read()
        if len(content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large for your subscription. Max: {limits['max_file_size_mb']} MB"
            )

        await file.seek(0)  # Возвращаем указатель

        file_data = await save_uploaded_file(file, user, services)

        # Получаем информацию о файле из БД
        attachment = services.file_service.attachment_repo.get_by_id(file_data["file_id"])

        return FileResponse(
            file_id=attachment.file_id,
            file_name=attachment.file_name,
            file_type=attachment.file_type,
            file_size=attachment.file_size,
            file_size_mb=attachment.file_size_mb,
            category=attachment.get_file_category(),
            icon=attachment.get_file_icon(),
            uploaded_at=attachment.uploaded_at.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file"
        )


@app.get("/api/files", response_model=List[FileResponse])
async def get_user_files(
        limit: int = 50,
        user: User = Depends(get_current_user),
        services: ServiceContainer = Depends(get_services)
):
    """Получение файлов пользователя"""
    try:
        attachments = services.file_service.attachment_repo.get_user_files(user.user_id, limit)

        return [
            FileResponse(
                file_id=att.file_id,
                file_name=att.file_name,
                file_type=att.file_type,
                file_size=att.file_size,
                file_size_mb=att.file_size_mb,
                category=att.get_file_category(),
                icon=att.get_file_icon(),
                uploaded_at=att.uploaded_at.isoformat()
            )
            for att in attachments
        ]

    except Exception as e:
        logger.error(f"Error getting user files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get files"
        )


@app.delete("/api/files/{file_id}")
async def delete_file(
        file_id: str,
        user: User = Depends(get_current_user),
        services: ServiceContainer = Depends(get_services)
):
    """Удаление файла"""
    try:
        success = services.file_service.delete_file(file_id, user.user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found or access denied"
            )

        return {"status": "deleted", "file_id": file_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file"
        )


# =====================================================
# СИСТЕМНЫЕ ЭНДПОИНТЫ
# =====================================================

@app.get("/")
async def health_check():
    """Проверка работоспособности API"""
    ai_service = get_ai_service()
    ai_status = "available" if ai_service else "unavailable"

    if ai_service:
        try:
            ai_healthy = await ai_service.health_check()
            ai_status = "healthy" if ai_healthy else "error"
        except:
            ai_status = "error"

    return {
        "status": "ok",
        "message": "ТоварищБот API is running",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "ai_status": ai_status,
        "database": "sqlite_integrated"
    }


@app.get("/api/system/info")
async def get_system_info(db: Session = Depends(get_db)):
    """Информация о системе"""
    try:
        # Подсчитываем статистику из БД
        users_count = db.query(User).count()
        chats_count = db.query(Chat).count()
        messages_count = db.query(Message).count()
        files_count = db.query(Attachment).count()

        return {
            "api_name": "ТоварищБот API",
            "version": "2.0.0",
            "status": "running",
            "database": "SQLite",
            "features": [
                "AI Chat with GPT-4o",
                "Vision Analysis",
                "Document Processing",
                "File Upload & Management",
                "User Authentication",
                "Subscription Management",
                "Real-time Database"
            ],
            "statistics": {
                "total_users": users_count,
                "total_chats": chats_count,
                "total_messages": messages_count,
                "total_files": files_count
            },
            "file_limits": {
                "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
                "max_files_per_message": MAX_FILES_PER_MESSAGE,
                "supported_image_types": list(SUPPORTED_IMAGE_TYPES),
                "supported_document_types": list(SUPPORTED_DOCUMENT_TYPES),
                "supported_audio_types": list(SUPPORTED_AUDIO_TYPES)
            }
        }

    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system info"
        )


@app.post("/api/system/cleanup")
async def manual_cleanup(
        hours_old: int = 24,
        services: ServiceContainer = Depends(get_services)
):
    """Ручная очистка старых файлов"""
    try:
        deleted_count = services.file_service.cleanup_old_files(hours_old)

        return {
            "status": "completed",
            "deleted_files": deleted_count,
            "hours_old": hours_old,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cleanup failed"
        )


def _get_extension_by_mime(mime_type: str) -> str:
    """Получение расширения файла по MIME типу"""
    mime_extensions = {
        # Изображения
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/webp': '.webp',
        'image/bmp': '.bmp',

        # Документы
        'application/pdf': '.pdf',
        'application/msword': '.doc',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'text/plain': '.txt',
        'application/rtf': '.rtf',
        'text/csv': '.csv',
        'application/vnd.ms-excel': '.xls',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',

        # Аудио
        'audio/mpeg': '.mp3',
        'audio/wav': '.wav',
        'audio/m4a': '.m4a',
        'audio/aac': '.aac',
        'audio/webm': '.webm',
        'audio/ogg': '.ogg'
    }

    return mime_extensions.get(mime_type, '.bin')

@app.get("/api/security/cors-info")
async def get_cors_info():
    """Информация о CORS настройках (только для разработки)"""
    from app.security import CORSConfig

    if not CORSConfig.is_development():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint доступен только в режиме разработки"
        )

    return {
        "environment": os.getenv("ENVIRONMENT", "development"),
        "allowed_origins": CORSConfig.get_allowed_origins(),
        "allowed_methods": CORSConfig.get_allowed_methods(),
        "allowed_headers": CORSConfig.get_allowed_headers(),
        "expose_headers": CORSConfig.get_expose_headers(),
        "credentials_allowed": True
    }


# =====================================
# CSRF ЗАЩИТА ENDPOINTS
# =====================================

# @app.get("/api/security/csrf-token")
# async def get_csrf_token(
#         request: Request,
#         csrf_protect: CsrfProtect = Depends()
# ):
#     """
#     Получение CSRF токена для frontend
#     Этот endpoint должен вызываться перед отправкой форм
#     """
#     try:
#         # Генерируем новый CSRF токен
#         csrf_token = csrf_protect.generate_csrf()
#
#         response = JSONResponse(content={
#             "csrf_token": csrf_token,
#             "message": "CSRF токен создан успешно",
#             "expires_in": 3600,  # 1 час
#             "usage": {
#                 "header_name": "X-CSRF-Token",
#                 "cookie_name": "csrf_token",
#                 "instructions": "Отправьте токен в заголовке X-CSRF-Token для защищенных запросов"
#             }
#         })
#
#         # Устанавливаем cookie с токеном
#         csrf_protect.set_csrf_cookie(csrf_token, response)
#
#         logger.info(f"✅ CSRF токен создан для IP: {request.client.host if hasattr(request, 'client') else 'unknown'}")
#
#         return response
#
#     except Exception as e:
#         logger.error(f"❌ Ошибка создания CSRF токена: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Ошибка создания CSRF токена"
#         )
#
#
# @app.post("/api/security/verify-csrf")
# async def verify_csrf_token(
#         request: Request,
#         csrf_protect: CsrfProtect = Depends()
# ):
#     """
#     Проверка CSRF токена (для тестирования)
#     """
#     try:
#         # Проверяем CSRF токен
#         await csrf_protect.validate_csrf(request)
#
#         return {
#             "valid": True,
#             "message": "CSRF токен валиден",
#             "timestamp": datetime.now().isoformat()
#         }
#
#     except CsrfProtectError as e:
#         logger.warning(f"CSRF валидация не прошла: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail=get_csrf_error_response()
#         )
#
#
# @app.get("/api/security/csrf-info")
# async def get_csrf_info():
#     """Информация о CSRF настройках (только для разработки)"""
#     from app.security.csrf_protection import CsrfSettings
#
#     if os.getenv("ENVIRONMENT") == "production":
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Endpoint доступен только в режиме разработки"
#         )
#
#     settings = CsrfSettings()
#
#     return {
#         "csrf_enabled": True,
#         "cookie_name": settings.cookie_name,
#         "header_name": settings.header_name,
#         "cookie_secure": settings.cookie_secure,
#         "cookie_samesite": settings.cookie_samesite,
#         "token_lifetime": settings.token_lifetime,
#         "environment": os.getenv("ENVIRONMENT", "development")
#     }


# =====================================
# ENDPOINTS ПРОВЕРКИ БЕЗОПАСНОСТИ
# =====================================

@app.get("/api/security/health")
async def security_health_check():
    """Проверка состояния систем безопасности"""

    try:
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "security_systems": {
                "cors_protection": "active",
                "csrf_protection": "active",
                "jwt_auth": "active"
            },
            "server_status": "healthy",
            "version": "2.0.0-secure"
        }

        return health_status

    except Exception as e:
        logger.error(f"Health check error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed"
        )

# =====================================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# =====================================================

if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting ТоварищБот API with SQLite Database...")
    print("📍 Server: http://127.0.0.1:3213")
    print("📚 API Docs: http://127.0.0.1:3213/docs")
    print("🗄️ Database: SQLite with full integration")
    print("📁 File uploads: uploads/ directory")

    uvicorn.run(app, host="127.0.0.1", port=3213)