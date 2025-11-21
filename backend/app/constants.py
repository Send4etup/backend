"""
Константы для ТоварищБот API
Вынесены из main.py для лучшей организации кода
"""
from pathlib import Path

# ============================================
# ДИРЕКТОРИИ
# ============================================

UPLOAD_DIR = Path("uploads")

# ============================================
# ПОДДЕРЖИВАЕМЫЕ ТИПЫ ФАЙЛОВ
# ============================================

SUPPORTED_IMAGE_TYPES = {
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/gif',
    'image/webp',
    'image/bmp',
    'image/heic',
    'image/heif'
}

SUPPORTED_DOCUMENT_TYPES = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
    'application/rtf',
    'text/csv',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
}

SUPPORTED_AUDIO_TYPES = {
    'audio/mpeg',
    'audio/mp3',
    'audio/wav',
    'audio/wave',
    'audio/x-wav',
    'audio/m4a',
    'audio/mp4',
    'audio/aac',
    'audio/webm',
    'audio/ogg',
    'audio/vorbis'
}

# ============================================
# ЛИМИТЫ
# ============================================

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_FILES_PER_MESSAGE = 10


# ============================================
# ФУНКЦИИ ПРОВЕРКИ
# ============================================

def is_image(mime_type: str) -> bool:
    """Проверка является ли файл изображением"""
    return mime_type in SUPPORTED_IMAGE_TYPES


def is_document(mime_type: str) -> bool:
    """Проверка является ли файл документом"""
    return mime_type in SUPPORTED_DOCUMENT_TYPES


def is_audio(mime_type: str) -> bool:
    """Проверка является ли файл аудио"""
    return mime_type in SUPPORTED_AUDIO_TYPES


def get_file_category(mime_type: str) -> str:
    """
    Определение категории файла по MIME типу

    Returns:
        'image' | 'document' | 'audio' | 'unknown'
    """
    if is_image(mime_type):
        return 'image'
    elif is_document(mime_type):
        return 'document'
    elif is_audio(mime_type):
        return 'audio'
    else:
        return 'unknown'