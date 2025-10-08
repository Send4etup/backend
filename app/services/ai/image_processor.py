# backend/services/ai/image_processor.py
"""
Модуль для обработки изображений
Включает кодирование, оптимизацию и анализ через GPT-4 Vision
"""

import base64
import io
import logging
from pathlib import Path
from typing import Optional
from PIL import Image

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Класс для обработки изображений"""

    def __init__(self, max_image_size: int = 2048):
        """
        Инициализация процессора изображений

        Args:
            max_image_size: Максимальный размер изображения в пикселях
        """
        self.max_image_size = max_image_size

        # Модели, поддерживающие vision
        self.vision_models = [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-vision-preview",
            "gpt-4-turbo"
        ]

    def encode_image_to_base64(self, image_path: str) -> Optional[str]:
        """
        Кодирование изображения в base64 с оптимизацией размера

        Args:
            image_path: Путь к файлу изображения

        Returns:
            Base64 строка или None при ошибке
        """
        try:
            # Открываем и оптимизируем изображение
            with Image.open(image_path) as img:
                # Конвертируем в RGB если нужно
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Уменьшаем размер если слишком большое
                if max(img.size) > self.max_image_size:
                    img.thumbnail(
                        (self.max_image_size, self.max_image_size),
                        Image.Resampling.LANCZOS
                    )
                    logger.info(
                        f"Image resized from {Image.open(image_path).size} "
                        f"to {img.size}"
                    )

                # Сохраняем в память как JPEG с оптимизацией
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85, optimize=True)
                buffer.seek(0)

                # Кодируем в base64
                base64_string = base64.b64encode(buffer.getvalue()).decode('utf-8')

                logger.info(
                    f"Image encoded successfully: {Path(image_path).name}, "
                    f"size: {len(base64_string)} bytes"
                )

                return base64_string

        except Exception as e:
            logger.error(f"Error encoding image {image_path}: {e}")
            return None

    def get_image_mime_type(self, image_path: str) -> str:
        """
        Получение MIME типа изображения по расширению файла

        Args:
            image_path: Путь к файлу изображения

        Returns:
            MIME тип (например, 'image/jpeg')
        """
        path = Path(image_path)
        extension = path.suffix.lower()

        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp'
        }

        mime_type = mime_types.get(extension, 'image/jpeg')
        logger.debug(f"Image MIME type for {path.name}: {mime_type}")

        return mime_type

    def validate_image(self, image_path: str) -> bool:
        """
        Проверка валидности изображения

        Args:
            image_path: Путь к файлу изображения

        Returns:
            True если изображение валидно, False иначе
        """
        try:
            with Image.open(image_path) as img:
                img.verify()

            # Повторное открытие после verify (требование PIL)
            with Image.open(image_path) as img:
                img.load()

            logger.info(f"Image validation successful: {Path(image_path).name}")
            return True

        except Exception as e:
            logger.error(f"Image validation failed for {image_path}: {e}")
            return False

    def get_image_info(self, image_path: str) -> dict:
        """
        Получение информации об изображении

        Args:
            image_path: Путь к файлу изображения

        Returns:
            Словарь с информацией об изображении
        """
        try:
            with Image.open(image_path) as img:
                info = {
                    'filename': Path(image_path).name,
                    'format': img.format,
                    'mode': img.mode,
                    'size': img.size,
                    'width': img.width,
                    'height': img.height,
                    'file_size_bytes': Path(image_path).stat().st_size,
                    'file_size_mb': round(Path(image_path).stat().st_size / (1024 * 1024), 2)
                }

                logger.info(f"Image info retrieved: {info}")
                return info

        except Exception as e:
            logger.error(f"Error getting image info for {image_path}: {e}")
            return {
                'filename': Path(image_path).name,
                'error': str(e)
            }

    def prepare_image_for_vision_api(
            self,
            image_path: str,
            detail: str = "auto"
    ) -> Optional[dict]:
        """
        Подготовка изображения для отправки в Vision API

        Args:
            image_path: Путь к файлу изображения
            detail: Уровень детализации ('auto', 'low', 'high')

        Returns:
            Словарь для Vision API или None при ошибке
        """
        try:
            # Валидация изображения
            if not self.validate_image(image_path):
                logger.error(f"Image validation failed: {image_path}")
                return None

            # Кодирование в base64
            base64_image = self.encode_image_to_base64(image_path)
            if not base64_image:
                logger.error(f"Failed to encode image: {image_path}")
                return None

            # Получение MIME типа
            mime_type = self.get_image_mime_type(image_path)

            # Формирование объекта для API
            image_data = {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_image}",
                    "detail": detail
                }
            }

            logger.info(
                f"Image prepared for Vision API: {Path(image_path).name}, "
                f"detail={detail}"
            )

            return image_data

        except Exception as e:
            logger.error(f"Error preparing image for Vision API {image_path}: {e}")
            return None

    def optimize_image_for_upload(
            self,
            image_path: str,
            output_path: Optional[str] = None,
            max_size_mb: float = 4.0,
            quality: int = 85
    ) -> Optional[str]:
        """
        Оптимизация изображения для загрузки (сжатие)

        Args:
            image_path: Путь к исходному файлу
            output_path: Путь для сохранения (если None, перезаписывает исходный)
            max_size_mb: Максимальный размер файла в MB
            quality: Качество JPEG (1-100)

        Returns:
            Путь к оптимизированному файлу или None при ошибке
        """
        try:
            output_path = output_path or image_path
            max_size_bytes = max_size_mb * 1024 * 1024

            with Image.open(image_path) as img:
                # Конвертируем в RGB если нужно
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Проверяем текущий размер
                current_size = Path(image_path).stat().st_size

                if current_size <= max_size_bytes:
                    logger.info(
                        f"Image {Path(image_path).name} already optimized "
                        f"({current_size / (1024 * 1024):.2f} MB)"
                    )
                    return image_path

                # Уменьшаем размер если нужно
                if max(img.size) > self.max_image_size:
                    img.thumbnail(
                        (self.max_image_size, self.max_image_size),
                        Image.Resampling.LANCZOS
                    )

                # Сохраняем с оптимизацией
                img.save(output_path, format="JPEG", quality=quality, optimize=True)

                new_size = Path(output_path).stat().st_size

                logger.info(
                    f"Image optimized: {Path(image_path).name}, "
                    f"size reduced from {current_size / (1024 * 1024):.2f} MB "
                    f"to {new_size / (1024 * 1024):.2f} MB"
                )

                return output_path

        except Exception as e:
            logger.error(f"Error optimizing image {image_path}: {e}")
            return None

    def create_thumbnail(
            self,
            image_path: str,
            output_path: str,
            size: tuple = (200, 200)
    ) -> Optional[str]:
        """
        Создание миниатюры изображения

        Args:
            image_path: Путь к исходному файлу
            output_path: Путь для сохранения миниатюры
            size: Размер миниатюры (ширина, высота)

        Returns:
            Путь к миниатюре или None при ошибке
        """
        try:
            with Image.open(image_path) as img:
                # Конвертируем в RGB если нужно
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Создаем миниатюру
                img.thumbnail(size, Image.Resampling.LANCZOS)

                # Сохраняем
                img.save(output_path, format="JPEG", quality=80, optimize=True)

                logger.info(
                    f"Thumbnail created: {Path(output_path).name}, "
                    f"size: {img.size}"
                )

                return output_path

        except Exception as e:
            logger.error(f"Error creating thumbnail for {image_path}: {e}")
            return None

    def is_vision_model_supported(self, model: str) -> bool:
        """
        Проверка поддержки Vision API для модели

        Args:
            model: Название модели

        Returns:
            True если модель поддерживает Vision
        """
        supported = model in self.vision_models
        logger.debug(f"Vision support check for {model}: {supported}")
        return supported

    def get_supported_formats(self) -> list:
        """
        Получение списка поддерживаемых форматов изображений

        Returns:
            Список расширений файлов
        """
        return ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']

    def is_supported_format(self, file_path: str) -> bool:
        """
        Проверка поддерживается ли формат файла

        Args:
            file_path: Путь к файлу

        Returns:
            True если формат поддерживается
        """
        extension = Path(file_path).suffix.lower()
        supported = extension in self.get_supported_formats()

        if not supported:
            logger.warning(f"Unsupported image format: {extension}")

        return supported


# Вспомогательные функции для быстрого доступа

def encode_image(image_path: str, max_size: int = 2048) -> Optional[str]:
    """
    Быстрое кодирование изображения в base64

    Args:
        image_path: Путь к изображению
        max_size: Максимальный размер

    Returns:
        Base64 строка или None
    """
    processor = ImageProcessor(max_image_size=max_size)
    return processor.encode_image_to_base64(image_path)


def validate_image_file(image_path: str) -> bool:
    """
    Быстрая валидация изображения

    Args:
        image_path: Путь к изображению

    Returns:
        True если валидно
    """
    processor = ImageProcessor()
    return processor.validate_image(image_path)


def get_image_data(image_path: str) -> dict:
    """
    Быстрое получение информации об изображении

    Args:
        image_path: Путь к изображению

    Returns:
        Словарь с информацией
    """
    processor = ImageProcessor()
    return processor.get_image_info(image_path)