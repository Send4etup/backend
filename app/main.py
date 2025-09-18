# app/main.py (ПОЛНОСТЬЮ ОБНОВЛЕННАЯ ВЕРСИЯ)
"""
ТоварищБот Backend API с полной SQLite интеграцией
"""
from fastapi import FastAPI, HTTPException, Depends, status, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
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
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    telegram_id: Optional[int] = None


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

@app.post("/api/auth/telegram")
async def telegram_auth_secure(
        request: TelegramAuthRequest,
        services: ServiceContainer = Depends(get_services)
):
    """Безопасная авторизация через Telegram с JWT"""
    try:
        # Создаем или находим пользователя
        user = await services.user_service.authenticate_or_create_user(
            request.dict(exclude_none=True)
        )

        # Создаем безопасный JWT токен
        token = JWTManager.create_access_token({
            "user_id": user.user_id,
            "telegram_id": user.telegram_id,
            "subscription_type": user.subscription_type
        })

        logger.info(f"✅ User authenticated successfully: {user.user_id}")

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": JWT_EXPIRATION_HOURS * 3600,  # в секундах
            "user": {
                "user_id": user.user_id,
                "telegram_id": user.telegram_id,
                "subscription_type": user.subscription_type,
                "tokens_balance": user.tokens_balance,
            }
        }

    except Exception as e:
        logger.error(f"❌ Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


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

@app.get("/api/user/profile", response_model=UserProfileResponse)
async def get_user_profile(
        user: User = Depends(get_current_user),
        services: ServiceContainer = Depends(get_services)
):
    """Получение профиля пользователя"""
    profile = services.user_service.get_user_profile(user.user_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )

    return UserProfileResponse(
        **profile,
        # display_name=user.display_name,
        subscription_limits=user.get_subscription_limits()
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
        message: str = Form(...),
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

        # 3. Отправляем сообщение пользователя
        user_message = None
        if message.strip():
            user_message = services.chat_service.send_message(
                chat_id, user.user_id, message, "user"
            )
            logger.info(f"Sent user message: {user_message.message_id}")

            # Связываем файлы с сообщением
            for file_data in uploaded_files:
                try:
                    # Обновляем attachment в БД
                    attachment = services.file_service.attachment_repo.get_by_id(file_data["file_id"])
                    if attachment:
                        attachment.message_id = user_message.message_id
                        services.file_service.attachment_repo.db.commit()
                except Exception as e:
                    logger.error(f"Error linking file to message: {e}")

        # 4. Списываем токены за сообщение
        tokens_used = 1  # Базовая стоимость сообщения
        tokens_used += len(uploaded_files) * 2  # +2 токена за каждый файл

        if user.tokens_balance >= tokens_used:
            services.user_service.user_repo.deduct_tokens(user.user_id, tokens_used)
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
            response_data["message"] = f"Загружено файлов: {len(uploaded_files)}"

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
    """Получение ответа от ИИ"""
    try:
        if not request.chat_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chat ID is required"
            )

        # Получаем контекст чата для ИИ
        chat_history = services.chat_service.get_chat_for_ai_context(request.chat_id)

        # Получаем ответ от ИИ
        ai_service = get_ai_service()
        if not ai_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI service is not available"
            )

        ai_response = await ai_service.get_response(
            request.message,
            request.context,
            chat_history,
            []  # Файлы пока пустые
        )

        # Сохраняем ответ ИИ в чат
        ai_message = services.chat_service.send_message(
            request.chat_id, user.user_id, ai_response, "assistant", tokens_count=2
        )

        # Списываем токены
        services.user_service.use_tokens(user.user_id, 2)

        return {
            "message_id": ai_message.message_id,
            "response": ai_response,
            "tokens_used": 2,
            "timestamp": ai_message.created_at.isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting AI response: {e}")
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