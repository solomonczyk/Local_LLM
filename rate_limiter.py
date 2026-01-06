"""
Simple rate limiting middleware for FastAPI
"""
import time
from collections import defaultdict, deque
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
import asyncio


class RateLimiter:
    def __init__(self, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

        # Хранилище запросов по IP
        self.minute_requests = defaultdict(deque)
        self.hour_requests = defaultdict(deque)

    def is_allowed(self, client_ip: str) -> tuple[bool, str]:
        """Проверяет, разрешен ли запрос от данного IP"""
        current_time = time.time()

        # Очищаем старые записи
        self._cleanup_old_requests(client_ip, current_time)

        # Проверяем лимиты
        minute_count = len(self.minute_requests[client_ip])
        hour_count = len(self.hour_requests[client_ip])

        if minute_count >= self.requests_per_minute:
            return False, f"Rate limit exceeded: {minute_count}/{self.requests_per_minute} requests per minute"

        if hour_count >= self.requests_per_hour:
            return False, f"Rate limit exceeded: {hour_count}/{self.requests_per_hour} requests per hour"

        # Добавляем текущий запрос
        self.minute_requests[client_ip].append(current_time)
        self.hour_requests[client_ip].append(current_time)

        return True, "OK"

    def _cleanup_old_requests(self, client_ip: str, current_time: float):
        """Удаляет старые записи запросов"""
        minute_ago = current_time - 60
        hour_ago = current_time - 3600

        # Очищаем минутные запросы
        while self.minute_requests[client_ip] and self.minute_requests[client_ip][0] < minute_ago:
            self.minute_requests[client_ip].popleft()

        # Очищаем часовые запросы
        while self.hour_requests[client_ip] and self.hour_requests[client_ip][0] < hour_ago:
            self.hour_requests[client_ip].popleft()


# Глобальный rate limiter
rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """Middleware для проверки rate limiting"""

    # Получаем IP клиента
    client_ip = request.client.host
    if not client_ip:
        client_ip = request.headers.get("X-Forwarded-For", "unknown")

    # Пропускаем health check endpoints
    if request.url.path in ["/health", "/", "/v1/health"]:
        response = await call_next(request)
        return response

    # Проверяем rate limit
    allowed, message = rate_limiter.is_allowed(client_ip)

    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded", "message": message, "retry_after": 60},
            headers={"Retry-After": "60"},
        )

    # Продолжаем обработку запроса
    response = await call_next(request)

    # Добавляем заголовки с информацией о лимитах
    remaining_minute = rate_limiter.requests_per_minute - len(rate_limiter.minute_requests[client_ip])
    remaining_hour = rate_limiter.requests_per_hour - len(rate_limiter.hour_requests[client_ip])

    response.headers["X-RateLimit-Limit-Minute"] = str(rate_limiter.requests_per_minute)
    response.headers["X-RateLimit-Remaining-Minute"] = str(max(0, remaining_minute))
    response.headers["X-RateLimit-Limit-Hour"] = str(rate_limiter.requests_per_hour)
    response.headers["X-RateLimit-Remaining-Hour"] = str(max(0, remaining_hour))

    return response
