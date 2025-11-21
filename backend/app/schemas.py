"""
Pydantic схемы для API запросов и ответов ТоварищБот
Все модели данных для валидации и сериализации
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class TelegramAuthRequest(BaseModel):
    """
    Новая модель для безопасной авторизации через Telegram
    """
    init_data: str  # Полные данные от window.Telegram.WebApp.initData

class CreateChatRequest(BaseModel):
    title: str
    chat_type: Optional[str] = "general"

class SendMessageRequest(BaseModel):
    chat_id: str
    message: str
    tool_type: Optional[str] = None

class ChatContext(BaseModel):
    tool_type: str = 'general'
    agent_prompt: Optional[str] = None
    temperature: float = 0.7

class AIResponseRequest(BaseModel):
    message: str
    chat_id: Optional[str] = None
    context: ChatContext
    file_ids: Optional[List[str]] = None

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

class UserFileResponse(BaseModel):
    file_id: str
    file_name: str
    file_type: str
    file_size: int
    file_size_mb: float
    category: str
    icon: str
    uploaded_at: str

class ImageGenerationRequest(BaseModel):
    """
    Запрос на генерацию изображения через DALL-E
    """
    chat_id: str = Field(..., description="ID чата")
    message: str = Field(..., description="Текстовый промпт для генерации")
    agent_prompt: Optional[str] = Field(None, description="Системный промпт агента")
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Дополнительный контекст (tool_type, temperature)"
    )
    file_ids: Optional[List[str]] = Field(
        default_factory=list,
        description="Массив ID файлов для анализа (опционально)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "chat_id": "chat_123abc",
                "message": "создай в стиле аниме",
                "agent_prompt": "Ты помощник для создания изображений",
                "context": {
                    "tool_type": "images",
                    "temperature": 0.7
                },
                "file_ids": ["file_abc123", "file_xyz789"]
            }
        }

class ImageGenerationResponse(BaseModel):
    """
    Ответ при генерации изображения
    """
    success: bool = Field(..., description="Успешность генерации")
    image_url: Optional[str] = Field(None, description="URL сгенерированного изображения")
    revised_prompt: Optional[str] = Field(None, description="Улучшенный промпт от DALL-E")
    analysis: Optional[str] = Field(None, description="Анализ загруженных изображений")
    message: str = Field(..., description="Сообщение для пользователя")
    error: Optional[str] = Field(None, description="Описание ошибки если есть")
    message_id: Optional[int] = Field(None, description="ID сохранённого сообщения")
    timestamp: Optional[str] = Field(None, description="Время создания")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "image_url": "https://oaidalleapiprodscus.blob.core.windows.net/...",
                "revised_prompt": "An anime-style illustration of a cute cat...",
                "analysis": "На изображении кошка сидит на подоконнике...",
                "message": "Изображение создано! 🎨",
                "message_id": 12345,
                "timestamp": "2025-01-17T10:30:00"
            }
        }

class ChatSettingsRequest(BaseModel):
    """
    Запрос на генерацию настроек чата
    """
    chat_id: str = Field(..., description="ID чата")
    message: str = Field(..., description="Сообщение пользователя для анализа")
    current_settings: Dict = Field(
        default_factory=dict,
        description="Текущие настройки чата"
    )
    context: Dict = Field(
        default_factory=dict,
        description="Дополнительный контекст (tool_type, agent_prompt и т.д.)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "chat_id": "temp_analysis_123",
                "message": "Помоги решить задачу по физике подробно",
                "current_settings": {
                    "temperature": 0.7,
                    "maxLength": "medium",
                    "language": "ru"
                },
                "context": {
                    "tool_type": "exam_prep",
                    "agent_prompt": "Ты помощник для подготовки к экзаменам..."
                }
            }
        }

class ChatSettingsResponse(BaseModel):
    """
    Ответ с рекомендованными настройками
    """
    settings: Dict = Field(..., description="Настройки для изменения")
    success: bool = Field(default=True)

    class Config:
        json_schema_extra = {
            "example": {
                "settings": {
                    "temperature": 0.5,
                    "maxLength": "detailed"
                },
                "success": True
            }
        }