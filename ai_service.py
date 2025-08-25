# ai_service.py
import os
import asyncio
from openai import AsyncOpenAI
from typing import Dict, List, Any, Optional
import logging
import base64
from pathlib import Path

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

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

    def encode_image_to_base64(self, image_path: str) -> str:
        """Кодирование изображения в base64"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
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

    def prepare_file_context(self, files_context: str) -> str:
        """Подготовка контекста файлов для AI"""
        if not files_context:
            return ""

        return f"\n\nПользователь прикрепил следующие файлы: {files_context}\n" \
               f"Пожалуйста, учти эти файлы в своем ответе."

    async def get_response(
            self,
            message: str,
            context: Dict[str, Any] = {},
            chat_history: List[Dict[str, str]] = []
    ) -> str:
        """Получить ответ от GPT с учетом файлов"""
        try:
            tool_type = context.get('tool_type', 'default')
            system_prompt = self.system_prompts.get(tool_type, self.system_prompts['default'])
            files_context = context.get('files_context', '')

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

            # Подготавливаем текущее сообщение
            current_message_content = message

            # Добавляем контекст файлов к сообщению
            if files_context:
                current_message_content += self.prepare_file_context(files_context)

            # Проверяем, есть ли изображения для анализа
            # (В реальной реализации здесь будет логика обработки изображений через GPT-4 Vision)
            has_images = files_context and "Изображение" in files_context

            if has_images and self.model in ["gpt-4o", "gpt-4o-mini", "gpt-4-vision-preview"]:
                # Для моделей с поддержкой изображений можно добавить специальную обработку
                current_message_content += "\n\n📸 Примечание: Обнаружены изображения. " \
                                           "В полной версии API они будут переданы для анализа."

            # Добавляем текущее сообщение
            messages.append({"role": "user", "content": current_message_content})

            # Вызываем GPT
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1500,  # Увеличиваем для более подробных ответов с файлами
                temperature=0.7,
                presence_penalty=0.1,
                frequency_penalty=0.1
            )

            ai_response = response.choices[0].message.content

            logger.info(f"GPT response generated for tool_type: {tool_type}, with_files: {bool(files_context)}")
            return ai_response

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            # Fallback на статичный ответ при ошибке
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
        """Анализ изображения (заглушка для будущей реализации)"""
        try:
            # В будущей версии здесь будет реальный анализ изображения через GPT-4 Vision
            base64_image = self.encode_image_to_base64(image_path)
            if not base64_image:
                return "Не удалось обработать изображение."

            # Заглушка для демонстрации
            image_name = Path(image_path).name
            analysis_prompt = prompt or "Опиши что ты видишь на этом изображении."

            return f"📸 Анализ изображения '{image_name}': В данной демо-версии анализ изображений " \
                   f"недоступен. В полной версии с GPT-4 Vision я смогу подробно описать содержимое, " \
                   f"стиль, цвета и дать рекомендации по вашему запросу: '{analysis_prompt}'"

        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return f"Ошибка при анализе изображения: {str(e)}"

    async def analyze_document(self, file_path: str, file_type: str) -> str:
        """Анализ документов (заглушка для будущей реализации)"""
        try:
            file_name = Path(file_path).name

            if "pdf" in file_type:
                return f"📄 PDF документ '{file_name}': В демо-версии анализ PDF недоступен. " \
                       f"В полной версии я смогу извлечь текст и проанализировать содержимое."

            elif "word" in file_type or "document" in file_type:
                return f"📝 Word документ '{file_name}': В демо-версии анализ документов недоступен. " \
                       f"В полной версии я смогу прочитать и проанализировать текст."

            elif "excel" in file_type or "spreadsheet" in file_type:
                return f"📊 Excel таблица '{file_name}': В демо-версии анализ таблиц недоступен. " \
                       f"В полной версии я смогу проанализировать данные и создать отчеты."

            elif file_type == "text/plain":
                # Для текстовых файлов можем попробовать прочитать содержимое
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(1000)  # Читаем первые 1000 символов

                    return f"📝 Текстовый файл '{file_name}': Содержит {len(content)} символов. " \
                           f"Начало файла: '{content[:200]}...'"

                except Exception:
                    return f"📝 Текстовый файл '{file_name}': Не удалось прочитать содержимое."

            else:
                return f"📎 Файл '{file_name}': Тип {file_type} поддерживается для загрузки, " \
                       f"но анализ содержимого в демо-версии недоступен."

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
        except:
            return False

    async def get_file_suggestions(self, file_type: str, file_name: str) -> str:
        """Получение предложений по работе с файлом"""
        suggestions = {
            'image': [
                "Опишите, что вы хотите создать на основе этого изображения",
                "Нужна ли обработка или редактирование изображения?",
                "Хотите создать похожее изображение в другом стиле?",
                "Нужен анализ композиции, цветов или стиля?"
            ],
            'pdf': [
                "Нужно ли извлечь основные идеи из документа?",
                "Хотите создать краткое содержание?",
                "Нужна помощь с пониманием сложных частей?",
                "Требуется анализ структуры документа?"
            ],
            'document': [
                "Нужна проверка грамматики и стиля?",
                "Хотите улучшить структуру текста?",
                "Требуется сократить или расширить содержание?",
                "Нужна помощь с форматированием?"
            ],
            'spreadsheet': [
                "Нужен анализ данных в таблице?",
                "Хотите создать графики или диаграммы?",
                "Требуется помощь с формулами?",
                "Нужна интерпретация результатов?"
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

        return f"📎 Файл '{file_name}' загружен! Вот что я могу с ним сделать:\n\n{suggestion_text}"


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