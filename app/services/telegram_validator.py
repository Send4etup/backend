# app/services/telegram_validator.py
"""
Безопасная валидация данных от Telegram WebApp
Реализует алгоритм HMAC-SHA256 согласно официальной документации Telegram
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from urllib.parse import parse_qs, unquote

logger = logging.getLogger(__name__)


class TelegramDataValidationError(Exception):
    """Исключение для ошибок валидации Telegram данных"""
    pass


class TelegramInitDataValidator:
    """
    Валидатор данных initData от Telegram WebApp

    Использует алгоритм HMAC-SHA256 для проверки подлинности данных:
    1. Парсит query string с initData
    2. Создает data_check_string из отсортированных пар key=value
    3. Генерирует secret_key = HMAC-SHA256("WebAppData", bot_token)
    4. Вычисляет подпись и сравнивает с полученным hash
    """

    def __init__(self, bot_token: str):
        """
        Инициализация валидатора

        Args:
            bot_token: Токен Telegram бота
        """
        if not bot_token:
            raise ValueError("Bot token is required")

        self.bot_token = bot_token
        self.max_auth_age_seconds = 3600  # 1 час максимальный возраст данных

        logger.info("Telegram validator initialized")

    def validate_init_data(self, init_data: str) -> Dict[str, Any]:
        """
        Валидация initData от Telegram WebApp

        Args:
            init_data: Строка с данными от window.Telegram.WebApp.initData

        Returns:
            Dict с проверенными данными пользователя

        Raises:
            TelegramDataValidationError: При любых ошибках валидации
        """
        try:
            logger.info("Starting Telegram initData validation")

            # 1. Базовые проверки
            if not init_data or not isinstance(init_data, str):
                raise TelegramDataValidationError("Empty or invalid initData")

            # 2. Парсим query string
            parsed_data = self._parse_init_data(init_data)

            # 3. Проверяем подпись HMAC-SHA256
            if not self._verify_signature(parsed_data, init_data):
                raise TelegramDataValidationError("Invalid HMAC signature")

            # 4. Проверяем временную метку
            self._verify_auth_date(parsed_data)

            # 5. Извлекаем и валидируем данные пользователя
            user_data = self._extract_user_data(parsed_data)

            logger.info(f"Successfully validated Telegram user: {user_data.get('id')}")

            return {
                'user': user_data,
                'auth_date': parsed_data.get('auth_date'),
                'query_id': parsed_data.get('query_id'),
                'chat_type': parsed_data.get('chat_type'),
                'chat_instance': parsed_data.get('chat_instance'),
                'start_param': parsed_data.get('start_param'),
            }

        except TelegramDataValidationError:
            # Перебрасываем наши исключения как есть
            raise
        except Exception as e:
            logger.error(f"Unexpected error during validation: {e}")
            raise TelegramDataValidationError(f"Validation failed: {str(e)}")

    def _parse_init_data(self, init_data: str) -> Dict[str, str]:
        """
        Парсинг query string с initData

        Args:
            init_data: Строка с данными

        Returns:
            Словарь с распарсенными данными
        """
        try:
            # Декодируем URL-encoded данные
            decoded_data = unquote(init_data)

            # Парсим как query string
            parsed = parse_qs(decoded_data, keep_blank_values=True)

            # Преобразуем в простой словарь (берем первое значение из списка)
            result = {}
            for key, values in parsed.items():
                if values:
                    result[key] = values[0]
                else:
                    result[key] = ''

            # Проверяем наличие обязательных полей
            if 'hash' not in result:
                raise TelegramDataValidationError("Missing hash field")

            if 'auth_date' not in result:
                raise TelegramDataValidationError("Missing auth_date field")

            logger.debug(f"Parsed initData fields: {list(result.keys())}")

            return result

        except Exception as e:
            logger.error(f"Failed to parse initData: {e}")
            raise TelegramDataValidationError(f"Invalid initData format: {str(e)}")

    def _verify_signature(self, parsed_data: Dict[str, str], original_init_data: str) -> bool:
        """
        Проверка HMAC-SHA256 подписи согласно алгоритму Telegram

        Args:
            parsed_data: Распарсенные данные
            original_init_data: Оригинальная строка initData

        Returns:
            True если подпись валидна
        """
        try:
            # 1. Извлекаем полученный hash
            received_hash = parsed_data.get('hash')
            if not received_hash:
                logger.error("No hash found in initData")
                return False

            # 2. Создаем data_check_string
            # Исключаем hash и сортируем по алфавиту
            data_pairs = []
            for key, value in parsed_data.items():
                if key != 'hash':
                    data_pairs.append(f"{key}={value}")

            # Сортируем по алфавиту
            data_pairs.sort()
            data_check_string = '\n'.join(data_pairs)

            logger.debug(f"Data check string created with {len(data_pairs)} pairs")

            # 3. Создаем secret_key = HMAC-SHA256("WebAppData", bot_token)
            secret_key = hmac.new(
                b"WebAppData",
                self.bot_token.encode('utf-8'),
                hashlib.sha256
            ).digest()

            # 4. Вычисляем подпись = HMAC-SHA256(data_check_string, secret_key)
            calculated_hash = hmac.new(
                secret_key,
                data_check_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            # 5. Безопасное сравнение хешей
            is_valid = hmac.compare_digest(received_hash, calculated_hash)

            if not is_valid:
                logger.warning("HMAC signature mismatch")
                logger.debug(f"Received: {received_hash}")
                logger.debug(f"Calculated: {calculated_hash}")

            return is_valid

        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False

    def _verify_auth_date(self, parsed_data: Dict[str, str]) -> None:
        """
        Проверка временной метки для защиты от replay-атак

        Args:
            parsed_data: Распарсенные данные

        Raises:
            TelegramDataValidationError: Если данные слишком старые
        """
        try:
            auth_date_str = parsed_data.get('auth_date')
            if not auth_date_str:
                raise TelegramDataValidationError("Missing auth_date")

            # Преобразуем timestamp в datetime
            auth_date_timestamp = int(auth_date_str)
            auth_date = datetime.fromtimestamp(auth_date_timestamp, tz=timezone.utc)
            current_time = datetime.now(timezone.utc)

            # Проверяем возраст данных
            age_seconds = (current_time - auth_date).total_seconds()

            if age_seconds > self.max_auth_age_seconds:
                raise TelegramDataValidationError(
                    f"InitData too old: {age_seconds:.0f}s > {self.max_auth_age_seconds}s"
                )

            if age_seconds < -60:  # Допускаем небольшое расхождение часов
                raise TelegramDataValidationError("InitData from future")

            logger.debug(f"Auth date verified: {age_seconds:.0f}s ago")

        except ValueError as e:
            raise TelegramDataValidationError(f"Invalid auth_date format: {e}")
        except TelegramDataValidationError:
            raise
        except Exception as e:
            raise TelegramDataValidationError(f"Auth date verification failed: {e}")

    def _extract_user_data(self, parsed_data: Dict[str, str]) -> Dict[str, Any]:
        """
        Извлечение и валидация данных пользователя

        Args:
            parsed_data: Распарсенные данные

        Returns:
            Словарь с данными пользователя

        Raises:
            TelegramDataValidationError: При ошибках парсинга пользователя
        """
        try:
            user_json = parsed_data.get('user')
            if not user_json:
                raise TelegramDataValidationError("Missing user data")

            # Парсим JSON с данными пользователя
            user_data = json.loads(user_json)

            # Проверяем обязательные поля
            required_fields = ['id']
            for field in required_fields:
                if field not in user_data:
                    raise TelegramDataValidationError(f"Missing user field: {field}")

            # Валидируем типы данных
            if not isinstance(user_data['id'], int):
                raise TelegramDataValidationError("Invalid user ID type")

            # Дополнительные проверки
            if user_data['id'] <= 0:
                raise TelegramDataValidationError("Invalid user ID value")

            logger.debug(f"Extracted user data for ID: {user_data['id']}")

            return user_data

        except json.JSONDecodeError as e:
            raise TelegramDataValidationError(f"Invalid user JSON: {e}")
        except TelegramDataValidationError:
            raise
        except Exception as e:
            raise TelegramDataValidationError(f"User data extraction failed: {e}")

    def create_test_init_data(self, user_data: Dict[str, Any]) -> str:
        """
        ТОЛЬКО ДЛЯ ТЕСТИРОВАНИЯ: Создание валидного initData
        НЕ ИСПОЛЬЗОВАТЬ В PRODUCTION!

        Args:
            user_data: Данные пользователя для тестирования

        Returns:
            Строка с валидным initData
        """
        if not user_data.get('id'):
            raise ValueError("User ID required for test data")

        # Создаем тестовые данные
        auth_date = int(datetime.now(timezone.utc).timestamp())
        query_id = "AAHdF6IQAAAAAN0XohDhrOrc"

        test_data = {
            'auth_date': str(auth_date),
            'query_id': query_id,
            'user': json.dumps(user_data, separators=(',', ':'))
        }

        # Создаем data_check_string
        data_pairs = []
        for key, value in sorted(test_data.items()):
            data_pairs.append(f"{key}={value}")

        data_check_string = '\n'.join(data_pairs)

        # Вычисляем подпись
        secret_key = hmac.new(
            b"WebAppData",
            self.bot_token.encode('utf-8'),
            hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Формируем финальную строку
        test_data['hash'] = calculated_hash

        # Создаем query string
        init_data_parts = []
        for key, value in test_data.items():
            init_data_parts.append(f"{key}={value}")

        return '&'.join(init_data_parts)


# Глобальный экземпляр валидатора (будет инициализирован при старте приложения)
_validator_instance: Optional[TelegramInitDataValidator] = None


def get_telegram_validator() -> TelegramInitDataValidator:
    """
    Получение глобального экземпляра валидатора

    Returns:
        Инициализированный валидатор

    Raises:
        RuntimeError: Если валидатор не инициализирован
    """
    global _validator_instance

    if _validator_instance is None:
        raise RuntimeError("Telegram validator not initialized. Call init_telegram_validator() first.")

    return _validator_instance


def init_telegram_validator(bot_token: str) -> None:
    """
    Инициализация глобального валидатора

    Args:
        bot_token: Токен Telegram бота
    """
    global _validator_instance

    if not bot_token:
        raise ValueError("Bot token is required for Telegram validator")

    _validator_instance = TelegramInitDataValidator(bot_token)
    logger.info("Telegram validator initialized globally")


def validate_telegram_init_data(init_data: str) -> Dict[str, Any]:
    """
    Удобная функция для валидации initData

    Args:
        init_data: Строка с данными от Telegram WebApp

    Returns:
        Проверенные данные пользователя

    Raises:
        TelegramDataValidationError: При ошибках валидации
    """
    validator = get_telegram_validator()
    return validator.validate_init_data(init_data)