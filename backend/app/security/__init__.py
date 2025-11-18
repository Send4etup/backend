# app/security/__init__.py
"""
Модуль безопасности ТоварищБот
"""

from .cors_config import CORSConfig
from .csrf_protection import init_csrf_protection, get_csrf_error_response

__all__ = [
    'CORSConfig',
    'init_csrf_protection',
    'get_csrf_error_response'
]