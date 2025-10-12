# backend/services/ai/response_handler.py
"""
Модуль для обработки ответов от GPT
Включает потоковую генерацию, подготовку контекста и fallback ответы
"""

import logging
from typing import Dict, Any, List, Optional, AsyncIterator
from openai import AsyncOpenAI
from .prompts import get_system_prompt

logger = logging.getLogger(__name__)


class ResponseHandler:
    """Класс для обработки ответов от GPT"""

    def __init__(
            self,
            openai_client: AsyncOpenAI,
            model: str = "gpt-4o",
            default_max_tokens: int = 2000
    ):
        """
        Инициализация обработчика ответов

        Args:
            openai_client: Клиент OpenAI
            model: Название модели для использования
            default_max_tokens: Максимальное количество токенов по умолчанию
        """
        self.client = openai_client
        self.model = model
        self.default_max_tokens = default_max_tokens

        # Параметры генерации
        self.generation_params = {
            'presence_penalty': 0.1,
            'frequency_penalty': 0.1
        }

    async def get_response_stream(
            self,
            message: str,
            context: str,
            chat_history: List[Dict[str, Any]] = None,
            files_context: str = '',
            max_tokens: Optional[int] = None,
            temperature: float = 0.7,
            agent_prompt: str = None,
    ) -> AsyncIterator[str]:
        """
        Получить потоковый ответ от GPT с учетом файлов и истории

        Args:
            message: Сообщение пользователя
            context: Контекст (tool_type и т.д.)
            chat_history: История чата
            files_context: Контекст из файлов
            max_tokens: Максимальное количество токенов
            temperature: float
            agent_prompt: str
        Yields:
            Части ответа (chunks)
        """
        try:
            chat_history = chat_history or []

            logger.info(
                f"Starting streaming request: message='{message[:50]}...', "
                f"history_length={len(chat_history)}, "
                f"has_files={bool(files_context)}"
            )

            # Получаем системный промпт
            tool_type = context
            base_prompt = get_system_prompt(tool_type)

            if agent_prompt:
                system_prompt = base_prompt + "\n\n" + agent_prompt
                logger.info(f"AI prompt: '{agent_prompt}'")

            else:
                system_prompt = base_prompt

            # Формируем сообщения для GPT
            messages = [
                {"role": "system", "content": system_prompt}
            ]


            # Добавляем историю чата
            if chat_history:
                logger.info(f"Adding {len(chat_history)} messages from chat history")

                # Берем последние 15 сообщений для контекста
                recent_history = chat_history[-15:]

                for msg in recent_history:
                    role = msg.get("role")
                    content = msg.get("content", "")

                    if not content or not role:
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

                    messages.append({
                        "role": role,
                        "content": content
                    })

                logger.info(f"Added {len(recent_history)} history messages to context")

            # Подготавливаем текущее сообщение с контекстом файлов
            if files_context:
                logger.info("Preparing current message with files context")
                message_content = (
                    f"Текст от пользователя:\n{message}\n\n"
                    f"Извлеченный текст из файлов:\n{files_context}"
                )
            else:
                message_content = message

            # Добавляем текущее сообщение
            messages.append({
                "role": "user",
                "content": message_content
            })

            logger.info(
                f"Sending streaming request to {self.model} with "
                f"{len(messages)} messages"
            )

            # Вызываем GPT с потоковым режимом
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens or self.default_max_tokens,
                stream=True,
                temperature=temperature,
                **self.generation_params
            )

            logger.info("Stream created successfully, starting to yield chunks...")
            chunk_count = 0

            # Генерируем чанки
            async for chunk in stream:
                chunk_count += 1

                if (chunk.choices and
                        len(chunk.choices) > 0 and
                        chunk.choices[0].delta.content is not None):
                    content_piece = chunk.choices[0].delta.content
                    logger.debug(f"Chunk {chunk_count}: '{content_piece[:30]}...'")
                    yield content_piece

            logger.info(
                f"GPT streaming completed successfully. Total chunks: {chunk_count}"
            )

        except Exception as e:
            logger.error(f"OpenAI API streaming error: {str(e)}", exc_info=True)

            # Fallback ответ
            fallback_response = self._get_fallback_response(
                message,
                context,
                bool(files_context)
            )

            logger.info(f"Yielding fallback response: {fallback_response[:100]}...")
            yield fallback_response

    def _get_fallback_response(
            self,
            message: str,
            tool_type: str = "default",
            has_files: bool = False
    ) -> str:
        """
        Резервный ответ при недоступности GPT

        Args:
            message: Сообщение пользователя
            tool_type: Тип инструмента
            has_files: Есть ли прикрепленные файлы

        Returns:
            Резервный ответ
        """
        file_info = ""
        if has_files:
            file_info = " Вижу прикрепленные файлы."

        fallback_responses = {
            "create_image": (
                f"Извините, временно не могу помочь с созданием изображений.{file_info} "
                f"Но ваша идея '{message[:50]}...' звучит интересно! 🎨 "
                f"Попробуйте позже, когда ИИ снова будет доступен."
            ),

            "coding": (
                f"Временные технические проблемы с ИИ.{file_info} "
                f"По вопросу '{message[:50]}...' рекомендую проверить документацию. 💻 "
                f"Как только система восстановится, смогу помочь с анализом кода."
            ),

            "brainstorm": (
                f"ИИ временно недоступен,{file_info} но тема '{message[:50]}...' "
                f"очень перспективна для обсуждения! 💡 Запишите свои идеи, "
                f"а я помогу их развить, когда вернусь онлайн."
            ),

            "excuse": (
                f"Хм, с отмазками сейчас проблемы...{file_info} Может, попробуем честность? 😅 "
                f"По поводу '{message[:30]}...' - иногда правда работает лучше любых оправданий!"
            ),

            "make_notes": (
                f"Временные проблемы с ИИ.{file_info} "
                f"Ваш запрос на создание заметок по '{message[:50]}...' получен. 📝 "
                f"Пока что рекомендую записать основные моменты самостоятельно."
            ),

            "audio_transcribe": (
                f"ИИ временно недоступен для обработки аудио.{file_info} "
                f"Ваш запрос получен. 🎧 Попробуйте позже, когда сервис восстановится."
            ),

            "default": (
                f"Извините, временные проблемы с ИИ.{file_info} "
                f"Ваш запрос '{message[:50]}...' получен, попробуйте позже! 🤖 "
                f"Система восстановится в ближайшее время."
            )
        }

        return fallback_responses.get(tool_type, fallback_responses["default"])

    def format_chat_history(
            self,
            chat_history: List[Dict[str, Any]],
            max_messages: int = 15
    ) -> List[Dict[str, str]]:
        """
        Форматирование истории чата для отправки в GPT

        Args:
            chat_history: История чата
            max_messages: Максимальное количество сообщений

        Returns:
            Отформатированная история
        """
        try:
            if not chat_history:
                return []

            # Берем последние сообщения
            recent_history = chat_history[-max_messages:]
            formatted_messages = []

            for msg in recent_history:
                role = msg.get("role")
                content = msg.get("content", "")

                if not content or not role:
                    continue

                # Базовое сообщение
                formatted_msg = {
                    "role": role,
                    "content": content
                }

                # Добавляем информацию о файлах если есть
                if msg.get("files") and role == "user":
                    file_names = [
                        f.get("original_name", "файл")
                        for f in msg["files"]
                    ]

                    if file_names:
                        file_info = ", ".join(file_names)
                        formatted_msg["content"] += f"\n[Файлы: {file_info}]"

                formatted_messages.append(formatted_msg)

            logger.info(
                f"Formatted {len(formatted_messages)} messages from history"
            )

            return formatted_messages

        except Exception as e:
            logger.error(f"Error formatting chat history: {e}")
            return []

    def prepare_message_with_files(
            self,
            message: str,
            files_data: List[Dict[str, Any]]
    ) -> str:
        """
        Подготовка сообщения с информацией о файлах

        Args:
            message: Текст сообщения
            files_data: Данные о файлах

        Returns:
            Подготовленное сообщение
        """
        try:
            if not files_data:
                return message

            file_contexts = []

            for file_data in files_data:
                file_name = file_data.get('original_name', 'unknown')
                file_type = file_data.get('file_type', 'unknown')
                extracted_text = file_data.get('extracted_text', '')

                if extracted_text and extracted_text.strip() and extracted_text != "None":
                    file_contexts.append(
                        f"\n--- Содержимое файла '{file_name}' ({file_type}) ---\n"
                        f"{extracted_text}\n"
                        f"--- Конец файла ---\n"
                    )
                else:
                    file_contexts.append(
                        f"\n[Прикреплен файл: '{file_name}' ({file_type})]\n"
                    )

            # Объединяем сообщение с контекстом файлов
            if file_contexts:
                prepared_message = (
                    f"{message}\n\n"
                    f"{''.join(file_contexts)}"
                )

                logger.info(
                    f"Prepared message with {len(files_data)} files, "
                    f"total length: {len(prepared_message)}"
                )

                return prepared_message

            return message

        except Exception as e:
            logger.error(f"Error preparing message with files: {e}")
            return message

    def estimate_tokens(self, text: str) -> int:
        """
        Примерная оценка количества токенов в тексте
        (грубая оценка: 1 токен ≈ 4 символа для английского, 2-3 для русского)

        Args:
            text: Текст для оценки

        Returns:
            Примерное количество токенов
        """
        # Простая эвристика: считаем среднее между английским и русским
        estimated_tokens = len(text) // 3

        logger.debug(f"Estimated tokens for text length {len(text)}: {estimated_tokens}")

        return estimated_tokens

    def truncate_context_if_needed(
            self,
            messages: List[Dict[str, str]],
            max_context_tokens: int = 8000
    ) -> List[Dict[str, str]]:
        """
        Обрезание контекста если он слишком большой

        Args:
            messages: Список сообщений
            max_context_tokens: Максимальное количество токенов контекста

        Returns:
            Обрезанный список сообщений
        """
        try:
            total_tokens = sum(
                self.estimate_tokens(msg.get('content', ''))
                for msg in messages
            )

            if total_tokens <= max_context_tokens:
                logger.info(
                    f"Context size OK: {total_tokens} tokens "
                    f"(limit: {max_context_tokens})"
                )
                return messages

            logger.warning(
                f"Context too large: {total_tokens} tokens, truncating..."
            )

            # Сохраняем системный промпт (первое сообщение)
            # и последнее сообщение пользователя
            system_message = messages[0] if messages else None
            user_message = messages[-1] if len(messages) > 1 else None

            truncated_messages = []

            if system_message:
                truncated_messages.append(system_message)

            # Добавляем сообщения из истории начиная с конца
            # пока не превысим лимит
            current_tokens = self.estimate_tokens(
                system_message.get('content', '') if system_message else ''
            )

            for msg in reversed(messages[1:-1]):  # Пропускаем первое и последнее
                msg_tokens = self.estimate_tokens(msg.get('content', ''))

                if current_tokens + msg_tokens > max_context_tokens * 0.8:
                    break

                truncated_messages.insert(1, msg)
                current_tokens += msg_tokens

            # Добавляем последнее сообщение пользователя
            if user_message:
                truncated_messages.append(user_message)

            logger.info(
                f"Context truncated: {len(messages)} → {len(truncated_messages)} messages, "
                f"~{current_tokens} tokens"
            )

            return truncated_messages

        except Exception as e:
            logger.error(f"Error truncating context: {e}")
            return messages

    async def get_single_response(
            self,
            message: str,
            context: str,
            chat_history: List[Dict[str, Any]] = None,
            files_context: str = '',
            max_tokens: Optional[int] = None,
            temperature: float = 0.7,
            agent_prompt: str = None,
    ) -> str:
        """
        Получить полный ответ (не потоковый) от GPT

        Args:
            message: Сообщение пользователя
            context: Контекст
            chat_history: История чата
            files_context: Контекст из файлов
            max_tokens: Максимальное количество токенов
            temperature: float,
            agent_prompt: str,
        Returns:
            Полный ответ от GPT
        """
        try:
            # Собираем полный ответ из потока
            full_response = ""

            async for chunk in self.get_response_stream(
                    message,
                    context,
                    chat_history,
                    files_context,
                    max_tokens,
                    temperature,
                    agent_prompt,
            ):
                full_response += chunk

            return full_response

        except Exception as e:
            logger.error(f"Error in get_single_response: {e}")

            # Fallback на резервный ответ
            return self._get_fallback_response(
                message,
                context,
                bool(files_context)
            )

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
        if temperature is not None:
            self.generation_params['temperature'] = temperature
            logger.info(f"Temperature set to {temperature}")

        if presence_penalty is not None:
            self.generation_params['presence_penalty'] = presence_penalty
            logger.info(f"Presence penalty set to {presence_penalty}")

        if frequency_penalty is not None:
            self.generation_params['frequency_penalty'] = frequency_penalty
            logger.info(f"Frequency penalty set to {frequency_penalty}")

    def get_generation_params(self) -> dict:
        """
        Получение текущих параметров генерации

        Returns:
            Словарь с параметрами
        """
        return self.generation_params.copy()

    def create_system_message(self, tool_type: str) -> Dict[str, str]:
        """
        Создание системного сообщения для конкретного инструмента

        Args:
            tool_type: Тип инструмента

        Returns:
            Системное сообщение
        """
        system_prompt = get_system_prompt(tool_type)

        return {
            "role": "system",
            "content": system_prompt
        }


# Вспомогательные функции для быстрого доступа

async def get_ai_response(
        message: str,
        openai_client: AsyncOpenAI,
        tool_type: str = "default",
        chat_history: List[Dict[str, Any]] = None,
        files_context: str = ''
) -> str:
    """
    Быстрое получение ответа от GPT

    Args:
        message: Сообщение пользователя
        openai_client: Клиент OpenAI
        tool_type: Тип инструмента
        chat_history: История чата
        files_context: Контекст из файлов

    Returns:
        Ответ от GPT
    """
    handler = ResponseHandler(openai_client)
    context = {'tool_type': tool_type}

    return await handler.get_single_response(
        message,
        context,
        chat_history,
        files_context
    )


async def stream_ai_response(
        message: str,
        openai_client: AsyncOpenAI,
        tool_type: str = "default",
        chat_history: List[Dict[str, Any]] = None,
        files_context: str = ''
) -> AsyncIterator[str]:
    """
    Быстрое получение потокового ответа от GPT

    Args:
        message: Сообщение пользователя
        openai_client: Клиент OpenAI
        tool_type: Тип инструмента
        chat_history: История чата
        files_context: Контекст из файлов

    Yields:
        Части ответа
    """
    handler = ResponseHandler(openai_client)
    context = {'tool_type': tool_type}

    async for chunk in handler.get_response_stream(
            message,
            context,
            chat_history,
            files_context
    ):
        yield chunk