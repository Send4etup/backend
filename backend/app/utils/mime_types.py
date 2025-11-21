"""
Утилиты для работы с MIME типами и расширениями файлов
"""

# ============================================
# MIME -> РАСШИРЕНИЯ
# ============================================

MIME_EXTENSIONS = {
    # Изображения
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp',
    'image/bmp': '.bmp',
    'image/heic': '.heic',
    'image/heif': '.heif',

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
    'audio/mp3': '.mp3',
    'audio/wav': '.wav',
    'audio/wave': '.wav',
    'audio/x-wav': '.wav',
    'audio/m4a': '.m4a',
    'audio/mp4': '.m4a',
    'audio/aac': '.aac',
    'audio/webm': '.webm',
    'audio/ogg': '.ogg',
    'audio/vorbis': '.ogg'
}


# ============================================
# ФУНКЦИИ
# ============================================

def get_extension_by_mime(mime_type: str) -> str:
    """
    Получение расширения файла по MIME типу

    Args:
        mime_type: MIME тип файла (например, 'image/jpeg')

    Returns:
        Расширение файла с точкой (например, '.jpg')
        Возвращает '.bin' если MIME тип не распознан
    """
    return MIME_EXTENSIONS.get(mime_type, '.bin')


def get_file_icon(mime_type: str) -> str:
    """
    Получение иконки для файла по MIME типу

    Args:
        mime_type: MIME тип файла

    Returns:
        Emoji иконка файла
    """
    if mime_type.startswith('image/'):
        return '🖼️'
    elif mime_type.startswith('audio/'):
        return '🎵'
    elif mime_type == 'application/pdf':
        return '📄'
    elif 'word' in mime_type:
        return '📝'
    elif 'excel' in mime_type or 'spreadsheet' in mime_type:
        return '📊'
    elif mime_type == 'text/plain':
        return '📃'
    elif mime_type == 'text/csv':
        return '📋'
    else:
        return '📎'