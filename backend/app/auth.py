import jwt
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)

# Настройки JWT
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "NTNv7j0TuYARvmNMmWXo6fKvM4o6nv/aUi9ryX38ZH+L1bkrnD1ObOQ8JAUmHCBq7Iy7otZcyAagBLHVKvvYaIpmMuxmARQ97jUVG16Jkpkp1wXOPsrF9zwew6TpczyHkHgX5EuLg2MeBuiT/qJACs1J0apruOOJCg/gOtkjB4c")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 7  # 7 дней


class JWTManager:
    """Менеджер для работы с JWT токенами"""

    @staticmethod
    def create_access_token(user_data: Dict[str, Any]) -> str:
        """Создание JWT токена"""
        try:
            # Данные для токена
            payload = {
                "user_id": user_data["user_id"],
                "telegram_id": user_data["telegram_id"],
                "subscription_type": user_data.get("subscription_type", "free"),
                "iat": datetime.now(timezone.utc),  # issued at
                "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),  # expiration
                "iss": "tovarishbot",  # issuer
                "aud": "tovarishbot-users"  # audience
            }

            # Создаем токен
            token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

            logger.info(f"✅ JWT token created for user: {user_data['user_id']}")
            return token

        except Exception as e:
            logger.error(f"❌ Error creating JWT token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token creation failed"
            )

    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """Проверка и декодирование JWT токена"""
        try:
            # Декодируем токен
            payload = jwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=JWT_ALGORITHM,
                issuer="tovarishbot",
                audience="tovarishbot-users"
            )

            logger.info(f"✅ JWT token verified for user: {payload.get('user_id')}")
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("❌ JWT token expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"❌ Invalid JWT token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        except Exception as e:
            logger.error(f"❌ Token verification error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token verification failed"
            )

    @staticmethod
    def refresh_token(token: str) -> str:
        """Обновление токена (если до истечения осталось меньше 24 часов)"""
        try:
            payload = JWTManager.verify_token(token)

            # Проверяем, нужно ли обновлять токен
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                exp_time = datetime.fromtimestamp(exp_timestamp, timezone.utc)
                time_left = exp_time - datetime.now(timezone.utc)

                # Если до истечения меньше 24 часов, создаем новый токен
                if time_left.total_seconds() < 24 * 3600:
                    return JWTManager.create_access_token({
                        "user_id": payload["user_id"],
                        "telegram_id": payload["telegram_id"],
                        "subscription_type": payload.get("subscription_type", "free")
                    })

            # Токен еще действителен, возвращаем тот же
            return token

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Token refresh error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token refresh failed"
            )
