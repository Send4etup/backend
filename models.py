"""
Pydantic модели для валидации данных
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# Request модели
class TelegramAuthRequest(BaseModel):
    telegram_id: Optional[int] = None
    name: Optional[str] = None
    username: Optional[str] = None


class RegisterRequest(BaseModel):
    telegram_id: int
    name: str
    school_name: str
    class_name: str
    city: str


class ProgressUpdateRequest(BaseModel):
    points: int = Field(..., ge=0, description="Количество очков для добавления")


class IdeaCreateRequest(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    tags: List[str] = Field(..., min_items=1, max_items=10)


class IdeaVoteRequest(BaseModel):
    vote_type: str = Field(..., pattern="^(like|dislike)$")


class CommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)
    idea_id: int


class TelegramAuthRequest(BaseModel):
    initData: Optional[str] = None
    user: Optional[Dict[str, Any]] = None


class SendMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    tool_type: Optional[str] = None


class UseToolRequest(BaseModel):
    tool_type: str = Field(..., min_length=1)
    data: Dict[str, Any] = Field(default_factory=dict)


class AddFriendRequest(BaseModel):
    user_id: int


# Response модели
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthResponse(BaseModel):
    exists: bool
    user: Optional["User"] = None
    access_token: Optional[str] = None


class User(BaseModel):
    id: int
    telegram_id: int
    name: str
    role: str
    current_points: int
    total_points: int
    streak_days: int
    tasks_completed: int
    subscription_type: str
    tokens_used: int
    tokens_limit: int
    school_name: str
    class_name: str
    city: str
    is_active: bool
    is_premium: bool
    created_at: str


class Friend(BaseModel):
    id: int
    name: str
    status: str
    points: int
    classPosition: int
    avatar: Optional[str]
    isOnline: bool
    class_name: str


class Teacher(BaseModel):
    id: int
    name: str
    role: str
    subjects: List[str]
    schedule: Dict[str, str]
    cabinet: str
    telegram: str
    email: str
    phone: str


class Task(BaseModel):
    id: int
    title: str
    subject: str
    date: str
    deadline: Optional[str] = None
    completedDate: Optional[str] = None
    progress: int
    total: int
    difficulty: str
    points: int
    score: Optional[int] = None
    description: str


class ChatMessage(BaseModel):
    id: int
    title: str
    subtitle: str
    tokens_used: int
    created_at: str
    messages: List[Dict[str, Any]]


class Idea(BaseModel):
    id: int
    author: str
    authorAvatar: Optional[str]
    date: str
    title: str
    description: str
    tags: List[str]
    likes: int
    dislikes: int
    comments: int
    status: str
    userVote: Optional[str]


class ProgressResponse(BaseModel):
    current_points: int
    total_points: int
    streak_days: int
    level_progress: int
    message: str


class Comment(BaseModel):
    id: int
    author: str
    authorAvatar: Optional[str]
    content: str
    created_at: str
    idea_id: int


class StatisticsResponse(BaseModel):
    total_students: int
    total_tasks: int
    completion_rate: float
    average_score: float
    top_subjects: List[str]


class HealthCheckResponse(BaseModel):
    message: str
    version: str
    status: str
    timestamp: datetime
    uptime: float


# Обновляем forward references
AuthResponse.model_rebuild()