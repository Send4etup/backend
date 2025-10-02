import os
import asyncio
from openai import AsyncOpenAI
from typing import Dict, List, Any, Optional, Union
import logging
import base64
from pathlib import Path
import json
import PyPDF2
import docx
import pandas as pd
import io
from PIL import Image
import subprocess
import tempfile
# from document_service import get_document_service

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")

        # Модели, поддерживающие vision
        self.vision_models = ["gpt-4o", "gpt-4o-mini", "gpt-4-vision-preview", "gpt-4-turbo"]

        # Максимальный размер изображения для обработки (в пикселях)
        self.max_image_size = 2048

        # Системные промпты для разных типов инструментов
        self.system_prompts = {
            "create_image": """Ты - ИИ помощник, специализирующийся на создании изображений. 
            Помогай пользователю детально описывать изображения, предлагай улучшения описаний, 
            советуй стили и техники. Если пользователь прикрепляет изображения, анализируй их и предлагай 
            идеи для создания похожих или улучшенных версий. Будь креативным и вдохновляющим! 
            Пиши друёёжелюбно и с энтузиазмом. Используй эмодзи уместно.""",

            "coding": """Ты - опытный программист и ментор. Помогай с кодом на любых языках программирования.
            Объясняй сложные концепции простыми словами, пиши чистый и читаемый код,
            предлагай лучшие практики. Если пользователь прикрепляет файлы с кодом или документацию,
            анализируй их и предлагай улучшения. Всегда включай комментарии в код.
            Будь терпеливым и поощряющим. Можешь использовать технические эмодзи.""",

            "brainstorm": """Ты - креативный помощник для мозгового штурма. Генерируй оригинальные идеи,
            задавай наводящие вопросы, помогай развивать мысли пользователя. Если пользователь прикрепляет
            файлы (изображения, документы), используй их как источник вдохновения для новых идей.
            Будь энергичным и вдохновляющим! Предлагай неожиданные связи и решения.
            Используй эмодзи для выражения энтузиазма.""",

            "excuse": """Ты - мастер творческих отмазок! Помогай придумывать правдоподобные,
            но безвредные объяснения для разных ситуаций. Если пользователь прикрепляет файлы,
            можешь использовать их как часть отмазки ("файл не открывается", "проблемы с форматом" и т.д.).
            Будь остроумным и изобретательным, но всегда этичным. Отмазки должны быть безобидными 
            и не вредить отношениям. Используй юмор и эмодзи.""",

            "make_notes": """Ты - профессиональный помощник для создания заметок и конспектов. 
            Помогай структурировать информацию, создавать четкие и полезные заметки.
            Если пользователь прикрепляет файлы (документы, изображения, аудио), анализируй их содержимое 
            и создавай структурированные заметки. Выделяй ключевые моменты, создавай списки, 
            используй заголовки и подзаголовки для лучшей организации информации.""",

            "default": """Ты - дружелюбный и умный ИИ помощник школьника. Отвечай полезно и интересно,
            объясняй сложные темы простым языком. Если пользователь прикрепляет файлы, анализируй их
            и помогай с содержимым. Будь поддерживающим и мотивирующим.
            Помогай с учебой, творчеством и повседневными задачами.""",

           "audio_transcribe": """Ты - помощник для работы с аудио контентом. Анализируй транскрипции аудиозаписей,
            выделяй ключевые моменты, создавай структурированные заметки из речи.
            Помогай с обработкой результатов транскрипции: создавай краткое содержание,
            выделяй важные фразы, организуй информацию. Будь внимательным к деталям и контексту."""
        }

    def check_ffmpeg_availability(self) -> bool:
        """Проверка доступности ffmpeg в системе"""
        try:
            result = subprocess.run(['ffmpeg', '-version'],
                                    capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False

    async def convert_audio_to_mp3(self, input_path: str) -> str:
        """Конвертация аудиофайла в MP3 формат"""
        try:
            # Проверяем доступность ffmpeg
            if not self.check_ffmpeg_availability():
                logger.warning("FFmpeg не найден. Используем исходный файл без конвертации.")
                return input_path

            input_path_obj = Path(input_path)

            # Если файл уже в MP3, возвращаем его
            if input_path_obj.suffix.lower() == '.mp3':
                logger.info(f"File {input_path_obj.name} already in MP3 format")
                return input_path

            # Создаем временный файл для результата
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                output_path = temp_file.name

            logger.info(f"Converting {input_path_obj.name} to MP3 format")

            # Конвертируем аудио в MP3 с помощью ffmpeg
            cmd = [
                'ffmpeg',
                '-i', input_path,  # Входной файл
                '-acodec', 'mp3',  # Кодек для аудио
                '-ab', '128k',  # Битрейт 128 kbps
                '-ar', '44100',  # Частота дискретизации 44.1 kHz
                '-y',  # Перезаписывать файл без запроса
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

            logger.info('start convert function')

            if process.returncode == 0:
                # Проверяем, что выходной файл создался и не пустой
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f"Successfully converted to MP3: {output_path}")

                    logger.info('successful')
                    # Удаляем исходный файл если конвертация прошла успешно
                    try:
                        os.unlink(input_path)
                        logger.info(f"Removed original file: {input_path}")
                    except OSError as e:
                        logger.warning(f"Could not remove original file {input_path}: {e}")

                    return output_path
                else:
                    logger.error("Output MP3 file is empty or doesn't exist")
                    # Очищаем пустой файл
                    if os.path.exists(output_path):
                        os.unlink(output_path)
                    return input_path
            else:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown error"
                logger.error(f"FFmpeg conversion failed: {error_msg}")

                # Очищаем файл результата при ошибке
                if os.path.exists(output_path):
                    os.unlink(output_path)
                return input_path

        except asyncio.TimeoutError:
            logger.error("FFmpeg conversion timeout")
            return input_path
        except Exception as e:
            logger.error(f"Error converting audio to MP3: {e}")
            return input_path

    def encode_image_to_base64(self, image_path: str) -> Optional[str]:
        """Кодирование изображения в base64 с оптимизацией размера"""
        try:
            # Открываем и оптимизируем изображение
            with Image.open(image_path) as img:
                # Конвертируем в RGB если нужно
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Уменьшаем размер если слишком большое
                if max(img.size) > self.max_image_size:
                    img.thumbnail((self.max_image_size, self.max_image_size), Image.Resampling.LANCZOS)

                # Сохраняем в память как JPEG с оптимизацией
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85, optimize=True)
                buffer.seek(0)

                # Кодируем в base64
                return base64.b64encode(buffer.getvalue()).decode('utf-8')

        except Exception as e:
            logger.error(f"Error encoding image {image_path}: {e}")
            return None

    def get_image_mime_type(self, image_path: str) -> str:
        """Получение MIME типа изображения"""
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

        return mime_types.get(extension, 'image/jpeg')

    async def extract_text_from_pdf(self, file_path: str) -> str:
        """Извлечение текста из PDF файла"""
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n"

            # Ограничиваем размер текста
            return text[:5000] if len(text) > 5000 else text

        except Exception as e:
            logger.error(f"Error extracting PDF text from {file_path}: {e}")
            return f"Ошибка при чтении PDF файла: {str(e)}"

    async def extract_text_from_docx(self, file_path: str) -> str:
        """Извлечение текста из Word документа"""
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs[:100]:  # Первые 100 параграфов
                text += paragraph.text + "\n"

            # Ограничиваем размер текста
            return text[:5000] if len(text) > 5000 else text

        except Exception as e:
            logger.error(f"Error extracting DOCX text from {file_path}: {e}")
            return f"Ошибка при чтении Word документа: {str(e)}"

    async def extract_text_from_excel(self, file_path: str) -> str:
        """Извлечение данных из Excel файла"""
        try:
            df = pd.read_excel(file_path, nrows=50)  # Первые 50 строк

            # Создаем описание таблицы
            description = f"Excel файл содержит {len(df)} строк и {len(df.columns)} столбцов.\n"
            description += f"Столбцы: {', '.join(df.columns.tolist())}\n\n"

            # Добавляем первые несколько строк
            description += "Первые строки данных:\n"
            description += df.head(10).to_string(max_cols=10, max_colwidth=50)

            return description

        except Exception as e:
            logger.error(f"Error reading Excel file {file_path}: {e}")
            return f"Ошибка при чтении Excel файла: {str(e)}"

    async def extract_text_from_csv(self, file_path: str) -> str:
        """Извлечение данных из CSV файла"""
        try:
            df = pd.read_csv(file_path, nrows=50)  # Первые 50 строк

            # Создаем описание таблицы
            description = f"CSV файл содержит {len(df)} строк и {len(df.columns)} столбцов.\n"
            description += f"Столбцы: {', '.join(df.columns.tolist())}\n\n"

            # Добавляем первые несколько строк
            description += "Первые строки данных:\n"
            description += df.head(10).to_string(max_cols=10, max_colwidth=50)

            return description

        except Exception as e:
            logger.error(f"Error reading CSV file {file_path}: {e}")
            return f"Ошибка при чтении CSV файла: {str(e)}"

    async def extract_text_from_audio(self, file_path: str) -> str:
        """Извлечение текста из аудио файлов через Whisper API с конвертацией в MP3"""
        try:
            file_name = Path(file_path).name
            original_size = os.path.getsize(file_path) / (1024 * 1024)  # размер в MB

            logger.info(f"Processing audio file: {file_name} ({original_size:.1f} MB)")

            # Конвертируем аудио в MP3 для лучшей совместимости
            mp3_file_path = await self.convert_audio_to_mp3(file_path)

            # Получаем финальный размер файла
            final_size = os.path.getsize(mp3_file_path) / (1024 * 1024)

            # Проверяем размер файла (Whisper API имеет лимит 25MB)
            if final_size > 25:
                return f"Аудиофайл слишком большой ({final_size:.1f} MB). Максимальный размер: 25 MB"

            logger.info(f"Using audio file for transcription: {Path(mp3_file_path).name} ({final_size:.1f} MB)")

            # Транскрибируем аудио через Whisper API
            with open(mp3_file_path, "rb") as audio_file:
                transcription = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                )

            # Получаем текст из объекта транскрипции
            transcription_text = transcription.text

            if not transcription_text or not transcription_text.strip():
                return f"Не удалось распознать речь в файле {file_name}"

            logger.info(f"Audio transcription completed for {file_name}")

            # Очищаем временный MP3 файл если он отличается от исходного
            if mp3_file_path != file_path and os.path.exists(mp3_file_path):
                try:
                    os.unlink(mp3_file_path)
                    logger.info(f"Cleaned up temporary MP3 file: {mp3_file_path}")
                except OSError as e:
                    logger.warning(f"Could not clean up temporary file {mp3_file_path}: {e}")

            return f"Транскрипция аудиофайла '{file_name}':\n\n{transcription_text}"

        except Exception as e:
            logger.error(f"Error processing audio file {file_path}: {e}")
            return f"Ошибка при обработке аудио файла: {str(e)}"

    async def extract_text_from_file(self, file_path: str, file_type: str) -> str:
        """Универсальная функция извлечения текста из файлов"""
        try:
            if file_type == "text/plain":
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(5000)  # Первые 5000 символов
                return content

            elif "pdf" in file_type:
                return await self.extract_text_from_pdf(file_path)

            elif "word" in file_type or "document" in file_type:
                return await self.extract_text_from_docx(file_path)

            elif "excel" in file_type or "spreadsheet" in file_type:
                return await self.extract_text_from_excel(file_path)

            elif "csv" in file_type:
                return await self.extract_text_from_csv(file_path)

            elif "audio" in file_type or file_type.startswith("audio/"):
                return await self.extract_text_from_audio(file_path)

            else:
                return f"Формат файла {file_type} поддерживается для загрузки, но извлечение текста не реализовано."

        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return f"Ошибка при обработке файла: {str(e)}"

    async def prepare_message_content(self, message: str, files_text: str) -> List[Dict]:
        """Подготовка контента сообщения с файлами для OpenAI API"""
        content = [{"type": "text", "text": message}]

        # Обрабатываем каждый файл
        for file_data in files_data:
            file_path = file_data.get('file_path')

            file_type = file_data.get('file_type')
            file_name = file_data.get('original_name', 'unknown')

            if not file_path or not os.path.exists(file_path):
                continue

            # Если это изображение и модель поддерживает vision
            if (file_type.startswith('image/') and
                    self.model in self.vision_models):

                base64_image = self.encode_image_to_base64(file_path)
                if base64_image:
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{file_type};base64,{base64_image}",
                            "detail": "auto"
                        }
                    })
                    logger.info(f"Added image {file_name} to message content")

            # Если это документ или аудио, извлекаем текст
            else:
                extracted_text = await self.extract_text_from_file(file_path, file_type)
                if extracted_text:
                    content.append({
                        "type": "text",
                        "text": f"\n\n--- Содержимое файла '{file_name}' ({file_type}) ---\n{extracted_text}\n--- Конец файла ---\n"
                    })
                    logger.info(f"Added content from {file_name} ({file_type})")

        return content

    async def get_response_stream(
            self,
            message: str,
            context: Dict[str, Any] = {},
            chat_history: List[Dict[str, Any]] = [],  # ← Изменили тип на Any
            files_context: str = '',
    ):
        """Получить потоковый ответ от GPT с учетом файлов и истории"""
        try:
            logger.info(f"Starting streaming request: message='{message[:50]}...', files_count={len(files_context)}")

            tool_type = context.get('tool_type', 'default')
            system_prompt = self.system_prompts.get(tool_type, self.system_prompts['default'])

            # Формируем сообщения для GPT
            messages = [
                {"role": "system", "content": system_prompt}
            ]

            # Добавляем историю чата
            if chat_history:
                logger.info(f"Adding {len(chat_history)} messages from chat history")

                # Берем последние N сообщений (можно настроить)
                recent_history = chat_history[-15:]  # ← Увеличили до 15

                for msg in recent_history:
                    role = msg.get("role")
                    content = msg.get("content", "")

                    # Пропускаем пустые сообщения
                    if not content or not role:
                        continue

                    # Добавляем информацию о файлах в текст сообщения
                    if msg.get("files") and role == "user":
                        file_names = [f.get("original_name", "файл") for f in msg["files"]]
                        file_info = ", ".join(file_names)
                        content = f"{content}\n[Прикреплены файлы: {file_info}]"

                    messages.append({
                        "role": role,
                        "content": content
                    })

                logger.info(f"Added {len(recent_history)} history messages to context")

            # Подготавливаем контент текущего сообщения с файлами
            if files_context:
                logger.info(f"Preparing message content with {len(files_context)} files")
                # message_content = await self.prepare_message_content(message, files_context)
                message_content = "Текст от пользователя:\n" + message + "\n Извлеченный текст из файла:\n" + files_context
            else:
                message_content = message

            # Добавляем текущее сообщение
            messages.append({
                "role": "user",
                "content": message_content
            })

            logger.info(f"Sending streaming request to {self.model} with {len(messages)} messages")

            # Вызываем GPT с потоковым режимом
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=2000,
                temperature=0.7,
                presence_penalty=0.1,
                frequency_penalty=0.1,
                stream=True
            )

            logger.info("Stream created successfully, starting to yield chunks...")
            chunk_count = 0

            # Генерируем чанки
            async for chunk in stream:
                chunk_count += 1
                if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta.content is not None:
                    content_piece = chunk.choices[0].delta.content
                    logger.debug(f"Chunk {chunk_count}: '{content_piece[:30]}...'")
                    yield content_piece

            logger.info(f"GPT streaming completed successfully. Total chunks: {chunk_count}")

        except Exception as e:
            logger.error(f"OpenAI API streaming error: {str(e)}", exc_info=True)
            # Fallback ответ
            files_context = ""
            if files_data:
                file_names = [f.get('original_name', 'unknown') for f in files_data]
                files_context = ", ".join(file_names)

            fallback_response = self._get_fallback_response(message, tool_type, files_context)
            logger.info(f"Yielding fallback response: {fallback_response[:100]}...")
            yield fallback_response

    # Сохраняем оригинальную функцию как fallback
    async def get_response(
            self,
            message: str,
            context: Dict[str, Any] = {},
            chat_history: List[Dict[str, str]] = [],
            files_data: List[Dict] = []
    ) -> str:
        """Получить полный ответ от GPT с учетом файлов (не потоковый режим)"""
        try:
            # Собираем полный ответ из потока
            full_response = ""
            async for chunk in self.get_response_stream(message, context, chat_history, files_data):
                full_response += chunk

            return full_response

        except Exception as e:
            logger.error(f"Error in get_response: {e}")
            # Fallback на статичный ответ при ошибке
            files_context = ""
            if files_data:
                file_names = [f.get('original_name', 'unknown') for f in files_data]
                files_context = ", ".join(file_names)

            return self._get_fallback_response(message, context.get('tool_type', 'default'), files_context)

    def _get_fallback_response(self, message: str, tool_type: str = "default", files_context: str = "") -> str:
        """Резервный ответ при недоступности GPT"""
        file_info = ""
        if files_context:
            file_info = f" Вижу прикрепленные файлы: {files_context}."

        fallback_responses = {
            "create_image": f"Извините, временно не могу помочь с созданием изображений.{file_info} "
                            f"Но ваша идея '{message[:50]}...' звучит интересно! 🎨 "
                            f"Попробуйте позже, когда ИИ снова будет доступен.",

            "coding": f"Временные технические проблемы с ИИ.{file_info} "
                      f"По вопросу '{message[:50]}...' рекомендую проверить документацию. 💻 "
                      f"Как только система восстановится, смогу помочь с анализом кода.",

            "brainstorm": f"ИИ временно недоступен,{file_info} но тема '{message[:50]}...' "
                          f"очень перспективная для обсуждения! 💡 Запишите свои идеи, "
                          f"а я помогу их развить, когда вернусь онлайн.",

            "excuse": f"Хм, с отмазками сейчас проблемы...{file_info} Может, попробуем честность? 😅 "
                      f"По поводу '{message[:30]}...' - иногда правда работает лучше любых оправданий!",

            "make_notes": f"Временные проблемы с ИИ.{file_info} "
                          f"Ваш запрос на создание заметок по '{message[:50]}...' получен. 📝 "
                          f"Пока что рекомендую записать основные моменты самостоятельно.",

            "default": f"Извините, временные проблемы с ИИ.{file_info} "
                       f"Ваш запрос '{message[:50]}...' получен, попробуйте позже! 🤖 "
                       f"Система восстановится в ближайшее время."
        }
        return fallback_responses.get(tool_type, fallback_responses["default"])

    async def analyze_image(self, image_path: str, prompt: str = "") -> str:
        """Анализ изображения через GPT-4 Vision"""
        try:
            if self.model not in self.vision_models:
                return f"📸 Модель {self.model} не поддерживает анализ изображений. Используйте gpt-4o или gpt-4o-mini."

            base64_image = self.encode_image_to_base64(image_path)
            if not base64_image:
                return "Не удалось обработать изображение."

            analysis_prompt = prompt or "Подробно опиши что ты видишь на этом изображении."
            mime_type = self.get_image_mime_type(image_path)

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": analysis_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}",
                                "detail": "auto"
                            }
                        }
                    ]
                }],
                max_tokens=1000
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return f"Ошибка при анализе изображения: {str(e)}"

    async def analyze_document(self, file_path: str, file_type: str, prompt: str = "") -> str:
        """Анализ документов с извлечением текста"""
        try:
            file_name = Path(file_path).name
            extracted_text = await self.extract_text_from_file(file_path, file_type)

            if not extracted_text or extracted_text.startswith("Ошибка"):
                return extracted_text

            analysis_prompt = prompt or f"Проанализируй содержимое документа '{file_name}' и дай краткое содержание."

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": f"{analysis_prompt}\n\nСодержимое файла:\n{extracted_text}"
                }],
                max_tokens=1000
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Document analysis error: {e}")
            return f"Ошибка при анализе документа: {str(e)}"

    async def health_check(self) -> bool:
        """Проверка доступности OpenAI API"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=5
            )
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def get_file_suggestions(self, file_type: str, file_name: str) -> str:
        """Получение предложений по работе с файлом"""
        suggestions = {
            'image': [
                "Опишите, что вы видите на изображении",
                "Нужна ли обработка или редактирование изображения?",
                "Хотите создать похожее изображение в другом стиле?",
                "Нужен анализ композиции, цветов или стиля?"
            ],
            'audio': [
                "Преобразовать речь в текст",
                "Проанализировать тон и настроение голоса",
                "Извлечь ключевые фразы из записи",
                "Создать краткое содержание аудио"
            ],
            'pdf': [
                "Извлечь основные идеи из документа",
                "Создать краткое содержание",
                "Найти ключевые моменты и выводы",
                "Проанализировать структуру документа"
            ],
            'document': [
                "Проверить грамматику и стиль",
                "Улучшить структуру текста",
                "Сократить или расширить содержание",
                "Переформатировать документ"
            ],
            'spreadsheet': [
                "Проанализировать данные в таблице",
                "Найти закономерности и тенденции",
                "Создать выводы на основе данных",
                "Проверить расчеты и формулы"
            ]
        }

        file_category = 'document'
        if 'image' in file_type:
            file_category = 'image'
        elif 'pdf' in file_type:
            file_category = 'pdf'
        elif 'audio' in file_type:
            file_category = 'audio'
        elif 'spreadsheet' in file_type or 'excel' in file_type:
            file_category = 'spreadsheet'

        file_suggestions = suggestions.get(file_category, suggestions['document'])
        suggestion_text = "\n".join([f"• {s}" for s in file_suggestions])

        return f"🔎 Файл '{file_name}' успешно загружен и обработан! Вот что я могу с ним сделать:\n\n{suggestion_text}"


# Глобальный экземпляр AI сервиса
ai_service = None


def get_ai_service() -> AIService:
    """Получить экземпляр AI сервиса"""
    global ai_service
    if ai_service is None:
        try:
            ai_service = AIService()
        except ValueError as e:
            logger.error(f"Failed to initialize AI service: {e}")
            ai_service = None
    return ai_service