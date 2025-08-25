# ai_service.py
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
from PIL import Image
import io

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
            Пиши дружелюбно и с энтузиазмом. Используй эмодзи уместно.""",

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

            "default": """Ты - дружелюбный и умный ИИ помощник школьника. Отвечай полезно и интересно,
            объясняй сложные темы простым языком. Если пользователь прикрепляет файлы, анализируй их
            и помогай с содержимым. Будь поддерживающим и мотивирующим.
            Помогай с учебой, творчеством и повседневными задачами."""
        }

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
                for page_num in range(min(len(pdf_reader.pages), 10)):  # Первые 10 страниц
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

            else:
                return f"Формат файла {file_type} поддерживается для загрузки, но извлечение текста не реализовано."

        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return f"Ошибка при обработке файла: {str(e)}"

    async def prepare_message_content(self, message: str, files_data: List[Dict]) -> List[Dict]:
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

            # Если это документ, извлекаем текст
            else:
                extracted_text = await self.extract_text_from_file(file_path, file_type)
                if extracted_text:
                    content.append({
                        "type": "text",
                        "text": f"\n\n--- Содержимое файла '{file_name}' ({file_type}) ---\n{extracted_text}\n--- Конец файла ---\n"
                    })
                    logger.info(f"Added document content from {file_name}")

        return content

    async def get_response(
            self,
            message: str,
            context: Dict[str, Any] = {},
            chat_history: List[Dict[str, str]] = [],
            files_data: List[Dict] = []
    ) -> str:
        """Получить ответ от GPT с учетом файлов"""
        try:
            tool_type = context.get('tool_type', 'default')
            system_prompt = self.system_prompts.get(tool_type, self.system_prompts['default'])

            # Формируем сообщения для GPT
            messages = [
                {"role": "system", "content": system_prompt}
            ]

            # Добавляем историю чата (последние 10 сообщений для контекста)
            if chat_history:
                for msg in chat_history[-10:]:
                    role = "user" if msg.get("type") == "user" else "assistant"
                    content = msg.get("message", "")
                    if content and not msg.get("is_tool_description"):
                        # Добавляем информацию о файлах в историческом сообщении
                        if msg.get("files") and role == "user":
                            file_info = ", ".join([f["original_name"] for f in msg.get("files", [])])
                            content += f" [Прикреплены файлы: {file_info}]"
                        messages.append({"role": role, "content": content})

            # Подготавливаем контент текущего сообщения с файлами
            if files_data:
                message_content = await self.prepare_message_content(message, files_data)
            else:
                message_content = message

            # Добавляем текущее сообщение
            messages.append({
                "role": "user",
                "content": message_content
            })

            logger.info(f"Sending request to {self.model} with {len(files_data)} files")

            # Вызываем GPT
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=2000,  # Увеличиваем для более подробных ответов с файлами
                temperature=0.7,
                presence_penalty=0.1,
                frequency_penalty=0.1
            )

            ai_response = response.choices[0].message.content

            logger.info(f"GPT response generated for tool_type: {tool_type}, with {len(files_data)} files")
            return ai_response

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            # Fallback на статичный ответ при ошибке
            files_context = ""
            if files_data:
                file_names = [f.get('original_name', 'unknown') for f in files_data]
                files_context = ", ".join(file_names)

            return self._get_fallback_response(message, tool_type, files_context)

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
        elif 'spreadsheet' in file_type or 'excel' in file_type:
            file_category = 'spreadsheet'

        file_suggestions = suggestions.get(file_category, suggestions['document'])
        suggestion_text = "\n".join([f"• {s}" for s in file_suggestions])

        return f"📎 Файл '{file_name}' успешно загружен и обработан! Вот что я могу с ним сделать:\n\n{suggestion_text}"


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