# ai_service.py
import os
import asyncio
from openai import AsyncOpenAI
from typing import Dict, List, Any, Optional
import logging

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
            советуй стили и техники. Будь креативным и вдохновляющим! 
            Пиши дружелюбно и с энтузиазмом. Используй эмодзи уместно.""",

            "coding": """Ты - опытный программист и ментор. Помогай с кодом на любых языках программирования.
            Объясняй сложные концепции простыми словами, пиши чистый и читаемый код,
            предлагай лучшие практики. Всегда включай комментарии в код.
            Будь терпеливым и поощряющим. Можешь использовать технические эмодзи.""",

            "brainstorm": """Ты - креативный помощник для мозгового штурма. Генерируй оригинальные идеи,
            задавай наводящие вопросы, помогай развивать мысли пользователя.
            Будь энергичным и вдохновляющим! Предлагай неожиданные связи и решения.
            Используй эмодзи для выражения энтузиазма.""",

            "excuse": """Ты - мастер творческих отмазок! Помогай придумывать правдоподобные,
            но безвредные объяснения для разных ситуаций. Будь остроумным и изобретательным,
            но всегда этичным. Отмазки должны быть безобидными и не вредить отношениям.
            Используй юмор и эмодзи.""",

            "default": """Ты - дружелюбный и умный ИИ помощник школьника. Отвечай полезно и интересно,
            объясняй сложные темы простым языком. Будь поддерживающим и мотивирующим.
            Помогай с учебой, творчеством и повседневными задачами."""
        }

    async def get_response(
            self,
            message: str,
            context: Dict[str, Any] = {},
            chat_history: List[Dict[str, str]] = []
    ) -> str:
        """Получить ответ от GPT"""
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
                    if content and not msg.get("is_tool_description"):  # Исключаем описания инструментов
                        messages.append({"role": role, "content": content})

            # Добавляем текущее сообщение
            messages.append({"role": "user", "content": message})

            # Вызываем GPT
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1000,
                temperature=0.7,
                presence_penalty=0.1,
                frequency_penalty=0.1
            )

            ai_response = response.choices[0].message.content

            logger.info(f"GPT response generated for tool_type: {tool_type}")
            return ai_response

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            # Fallback на статичный ответ при ошибке
            return self._get_fallback_response(message, tool_type)

    def _get_fallback_response(self, message: str, tool_type: str = "default") -> str:
        """Резервный ответ при недоступности GPT"""
        fallback_responses = {
            "create_image": f"Извините, временно не могу помочь с созданием изображений. Но ваша идея '{message[:50]}...' звучит интересно! 🎨",
            "coding": f"Временные технические проблемы с ИИ. По вопросу '{message[:50]}...' рекомендую проверить документацию. 💻",
            "brainstorm": f"ИИ временно недоступен, но тема '{message[:50]}...' очень перспективная для обсуждения! 💡",
            "excuse": f"Хм, с отмазками сейчас проблемы... Может, попробуем честность? 😅 По поводу '{message[:30]}...'",
            "default": f"Извините, временные проблемы с ИИ. Ваш запрос '{message[:50]}...' получен, попробуйте позже! 🤖"
        }
        return fallback_responses.get(tool_type, fallback_responses["default"])

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