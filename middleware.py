"""
Middleware для FastAPI приложения
"""

import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware для логирования запросов"""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.time()

        # Логируем входящий запрос
        logger.info(
            f"📥 {request.method} {request.url.path} - "
            f"Client: {request.client.host if request.client else 'unknown'}"
        )

        # Обрабатываем запрос
        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # Логируем ответ
            logger.info(
                f"📤 {request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Time: {process_time:.3f}s"
            )

            # Добавляем заголовок с временем обработки
            response.headers["X-Process-Time"] = str(process_time)

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"❌ {request.method} {request.url.path} - "
                f"Error: {str(e)} - "
                f"Time: {process_time:.3f}s"
            )
            raise

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Простой middleware для ограничения количества запросов"""

    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.clients = {}  # IP -> [(timestamp, count)]

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # Очищаем старые записи
        if client_ip in self.clients:
            self.clients[client_ip] = [
                (timestamp, count) for timestamp, count in self.clients[client_ip]
                if current_time - timestamp < self.period
            ]
        else:
            self.clients[client_ip] = []

        # Подсчитываем запросы за период
        total_requests = sum(count for _, count in self.clients[client_ip])

        if total_requests >= self.calls:
            logger.warning(f"🚫 Rate limit exceeded for {client_ip}")
            return Response(
                content='{"detail": "Превышен лимит запросов"}',
                status_code=429,
                media_type="application/json"
            )

        # Добавляем текущий запрос
        self.clients[client_ip].append((current_time, 1))

        response = await call_next(request)

        # Добавляем заголовки с информацией о лимитах
        response.headers["X-RateLimit-Limit"] = str(self.calls)
        response.headers["X-RateLimit-Remaining"] = str(self.calls - total_requests - 1)
        response.headers["X-RateLimit-Reset"] = str(int(current_time + self.period))

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware для добавления заголовков безопасности"""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        # Добавляем заголовки безопасности
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # CSP для API (довольно строгий)
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; "
            "script-src 'none'; "
            "style-src 'none'; "
            "img-src 'none'; "
            "font-src 'none'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )

        return response


def setup_middleware(app):
    """Настройка middleware для приложения"""

    # Добавляем middleware в обратном порядке
    # (последний добавленный выполняется первым)

    # Заголовки безопасности (выполняется последним)
    app.add_middleware(SecurityHeadersMiddleware)

    # Ограничение запросов
    app.add_middleware(RateLimitMiddleware, calls=100, period=60)

    # Логирование (выполняется первым)
    app.add_middleware(LoggingMiddleware)

    logger.info("✅ Middleware настроен успешно")