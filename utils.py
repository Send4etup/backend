"""
Утилиты для работы с данными и общие функции
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class MockDatabase:
    """Класс для работы с mock данными как с базой данных"""

    def __init__(self):
        self.data = self._load_initial_data()
        self.backup_data = None

    def _load_initial_data(self) -> Dict[str, Any]:
        """Загрузка начальных данных"""
        return {
            "current_user": {
                "id": 1,
                "telegram_id": 123456789,
                "name": "Иванов Иван",
                "role": "student",
                "current_points": 34,
                "total_points": 340,
                "streak_days": 156,
                "tasks_completed": 23,
                "subscription_type": "free",
                "tokens_used": 450,
                "tokens_limit": 1000,
                "school_name": "Школа №1499",
                "class_name": "11-А",
                "city": "Москва",
                "is_active": True,
                "is_premium": False,
                "created_at": "2024-01-01T10:00:00"
            },
            "users": [],  # Для хранения всех пользователей
            "sessions": {},  # Для хранения активных сессий
            "activity_log": []  # Для логирования активности
        }

    def create_backup(self):
        """Создание резервной копии данных"""
        self.backup_data = json.loads(json.dumps(self.data))
        logger.info("📦 Создана резервная копия данных")

    def restore_backup(self):
        """Восстановление из резервной копии"""
        if self.backup_data:
            self.data = json.loads(json.dumps(self.backup_data))
            logger.info("🔄 Данные восстановлены из резервной копии")
        else:
            logger.warning("⚠️ Резервная копия не найдена")

    def reset_to_initial(self):
        """Сброс к начальным данным"""
        self.data = self._load_initial_data()
        logger.info("🔄 Данные сброшены к начальному состоянию")

    def log_activity(self, user_id: int, action: str, details: Dict[str, Any] = None):
        """Логирование активности пользователя"""
        activity_record = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "action": action,
            "details": details or {}
        }

        self.data["activity_log"].append(activity_record)

        # Ограничиваем размер лога
        if len(self.data["activity_log"]) > 1000:
            self.data["activity_log"] = self.data["activity_log"][-500:]

        logger.info(f"📝 Активность: {action} от пользователя {user_id}")


def generate_mock_token(telegram_id: int, expires_in: int = 86400) -> str:
    """Генерация mock токена"""
    timestamp = datetime.now().timestamp()
    expire_time = timestamp + expires_in

    # Создаем "подпись" токена
    data = f"{telegram_id}:{expire_time}"
    signature = hashlib.md5(data.encode()).hexdigest()[:8]

    return f"mock_token_{telegram_id}_{int(expire_time)}_{signature}"


def validate_mock_token(token: str) -> Optional[Dict[str, Any]]:
    """Валидация mock токена"""
    try:
        if not token.startswith("mock_token_"):
            return None

        parts = token.split("_")
        if len(parts) != 4:
            return None

        telegram_id = int(parts[2])
        expire_time = int(parts[3])
        signature = parts[4] if len(parts) > 4 else ""

        # Проверяем срок действия
        if datetime.now().timestamp() > expire_time:
            return None

        # Проверяем подпись (упрощенная проверка)
        expected_data = f"{telegram_id}:{expire_time}"
        expected_signature = hashlib.md5(expected_data.encode()).hexdigest()[:8]

        if signature != expected_signature:
            return None

        return {
            "telegram_id": telegram_id,
            "expires_at": expire_time,
            "valid": True
        }

    except (ValueError, IndexError):
        return None


def format_datetime(dt: datetime, format_type: str = "default") -> str:
    """Форматирование даты и времени"""
    formats = {
        "default": "%Y-%m-%d %H:%M:%S",
        "date_only": "%Y-%m-%d",
        "time_only": "%H:%M:%S",
        "russian": "%d.%m.%Y %H:%M",
        "iso": "%Y-%m-%dT%H:%M:%S"
    }

    return dt.strftime(formats.get(format_type, formats["default"]))


def calculate_user_level(points: int) -> Dict[str, Any]:
    """Расчет уровня пользователя на основе очков"""
    # Уровни: 0-100, 100-300, 300-600, 600-1000, 1000-1500, 1500+
    levels = [
        {"level": 1, "min_points": 0, "max_points": 100, "title": "Новичок"},
        {"level": 2, "min_points": 100, "max_points": 300, "title": "Ученик"},
        {"level": 3, "min_points": 300, "max_points": 600, "title": "Знаток"},
        {"level": 4, "min_points": 600, "max_points": 1000, "title": "Эксперт"},
        {"level": 5, "min_points": 1000, "max_points": 1500, "title": "Мастер"},
        {"level": 6, "min_points": 1500, "max_points": float('inf'), "title": "Гуру"}
    ]

    for level_info in levels:
        if level_info["min_points"] <= points < level_info["max_points"]:
            progress = 0
            if level_info["max_points"] != float('inf'):
                progress = ((points - level_info["min_points"]) /
                            (level_info["max_points"] - level_info["min_points"])) * 100

            return {
                "current_level": level_info["level"],
                "level_title": level_info["title"],
                "points_in_level": points - level_info["min_points"],
                "points_to_next": (level_info["max_points"] - points
                                   if level_info["max_points"] != float('inf') else 0),
                "progress_percent": round(progress, 1),
                "total_points": points
            }

    return {
        "current_level": 1,
        "level_title": "Новичок",
        "points_in_level": points,
        "points_to_next": 100 - points,
        "progress_percent": points,
        "total_points": points
    }


def filter_tasks_by_criteria(
        tasks: List[Dict[str, Any]],
        subject: Optional[str] = None,
        difficulty: Optional[str] = None,
        deadline_days: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Фильтрация задач по различным критериям"""
    filtered_tasks = tasks.copy()

    # Фильтр по предмету
    if subject:
        filtered_tasks = [
            task for task in filtered_tasks
            if task.get("subject", "").lower() == subject.lower()
        ]

    # Фильтр по сложности
    if difficulty:
        filtered_tasks = [
            task for task in filtered_tasks
            if task.get("difficulty", "").lower() == difficulty.lower()
        ]

    # Фильтр по дедлайну (задачи, которые нужно сдать в ближайшие N дней)
    if deadline_days is not None:
        current_time = datetime.now()
        future_time = current_time + timedelta(days=deadline_days)

        filtered_tasks = [
            task for task in filtered_tasks
            if task.get("deadline") and
               datetime.fromisoformat(task["deadline"].replace("Z", "+00:00")) <= future_time
        ]

    return filtered_tasks


def calculate_statistics(data: Dict[str, Any]) -> Dict[str, Any]:
    """Расчет различной статистики"""
    stats = {
        "users": {
            "total": 1,  # Только текущий пользователь в mock данных
            "active": 1,
            "premium": 0
        },
        "tasks": {
            "total": 0,
            "completed": 0,
            "active": 0,
            "completion_rate": 0
        },
        "subjects": {},
        "difficulty_distribution": {},
        "ideas": {
            "total": 0,
            "new": 0,
            "considering": 0,
            "planned": 0
        }
    }

    # Статистика по задачам
    if "tasks" in data:
        active_tasks = data["tasks"].get("active", [])
        completed_tasks = data["tasks"].get("completed", [])

        stats["tasks"]["active"] = len(active_tasks)
        stats["tasks"]["completed"] = len(completed_tasks)
        stats["tasks"]["total"] = stats["tasks"]["active"] + stats["tasks"]["completed"]

        if stats["tasks"]["total"] > 0:
            stats["tasks"]["completion_rate"] = round(
                (stats["tasks"]["completed"] / stats["tasks"]["total"]) * 100, 2
            )

        # Статистика по предметам
        all_tasks = active_tasks + completed_tasks
        for task in all_tasks:
            subject = task.get("subject", "unknown")
            if subject not in stats["subjects"]:
                stats["subjects"][subject] = {"total": 0, "completed": 0}

            stats["subjects"][subject]["total"] += 1
            if task in completed_tasks:
                stats["subjects"][subject]["completed"] += 1

        # Статистика по сложности
        for task in all_tasks:
            difficulty = task.get("difficulty", "unknown")
            stats["difficulty_distribution"][difficulty] = \
                stats["difficulty_distribution"].get(difficulty, 0) + 1

    # Статистика по идеям
    if "ideas" in data:
        ideas = data["ideas"]
        stats["ideas"]["total"] = len(ideas)

        for idea in ideas:
            status = idea.get("status", "new")
            if status in stats["ideas"]:
                stats["ideas"][status] += 1

    return stats


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """Очистка и валидация пользовательского ввода"""
    if not text:
        return ""

    # Удаляем потенциально опасные символы
    sanitized = text.strip()

    # Ограничиваем длину
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    # Удаляем множественные пробелы
    sanitized = " ".join(sanitized.split())

    return sanitized


# Глобальный экземпляр mock базы данных
mock_db = MockDatabase()