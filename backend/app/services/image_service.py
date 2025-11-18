# app/services/image_service.py
"""
Сервис для работы с генерированными изображениями
Обеспечивает: загрузку, сжатие, оптимизацию, хранение
"""
import os
import logging
import aiohttp
import aiofiles
from pathlib import Path
from PIL import Image
from typing import Optional, Dict, Tuple
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class ImageService:
    """Сервис для работы с генерированными изображениями"""

    def __init__(self, base_upload_dir: str = "uploads"):
        self.base_upload_dir = Path(base_upload_dir)
        self.generated_dir = self.base_upload_dir / "generated-images"
        self.compressed_dir = self.generated_dir / "compressed"
        self.original_dir = self.generated_dir / "original"
        
        # Создаем необходимые директории
        self._create_directories()
        
        # Настройки сжатия
        self.WEBP_QUALITY = 85  # Качество WebP (80-90 оптимально)
        self.MAX_DISPLAY_WIDTH = 1024  # Максимальная ширина для отображения
        self.ORIGINAL_FORMAT = "PNG"  # Формат оригинала
        
    def _create_directories(self):
        """Создание необходимых директорий"""
        try:
            self.generated_dir.mkdir(parents=True, exist_ok=True)
            self.compressed_dir.mkdir(parents=True, exist_ok=True)
            self.original_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Image directories created: {self.generated_dir}")
        except Exception as e:
            logger.error(f"❌ Error creating directories: {e}")
            raise

    def _generate_filename(self, user_id: str, prompt: str) -> str:
        """
        Генерация уникального имени файла
        
        Args:
            user_id: ID пользователя
            prompt: Промпт для генерации (для уникальности)
            
        Returns:
            Уникальное имя файла без расширения
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Создаем короткий хеш из промпта для уникальности
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
        
        return f"{user_id}_{timestamp}_{prompt_hash}"

    async def download_and_save_image(
        self, 
        image_url: str, 
        user_id: str,
        prompt: str
    ) -> Dict[str, str]:
        """
        Скачивание изображения с URL и сохранение в двух версиях:
        1. Оригинал (PNG) - в original/
        2. Сжатая версия (WebP) - в compressed/
        
        Args:
            image_url: URL изображения от DALL-E
            user_id: ID пользователя
            prompt: Промпт для уникального имени
            
        Returns:
            Dict с путями к файлам:
            {
                "original_path": "path/to/original.png",
                "compressed_path": "path/to/compressed.webp",
                "original_url": "/uploads/generated-images/original/...",
                "compressed_url": "/uploads/generated-images/compressed/...",
                "file_size_original": 1234567,
                "file_size_compressed": 123456,
                "compression_ratio": 90.0
            }
        """
        try:
            logger.info(f"🎨 Downloading image from DALL-E: {image_url[:100]}...")
            
            # 1. Скачиваем изображение
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to download image: {response.status}")
                    
                    image_data = await response.read()
                    logger.info(f"✅ Downloaded {len(image_data)} bytes")

            # 2. Генерируем имена файлов
            base_filename = self._generate_filename(user_id, prompt)
            
            original_filename = f"{base_filename}.png"
            compressed_filename = f"{base_filename}.webp"
            
            original_path = self.original_dir / original_filename
            compressed_path = self.compressed_dir / compressed_filename

            # 3. Сохраняем ОРИГИНАЛ (PNG)
            async with aiofiles.open(original_path, 'wb') as f:
                await f.write(image_data)
            
            original_size = original_path.stat().st_size
            logger.info(f"💾 Original saved: {original_path.name} ({original_size / 1024:.1f} KB)")

            # 4. Создаем СЖАТУЮ версию (WebP)
            compressed_size = await self._create_compressed_version(
                original_path, 
                compressed_path
            )
            
            compression_ratio = ((original_size - compressed_size) / original_size) * 100
            
            logger.info(
                f"🗜️ Compressed: {compressed_path.name} "
                f"({compressed_size / 1024:.1f} KB, "
                f"saved {compression_ratio:.1f}%)"
            )

            # 5. Формируем результат
            return {
                "original_path": str(original_path),
                "compressed_path": str(compressed_path),
                "original_url": f"/uploads/generated-images/original/{original_filename}",
                "compressed_url": f"/uploads/generated-images/compressed/{compressed_filename}",
                "file_size_original": original_size,
                "file_size_compressed": compressed_size,
                "compression_ratio": round(compression_ratio, 1)
            }

        except Exception as e:
            logger.error(f"❌ Error downloading/saving image: {e}")
            raise

    async def _create_compressed_version(
        self, 
        original_path: Path, 
        compressed_path: Path
    ) -> int:
        """
        Создание сжатой WebP версии изображения
        
        Args:
            original_path: Путь к оригиналу
            compressed_path: Путь для сохранения сжатой версии
            
        Returns:
            Размер сжатого файла в байтах
        """
        try:
            # Открываем изображение
            with Image.open(original_path) as img:
                # Конвертируем в RGB (WebP не поддерживает RGBA полноценно)
                if img.mode in ('RGBA', 'LA'):
                    # Создаем белый фон для прозрачности
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        background.paste(img, mask=img.split()[3])
                    else:
                        background.paste(img, mask=img.split()[1])
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                # Изменяем размер если слишком большое
                if img.width > self.MAX_DISPLAY_WIDTH:
                    ratio = self.MAX_DISPLAY_WIDTH / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize(
                        (self.MAX_DISPLAY_WIDTH, new_height),
                        Image.Resampling.LANCZOS  # Высокое качество ресайза
                    )
                    logger.info(f"📐 Resized to {self.MAX_DISPLAY_WIDTH}x{new_height}")

                # Сохраняем в WebP с оптимизацией
                img.save(
                    compressed_path,
                    format='WEBP',
                    quality=self.WEBP_QUALITY,
                    method=6  # Максимальная компрессия (0-6, где 6 = лучшее)
                )

            return compressed_path.stat().st_size

        except Exception as e:
            logger.error(f"❌ Error creating compressed version: {e}")
            raise

    def get_image_info(self, filename: str, version: str = "compressed") -> Optional[Dict]:
        """
        Получение информации об изображении
        
        Args:
            filename: Имя файла (без пути)
            version: "original" или "compressed"
            
        Returns:
            Dict с информацией или None
        """
        try:
            if version == "original":
                path = self.original_dir / f"{filename}.png"
            else:
                path = self.compressed_dir / f"{filename}.webp"

            if not path.exists():
                return None

            stat = path.stat()
            
            with Image.open(path) as img:
                return {
                    "filename": path.name,
                    "path": str(path),
                    "size": stat.st_size,
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat()
                }

        except Exception as e:
            logger.error(f"❌ Error getting image info: {e}")
            return None

    async def cleanup_old_images(self, days: int = 30) -> Dict[str, int]:
        """
        Очистка изображений старше указанного количества дней
        
        Args:
            days: Возраст файлов для удаления
            
        Returns:
            Dict со статистикой очистки
        """
        try:
            from datetime import timedelta
            
            cutoff_time = datetime.now() - timedelta(days=days)
            cutoff_timestamp = cutoff_time.timestamp()
            
            deleted_count = 0
            freed_space = 0

            # Очищаем обе директории
            for directory in [self.original_dir, self.compressed_dir]:
                for file_path in directory.glob("*"):
                    if file_path.is_file():
                        file_time = file_path.stat().st_mtime
                        
                        if file_time < cutoff_timestamp:
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            deleted_count += 1
                            freed_space += file_size
                            logger.info(f"🗑️ Deleted old image: {file_path.name}")

            logger.info(
                f"✅ Cleanup completed: {deleted_count} files, "
                f"{freed_space / (1024*1024):.2f} MB freed"
            )

            return {
                "deleted_count": deleted_count,
                "freed_space_mb": round(freed_space / (1024*1024), 2)
            }

        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")
            return {"deleted_count": 0, "freed_space_mb": 0}

    def get_storage_stats(self) -> Dict[str, any]:
        """
        Получение статистики хранилища изображений
        
        Returns:
            Dict со статистикой
        """
        try:
            original_files = list(self.original_dir.glob("*.png"))
            compressed_files = list(self.compressed_dir.glob("*.webp"))
            
            original_size = sum(f.stat().st_size for f in original_files)
            compressed_size = sum(f.stat().st_size for f in compressed_files)
            
            total_saved = original_size - compressed_size if original_size > 0 else 0
            savings_percent = (total_saved / original_size * 100) if original_size > 0 else 0

            return {
                "original_count": len(original_files),
                "compressed_count": len(compressed_files),
                "original_size_mb": round(original_size / (1024*1024), 2),
                "compressed_size_mb": round(compressed_size / (1024*1024), 2),
                "space_saved_mb": round(total_saved / (1024*1024), 2),
                "savings_percent": round(savings_percent, 1)
            }

        except Exception as e:
            logger.error(f"❌ Error getting storage stats: {e}")
            return {}