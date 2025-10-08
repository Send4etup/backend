# backend/services/ai/__init__.py
"""
AI сервис для работы с OpenAI API
Включает обработку текста, изображений, документов и аудио
"""

from .ai_service import AIService, get_ai_service
from .image_processor import ImageProcessor
from .document_processor import DocumentProcessor
from .audio_processor import AudioProcessor
from .response_handler import ResponseHandler

__all__ = [
    'AIService',
    'get_ai_service',
    'ImageProcessor',
    'DocumentProcessor',
    'AudioProcessor',
    'ResponseHandler',
]