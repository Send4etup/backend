import hashlib
import hmac
from urllib.parse import unquote
from typing import Dict, Optional
import logging
from datetime import datetime, timedelta
import jwt
from ..config import settings

logger = logging.getLogger(__name__)

class TelegramAuthService:
    """Сервис аутентификации через Telegram"""
    
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    
    def verify_telegram_auth(self, init_data: str) -> Optional[Dict]:
        """
        Проверка подлинности данных от Telegram Web App
        
        Args:
            init_data: строка с данными от Telegram
            
        Returns:
            Dict с данными пользователя или None если проверка не прошла
        """
        try:
            # Парсим данные
            data = {}
            for item in init_data.split('&'):
                if '=' in item:
                    key, value = item.split('=', 1)
                    data[unquote(key)] = unquote(value)
            
            # Извлекаем hash
            received_hash = data.pop('hash', None)
            if not received_hash:
                logger.warning("No hash found in init_data")
                return None
            
            # Создаем строку для проверки
            data_check_string = '\n'.join([f"{k}={v}" for k, v in sorted(data.items())])
            
            # Создаем секретный ключ
            secret_key = hmac.new(
                "WebAppData".encode(),
                self.bot_token.encode(),
                hashlib.sha256
            ).digest()
            
            # Вычисляем hash
            calculated_hash = hmac.new(
                secret_key,
                data_check_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Проверяем hash
            if calculated_hash != received_hash:
                logger.warning("Hash verification failed")
                return None
            
            # Проверяем время (данные действительны в течение 24 часов)
            auth_date = int(data.get('auth_date', 0))
            if auth_date == 0:
                logger.warning("No auth_date found")
                return None
                
            current_time = int(datetime.now().timestamp())
            if current_time - auth_date > 86400:  # 24 часа
                logger.warning("Auth data expired")
                return None
            
            # Извлекаем данные пользователя
            user_data = {}
            if 'user' in data:
                import json
                user_data = json.loads(data['user'])
            else:
                # Fallback для старого формата
                user_data = {
                    'id': int(data.get('id', 0)),
                    'first_name': data.get('first_name', ''),
                    'last_name': data.get('last_name', ''),
                    'username': data.get('username', ''),
                }
            
            logger.info(f"Telegram auth successful for user {user_data.get('id')}")
            return user_data
            
        except Exception as e:
            logger.error(f"Error verifying Telegram auth: {e}")
            return None
    
    def create_access_token(self, user_data: Dict) -> str:
        """
        Создание JWT токена для пользователя
        
        Args:
            user_data: данные пользователя
            
        Returns:
            JWT токен
        """
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode = {
            'user_id': user_data.get('id'),
            'telegram_id': user_data.get('id'),
            'first_name': user_data.get('first_name'),
            'username': user_data.get('username'),
            'exp': expire,
            'iat': datetime.utcnow(),
        }
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """
        Проверка JWT токена
        
        Args:
            token: JWT токен
            
        Returns:
            Данные пользователя или None
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.JWTError as e:
            logger.warning(f"JWT error: {e}")
            return None
    
    def create_simple_token(self, telegram_id: int) -> str:
        """
        Создание простого токена для тестирования
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            Простой токен
        """
        timestamp = int(datetime.now().timestamp())
        return f"simple_token_{telegram_id}_{timestamp}"
    
    def authenticate_user(self, init_data: Optional[str] = None, 
                         telegram_id: Optional[int] = None,
                         simple_auth: bool = False) -> tuple[Optional[str], Optional[Dict]]:
        """
        Основной метод аутентификации
        
        Args:
            init_data: данные от Telegram Web App
            telegram_id: ID пользователя для простой аутентификации
            simple_auth: использовать простую аутентификацию
            
        Returns:
            Кортеж (токен, данные пользователя)
        """
        try:
            if simple_auth and telegram_id:
                # Простая аутентификация для тестирования
                user_data = {
                    'id': telegram_id,
                    'first_name': 'Test User',
                    'username': f'test_user_{telegram_id}'
                }
                token = self.create_simple_token(telegram_id)
                return token, user_data
            
            elif init_data:
                # Полная аутентификация через Telegram
                user_data = self.verify_telegram_auth(init_data)
                if user_data:
                    token = self.create_access_token(user_data)
                    return token, user_data
            
            return None, None
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None, None


# Глобальный экземпляр сервиса
auth_service = TelegramAuthService()