# app/services/exam_service.py
"""
Сервис для работы с экзаменационной системой
Содержит всю бизнес-логику работы с экзаменами
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional, Tuple
from datetime import date, datetime, timedelta
import random

from app.models import (
    User, ExamSettings, ExamSubject, ExamTask,
    UserTaskAttempt, ExamProgress, ExamStats
)
from app.schemas import (
    ExamSettingsCreate, SubjectCreate, SubjectUpdate,
    TaskFilter, TaskAttemptCreate, SubjectStats
)


class ExamService:
    """Сервис для работы с экзаменами"""

    # =====================================================
    # EXAM SETTINGS
    # =====================================================

    @staticmethod
    def create_exam_settings(
            db: Session,
            user_id: str,
            data: ExamSettingsCreate
    ) -> ExamSettings:
        """
        Создание настроек экзамена с предметами

        Args:
            db: Сессия БД
            user_id: ID пользователя
            data: Данные для создания настроек

        Returns:
            ExamSettings: Созданные настройки экзамена
        """
        # Создаем настройки экзамена
        exam_settings = ExamSettings(
            user_id=user_id,
            exam_type=data.exam_type.value,
            exam_date=data.exam_date
        )
        db.add(exam_settings)
        db.flush()  # Получаем ID для связи с предметами

        # Создаем предметы
        for subject_data in data.subjects:
            subject = ExamSubject(
                exam_settings_id=exam_settings.id,
                subject_id=subject_data.subject_id,
                target_score=subject_data.target_score,
                current_score=0
            )
            db.add(subject)

        db.commit()
        db.refresh(exam_settings)
        return exam_settings

    @staticmethod
    def get_user_exam_settings(
            db: Session,
            user_id: str,
            exam_type: Optional[str] = None
    ) -> List[ExamSettings]:
        """
        Получение настроек экзаменов пользователя

        Args:
            db: Сессия БД
            user_id: ID пользователя
            exam_type: Фильтр по типу экзамена (опционально)

        Returns:
            List[ExamSettings]: Список настроек экзаменов
        """
        query = db.query(ExamSettings).filter(ExamSettings.user_id == user_id)

        if exam_type:
            query = query.filter(ExamSettings.exam_type == exam_type)

        return query.order_by(ExamSettings.created_at.desc()).all()

    @staticmethod
    def update_exam_settings(
            db: Session,
            settings_id: int,
            user_id: str,
            exam_date: Optional[date] = None
    ) -> Optional[ExamSettings]:
        """Обновление настроек экзамена"""
        settings = db.query(ExamSettings).filter(
            ExamSettings.id == settings_id,
            ExamSettings.user_id == user_id
        ).first()

        if not settings:
            return None

        if exam_date is not None:
            settings.exam_date = exam_date

        db.commit()
        db.refresh(settings)
        return settings

    @staticmethod
    def delete_exam_settings(
            db: Session,
            settings_id: int,
            user_id: str
    ) -> bool:
        """Удаление настроек экзамена"""
        settings = db.query(ExamSettings).filter(
            ExamSettings.id == settings_id,
            ExamSettings.user_id == user_id
        ).first()

        if not settings:
            return False

        db.delete(settings)
        db.commit()
        return True

    # =====================================================
    # SUBJECTS
    # =====================================================

    @staticmethod
    def add_subjects(
            db: Session,
            settings_id: int,
            user_id: str,
            subjects: List[SubjectCreate]
    ) -> List[ExamSubject]:
        """Добавление предметов к существующим настройкам"""
        # Проверяем что настройки принадлежат пользователю
        settings = db.query(ExamSettings).filter(
            ExamSettings.id == settings_id,
            ExamSettings.user_id == user_id
        ).first()

        if not settings:
            raise ValueError("Настройки экзамена не найдены")

        # Получаем уже существующие предметы
        existing_subjects = db.query(ExamSubject.subject_id).filter(
            ExamSubject.exam_settings_id == settings_id
        ).all()
        existing_ids = {s[0] for s in existing_subjects}

        # Добавляем только новые предметы
        new_subjects = []
        for subject_data in subjects:
            if subject_data.subject_id not in existing_ids:
                subject = ExamSubject(
                    exam_settings_id=settings_id,
                    subject_id=subject_data.subject_id,
                    target_score=subject_data.target_score,
                    current_score=0
                )
                db.add(subject)
                new_subjects.append(subject)

        db.commit()
        for subject in new_subjects:
            db.refresh(subject)

        return new_subjects

    @staticmethod
    def update_subject(
            db: Session,
            subject_id: int,
            user_id: str,
            data: SubjectUpdate
    ) -> Optional[ExamSubject]:
        """Обновление предмета"""
        subject = db.query(ExamSubject).join(ExamSettings).filter(
            ExamSubject.id == subject_id,
            ExamSettings.user_id == user_id
        ).first()

        if not subject:
            return None

        if data.target_score is not None:
            subject.target_score = data.target_score
        if data.current_score is not None:
            subject.current_score = data.current_score

        db.commit()
        db.refresh(subject)
        return subject

    # =====================================================
    # TASKS
    # =====================================================

    @staticmethod
    def get_random_task(
            db: Session,
            user_id: str,
            filter_data: TaskFilter
    ) -> Optional[ExamTask]:
        """
        Получение случайного задания с учетом фильтров

        Args:
            db: Сессия БД
            user_id: ID пользователя
            filter_data: Фильтры для заданий

        Returns:
            Optional[ExamTask]: Случайное задание или None
        """
        # Базовый запрос
        query = db.query(ExamTask).filter(
            ExamTask.subject_id == filter_data.subject_id,
            ExamTask.exam_type == filter_data.exam_type.value,
            ExamTask.is_active == True
        )

        # Фильтр по сложности
        if filter_data.difficulty:
            query = query.filter(ExamTask.difficulty == filter_data.difficulty.value)

        # Исключаем уже решенные задания
        if filter_data.exclude_solved:
            solved_task_ids = db.query(UserTaskAttempt.task_id).filter(
                UserTaskAttempt.user_id == user_id
            ).distinct().subquery()

            query = query.filter(~ExamTask.id.in_(solved_task_ids))

        # Получаем все подходящие задания
        tasks = query.all()

        if not tasks:
            return None

        # Возвращаем случайное задание
        return random.choice(tasks)

    @staticmethod
    def get_bulk_tasks(
            db: Session,
            user_id: str,
            filter_data: TaskFilter,
            count: int = 5
    ) -> Tuple[List[ExamTask], int]:
        """
        Получение пакета заданий

        Returns:
            Tuple[List[ExamTask], int]: (Список заданий, Общее количество доступных)
        """
        # Базовый запрос (аналогично get_random_task)
        query = db.query(ExamTask).filter(
            ExamTask.subject_id == filter_data.subject_id,
            ExamTask.exam_type == filter_data.exam_type.value,
            ExamTask.is_active == True
        )

        if filter_data.difficulty:
            query = query.filter(ExamTask.difficulty == filter_data.difficulty.value)

        if filter_data.exclude_solved:
            solved_task_ids = db.query(UserTaskAttempt.task_id).filter(
                UserTaskAttempt.user_id == user_id
            ).distinct().subquery()
            query = query.filter(~ExamTask.id.in_(solved_task_ids))

        # Получаем общее количество
        total_count = query.count()

        # Получаем случайные задания
        tasks = query.order_by(func.random()).limit(count).all()

        return tasks, total_count

    # =====================================================
    # ATTEMPTS
    # =====================================================

    @staticmethod
    def submit_answer(
            db: Session,
            user_id: str,
            attempt_data: TaskAttemptCreate
    ) -> Tuple[UserTaskAttempt, bool, int]:
        """
        Отправка ответа на задание с проверкой и обновлением статистики

        Args:
            db: Сессия БД
            user_id: ID пользователя
            attempt_data: Данные попытки

        Returns:
            Tuple[UserTaskAttempt, bool, int]: (Попытка, Правильно ли, Баллы)
        """
        # Получаем задание
        task = db.query(ExamTask).filter(ExamTask.id == attempt_data.task_id).first()
        if not task:
            raise ValueError("Задание не найдено")

        # Проверяем ответ (нормализуем для сравнения)
        user_answer_normalized = attempt_data.user_answer.strip().lower()
        correct_answer_normalized = task.correct_answer.strip().lower()
        is_correct = user_answer_normalized == correct_answer_normalized

        points_earned = task.points if is_correct else 0

        # Создаем запись попытки (с денормализацией для аналитики)
        attempt = UserTaskAttempt(
            user_id=user_id,
            task_id=task.id,
            user_answer=attempt_data.user_answer,
            is_correct=is_correct,
            subject_id=task.subject_id,
            exam_type=task.exam_type,
            difficulty=task.difficulty,
            time_spent=attempt_data.time_spent
        )
        db.add(attempt)

        # Обновляем статистику
        ExamService._update_user_stats(db, user_id, is_correct, points_earned)

        # Обновляем прогресс предмета
        ExamService._update_subject_progress(
            db, user_id, task.subject_id, task.exam_type, is_correct
        )

        # Обновляем ежедневный прогресс
        ExamService._update_daily_progress(db, user_id)

        db.commit()
        db.refresh(attempt)

        return attempt, is_correct, points_earned

    @staticmethod
    def _update_user_stats(
            db: Session,
            user_id: str,
            is_correct: bool,
            points: int
    ) -> None:
        """Обновление общей статистики пользователя"""
        stats = db.query(ExamStats).filter(ExamStats.user_id == user_id).first()

        if not stats:
            stats = ExamStats(user_id=user_id)
            db.add(stats)

        stats.tasks_solved += 1
        if is_correct:
            stats.tasks_correct += 1
            stats.total_points += points

        stats.last_updated = datetime.now()
        db.flush()

    @staticmethod
    def _update_subject_progress(
            db: Session,
            user_id: str,
            subject_id: str,
            exam_type: str,
            is_correct: bool
    ) -> None:
        """Обновление прогресса по предмету"""
        # Находим предмет пользователя
        subject = db.query(ExamSubject).join(ExamSettings).filter(
            ExamSettings.user_id == user_id,
            ExamSettings.exam_type == exam_type,
            ExamSubject.subject_id == subject_id
        ).first()

        if subject and is_correct:
            # Увеличиваем current_score (можно настроить логику)
            subject.current_score = min(100, subject.current_score + 1)
            db.flush()

    @staticmethod
    def _update_daily_progress(db: Session, user_id: str) -> None:
        """Обновление ежедневного прогресса"""
        today = date.today()

        progress = db.query(ExamProgress).filter(
            ExamProgress.user_id == user_id,
            ExamProgress.date == today
        ).first()

        if not progress:
            progress = ExamProgress(
                user_id=user_id,
                date=today,
                tasks_completed=0,
                is_completed=False
            )
            db.add(progress)

        progress.tasks_completed += 1

        # Дневная норма - 5 заданий
        if progress.tasks_completed >= 5:
            progress.is_completed = True

            # Обновляем серию дней
            ExamService._update_streak(db, user_id, today)

        db.flush()

    @staticmethod
    def _update_streak(db: Session, user_id: str, today: date) -> None:
        """Обновление серии дней"""
        stats = db.query(ExamStats).filter(ExamStats.user_id == user_id).first()
        if not stats:
            return

        # Проверяем был ли вчера прогресс
        yesterday = today - timedelta(days=1)
        yesterday_progress = db.query(ExamProgress).filter(
            ExamProgress.user_id == user_id,
            ExamProgress.date == yesterday,
            ExamProgress.is_completed == True
        ).first()

        if yesterday_progress:
            # Продолжаем серию
            stats.streak_days += 1
        else:
            # Начинаем новую серию
            stats.streak_days = 1

        # Обновляем лучшую серию
        if stats.streak_days > stats.best_streak:
            stats.best_streak = stats.streak_days

        db.flush()

    # =====================================================
    # STATISTICS
    # =====================================================

    @staticmethod
    def get_user_stats(db: Session, user_id: str) -> Optional[ExamStats]:
        """Получение статистики пользователя"""
        stats = db.query(ExamStats).filter(ExamStats.user_id == user_id).first()

        if not stats:
            # Создаем пустую статистику
            stats = ExamStats(user_id=user_id)
            db.add(stats)
            db.commit()
            db.refresh(stats)

        return stats

    @staticmethod
    def get_subject_stats(
            db: Session,
            user_id: str,
            subject_id: str
    ) -> SubjectStats:
        """Получение статистики по предмету"""
        # Все попытки по предмету
        attempts = db.query(UserTaskAttempt).filter(
            UserTaskAttempt.user_id == user_id,
            UserTaskAttempt.subject_id == subject_id
        ).all()

        if not attempts:
            return SubjectStats(subject_id=subject_id)

        total = len(attempts)
        correct = sum(1 for a in attempts if a.is_correct)
        accuracy = (correct / total * 100) if total > 0 else 0.0

        # Среднее время
        times = [a.time_spent for a in attempts if a.time_spent]
        avg_time = sum(times) / len(times) if times else None

        # По сложности
        easy_attempts = [a for a in attempts if a.difficulty == "easy"]
        medium_attempts = [a for a in attempts if a.difficulty == "medium"]
        hard_attempts = [a for a in attempts if a.difficulty == "hard"]

        def calc_accuracy(attempts_list):
            if not attempts_list:
                return 0.0
            correct = sum(1 for a in attempts_list if a.is_correct)
            return (correct / len(attempts_list) * 100)

        return SubjectStats(
            subject_id=subject_id,
            total_attempts=total,
            correct_attempts=correct,
            accuracy=round(accuracy, 2),
            average_time=round(avg_time, 2) if avg_time else None,
            easy_accuracy=round(calc_accuracy(easy_attempts), 2),
            medium_accuracy=round(calc_accuracy(medium_attempts), 2),
            hard_accuracy=round(calc_accuracy(hard_attempts), 2)
        )

    # =====================================================
    # PROGRESS
    # =====================================================

    @staticmethod
    def get_progress_period(
            db: Session,
            user_id: str,
            start_date: date,
            end_date: date
    ) -> List[ExamProgress]:
        """Получение прогресса за период"""
        return db.query(ExamProgress).filter(
            ExamProgress.user_id == user_id,
            ExamProgress.date >= start_date,
            ExamProgress.date <= end_date
        ).order_by(ExamProgress.date).all()

    @staticmethod
    def get_today_progress(db: Session, user_id: str) -> Optional[ExamProgress]:
        """Получение сегодняшнего прогресса"""
        today = date.today()
        return db.query(ExamProgress).filter(
            ExamProgress.user_id == user_id,
            ExamProgress.date == today
        ).first()