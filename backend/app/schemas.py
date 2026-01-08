"""
Pydantic схемы для API запросов и ответов ТоварищБот
Все модели данных для валидации и сериализации
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# =====================================================
# BASIC SCHEMAS
# =====================================================


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

class UserEducationUpdate(BaseModel):
    user_type: Optional[str] = None
    grade: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "user_type": "schooler",
                "grade": 10
            }
        }

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
    attachment_id: Optional[str] = Field(None, description="ID сгенерированного изображения")
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

# =====================================================
# EXAM MODE - ENUMS
# =====================================================

class ExamType(str, Enum):
    """Тип экзамена"""
    OGE = "ОГЭ"
    EGE = "ЕГЭ"


class Difficulty(str, Enum):
    """Уровень сложности задания"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class AnswerType(str, Enum):
    """Тип ответа на задание"""
    TEXT = "text"
    NUMBER = "number"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"

# =====================================================
# EXAM SETTINGS
# =====================================================

class SubjectBase(BaseModel):
    """Базовая схема предмета"""
    subject_id: str = Field(..., description="ID предмета (математика, русский язык)")
    target_score: Optional[int] = Field(None, ge=0, le=100, description="Целевой балл")


class SubjectCreate(SubjectBase):
    """Схема создания предмета"""
    pass


class SubjectUpdate(BaseModel):
    """Схема обновления предмета"""
    target_score: Optional[int] = Field(None, ge=0, le=100)
    current_score: Optional[int] = Field(None, ge=0, le=100)


class SubjectResponse(SubjectBase):
    """Схема ответа с предметом"""
    id: int
    exam_settings_id: int
    current_score: int = Field(default=0, description="Текущий балл подготовки")
    progress_percentage: int = Field(description="Процент прогресса")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExamSettingsCreate(BaseModel):
    """Схема создания настроек экзамена"""
    exam_type: ExamType = Field(..., description="Тип экзамена (ОГЭ или ЕГЭ)")
    exam_date: Optional[date] = Field(None, description="Дата экзамена")
    subjects: List[SubjectCreate] = Field(..., min_items=1, description="Список предметов для сдачи")

    @validator('subjects')
    def validate_subjects(cls, v):
        """Проверка уникальности предметов"""
        subject_ids = [s.subject_id for s in v]
        if len(subject_ids) != len(set(subject_ids)):
            raise ValueError("Предметы должны быть уникальными")
        return v


class ExamSettingsUpdate(BaseModel):
    """Схема обновления настроек экзамена"""
    exam_date: Optional[date] = None


class ExamSettingsResponse(BaseModel):
    """Схема ответа с настройками экзамена"""
    id: int
    user_id: str
    exam_type: str
    exam_date: Optional[date]
    subjects: List[SubjectResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# =====================================================
# EXAM TASKS
# =====================================================

class TaskFilter(BaseModel):
    """Фильтр для получения заданий"""
    subject_id: str = Field(..., description="ID предмета")
    exam_type: ExamType = Field(..., description="Тип экзамена")
    difficulty: Optional[Difficulty] = Field(None, description="Сложность")
    exclude_solved: bool = Field(True, description="Исключить уже решенные задания")


class TaskResponse(BaseModel):
    """Схема ответа с заданием"""
    id: int
    subject_id: str
    exam_type: str
    task_number: Optional[int]
    difficulty: str
    question_text: str
    answer_type: str
    answer_options: Optional[List[str]] = Field(None, description="Варианты ответа (если есть)")
    points: int
    estimated_time: Optional[int] = Field(None, description="Примерное время (минуты)")

    class Config:
        from_attributes = True


class TaskWithExplanation(TaskResponse):
    """Схема задания с разбором (после ответа)"""
    correct_answer: str
    explanation: Optional[str]


# =====================================================
# TASK ATTEMPTS
# =====================================================

class TaskAttemptCreate(BaseModel):
    """Схема отправки ответа на задание"""
    task_id: int = Field(..., description="ID задания")
    user_answer: str = Field(..., min_length=1, description="Ответ пользователя")
    time_spent: Optional[int] = Field(None, ge=0, description="Время на задание (секунды)")


class TaskAttemptResponse(BaseModel):
    """Схема ответа после проверки задания"""
    id: int
    task_id: int
    user_answer: str
    is_correct: bool
    points_earned: int
    time_spent: Optional[int]
    attempted_at: datetime

    # Детали задания
    task: TaskWithExplanation

    class Config:
        from_attributes = True


# =====================================================
# STATISTICS
# =====================================================

class SubjectStats(BaseModel):
    """Статистика по предмету"""
    subject_id: str
    total_attempts: int = 0
    correct_attempts: int = 0
    accuracy: float = Field(0.0, ge=0, le=100, description="Точность в процентах")
    average_time: Optional[float] = Field(None, description="Среднее время (секунды)")

    # По сложности
    easy_accuracy: float = 0.0
    medium_accuracy: float = 0.0
    hard_accuracy: float = 0.0


class ExamStatsResponse(BaseModel):
    """Общая статистика пользователя"""
    user_id: str
    total_points: int
    tasks_solved: int
    tasks_correct: int
    accuracy_percentage: int
    streak_days: int
    best_streak: int
    last_updated: datetime

    # Статистика по предметам
    subjects: List[SubjectStats] = []

    class Config:
        from_attributes = True


# =====================================================
# PROGRESS
# =====================================================

class DailyProgress(BaseModel):
    """Прогресс за день"""
    date: date
    is_completed: bool
    tasks_completed: int
    target_tasks: int = Field(5, description="Целевое количество заданий в день")
    completion_percentage: int = Field(ge=0, le=100)


class ProgressCalendar(BaseModel):
    """Календарь прогресса за период"""
    user_id: str
    period_start: date
    period_end: date
    days: List[DailyProgress]
    total_days: int
    completed_days: int
    completion_rate: float = Field(ge=0, le=100, description="Процент выполненных дней")


# =====================================================
# DASHBOARD
# =====================================================

class ExamDashboard(BaseModel):
    """Полная информация для дашборда экзаменов"""
    # Настройки
    exam_settings: Optional[ExamSettingsResponse] = None

    # Статистика
    stats: ExamStatsResponse

    # Прогресс за последние 7 дней
    recent_progress: List[DailyProgress]

    # Сегодняшний прогресс
    today_progress: DailyProgress

    # Рекомендации
    recommended_subjects: List[str] = Field(description="Предметы требующие внимания")


# =====================================================
# UTILITY
# =====================================================

class AvailableSubjects(BaseModel):
    """Список доступных предметов"""
    oge_subjects: List[str] = [
        "математика", "русский язык", "английский язык",
        "физика", "химия", "биология", "география",
        "обществознание", "история", "информатика", "литература"
    ]
    ege_subjects: List[str] = [
        "математика (базовая)", "математика (профильная)",
        "русский язык", "английский язык", "немецкий язык",
        "физика", "химия", "биология", "география",
        "обществознание", "история", "информатика", "литература"
    ]


class BulkTasksRequest(BaseModel):
    """Запрос пакета заданий"""
    subject_id: str
    exam_type: ExamType
    count: int = Field(5, ge=1, le=20, description="Количество заданий")
    difficulty: Optional[Difficulty] = None
    exclude_solved: bool = True


class BulkTasksResponse(BaseModel):
    """Ответ с пакетом заданий"""
    tasks: List[TaskResponse]
    total_available: int = Field(description="Всего доступных заданий")
    has_more: bool = Field(description="Есть ли еще задания")
