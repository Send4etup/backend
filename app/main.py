from fastapi import FastAPI, HTTPException, Depends, status, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid
import asyncio
import random
import os
import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv
import aiofiles
import magic  # для определения типа файла
from PIL import Image
import hashlib
import mimetypes

from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chat, Message
from app.services.ai_service import get_ai_service, AIService
from app.services.cleanup_service import get_cleanup_service

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

# Создаем директории для файлов
UPLOAD_DIR = Path("../uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Поддерживаемые типы файлов
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
   'audio/webm', 'audio/ogg', 'audio/vorbis', 'audio/flac',
   'audio/x-flac', 'audio/3gpp', 'audio/amr', 'audio/opus'
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_FILES_PER_MESSAGE = 10

# Монтируем статические файлы
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Схема авторизации (опционально)
security = HTTPBearer(auto_error=False)

# Временное хранилище
chat_storage = {}
user_storage = {}
file_storage = {}

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


class FileInfo(BaseModel):
    file_id: str
    original_name: str
    file_path: str
    file_url: str
    file_type: str
    file_size: int
    created_at: str


# Модели ответов
class AuthResponse(BaseModel):
    token: str
    user: Dict[str, Any]


class MessageResponse(BaseModel):
    message_id: str
    chat_id: str
    status: str
    timestamp: str
    files: Optional[List[FileInfo]] = []


class AIResponse(BaseModel):
    message: str
    response_id: str
    timestamp: str


class FileUploadResponse(BaseModel):
    file_id: str
    file_info: FileInfo
    status: str


# Утилиты для работы с файлами
def get_file_hash(file_content: bytes) -> str:
    """Генерация хеша файла"""
    return hashlib.md5(file_content).hexdigest()


def get_safe_filename(filename: str) -> str:
    """Безопасное имя файла"""
    # Удаляем опасные символы
    safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_"
    safe_name = "".join(c for c in filename if c in safe_chars)
    return safe_name[:100] if safe_name else "unnamed_file"


def is_supported_file_type(file_type: str) -> bool:
    """Проверка поддерживаемого типа файла"""
    return file_type in SUPPORTED_IMAGE_TYPES or file_type in SUPPORTED_DOCUMENT_TYPES or file_type in SUPPORTED_AUDIO_TYPES

def is_image_file(file_type: str) -> bool:
    """Проверка, является ли файл изображением"""
    return file_type in SUPPORTED_IMAGE_TYPES

def is_audio_file(file_type: str) -> bool:
    """Проверка, является ли файл аудио"""
    return file_type in SUPPORTED_AUDIO_TYPES

async def save_uploaded_file(file: UploadFile, user_id: int) -> FileInfo:
    """Сохранение загруженного файла"""
    # Читаем содержимое файла
    content = await file.read()
    await file.seek(0)  # Возвращаем указатель в начало

    # Проверяем размер
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Файл слишком большой. Максимальный размер: {MAX_FILE_SIZE // (1024 * 1024)} MB"
        )

    # Определяем тип файла
    file_type = file.content_type
    if not file_type:
        file_type = mimetypes.guess_type(file.filename)[0] or 'application/octet-stream'

    # Проверяем поддерживаемый тип
    if not is_supported_file_type(file_type):
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый тип файла: {file_type}"
        )

    # Генерируем уникальное имя файла
    file_hash = get_file_hash(content)
    file_extension = Path(file.filename).suffix.lower() if file.filename else ""
    safe_filename = get_safe_filename(file.filename or "file")

    file_id = str(uuid.uuid4())
    unique_filename = f"{file_id}_{file_hash[:8]}{file_extension}"

    # Создаем путь для сохранения
    user_dir = UPLOAD_DIR / str(user_id)
    user_dir.mkdir(exist_ok=True)

    file_path = user_dir / unique_filename

    # Сохраняем файл
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)

    # Если это изображение, создаем превью (опционально)
    if is_image_file(file_type):
        try:
            await create_image_thumbnail(file_path)
        except Exception as e:
            logger.warning(f"Failed to create thumbnail for {file_path}: {e}")

    # Создаем информацию о файле
    file_info = FileInfo(
        file_id=file_id,
        original_name=file.filename or "unnamed",
        file_path=str(file_path),
        file_url=f"/uploads/{user_id}/{unique_filename}",
        file_type=file_type,
        file_size=len(content),
        created_at=datetime.now().isoformat()
    )

    # Сохраняем в storage
    file_storage[file_id] = {
        **file_info.dict(),
        "user_id": user_id,
        "hash": file_hash
    }

    logger.info(f"File saved: {file_id} ({file.filename}) by user {user_id}")

    return file_info


async def create_image_thumbnail(image_path: Path, max_size: int = 300):
    """Создание превью для изображения"""
    try:
        thumbnail_path = image_path.parent / f"thumb_{image_path.name}"

        with Image.open(image_path) as img:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            img.save(thumbnail_path, optimize=True, quality=85)

        logger.info(f"Thumbnail created: {thumbnail_path}")
    except Exception as e:
        logger.error(f"Error creating thumbnail for {image_path}: {e}")


def analyze_file_for_ai(file_info: FileInfo) -> str:
    """Анализ файла для передачи контекста в AI"""
    context = f"Файл: {file_info.original_name} ({file_info.file_type}), размер: {file_info.file_size // 1024} KB"

    if is_image_file(file_info.file_type):
        context += " [Изображение]"
    elif is_audio_file(file_info.file_type):
        context += " [Аудиофайл]"
    elif "pdf" in file_info.file_type:
        context += " [PDF документ]"
    elif "word" in file_info.file_type or "document" in file_info.file_type:
        context += " [Текстовый документ]"
    elif "excel" in file_info.file_type or "spreadsheet" in file_info.file_type:
        context += " [Электронная таблица]"

    return context


# Вспомогательные функции
def generate_mock_token(telegram_id: int) -> str:
    return f"mock_token_{telegram_id}_{int(datetime.now().timestamp())}"


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Получение текущего пользователя (без проверки токена)"""
    return DEFAULT_USER


async def get_gpt_response(message: str, context: Dict[str, Any] = {}) -> str:
    """Получить ответ от GPT или fallback"""
    ai_service = get_ai_service()

    if ai_service is None:
        print("AI сервис не запустился!")
        return await simulate_ai_response(message, context)

    try:
        # Получаем историю чата для контекста
        chat_id = context.get('chat_id')
        chat_history = []

        if chat_id and chat_id in chat_storage:
            chat_history = chat_storage[chat_id]["messages"]

        # Получаем данные файлов из последнего сообщения
        files_data = []
        if chat_id and chat_id in chat_storage:
            messages = chat_storage[chat_id]["messages"]
            if messages:
                last_message = messages[-1]
                if last_message.get("files") and last_message.get("type") == "user":
                    files_data = last_message["files"]
                    logger.info(f"Found {len(files_data)} files in last message for AI processing")

        # Вызываем GPT с файлами (файлы будут автоматически удалены после обработки)
        response = await ai_service.get_response(
            message,
            context,
            chat_history,
            files_data
        )

        # Удаляем информацию о файлах из storage после успешной обработки
        if files_data:
            for file_data in files_data:
                file_id = file_data.get('file_id')
                if file_id and file_id in file_storage:
                    del file_storage[file_id]
                    logger.info(f"File {file_id} removed from storage after processing")

        return response

    except Exception as e:
        logger.error(f"GPT error, falling back to static response: {e}")

        # В случае ошибки тоже очищаем файлы
        if context.get('chat_id') and context['chat_id'] in chat_storage:
            messages = chat_storage[context['chat_id']]["messages"]
            if messages:
                last_message = messages[-1]
                if last_message.get("files"):
                    for file_data in last_message["files"]:
                        file_id = file_data.get('file_id')
                        file_path = file_data.get('file_path')

                        # Удаляем файл с диска
                        if file_path and os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                                logger.info(f"Cleaned up file after error: {file_path}")
                            except Exception as cleanup_error:
                                logger.warning(f"Failed to cleanup file {file_path}: {cleanup_error}")

                        # Удаляем из storage
                        if file_id and file_id in file_storage:
                            del file_storage[file_id]

        return await simulate_ai_response(message, context)


async def simulate_ai_response(message: str, context: Dict[str, Any] = {}) -> str:
    """Статичная симуляция ИИ (fallback)"""
    await asyncio.sleep(random.uniform(0.5, 1.0))

    tool_type = context.get('tool_type')
    files_context = context.get('files_context', '')

    file_info = ""
    if files_context:
        file_info = f" Вижу прикрепленные файлы: {files_context}."

    if tool_type == 'create_image':
        return f"🎨 (Режим fallback) Понял! Хотите создать изображение: '{message}'.{file_info} Опишите подробнее стиль и детали!"
    elif tool_type == 'coding':
        return f"💻 (Режим fallback) Отличная задача по программированию! '{message}'{file_info} - давайте разберем пошагово."
    elif tool_type == 'brainstorm':
        return f"💡 (Режим fallback) Супер тема для мозгового штурма: '{message}'!{file_info} Вот несколько направлений для размышлений..."
    elif tool_type == 'excuse':
        return f"😅 (Режим fallback) Нужна отмазка для '{message}'?{file_info} Придумываю креативное объяснение!"
    else:
        return f"🤖 (Режим fallback) Интересный вопрос! По теме '{message}'{file_info} могу предложить несколько идей..."


# АВТОРИЗАЦИЯ (упрощенная)
@app.post("/api/auth/telegram", response_model=AuthResponse)
async def simple_auth():
    try:
        token = "simple_token_123"
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

    if profile_data.name:
        user["name"] = profile_data.name
    if profile_data.school_name:
        user["school_name"] = profile_data.school_name
    if profile_data.class_name:
        user["class_name"] = profile_data.class_name

    user["updated_at"] = datetime.now().isoformat()
    user_storage[user_id] = user

    return user


# ФАЙЛЫ
@app.post("/api/files/upload", response_model=FileUploadResponse)
async def upload_file(
        file: UploadFile = File(...),
        chat_id: Optional[str] = Form(None),
        user=Depends(get_current_user)
):
    """Загрузка одиночного файла"""
    try:
        file_info = await save_uploaded_file(file, user["id"])

        return FileUploadResponse(
            file_id=file_info.file_id,
            file_info=file_info,
            status="uploaded"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload file")


@app.get("/api/files/{file_id}", response_model=FileInfo)
async def get_file_info(
        file_id: str,
        user=Depends(get_current_user)
):
    """Получение информации о файле"""
    if file_id not in file_storage:
        raise HTTPException(status_code=404, detail="File not found")

    file_data = file_storage[file_id]

    # Проверяем права доступа
    if file_data["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    return FileInfo(**file_data)


@app.delete("/api/files/{file_id}")
async def delete_file(
        file_id: str,
        user=Depends(get_current_user)
):
    """Удаление файла"""
    if file_id not in file_storage:
        raise HTTPException(status_code=404, detail="File not found")

    file_data = file_storage[file_id]

    # Проверяем права доступа
    if file_data["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    # Удаляем файл с диска
    try:
        file_path = Path(file_data["file_path"])
        if file_path.exists():
            file_path.unlink()

        # Удаляем превью если есть
        thumbnail_path = file_path.parent / f"thumb_{file_path.name}"
        if thumbnail_path.exists():
            thumbnail_path.unlink()

        # Удаляем из storage
        del file_storage[file_id]

        logger.info(f"File deleted: {file_id} by user {user['id']}")

        return {"status": "deleted", "file_id": file_id}

    except Exception as e:
        logger.error(f"Error deleting file {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete file")


# ЧАТ с поддержкой файлов
@app.post("/api/chat/send-with-files", response_model=MessageResponse)
async def send_message_with_files(
        message: Optional[str] = Form(None),
        chat_id: Optional[str] = Form(None),
        tool_type: Optional[str] = Form(None),
        files: List[UploadFile] = File(...),
        user=Depends(get_current_user)
):
    """Отправка сообщения с файлами"""
    if len(files) > MAX_FILES_PER_MESSAGE:
        raise HTTPException(
            status_code=400,
            detail=f"Максимальное количество файлов: {MAX_FILES_PER_MESSAGE}"
        )

    message_id = str(uuid.uuid4())
    chat_id = chat_id or str(uuid.uuid4())

    # Создаем чат если не существует
    if chat_id not in chat_storage:
        chat_storage[chat_id] = {
            "chat_id": chat_id,
            "user_id": user["id"],
            "tool_type": tool_type,
            "created_at": datetime.now().isoformat(),
            "messages": []
        }

    # Загружаем файлы
    uploaded_files = []
    for file in files:
        try:
            file_info = await save_uploaded_file(file, user["id"])
            uploaded_files.append(file_info)
        except HTTPException as e:
            logger.error(f"Failed to upload file {file.filename}: {e.detail}")
            # Можно либо прервать загрузку, либо продолжить с остальными файлами
            continue

    # Сохраняем сообщение с файлами
    message_data = {
        "message_id": message_id,
        "chat_id": chat_id,
        "user_id": user["id"],
        "message": message,
        "tool_type": tool_type,
        "type": "user",
        "files": [f.dict() for f in uploaded_files],
        "timestamp": datetime.now().isoformat()
    }

    chat_storage[chat_id]["messages"].append(message_data)

    logger.info(f"Message with {len(uploaded_files)} files sent to chat {chat_id}")

    return MessageResponse(
        message_id=message_id,
        chat_id=chat_id,
        status="sent",
        timestamp=message_data["timestamp"],
        files=uploaded_files
    )


@app.post("/api/chat/send", response_model=MessageResponse)
async def send_message(
        request: SendMessageRequest,
        user=Depends(get_current_user)
):
    """Отправка текстового сообщения в чат"""
    message_id = str(uuid.uuid4())
    chat_id = request.chat_id or str(uuid.uuid4())

    if chat_id not in chat_storage:
        chat_storage[chat_id] = {
            "chat_id": chat_id,
            "user_id": user["id"],
            "tool_type": request.tool_type,
            "created_at": datetime.now().isoformat(),
            "messages": []
        }

    message_data = {
        "message_id": message_id,
        "chat_id": chat_id,
        "user_id": user["id"],
        "message": request.message,
        "tool_type": request.tool_type,
        "type": "user",
        "files": [],
        "timestamp": datetime.now().isoformat()
    }

    chat_storage[chat_id]["messages"].append(message_data)

    logger.info(f"Message sent to chat {chat_id}: {request.message[:50]}...")

    return MessageResponse(
        message_id=message_id,
        chat_id=chat_id,
        status="sent",
        timestamp=message_data["timestamp"],
        files=[]
    )


@app.post("/api/chat/ai-response", response_model=AIResponse)
async def get_ai_response(
        request: AIResponseRequest,
        user=Depends(get_current_user)
):
    """Получение ответа от ИИ с учетом файлов"""
    try:
        # Анализируем файлы если они есть
        files_context = ""
        if request.context.get("has_files"):
            chat_id = request.context.get("chat_id")
            if chat_id and chat_id in chat_storage:
                last_message = chat_storage[chat_id]["messages"][-1]
                if last_message.get("files"):
                    file_descriptions = []
                    for file_data in last_message["files"]:
                        file_info = FileInfo(**file_data)
                        file_descriptions.append(analyze_file_for_ai(file_info))
                    files_context = "; ".join(file_descriptions)

        # Добавляем контекст файлов
        context_with_files = {
            **request.context,
            "files_context": files_context
        }

        ai_message = await get_gpt_response(request.message, context_with_files)

        response_id = str(uuid.uuid4())
        chat_id = request.context.get("chat_id")
        tool_type = request.context.get("tool_type")

        if chat_id and chat_id in chat_storage:
            ai_response_data = {
                "message_id": response_id,
                "chat_id": chat_id,
                "user_id": user["id"],
                "message": ai_message,
                "tool_type": tool_type,
                "type": "assistant",
                "files": [],
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


@app.post("/api/chat/ai-response-stream")
async def get_ai_response_stream(
        request: AIResponseRequest,
        user=Depends(get_current_user)
):
    """Получение потокового ответа от ИИ с учетом файлов"""

    async def generate_response():
        try:
            logger.info(f"Stream request received: {request.message[:50]}...")

            ai_service = get_ai_service()
            if not ai_service:
                logger.error("AI service is not available")
                yield f"data: {json.dumps({'type': 'error', 'message': 'AI service unavailable'})}\n\n"
                return

            # Анализируем файлы если они есть
            files_context = ""
            if request.context.get("has_files"):
                logger.info("Processing files context...")
                chat_id = request.context.get("chat_id")
                if chat_id and chat_id in chat_storage:
                    last_message = chat_storage[chat_id]["messages"][-1]
                    if last_message.get("files"):
                        file_descriptions = []
                        for file_data in last_message["files"]:
                            file_info = FileInfo(**file_data)
                            file_descriptions.append(analyze_file_for_ai(file_info))
                        files_context = "; ".join(file_descriptions)
                        logger.info(f"Files context prepared: {len(file_descriptions)} files")

            # Добавляем контекст файлов
            context_with_files = {
                **request.context,
                "files_context": files_context
            }

            # Получаем историю чата для контекста
            chat_id = request.context.get("chat_id")
            chat_history = []
            if chat_id and chat_id in chat_storage:
                chat_history = chat_storage[chat_id]["messages"]
                logger.info(f"Chat history loaded: {len(chat_history)} messages")

            # Получаем данные файлов из последнего сообщения
            files_data = []
            if chat_id and chat_id in chat_storage:
                messages = chat_storage[chat_id]["messages"]
                if messages:
                    last_message = messages[-1]
                    if last_message.get("files") and last_message.get("type") == "user":
                        files_data = last_message["files"]
                        logger.info(f"Files data loaded: {len(files_data)} files")

            # Отправляем начальное сообщение
            yield f"data: {json.dumps({'type': 'start'})}\n\n"
            logger.info("Stream started, yielding chunks...")

            chunk_count = 0
            # Получаем потоковый ответ
            async for chunk in ai_service.get_response_stream(
                    request.message,
                    context_with_files,
                    chat_history,
                    files_data
            ):
                chunk_count += 1
                logger.debug(f"Yielding chunk {chunk_count}: {chunk[:30]}...")

                # Отправляем каждый чанк
                chunk_data = {
                    'type': 'chunk',
                    'content': chunk
                }
                yield f"data: {json.dumps(chunk_data)}\n\n"

                # Небольшая задержка для предотвращения блокировки
                await asyncio.sleep(0.01)

            # Сигнал завершения
            logger.info(f"Stream completed successfully. Total chunks: {chunk_count}")
            yield f"data: {json.dumps({'type': 'end'})}\n\n"

            # НE очищаем файлы здесь - пусть это делает обычный процесс
            # Это может вызывать проблемы в streaming режиме

        except Exception as e:
            logger.error(f"AI streaming response error: {str(e)}", exc_info=True)
            error_data = {
                'type': 'error',
                'message': f'Ошибка при генерации ответа: {str(e)}'
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        generate_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@app.get("/api/chat/history")
async def get_chat_history(
        chat_id: Optional[str] = None,
        limit: int = 20,
        user=Depends(get_current_user)
):
    """Получение истории чатов"""
    user_id = user["id"]

    if chat_id:
        if chat_id in chat_storage and chat_storage[chat_id]["user_id"] == user_id:
            chat = chat_storage[chat_id]
            return chat["messages"][-limit:] if chat["messages"] else []
        else:
            return []
    else:
        user_chats = []
        for chat_id, chat_data in chat_storage.items():
            if chat_data["user_id"] == user_id:
                last_message = chat_data["messages"][-1] if chat_data["messages"] else None

                chat_info = {
                    "chat_id": chat_id,
                    "title": chat_data.get("title", f"Чат {chat_id[:8]}..."),
                    "last_message": last_message["message"] if last_message else None,
                    "last_message_time": last_message["timestamp"] if last_message else chat_data["created_at"],
                    "message_count": len(chat_data["messages"]),
                    "has_files": any(msg.get("files") for msg in chat_data["messages"])
                }
                user_chats.append(chat_info)

        user_chats.sort(key=lambda x: x["last_message_time"], reverse=True)
        return user_chats[:limit]


@app.post("/api/chat/create")
async def create_new_chat(
        request: CreateChatRequest,
        user=Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Создание нового чата"""
    chat_id = str(uuid.uuid4())

    chat = Chat(
        chat_id=chat_id,  # UUID чата
        user_id=user["id"],
        type=request.tool_type,
        title=request.tool_title,
        created_at=datetime.utcnow()
    )

    try:
        db.add(chat)
        db.commit()
        db.refresh(chat)  # получаем обновленные данные (id, timestamps)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка создания чата: {e}")

    chat_storage[chat_id] = chat
    logger.info(f"New chat created: {chat_id} by user {user['id']}")

    return {
        "chat_id": chat_id,
        "title": request.title,
        "status": "created"
    }


@app.post("/api/chat/create-tool")
async def create_tool_chat(
        request: CreateToolChatRequest,
        user=Depends(get_current_user),
        db: Session = Depends(get_db)
):
    chat_id = str(uuid.uuid4())

    # Создаем ORM-модель чата
    chat = Chat(
        chat_id=chat_id,                # UUID чата
        user_id=user["id"],
        type=request.tool_type,
        title=request.tool_title,
        created_at=datetime.now()
    )

    try:
        db.add(chat)
        db.commit()
        db.refresh(chat)  # получаем обновленные данные (id, timestamps)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка создания чата: {e}")

    # Если есть описание, создаем первое сообщение
    if request.description:
        initial_message = Message(
            message_id=int(uuid.uuid4()),
            chat_id=chat.chat_id,
            user_id=user["id"],
            content=request.description,
            role="assistant",
        )
        try:
            db.add(initial_message)
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Ошибка сохранения сообщения: {e}")

    return {
        "chat_id": chat.chat_id,
        "tool_type": chat.type,
        "tool_title": chat.title,
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
            "chats": len(chat_storage),
            "files": len(file_storage)
        }
    }


@app.get("/api/system/info")
async def get_system_info():
    """Информация о системе"""
    total_messages = sum(len(chat["messages"]) for chat in chat_storage.values())

    # Получаем статистику хранилища
    cleanup_service = get_cleanup_service()
    storage_stats = cleanup_service.get_storage_stats()

    # Статистика по типам файлов
    file_type_stats = {}
    for file_data in file_storage.values():
        file_type = file_data.get("file_type", "unknown")
        file_type_stats[file_type] = file_type_stats.get(file_type, 0) + 1

    return {
        "api_name": "School Assistant API",
        "version": "2.1.0",
        "status": "running",
        "features": [
            "AI Chat with GPT-4o",
            "Vision Analysis",
            "Document Text Extraction",
            "Auto File Cleanup",
            "OCR Support (Optional)",
            "Specialized Tools"
        ],
        "statistics": {
            "total_users": len(user_storage),
            "total_chats": len(chat_storage),
            "total_messages": total_messages,
            "active_files": len(file_storage),
            "storage_used_mb": storage_stats["total_size_mb"],
            "total_files_on_disk": storage_stats["total_files"],
            "file_types": file_type_stats
        },
        "file_limits": {
            "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
            "max_files_per_message": MAX_FILES_PER_MESSAGE,
            "file_retention_hours": 24,
            "cleanup_interval_hours": 1,
            "supported_image_types": list(SUPPORTED_IMAGE_TYPES),
            "supported_document_types": list(SUPPORTED_DOCUMENT_TYPES),
            "supported_audio_types": list(SUPPORTED_AUDIO_TYPES),
        },
        "ai_status": {
            "service_available": get_ai_service() is not None,
            "model": os.getenv("OPENAI_MODEL", "gpt-4o"),
            "vision_enabled": True,
            "document_processing": True
        },
        "endpoints": {
            "auth": "/api/auth/telegram",
            "profile": "/api/user/profile",
            "file_upload": "/api/files/upload",
            "file_analyze": "/api/files/{file_id}/analyze",
            "chat_send": "/api/chat/send",
            "chat_send_files": "/api/chat/send-with-files",
            "chat_ai": "/api/chat/ai-response",
            "chat_history": "/api/chat/history",
            "system_cleanup": "/api/system/cleanup",
            "storage_stats": "/api/system/storage-stats"
        }
    }


# DEBUG ЭНДПОИНТЫ
@app.get("/api/debug/storage")
async def debug_get_storage():
    """DEBUG: Просмотр всего хранилища"""
    cleanup_service = get_cleanup_service()
    storage_stats = cleanup_service.get_storage_stats()

    return {
        "users": user_storage,
        "chats": {k: {**v, "messages": len(v["messages"])} for k, v in chat_storage.items()},
        "files": {k: {**v, "file_path": "***"} for k, v in file_storage.items()},
        "storage_stats": storage_stats
    }


@app.delete("/api/debug/clear")
async def debug_clear_storage():
    """DEBUG: Очистка хранилища"""
    cleanup_service = get_cleanup_service()

    # Удаляем все файлы
    for file_id, file_data in file_storage.items():
        try:
            file_path = Path(file_data["file_path"])
            if file_path.exists():
                file_path.unlink()

            # Удаляем превью
            thumbnail_path = file_path.parent / f"thumb_{file_path.name}"
            if thumbnail_path.exists():
                thumbnail_path.unlink()
        except Exception as e:
            logger.error(f"Error deleting file during debug cleanup: {e}")

    # Принудительная очистка всех старых файлов
    await cleanup_service.cleanup_old_files()

    # Очищаем storage
    chat_storage.clear()
    user_storage.clear()
    file_storage.clear()

    # Пересоздаем тестового пользователя
    user_storage[1] = DEFAULT_USER.copy()

    # Получаем финальную статистику
    final_stats = cleanup_service.get_storage_stats()

    return {
        "status": "cleared",
        "message": "All data and files cleared",
        "remaining_files": final_stats
    }


@app.get("/api/debug/files")
async def debug_list_files():
    """DEBUG: Список всех файлов"""
    cleanup_service = get_cleanup_service()
    storage_stats = cleanup_service.get_storage_stats()

    files_info = []
    for file_id, file_data in file_storage.items():
        file_path = Path(file_data["file_path"])
        files_info.append({
            "file_id": file_id,
            "original_name": file_data["original_name"],
            "file_type": file_data["file_type"],
            "file_size": file_data["file_size"],
            "exists_on_disk": file_path.exists(),
            "created_at": file_data["created_at"],
            "age_hours": (datetime.now() - datetime.fromisoformat(file_data["created_at"])).total_seconds() / 3600
        })

    return {
        "total_files_in_storage": len(files_info),
        "total_files_on_disk": storage_stats["total_files"],
        "storage_size_mb": storage_stats["total_size_mb"],
        "files": files_info,
        "cleanup_info": {
            "max_age_hours": 24,
            "cleanup_interval_hours": 1,
            "next_cleanup": "Automatic every hour"
        }
    }


@app.post("/api/debug/emergency-cleanup")
async def debug_emergency_cleanup(max_size_mb: float = 100):
    """DEBUG: Экстренная очистка при превышении лимитов"""
    cleanup_service = get_cleanup_service()

    stats_before = cleanup_service.get_storage_stats()
    await cleanup_service.emergency_cleanup(max_size_mb)
    stats_after = cleanup_service.get_storage_stats()

    return {
        "status": "emergency_cleanup_completed",
        "before": stats_before,
        "after": stats_after,
        "freed_mb": stats_before["total_size_mb"] - stats_after["total_size_mb"],
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting School Assistant API with File Support...")
    print("📍 Server: http://127.0.0.1:3213")
    print("📚 API Docs: http://127.0.0.1:3213/docs")
    print("📁 File uploads will be stored in: uploads/")
    print("🔗 Static files available at: http://127.0.0.1:3213/uploads/")

    uvicorn.run(app, host="127.0.0.1", port=3213)