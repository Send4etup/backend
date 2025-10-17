# backend/services/ai/ai_service.py
"""
Главный класс AI сервиса
Координирует работу всех процессоров и предоставляет единый интерфейс
"""

import os
import logging
from typing import Dict, Any, List, Optional, AsyncIterator
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from pyexpat.errors import messages

from .prompts import get_system_prompt, TOOL_METADATA
from .image_processor import ImageProcessor
from .audio_processor import AudioProcessor
from .document_processor import DocumentProcessor
from .response_handler import ResponseHandler

logger = logging.getLogger(__name__)

class ImageGenerationResponse(BaseModel):
    """Модель ответа со сгенерированным изображением"""
    success: bool
    image_url: Optional[str] = None
    revised_prompt: Optional[str] = None
    error: Optional[str] = None

class AIService:
    """Главный класс для работы с AI функциональностью"""

    def __init__(self):
        """Инициализация AI сервиса"""
        # Получаем API ключ
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")

        # Инициализируем клиент OpenAI
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")

        logger.info(f"AIService initialized with model: {self.model}")

        # Инициализируем процессоры
        self.image_processor = ImageProcessor(max_image_size=2048)
        self.audio_processor = AudioProcessor(openai_client=self.client)
        self.document_processor = DocumentProcessor(max_text_length=5000)
        self.response_handler = ResponseHandler(
            openai_client=self.client,
            model=self.model,
            default_max_tokens=2000
        )

        logger.info("All processors initialized successfully")

    # ==================== ОСНОВНЫЕ МЕТОДЫ ДЛЯ РАБОТЫ С GPT ====================

    async def get_response_stream(
            self,
            message: str,
            context: str = 'general',
            chat_history: List[Dict[str, Any]] = None,
            files_context: str = '',
            temperature: float = 0.7,
            agent_prompt: str = None,
    ) -> AsyncIterator[str]:
        """
        Получить потоковый ответ от GPT

        Args:
            message: Сообщение пользователя
            context: Контекст (tool_type и т.д.)
            chat_history: История чата
            files_context: Извлеченный текст из файлов
            temperature: float
            agent_prompt: str

        Yields:
            Части ответа (chunks)
        """
        logger.info(f"Getting streaming response for message: '{message[:50]}...'")

        async for chunk in self.response_handler.get_response_stream(
                message=message,
                context=context,
                chat_history=chat_history or [],
                files_context=files_context,
                temperature=temperature,
                agent_prompt=agent_prompt,
        ):
            yield chunk

    async def get_response(
            self,
            message: str,
            context: str = 'general',
            chat_history: List[Dict[str, Any]] = None,
            files_context: str = '',
            temperature: float = 0.7,
            agent_prompt: str = None,
    ) -> str:
        """
        Получить полный ответ от GPT (не потоковый)

        Args:
            message: Сообщение пользователя
            context: Контекст
            chat_history: История чата
            files_context: Извлеченный текст из файлов
            temperature: float
            agent_prompt: str
        Returns:
            Полный ответ от GPT
        """
        logger.info(f"Getting single response for message: '{message[:50]}...'")

        return await self.response_handler.get_single_response(
            message=message,
            context=context,
            chat_history=chat_history or [],
            files_context=files_context,
            temperature=temperature,
            agent_prompt=agent_prompt,
        )

    async def generate_image(
            self,
            message: str,
            chat_history: List[Dict[str, Any]] = None,
            n: int = 1,
            agent_prompt: str = None,
            files_context: str = '',
    ):
        """
        Генерация изображения через DALL-E API

        Args:
            message: Промпт пользователя для генерации
            chat_history: История чата для контекста
            n: Количество изображений (всегда 1 для DALL-E 3)
            agent_prompt: Системный промпт агента
            files_context: Контекст из прикрепленных файлов

        Returns:
            ImageGenerationResponse с URL изображения или ошибкой
        """
        try:
            chat_history = chat_history or []

            system_prompt = message
            params = {}  # Дефолтные параметры

            # Если есть agent_prompt - извлекаем из него параметры
            if agent_prompt:
                system_prompt = message + "\n\n" + agent_prompt
                params = self.detect_image_params(agent_prompt)
                logger.info(f"🎨 AI params from agent_prompt: {params}")
            else:
                # Если промпта нет - пытаемся извлечь из сообщения
                params = self.detect_image_params(message)

            if chat_history:
                logger.info(f"📜 Adding {len(chat_history[-10:])} messages from chat history")

                # Берем последние 10 сообщений для контекста
                recent_history = chat_history[-10:]

                context_text = "\n\nКонтекст из истории чата:\n\n"

                for msg in recent_history:
                    role = msg.get("role")
                    content = msg.get("content", "")

                    if role != "user" or not content:
                        continue

                    # Обрабатываем файлы из истории
                    if msg.get("files") and role == "user":
                        file_texts = []
                        file_names = []

                        for file_data in msg["files"]:
                            file_name = file_data.get("original_name", "файл")
                            file_names.append(file_name)

                            # Извлекаем текст если есть
                            extracted = file_data.get("extracted_text")
                            if extracted and extracted.strip() and extracted != "None":
                                file_texts.append(
                                    f"\n--- Содержимое файла '{file_name}' ---\n"
                                    f"{extracted}\n"
                                    f"--- Конец файла ---\n"
                                )

                        # Формируем content с текстами файлов
                        if file_texts:
                            content = f"{content}\n\n{''.join(file_texts)}"
                        elif file_names:
                            file_info = ", ".join(file_names)
                            content = f"{content}\n[Прикреплены файлы: {file_info}]"

                    context_text += content + "\n\n"

                # Добавляем контекст к промпту
                system_prompt = message + context_text

                logger.info(f"✅ Added {len(recent_history)} history messages to context")

            # DALL-E 3 принимает только эти размеры
            valid_sizes = ["1024x1024", "1792x1024", "1024x1792"]
            size = params.get("aspectRatio", "1024x1024")

            if size not in valid_sizes:
                logger.warning(f"⚠️ Invalid size {size}, using default 1024x1024")
                size = "1024x1024"

            quality = params.get("quality", "standard")
            if quality not in ["standard", "hd"]:
                quality = "standard"

            style = params.get("style", "vivid")
            if style not in ["vivid", "natural"]:
                style = "vivid"

            logger.info(f"🎨 Final DALL-E params: size={size}, quality={quality}, style={style}")
            logger.info(f"📝 Prompt length: {len(message)} characters")

            response = await self.client.images.generate(
                model="dall-e-3",  # DALL-E 3 для лучшего качества
                prompt=system_prompt,
                n=1,  # DALL-E 3 поддерживает только n=1
                size=size,
                quality=quality,
                style=style,
            )



            if response.data and len(response.data) > 0:
                image_data = response.data[0]
                logger.info("✅ Image generated successfully")

                return ImageGenerationResponse(
                    success=True,
                    image_url=image_data.url,
                    revised_prompt=getattr(image_data, 'revised_prompt', None)
                )
            else:
                logger.error("❌ No image data received from DALL-E")
                return ImageGenerationResponse(
                    success=False,
                    error="Не удалось получить изображение от DALL-E"
                )

        except Exception as e:
            logger.error(f"❌ Error generating image: {str(e)}", exc_info=True)

            error_message = str(e)

            if "billing" in error_message.lower() or "quota" in error_message.lower():
                error_message = "Превышен лимит API. Проверьте баланс OpenAI аккаунта."
            elif "content_policy" in error_message.lower():
                error_message = "Промпт нарушает политику контента. Попробуйте изменить описание."
            elif "rate_limit" in error_message.lower():
                error_message = "Слишком много запросов. Попробуйте через несколько секунд."
            else:
                error_message = f"Ошибка генерации: {error_message[:100]}"

            return ImageGenerationResponse(
                success=False,
                error=error_message
            )

    def detect_image_params(self, user_prompt: str) -> dict:
        """
        Определение параметров генерации изображения из промпта пользователя

        Args:
            user_prompt: Промпт от пользователя (может содержать настройки)

        Returns:
            dict: Параметры для DALL-E API
        """
        prompt = user_prompt.lower()
        params = {}

        # ✅ Стиль изображения (style parameter для DALL-E 3)
        if any(word in prompt for word in ["realistic", "фотореалистично", "фото", "реалистичный"]):
            params["style"] = "natural"
        elif any(word in prompt for word in ["anime", "мультяшно", "cartoon", "artistic", "vivid"]):
            params["style"] = "vivid"
        else:
            params["style"] = "vivid"  # По умолчанию более креативный стиль

        # ✅ Соотношение сторон (size parameter для DALL-E 3)
        # DALL-E 3 поддерживает только: 1024x1024, 1792x1024, 1024x1792
        if any(word in prompt for word in ["landscape", "широкий", "горизонтальный", "panorama"]):
            params["aspectRatio"] = "1792x1024"  # Горизонтальный
        elif any(word in prompt for word in ["portrait", "вертикальный", "портрет", "tall"]):
            params["aspectRatio"] = "1024x1792"  # Вертикальный
        elif any(word in prompt for word in ["квадрат", "square", "квадратный"]):
            params["aspectRatio"] = "1024x1024"  # Квадратный
        else:
            params["aspectRatio"] = "1024x1024"  # По умолчанию квадрат

        # ✅ Качество (quality parameter для DALL-E 3)
        if any(word in prompt for word in ["высокое качество", "hd", "high quality", "detailed"]):
            params["quality"] = "hd"
        else:
            params["quality"] = "standard"

        # ℹ️ Уровень детализации (используется только для промпта, не API параметр)
        if any(word in prompt for word in ["detailed", "детально", "детализация"]):
            params["detailLevel"] = "detailed"
        elif any(word in prompt for word in ["simple", "простая"]):
            params["detailLevel"] = "simple"
        else:
            params["detailLevel"] = "medium"

        logger.info(f"🎨 Detected image params: {params}")

        return params

    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С ИЗОБРАЖЕНИЯМИ ====================

    async def analyze_image(
            self,
            image_path: str,
            prompt: str = ""
    ) -> str:
        """
        Анализ изображения через GPT-4 Vision

        Args:
            image_path: Путь к изображению
            prompt: Промпт для анализа

        Returns:
            Результат анализа
        """
        try:
            logger.info(f"Analyzing image: {image_path}")

            # Проверяем поддержку Vision
            if not self.image_processor.is_vision_model_supported(self.model):
                return (
                    f"🔸 Модель {self.model} не поддерживает анализ изображений. "
                    f"Используйте gpt-4o или gpt-4o-mini."
                )

            # Подготавливаем изображение для Vision API
            image_data = self.image_processor.prepare_image_for_vision_api(
                image_path,
                detail="auto"
            )

            if not image_data:
                return "Не удалось обработать изображение."

            # Формируем промпт
            analysis_prompt = (
                "Проанализируй это изображение максимально детально и структурированно.\n\n"
                "ОБЯЗАТЕЛЬНО УКАЖИ:\n"
                "1. **ТЕКСТ** (если есть):\n"
                "   - Весь видимый текст дословно, построчно\n"
                "   - Заголовки, подзаголовки, основной текст\n"
                "   - Формулы, уравнения, математические выражения\n"
                "   - Таблицы и их содержимое\n"
                "   - Подписи к диаграммам, графикам\n\n"
                "2. **ВИЗУАЛЬНЫЙ КОНТЕНТ**:\n"
                "   - Основные объекты и их расположение\n"
                "   - Графики, диаграммы, схемы (с описанием данных)\n"
                "   - Фотографии, иллюстрации (что изображено)\n"
                "   - Цвета, стиль оформления\n\n"
                "3. **СТРУКТУРА И КОНТЕКСТ**:\n"
                "   - Тип документа (скриншот, фото доски, учебник, презентация, задача и т.д.)\n"
                "   - Предметная область (математика, физика, история и т.д.)\n"
                "   - Важные детали для понимания темы\n\n"
                "4. **ОБРАЗОВАТЕЛЬНАЯ ЦЕННОСТЬ**:\n"
                "   - Если это задача - опиши условие полностью\n"
                "   - Если это конспект - выдели ключевые понятия\n"
                "   - Если это таблица - сохрани структуру данных\n\n"
                "ИНСТРУКЦИЯ НА СЛУЧАЙ ОШИБКИ РАСПОЗНАВАНИЯ:\n"
                "- Сообщи о невозможности анализа изображения.\n"
                "- Укажи возможные причины ошибки, такие как низкое качество изображения или неподдерживаемый формат.\n"
                "- Порекомендуй проверить изображение и попытаться еще раз с улучшенным качеством или другим форматом.\n\n"
                "ФОРМАТ ОТВЕТА:\n"
                "Структурируй информацию так, чтобы её можно было использовать для:\n"
                "- Поиска по содержимому\n"
                "- Ответов на вопросы об этом изображении\n"
                "- Создания конспектов и заметок\n"
                "- Решения задач из этого изображения\n\n"
                "Будь максимально точным и сохраняй ВСЮ важную информацию!"
            )

            # Отправляем запрос к Vision API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": analysis_prompt},
                        image_data
                    ]
                }],
                max_tokens=1000
            )

            result = response.choices[0].message.content

            logger.info(f"Image analysis completed: {len(result)} characters")

            return result

        except Exception as e:
            logger.error(f"Image analysis error: {e}", exc_info=True)
            return f"Ошибка при анализе изображения: {str(e)}"

    def encode_image_to_base64(self, image_path: str) -> Optional[str]:
        """
        Кодирование изображения в base64

        Args:
            image_path: Путь к изображению

        Returns:
            Base64 строка или None
        """
        return self.image_processor.encode_image_to_base64(image_path)

    def get_image_info(self, image_path: str) -> dict:
        """
        Получение информации об изображении

        Args:
            image_path: Путь к изображению

        Returns:
            Словарь с информацией
        """
        return self.image_processor.get_image_info(image_path)

    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С АУДИО ====================

    async def transcribe_audio(
            self,
            file_path: str,
            language: Optional[str] = None
    ) -> str:
        """
        Транскрипция аудио через Whisper API

        Args:
            file_path: Путь к аудио файлу
            language: Язык аудио (опционально)

        Returns:
            Текст транскрипции
        """
        logger.info(f"Transcribing audio: {file_path}")

        return await self.audio_processor.extract_text_from_audio(
            file_path,
            language=language
        )

    async def convert_audio_to_mp3(self, input_path: str) -> str:
        """
        Конвертация аудио в MP3

        Args:
            input_path: Путь к исходному файлу

        Returns:
            Путь к MP3 файлу
        """
        return await self.audio_processor.convert_audio_to_mp3(input_path)

    def get_audio_info(self, file_path: str) -> dict:
        """
        Получение информации об аудио файле

        Args:
            file_path: Путь к аудио файлу

        Returns:
            Словарь с информацией
        """
        return self.audio_processor.get_audio_info(file_path)

    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С ДОКУМЕНТАМИ ====================

    async def analyze_document(
            self,
            file_path: str,
            file_type: str,
            prompt: str = ""
    ) -> str:
        """
        Анализ документов с извлечением текста

        Args:
            file_path: Путь к документу
            file_type: MIME тип файла
            prompt: Промпт для анализа

        Returns:
            Результат анализа
        """
        try:
            logger.info(f"Analyzing document: {file_path}, type: {file_type}")

            # Извлекаем текст из документа
            extracted_text = await self.document_processor.extract_text_from_file(
                file_path,
                file_type
            )

            if not extracted_text or extracted_text.startswith("Ошибка"):
                return extracted_text

            # Если нет промпта, возвращаем просто извлеченный текст
            if not prompt:
                return extracted_text

            # Анализируем с помощью GPT
            file_name = os.path.basename(file_path)
            analysis_prompt = (
                f"{prompt}\n\n"
                f"Содержимое документа '{file_name}':\n{extracted_text}"
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": analysis_prompt
                }],
                max_tokens=1000
            )

            result = response.choices[0].message.content

            logger.info(f"Document analysis completed: {len(result)} characters")

            return result

        except Exception as e:
            logger.error(f"Document analysis error: {e}", exc_info=True)
            return f"Ошибка при анализе документа: {str(e)}"

    async def extract_text_from_file(
            self,
            file_path: str,
            file_type: str
    ) -> str:
        """
        Извлечение текста из файла

        Args:
            file_path: Путь к файлу
            file_type: MIME тип файла

        Returns:
            Извлеченный текст
        """
        logger.info(f"Extracting text from file: {file_path}, type: {file_type}")

        # Для аудио используем транскрипцию
        if file_type.startswith("audio/") or "audio" in file_type:
            return await self.audio_processor.extract_text_from_audio(file_path)

        # Для остальных форматов используем document processor
        return await self.document_processor.extract_text_from_file(
            file_path,
            file_type
        )

    def get_document_info(self, file_path: str) -> dict:
        """
        Получение информации о документе

        Args:
            file_path: Путь к документу

        Returns:
            Словарь с информацией
        """
        return self.document_processor.get_document_info(file_path)

    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================

    async def health_check(self) -> bool:
        """
        Проверка доступности OpenAI API

        Returns:
            True если API доступен
        """
        try:
            logger.info("Performing health check...")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=5
            )

            logger.info("Health check passed")
            return True

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def get_file_suggestions(self, file_type: str, file_name: str) -> str:
        """
        Получение предложений по работе с файлом

        Args:
            file_type: MIME тип файла
            file_name: Имя файла

        Returns:
            Текст с предложениями
        """
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

        # Определяем категорию файла
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

        return (
            f"🔎 Файл '{file_name}' успешно загружен и обработан! "
            f"Вот что я могу с ним сделать:\n\n{suggestion_text}"
        )

    def get_supported_file_formats(self) -> dict:
        """
        Получение всех поддерживаемых форматов файлов

        Returns:
            Словарь с форматами по категориям
        """
        return {
            'images': self.image_processor.get_supported_formats(),
            'audio': self.audio_processor.get_supported_formats(),
            'documents': self.document_processor.get_supported_formats()
        }

    def get_available_tools(self) -> list:
        """
        Получение списка доступных инструментов

        Returns:
            Список метаданных инструментов
        """
        return [
            {
                'type': tool_type,
                **TOOL_METADATA[tool_type]
            }
            for tool_type in TOOL_METADATA.keys()
        ]

    def set_model(self, model_name: str):
        """
        Изменение используемой модели

        Args:
            model_name: Название модели
        """
        old_model = self.model
        self.model = model_name
        self.response_handler.model = model_name

        logger.info(f"Model changed: {old_model} -> {model_name}")

    def get_current_model(self) -> str:
        """
        Получение текущей модели

        Returns:
            Название модели
        """
        return self.model

    def get_generation_params(self) -> dict:
        """
        Получение параметров генерации

        Returns:
            Словарь с параметрами
        """
        return self.response_handler.get_generation_params()

    def set_generation_params(
            self,
            temperature: Optional[float] = None,
            presence_penalty: Optional[float] = None,
            frequency_penalty: Optional[float] = None
    ):
        """
        Установка параметров генерации

        Args:
            temperature: Температура (0-2)
            presence_penalty: Штраф за присутствие (-2 до 2)
            frequency_penalty: Штраф за частоту (-2 до 2)
        """
        self.response_handler.set_generation_params(
            temperature=temperature,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty
        )

    def validate_file(
            self,
            file_path: str,
            file_type: str
    ) -> tuple[bool, Optional[str]]:
        """
        Валидация файла перед обработкой

        Args:
            file_path: Путь к файлу
            file_type: MIME тип файла

        Returns:
            Tuple (is_valid, error_message)
        """
        try:
            # Определяем тип файла и валидируем соответствующим процессором
            if 'image' in file_type:
                if not self.image_processor.validate_image(file_path):
                    return False, "Файл изображения поврежден или недоступен"

            elif 'audio' in file_type:
                return self.audio_processor.validate_audio_file(file_path)

            else:
                return self.document_processor.validate_document(file_path)

            return True, None

        except Exception as e:
            logger.error(f"File validation error: {e}")
            return False, str(e)

    async def get_chat_title(
            self,
            chat_id: str,
            prompt: str = "",
            tool_type: str = "default",
    ) -> str:
        """
        💰 БЮДЖЕТНАЯ генерация названия чата с помощью GPT-4o-mini

        Стоимость: ~$0.00015 за запрос (в 15 раз дешевле GPT-4o)

        Args:
            chat_id: ID чата
            prompt: Текст первого сообщения пользователя
            tool_type: Тип инструмента (например, "pdf", "excel", "default")

        Returns:
            Короткое и осмысленное название чата
        """
        try:
            if not prompt.strip():
                return f"Чат {tool_type}"

            logger.info(f"Generating chat title for chat {chat_id} (tool: {tool_type})")

            system_prompt = (
                "Создай короткое название чата (макс 5 слов) на русском. "
                "Ответ: только название, без кавычек и точек."
            )

            # Ограничиваем входные токены для экономии
            user_prompt = f"Инструмент: {tool_type}\nЗапрос: {prompt[:200]}"

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=30,
                temperature=0.7,
            )

            title = response.choices[0].message.content.strip()

            # Очистка от лишних символов
            title = title.strip('"').strip("'").strip('.')

            # Ограничиваем длину на всякий случай
            if len(title) > 50:
                title = title[:47] + "..."

            logger.info(f"✅ Chat title generated: '{title}'")
            return title

        except Exception as e:
            logger.warning(f"LLM title generation failed for chat {chat_id}: {e}")

            if prompt.strip():
                words = prompt.strip().split()[:4]
                fallback_title = " ".join(words)
                if len(fallback_title) > 50:
                    fallback_title = fallback_title[:47] + "..."
            else:
                fallback_title = f"{tool_type.capitalize()} чат"

            logger.info(f"Using fallback title: '{fallback_title}'")
            return fallback_title


# ==================== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР СЕРВИСА ====================

_ai_service_instance = None


def get_ai_service() -> AIService:
    """
    Получить глобальный экземпляр AI сервиса (Singleton)

    Returns:
        Экземпляр AIService
    """
    global _ai_service_instance

    if _ai_service_instance is None:
        try:
            _ai_service_instance = AIService()
            logger.info("AIService instance created successfully")
        except ValueError as e:
            logger.error(f"Failed to initialize AI service: {e}")
            _ai_service_instance = None

    return _ai_service_instance


def reset_ai_service():
    """
    Сброс глобального экземпляра (для тестирования)
    """
    global _ai_service_instance
    _ai_service_instance = None
    logger.info("AIService instance reset")


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def quick_ask(
        message: str,
        tool_type: str = "default",
        chat_history: List[Dict[str, Any]] = None
) -> str:
    """
    Быстрый способ получить ответ от AI

    Args:
        message: Сообщение пользователя
        tool_type: Тип инструмента
        chat_history: История чата

    Returns:
        Ответ от AI
    """
    service = get_ai_service()
    if not service:
        return "AI сервис недоступен"

    context = {'tool_type': tool_type}
    return await service.get_response(message, context, chat_history or [])


async def quick_analyze_file(
        file_path: str,
        file_type: str,
        prompt: str = ""
) -> str:
    """
    Быстрый анализ файла

    Args:
        file_path: Путь к файлу
        file_type: MIME тип
        prompt: Промпт для анализа

    Returns:
        Результат анализа
    """
    service = get_ai_service()
    if not service:
        return "AI сервис недоступен"

    # Определяем тип файла и вызываем соответствующий метод
    if 'image' in file_type:
        return await service.analyze_image(file_path, prompt)
    else:
        return await service.analyze_document(file_path, file_type, prompt)
