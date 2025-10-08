# backend/services/ai/audio_processor.py
"""
Модуль для обработки аудио файлов
Включает конвертацию, транскрипцию через Whisper API и оптимизацию
"""

import os
import asyncio
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Optional
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Класс для обработки аудио файлов"""

    def __init__(self, openai_client: Optional[AsyncOpenAI] = None):
        """
        Инициализация процессора аудио

        Args:
            openai_client: Клиент OpenAI для транскрипции (опционально)
        """
        self.client = openai_client

        # Максимальный размер файла для Whisper API (25 MB)
        self.max_file_size_mb = 25
        self.max_file_size_bytes = self.max_file_size_mb * 1024 * 1024

        # Поддерживаемые форматы
        self.supported_formats = [
            '.mp3', '.mp4', '.mpeg', '.mpga',
            '.m4a', '.wav', '.webm', '.ogg', '.flac'
        ]

        # Проверка доступности ffmpeg при инициализации
        self.ffmpeg_available = self.check_ffmpeg_availability()

        if not self.ffmpeg_available:
            logger.warning(
                "FFmpeg not found. Audio conversion will be limited. "
                "Install ffmpeg for full functionality."
            )

    def check_ffmpeg_availability(self) -> bool:
        """
        Проверка доступности ffmpeg в системе

        Returns:
            True если ffmpeg доступен
        """
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            available = result.returncode == 0

            if available:
                logger.info("FFmpeg is available")
            else:
                logger.warning("FFmpeg check failed")

            return available

        except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning(f"FFmpeg availability check failed: {e}")
            return False

    async def convert_audio_to_mp3(
            self,
            input_path: str,
            output_path: Optional[str] = None,
            bitrate: str = '128k',
            sample_rate: int = 44100
    ) -> str:
        """
        Конвертация аудио файла в MP3 формат с помощью ffmpeg

        Args:
            input_path: Путь к исходному аудио файлу
            output_path: Путь для сохранения (если None, создается временный)
            bitrate: Битрейт аудио (например, '128k', '192k')
            sample_rate: Частота дискретизации (например, 44100, 48000)

        Returns:
            Путь к конвертированному MP3 файлу
        """
        try:
            input_path_obj = Path(input_path)

            # Если уже MP3, возвращаем исходный файл
            if input_path_obj.suffix.lower() == '.mp3':
                logger.info(f"File {input_path_obj.name} already in MP3 format")
                return input_path

            # Проверяем доступность ffmpeg
            if not self.ffmpeg_available:
                logger.warning("FFmpeg not available, returning original file")
                return input_path

            # Создаем путь для выходного файла
            if output_path is None:
                temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
                output_path = temp_file.name
                temp_file.close()

            original_size = os.path.getsize(input_path) / (1024 * 1024)
            logger.info(
                f"Converting {input_path_obj.name} ({original_size:.1f} MB) to MP3"
            )

            # Команда ffmpeg для конвертации
            cmd = [
                'ffmpeg',
                '-i', input_path,  # Входной файл
                '-acodec', 'libmp3lame',  # Кодек MP3
                '-ab', bitrate,  # Битрейт
                '-ar', str(sample_rate),  # Частота дискретизации
                '-y',  # Перезаписывать без запроса
                '-loglevel', 'error',  # Только ошибки в логах
                output_path
            ]

            # Запускаем процесс конвертации
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                # Проверяем, что выходной файл создался и не пустой
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    output_size = os.path.getsize(output_path) / (1024 * 1024)

                    logger.info(
                        f"Successfully converted to MP3: {Path(output_path).name}, "
                        f"size: {output_size:.1f} MB "
                        f"(reduced by {((original_size - output_size) / original_size * 100):.1f}%)"
                    )

                    # Удаляем исходный файл если конвертация успешна
                    try:
                        if input_path != output_path:
                            os.unlink(input_path)
                            logger.info(f"Removed original file: {input_path}")
                    except OSError as e:
                        logger.warning(f"Could not remove original file {input_path}: {e}")

                    return output_path
                else:
                    logger.error("Output MP3 file is empty or doesn't exist")
                    if os.path.exists(output_path):
                        os.unlink(output_path)
                    return input_path
            else:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown error"
                logger.error(f"FFmpeg conversion failed: {error_msg}")

                # Очищаем выходной файл при ошибке
                if os.path.exists(output_path):
                    os.unlink(output_path)

                return input_path

        except asyncio.TimeoutError:
            logger.error("FFmpeg conversion timeout")
            return input_path

        except Exception as e:
            logger.error(f"Error converting audio to MP3: {e}")
            return input_path

    async def extract_text_from_audio(
            self,
            file_path: str,
            language: Optional[str] = None,
            prompt: Optional[str] = None
    ) -> str:
        """
        Извлечение текста из аудио через Whisper API

        Args:
            file_path: Путь к аудио файлу
            language: Язык аудио (опционально, например 'ru', 'en')
            prompt: Подсказка для улучшения транскрипции

        Returns:
            Текст транскрипции или сообщение об ошибке
        """
        try:
            if not self.client:
                return "OpenAI клиент не инициализирован. Невозможно выполнить транскрипцию."

            file_name = Path(file_path).name
            original_size = os.path.getsize(file_path) / (1024 * 1024)

            logger.info(f"Processing audio file: {file_name} ({original_size:.1f} MB)")

            # Конвертируем аудио в MP3 для лучшей совместимости
            mp3_file_path = await self.convert_audio_to_mp3(file_path)

            # Получаем финальный размер файла
            final_size = os.path.getsize(mp3_file_path) / (1024 * 1024)

            # Проверяем размер файла (Whisper API имеет лимит 25MB)
            if final_size > self.max_file_size_mb:
                error_msg = (
                    f"Аудиофайл слишком большой ({final_size:.1f} MB). "
                    f"Максимальный размер: {self.max_file_size_mb} MB"
                )
                logger.error(error_msg)
                return error_msg

            logger.info(
                f"Using audio file for transcription: "
                f"{Path(mp3_file_path).name} ({final_size:.1f} MB)"
            )

            # Транскрибируем аудио через Whisper API
            with open(mp3_file_path, "rb") as audio_file:
                # Формируем параметры запроса
                transcription_params = {
                    "model": "whisper-1",
                    "file": audio_file,
                }

                # Добавляем опциональные параметры
                if language:
                    transcription_params["language"] = language

                if prompt:
                    transcription_params["prompt"] = prompt

                # Выполняем транскрипцию
                transcription = await self.client.audio.transcriptions.create(
                    **transcription_params
                )

            # Получаем текст из объекта транскрипции
            transcription_text = transcription.text

            if not transcription_text or not transcription_text.strip():
                error_msg = f"Не удалось распознать речь в файле {file_name}"
                logger.warning(error_msg)
                return error_msg

            logger.info(
                f"Audio transcription completed for {file_name}, "
                f"text length: {len(transcription_text)} characters"
            )

            # Очищаем временный MP3 файл если он отличается от исходного
            if mp3_file_path != file_path and os.path.exists(mp3_file_path):
                try:
                    os.unlink(mp3_file_path)
                    logger.info(f"Cleaned up temporary MP3 file: {mp3_file_path}")
                except OSError as e:
                    logger.warning(f"Could not clean up temporary file {mp3_file_path}: {e}")

            # Формируем результат
            result = f"Транскрипция аудиофайла '{file_name}':\n\n{transcription_text}"

            return result

        except Exception as e:
            logger.error(f"Error processing audio file {file_path}: {e}", exc_info=True)
            return f"Ошибка при обработке аудио файла: {str(e)}"

    def get_audio_info(self, file_path: str) -> dict:
        """
        Получение информации об аудио файле

        Args:
            file_path: Путь к аудио файлу

        Returns:
            Словарь с информацией о файле
        """
        try:
            path = Path(file_path)
            file_size_bytes = path.stat().st_size
            file_size_mb = round(file_size_bytes / (1024 * 1024), 2)

            info = {
                'filename': path.name,
                'extension': path.suffix.lower(),
                'file_size_bytes': file_size_bytes,
                'file_size_mb': file_size_mb,
                'is_supported': self.is_supported_format(file_path),
                'within_size_limit': file_size_mb <= self.max_file_size_mb
            }

            # Если ffmpeg доступен, получаем дополнительную информацию
            if self.ffmpeg_available:
                try:
                    cmd = [
                        'ffprobe',
                        '-v', 'error',
                        '-show_entries', 'format=duration,bit_rate',
                        '-show_entries', 'stream=codec_name,sample_rate,channels',
                        '-of', 'default=noprint_wrappers=1',
                        file_path
                    ]

                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )

                    if result.returncode == 0:
                        output_lines = result.stdout.strip().split('\n')
                        for line in output_lines:
                            if '=' in line:
                                key, value = line.split('=', 1)
                                info[key] = value

                except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
                    logger.warning(f"Could not get detailed audio info: {e}")

            logger.info(f"Audio info retrieved: {info}")
            return info

        except Exception as e:
            logger.error(f"Error getting audio info for {file_path}: {e}")
            return {
                'filename': Path(file_path).name,
                'error': str(e)
            }

    def is_supported_format(self, file_path: str) -> bool:
        """
        Проверка поддерживается ли формат аудио файла

        Args:
            file_path: Путь к файлу

        Returns:
            True если формат поддерживается
        """
        extension = Path(file_path).suffix.lower()
        supported = extension in self.supported_formats

        if not supported:
            logger.warning(f"Unsupported audio format: {extension}")

        return supported

    def get_supported_formats(self) -> list:
        """
        Получение списка поддерживаемых форматов аудио

        Returns:
            Список расширений файлов
        """
        return self.supported_formats.copy()

    async def optimize_audio_for_transcription(
            self,
            input_path: str,
            output_path: Optional[str] = None
    ) -> str:
        """
        Оптимизация аудио для транскрипции (снижение битрейта/размера)

        Args:
            input_path: Путь к исходному файлу
            output_path: Путь для сохранения (если None, создается временный)

        Returns:
            Путь к оптимизированному файлу
        """
        try:
            file_size_mb = os.path.getsize(input_path) / (1024 * 1024)

            # Если файл уже в пределах лимита, возвращаем его
            if file_size_mb <= self.max_file_size_mb:
                logger.info(f"Audio file already optimized: {file_size_mb:.1f} MB")
                return input_path

            # Если ffmpeg недоступен, возвращаем исходный файл
            if not self.ffmpeg_available:
                logger.warning("Cannot optimize audio: FFmpeg not available")
                return input_path

            # Конвертируем с более низким битрейтом
            logger.info(f"Optimizing audio file: {file_size_mb:.1f} MB")

            optimized_path = await self.convert_audio_to_mp3(
                input_path,
                output_path,
                bitrate='64k',  # Низкий битрейт для меньшего размера
                sample_rate=16000  # Более низкая частота дискретизации
            )

            optimized_size_mb = os.path.getsize(optimized_path) / (1024 * 1024)

            logger.info(
                f"Audio optimized: {file_size_mb:.1f} MB → {optimized_size_mb:.1f} MB "
                f"(reduced by {((file_size_mb - optimized_size_mb) / file_size_mb * 100):.1f}%)"
            )

            return optimized_path

        except Exception as e:
            logger.error(f"Error optimizing audio: {e}")
            return input_path

    def validate_audio_file(self, file_path: str) -> tuple[bool, Optional[str]]:
        """
        Валидация аудио файла

        Args:
            file_path: Путь к файлу

        Returns:
            Tuple (is_valid, error_message)
        """
        try:
            # Проверка существования файла
            if not os.path.exists(file_path):
                return False, "Файл не найден"

            # Проверка формата
            if not self.is_supported_format(file_path):
                return False, f"Неподдерживаемый формат: {Path(file_path).suffix}"

            # Проверка размера
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

            # Если размер больше лимита, но ffmpeg доступен - можно оптимизировать
            if file_size_mb > self.max_file_size_mb and not self.ffmpeg_available:
                return False, (
                    f"Файл слишком большой ({file_size_mb:.1f} MB), "
                    f"максимум {self.max_file_size_mb} MB. "
                    f"FFmpeg недоступен для оптимизации."
                )

            logger.info(f"Audio file validation successful: {Path(file_path).name}")
            return True, None

        except Exception as e:
            logger.error(f"Audio validation error: {e}")
            return False, str(e)


# Вспомогательные функции для быстрого доступа

async def transcribe_audio(
        file_path: str,
        openai_client: AsyncOpenAI,
        language: Optional[str] = None
) -> str:
    """
    Быстрая транскрипция аудио

    Args:
        file_path: Путь к аудио файлу
        openai_client: Клиент OpenAI
        language: Язык аудио

    Returns:
        Текст транскрипции
    """
    processor = AudioProcessor(openai_client)
    return await processor.extract_text_from_audio(file_path, language)


def get_audio_metadata(file_path: str) -> dict:
    """
    Быстрое получение метаданных аудио

    Args:
        file_path: Путь к аудио файлу

    Returns:
        Словарь с метаданными
    """
    processor = AudioProcessor()
    return processor.get_audio_info(file_path)


def check_audio_valid(file_path: str) -> bool:
    """
    Быстрая проверка валидности аудио

    Args:
        file_path: Путь к аудио файлу

    Returns:
        True если валидно
    """
    processor = AudioProcessor()
    is_valid, _ = processor.validate_audio_file(file_path)
    return is_valid