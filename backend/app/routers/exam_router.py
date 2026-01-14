# app/routers/exam_router.py
"""
API endpoints для экзаменационной системы
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, timedelta, datetime
import json

from app.logging import setup_logging
from app.database import get_db
from app.services.exam_service import ExamService
from app.schemas import (
    # Settings
    ExamSettingsCreate, ExamSettingsUpdate, ExamSettingsResponse,
    # Subjects
    SubjectCreate, SubjectUpdate, SubjectResponse, AvailableSubjects,
    # Tasks
    TaskFilter, TaskResponse, BulkTasksRequest, BulkTasksResponse,
    # Attempts
    TaskAttemptCreate, TaskAttemptResponse,
    # Stats
    ExamStatsResponse, SubjectStats,
    # Progress
    DailyProgress, ProgressCalendar,
    # Enums
    ExamType, Difficulty,

    QualityAnalytics,
    DifficultyQuality,
    SubjectQuality,
    TaskHistoryFilter,
    TaskHistoryResponse,
    TaskAttemptHistory,
    IncorrectTasksSummary,
)

from app.models import ExamSettings, ExamSubject, ExamTask, UserTaskAttempt


router = APIRouter(prefix="/exam", tags=["Экзамены"])

logger = setup_logging()


# =====================================================
# EXAM SETTINGS
# =====================================================

@router.post("/settings", response_model=ExamSettingsResponse, status_code=status.HTTP_201_CREATED)
async def create_exam_settings(
        data: ExamSettingsCreate,
        user_id: str = Query(..., description="ID пользователя"),
        db: Session = Depends(get_db)
):
    """
    Создание настроек экзамена

    - **exam_type**: Тип экзамена (ОГЭ или ЕГЭ)
    - **exam_date**: Дата экзамена (опционально)
    - **subjects**: Список предметов для сдачи (минимум 1)
    """
    try:
        settings = ExamService.create_exam_settings(db, user_id, data)
        return settings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка создания настроек: {str(e)}"
        )


@router.get("/settings", response_model=List[ExamSettingsResponse])
async def get_exam_settings(
        user_id: str = Query(..., description="ID пользователя"),
        exam_type: Optional[ExamType] = Query(None, description="Фильтр по типу экзамена"),
        db: Session = Depends(get_db)
):
    """
    Получение всех настроек экзаменов пользователя

    Можно фильтровать по типу экзамена (ОГЭ или ЕГЭ)
    """
    settings = ExamService.get_user_exam_settings(
        db, user_id, exam_type.value if exam_type else None
    )
    return settings


@router.get("/settings/{settings_id}", response_model=ExamSettingsResponse)
async def get_exam_settings_by_id(
        settings_id: int,
        user_id: str = Query(..., description="ID пользователя"),
        db: Session = Depends(get_db)
):
    """Получение конкретных настроек экзамена по ID"""
    settings = db.query(ExamSettings).filter(
        ExamSettings.id == settings_id,
        ExamSettings.user_id == user_id
    ).first()

    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Настройки экзамена не найдены"
        )

    return settings


@router.patch("/settings/{settings_id}", response_model=ExamSettingsResponse)
async def update_exam_settings(
        settings_id: int,
        data: ExamSettingsUpdate,
        user_id: str = Query(..., description="ID пользователя"),
        db: Session = Depends(get_db)
):
    """
    Полное обновление настроек экзамена

    Позволяет обновить:
    - Дату экзамена (exam_date)
    - Список предметов и их целевые баллы (subjects)
    """
    try:
        logger.info(f"📝 Updating exam settings {settings_id} for user {user_id}")
        logger.info(f"Data: exam_date={data.exam_date}, subjects={data.subjects}")

        # Преобразуем subjects в список словарей, если они есть
        subjects_data = None
        if data.subjects is not None:
            subjects_data = [
                {
                    "subject_id": subject.subject_id,
                    "target_score": subject.target_score
                }
                for subject in data.subjects
            ]

        # Обновляем настройки через сервис
        settings = ExamService.update_exam_settings_full(
            db=db,
            settings_id=settings_id,
            user_id=user_id,
            exam_date=data.exam_date,
            subjects=subjects_data
        )

        if not settings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Настройки экзамена не найдены или у вас нет доступа"
            )

        logger.info(f"✅ ExamSettings {settings_id} updated successfully")
        return settings

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating exam settings {settings_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении настроек экзамена: {str(e)}"
        )


@router.delete("/settings/{settings_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam_settings(
        settings_id: int,
        user_id: str = Query(..., description="ID пользователя"),
        db: Session = Depends(get_db)
):
    """Удаление настроек экзамена"""
    success = ExamService.delete_exam_settings(db, settings_id, user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Настройки экзамена не найдены"
        )


# =====================================================
# SUBJECTS
# =====================================================

@router.post("/settings/{settings_id}/subjects", response_model=List[SubjectResponse])
async def add_subjects(
        settings_id: int,
        subjects: List[SubjectCreate],
        user_id: str = Query(..., description="ID пользователя"),
        db: Session = Depends(get_db)
):
    """
    Добавление предметов к существующим настройкам экзамена

    Дубликаты будут автоматически пропущены
    """
    try:
        new_subjects = ExamService.add_subjects(db, settings_id, user_id, subjects)
        return new_subjects
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.patch("/subjects/{subject_id}", response_model=SubjectResponse)
async def update_subject(
        subject_id: int,
        data: SubjectUpdate,
        user_id: str = Query(..., description="ID пользователя"),
        db: Session = Depends(get_db)
):
    """
    Обновление предмета (целевой балл или текущий балл)
    """
    subject = ExamService.update_subject(db, subject_id, user_id, data)

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Предмет не найден"
        )

    return subject


# =====================================================
# TASKS
# =====================================================

@router.get("/task", response_model=TaskResponse)
async def get_random_task(
        subject_id: str = Query(..., description="ID предмета"),
        exam_type: ExamType = Query(..., description="Тип экзамена"),
        difficulty: Optional[Difficulty] = Query(None, description="Сложность задания"),
        exclude_solved: bool = Query(True, description="Исключить уже решенные"),
        user_id: str = Query(..., description="ID пользователя"),
        db: Session = Depends(get_db)
):
    """
    Получение случайного задания

    - **subject_id**: Предмет (математика, русский язык, и т.д.)
    - **exam_type**: ОГЭ или ЕГЭ
    - **difficulty**: easy, medium, hard (опционально)
    - **exclude_solved**: Исключить уже решенные задания (по умолчанию true)
    """
    filter_data = TaskFilter(
        subject_id=subject_id,
        exam_type=exam_type,
        difficulty=difficulty,
        exclude_solved=exclude_solved
    )

    task = ExamService.get_random_task(db, user_id, filter_data)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Нет доступных заданий с указанными параметрами"
        )

    task_dict = {
        "id": task.id,
        "subject_id": task.subject_id,
        "exam_type": task.exam_type,
        "task_number": task.task_number,
        "difficulty": task.difficulty,
        "question_text": task.question_text,
        "answer_type": task.answer_type,
        "answer_options": json.loads(task.answer_options) if task.answer_options else None,
        "correct_answer": task.correct_answer,
        "explanation": task.explanation,
        "points": task.points,
        "estimated_time": task.estimated_time
    }

    return task_dict


@router.post("/tasks/bulk", response_model=BulkTasksResponse)
async def get_bulk_tasks(
        data: BulkTasksRequest,
        user_id: str = Query(..., description="ID пользователя"),
        db: Session = Depends(get_db)
):
    """
    Получение пакета заданий

    Возвращает несколько случайных заданий за раз (до 20 штук)
    """
    filter_data = TaskFilter(
        subject_id=data.subject_id,
        exam_type=data.exam_type,
        difficulty=data.difficulty,
        exclude_solved=data.exclude_solved
    )

    tasks, total_available = ExamService.get_bulk_tasks(
        db, user_id, filter_data, data.count
    )

    return BulkTasksResponse(
        tasks=tasks,
        total_available=total_available,
        has_more=total_available > len(tasks)
    )


# =====================================================
# ATTEMPTS
# =====================================================

@router.post("/answer", response_model=TaskAttemptResponse)
async def submit_answer(
        data: TaskAttemptCreate,
        user_id: str = Query(..., description="ID пользователя"),
        db: Session = Depends(get_db)
):
    """
    Отправка ответа на задание

    Система автоматически проверит ответ, обновит статистику и прогресс

    - **task_id**: ID задания
    - **user_answer**: Ответ пользователя
    - **time_spent**: Время на задание в секундах (опционально)
    """
    try:
        attempt, is_correct, points = ExamService.submit_answer(db, user_id, data)

        task = db.query(ExamTask).filter(ExamTask.id == data.task_id).first()

        task_dict = {
            "id": task.id,
            "subject_id": task.subject_id,
            "exam_type": task.exam_type,
            "task_number": task.task_number,
            "difficulty": task.difficulty,
            "question_text": task.question_text,
            "answer_type": task.answer_type,
            "answer_options": json.loads(task.answer_options) if task.answer_options else None,
            "correct_answer": task.correct_answer,
            "explanation": task.explanation,
            "points": task.points,
            "estimated_time": task.estimated_time
        }

        return {
            "id": attempt.id,
            "task_id": attempt.task_id,
            "user_answer": attempt.user_answer,
            "is_correct": is_correct,
            "points_earned": points,
            "time_spent": attempt.time_spent,
            "attempted_at": attempt.attempted_at,
            "task": task_dict
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


# =====================================================
# STATISTICS
# =====================================================

@router.get("/stats", response_model=ExamStatsResponse)
async def get_user_stats(
        user_id: str = Query(..., description="ID пользователя"),
        db: Session = Depends(get_db)
):
    """
    Получение общей статистики пользователя

    Включает:
    - Общее количество решенных заданий
    - Точность ответов
    - Серия дней подряд
    - Статистика по каждому предмету
    """
    stats = ExamService.get_user_stats(db, user_id)

    # Получаем список предметов пользователя
    subjects = db.query(ExamSubject).join(ExamSettings).filter(
        ExamSettings.user_id == user_id
    ).all()

    # Собираем статистику по каждому предмету
    subject_stats = []
    for subject in subjects:
        subject_stat = ExamService.get_subject_stats(db, user_id, subject.subject_id)
        subject_stats.append(subject_stat)

    return {
        "user_id": user_id,
        "total_points": stats.total_points,
        "tasks_solved": stats.tasks_solved,
        "tasks_correct": stats.tasks_correct,
        "accuracy_percentage": stats.accuracy_percentage,
        "streak_days": stats.streak_days,
        "best_streak": stats.best_streak,
        "last_updated": stats.last_updated,
        "subjects": subject_stats
    }


@router.get("/stats/subject/{subject_id}", response_model=SubjectStats)
async def get_subject_stats(
        subject_id: str,
        user_id: str = Query(..., description="ID пользователя"),
        db: Session = Depends(get_db)
):
    """
    Получение статистики по конкретному предмету

    Включает:
    - Общее количество попыток
    - Точность ответов
    - Среднее время на задание
    - Точность по каждой сложности (easy, medium, hard)
    """
    return ExamService.get_subject_stats(db, user_id, subject_id)


# =====================================================
# PROGRESS
# =====================================================

@router.get("/progress/today", response_model=Optional[DailyProgress])
async def get_today_progress(
        user_id: str = Query(..., description="ID пользователя"),
        db: Session = Depends(get_db)
):
    """Получение прогресса за сегодня"""
    progress = ExamService.get_today_progress(db, user_id)

    if not progress:
        # Возвращаем пустой прогресс
        return DailyProgress(
            date=date.today(),
            is_completed=False,
            tasks_completed=0,
            target_tasks=5,
            completion_percentage=0
        )

    return DailyProgress(
        date=progress.date,
        is_completed=progress.is_completed,
        tasks_completed=progress.tasks_completed,
        target_tasks=5,
        completion_percentage=min(100, int(progress.tasks_completed / 5 * 100))
    )


@router.get("/progress/calendar", response_model=ProgressCalendar)
async def get_progress_calendar(
        user_id: str = Query(..., description="ID пользователя"),
        days: int = Query(7, ge=1, le=90, description="Количество дней назад"),
        db: Session = Depends(get_db)
):
    """
    Получение календаря прогресса

    - **days**: Количество дней назад (по умолчанию 7)

    Возвращает прогресс за последние N дней
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    progress_list = ExamService.get_progress_period(db, user_id, start_date, end_date)

    # Формируем список дней (заполняем пропуски)
    days_data = []
    progress_dict = {p.date: p for p in progress_list}

    current_date = start_date
    while current_date <= end_date:
        progress = progress_dict.get(current_date)

        if progress:
            days_data.append(DailyProgress(
                date=progress.date,
                is_completed=progress.is_completed,
                tasks_completed=progress.tasks_completed,
                target_tasks=5,
                completion_percentage=min(100, int(progress.tasks_completed / 5 * 100))
            ))
        else:
            days_data.append(DailyProgress(
                date=current_date,
                is_completed=False,
                tasks_completed=0,
                target_tasks=5,
                completion_percentage=0
            ))

        current_date += timedelta(days=1)

    completed_days = sum(1 for d in days_data if d.is_completed)

    return ProgressCalendar(
        user_id=user_id,
        period_start=start_date,
        period_end=end_date,
        days=days_data,
        total_days=len(days_data),
        completed_days=completed_days,
        completion_rate=round(completed_days / len(days_data) * 100, 2) if days_data else 0
    )


# =====================================================
# УТИЛИТЫ ДЛЯ ФОРМАТИРОВАНИЯ НАЗВАНИЙ
# =====================================================

def get_subject_name(subject_id: str) -> str:
    """
    Получить русское название предмета по ID
    """
    subject_names = {
        'russian': 'Русский язык',
        'mathematics': 'Математика',
        'mathematics_base': 'Математика (база)',
        'mathematics_profile': 'Математика (профиль)',
        'physics': 'Физика',
        'chemistry': 'Химия',
        'biology': 'Биология',
        'informatics': 'Информатика',
        'history': 'История',
        'social_studies': 'Обществознание',
        'geography': 'География',
        'literature': 'Литература',
        'english': 'Английский язык',
        'german': 'Немецкий язык',
        'french': 'Французский язык',
        'spanish': 'Испанский язык',
        'chinese': 'Китайский язык'
    }
    return subject_names.get(subject_id, subject_id)


def generate_recommendations(quality_data: dict) -> List[str]:
    """
    Генерация рекомендаций на основе данных о качестве
    """
    recommendations = []

    # Анализ по сложности
    if quality_data.get('hard_accuracy', 0) < 50:
        recommendations.append("💪 Больше времени уделяйте сложным заданиям - практика повысит вашу точность")

    if quality_data.get('easy_accuracy', 0) < 70:
        recommendations.append("📚 Повторите базовые темы - это фундамент для более сложных заданий")

    if quality_data.get('medium_accuracy', 0) < 60:
        recommendations.append("🎯 Сосредоточьтесь на заданиях среднего уровня - они составляют основу экзамена")

    # Анализ по времени
    if quality_data.get('average_time', 0) > 180:
        recommendations.append("⏱️ Работайте над скоростью решения - тренируйтесь с таймером")

    # Общая точность
    if quality_data.get('overall_accuracy', 0) < 60:
        recommendations.append("📖 Уделите внимание теоретической подготовке перед практикой")
    elif quality_data.get('overall_accuracy', 0) > 80:
        recommendations.append("🌟 Отличная работа! Продолжайте поддерживать высокий уровень")

    # Если нет рекомендаций
    if not recommendations:
        recommendations.append("✨ Продолжайте регулярную практику для стабильных результатов")

    return recommendations


# =====================================================
# КАЧЕСТВО ОБУЧЕНИЯ
# =====================================================

@router.get("/quality/analytics", response_model=QualityAnalytics)
async def get_quality_analytics(
        user_id: str = Query(..., description="ID пользователя"),
        exam_type: Optional[str] = Query(None, description="Фильтр по типу экзамена (ОГЭ/ЕГЭ)"),
        subject_id: Optional[str] = Query(None, description="Фильтр по конкретному предмету"),
        db: Session = Depends(get_db)
):
    """
    Получение аналитики качества обучения пользователя

    Включает:
    - Общую точность ответов
    - Статистику по уровням сложности (easy/medium/hard)
    - Статистику по предметам
    - Слабые места и рекомендации

    **Параметры:**
    - user_id: ID пользователя
    - exam_type: Опциональный фильтр по типу экзамена
    - subject_id: Опциональный фильтр по предмету
    """

    # Базовый запрос
    base_query = db.query(UserTaskAttempt).filter(
        UserTaskAttempt.user_id == user_id
    )

    # Применяем фильтры
    if exam_type:
        base_query = base_query.filter(UserTaskAttempt.exam_type == exam_type)

    if subject_id:
        base_query = base_query.filter(UserTaskAttempt.subject_id == subject_id)

    all_attempts = base_query.all()

    # Если нет данных
    if not all_attempts:
        return QualityAnalytics(
            user_id=user_id,
            exam_type=exam_type or "Не указан",
            total_attempts=0,
            correct_attempts=0,
            overall_accuracy=0.0,
            difficulties=[],
            subjects=[],
            weak_areas=[],
            recommendations=["Начните решать задания, чтобы увидеть аналитику"]
        )

    # Общая статистика
    total_attempts = len(all_attempts)
    correct_attempts = sum(1 for a in all_attempts if a.is_correct)
    overall_accuracy = round((correct_attempts / total_attempts) * 100, 2) if total_attempts > 0 else 0.0

    # ============================================
    # СТАТИСТИКА ПО СЛОЖНОСТИ
    # ============================================
    difficulties_data = []

    for diff in ['easy', 'medium', 'hard']:
        diff_attempts = [a for a in all_attempts if a.difficulty == diff]

        if diff_attempts:
            diff_correct = sum(1 for a in diff_attempts if a.is_correct)
            diff_accuracy = round((diff_correct / len(diff_attempts)) * 100, 2)

            # Среднее время (если указано)
            times = [a.time_spent for a in diff_attempts if a.time_spent]
            avg_time = round(sum(times) / len(times), 2) if times else None

            difficulties_data.append(DifficultyQuality(
                difficulty=diff,
                total_attempts=len(diff_attempts),
                correct_attempts=diff_correct,
                accuracy=diff_accuracy,
                average_time=avg_time
            ))

    # ============================================
    # СТАТИСТИКА ПО ПРЕДМЕТАМ
    # ============================================
    subjects_data = []
    weak_areas = []

    # Группируем по предметам
    subjects_dict = {}
    for attempt in all_attempts:
        subj_id = attempt.subject_id
        if subj_id not in subjects_dict:
            subjects_dict[subj_id] = []
        subjects_dict[subj_id].append(attempt)

    for subj_id, attempts in subjects_dict.items():
        total = len(attempts)
        correct = sum(1 for a in attempts if a.is_correct)
        accuracy = round((correct / total) * 100, 2) if total > 0 else 0.0

        # Среднее время
        times = [a.time_spent for a in attempts if a.time_spent]
        avg_time = round(sum(times) / len(times), 2) if times else None

        # Точность по сложности
        easy_acc = 0.0
        medium_acc = 0.0
        hard_acc = 0.0

        for diff in ['easy', 'medium', 'hard']:
            diff_attempts = [a for a in attempts if a.difficulty == diff]
            if diff_attempts:
                diff_correct = sum(1 for a in diff_attempts if a.is_correct)
                acc = round((diff_correct / len(diff_attempts)) * 100, 2)

                if diff == 'easy':
                    easy_acc = acc
                elif diff == 'medium':
                    medium_acc = acc
                elif diff == 'hard':
                    hard_acc = acc

        subjects_data.append(SubjectQuality(
            subject_id=subj_id,
            subject_name=get_subject_name(subj_id),
            total_attempts=total,
            correct_attempts=correct,
            accuracy=accuracy,
            average_time=avg_time,
            easy_accuracy=easy_acc,
            medium_accuracy=medium_acc,
            hard_accuracy=hard_acc
        ))

        # Определяем слабые места (точность < 60%)
        if accuracy < 60:
            weak_areas.append(get_subject_name(subj_id))

    # ============================================
    # РЕКОМЕНДАЦИИ
    # ============================================
    quality_data = {
        'overall_accuracy': overall_accuracy,
        'easy_accuracy': next((d.accuracy for d in difficulties_data if d.difficulty == 'easy'), 0),
        'medium_accuracy': next((d.accuracy for d in difficulties_data if d.difficulty == 'medium'), 0),
        'hard_accuracy': next((d.accuracy for d in difficulties_data if d.difficulty == 'hard'), 0),
        'average_time': sum(a.time_spent for a in all_attempts if a.time_spent) / len(
            [a for a in all_attempts if a.time_spent]) if [a for a in all_attempts if a.time_spent] else 0
    }

    recommendations = generate_recommendations(quality_data)

    return QualityAnalytics(
        user_id=user_id,
        exam_type=exam_type or "Все экзамены",
        total_attempts=total_attempts,
        correct_attempts=correct_attempts,
        overall_accuracy=overall_accuracy,
        difficulties=difficulties_data,
        subjects=subjects_data,
        weak_areas=weak_areas,
        recommendations=recommendations
    )


# =====================================================
# ИСТОРИЯ ЗАДАНИЙ
# =====================================================

@router.get("/history/tasks", response_model=TaskHistoryResponse)
async def get_task_history(
        user_id: str = Query(..., description="ID пользователя"),
        exam_type: Optional[str] = Query(None, description="Фильтр по типу экзамена"),
        subject_id: Optional[str] = Query(None, description="Фильтр по предмету"),
        difficulty: Optional[str] = Query(None, description="Фильтр по сложности"),
        is_correct: Optional[bool] = Query(None, description="Фильтр по правильности"),
        date_from: Optional[datetime] = Query(None, description="С какой даты"),
        date_to: Optional[datetime] = Query(None, description="До какой даты"),
        limit: int = Query(20, ge=1, le=100, description="Максимальное количество записей"),
        offset: int = Query(0, ge=0, description="Смещение для пагинации"),
        db: Session = Depends(get_db)
):
    """
    Получение истории решения заданий

    Показывает УНИКАЛЬНЫЕ задания (по task_id) с последней попыткой для каждого.

    Поддерживает фильтрацию по:
    - Типу экзамена (ОГЭ/ЕГЭ)
    - Предмету
    - Сложности (easy/medium/hard)
    - Правильности ответа (True/False)
    - Датам

    **Примеры использования:**
    - Все задания: `/history/tasks?user_id=xxx`
    - Только неправильные: `/history/tasks?user_id=xxx&is_correct=false`
    - Математика сложная: `/history/tasks?user_id=xxx&subject_id=mathematics&difficulty=hard`
    """

    # Шаг 1: Создаём подзапрос для получения ID последней попытки каждого задания
    subquery = db.query(
        UserTaskAttempt.task_id,
        func.max(UserTaskAttempt.id).label('last_attempt_id')
    ).filter(
        UserTaskAttempt.user_id == user_id
    )

    # Применяем фильтры к подзапросу
    if exam_type:
        subquery = subquery.filter(UserTaskAttempt.exam_type == exam_type)

    if subject_id:
        subquery = subquery.filter(UserTaskAttempt.subject_id == subject_id)

    if difficulty:
        subquery = subquery.filter(UserTaskAttempt.difficulty == difficulty)

    if is_correct is not None:
        subquery = subquery.filter(UserTaskAttempt.is_correct == is_correct)

    if date_from:
        subquery = subquery.filter(UserTaskAttempt.attempted_at >= date_from)

    if date_to:
        subquery = subquery.filter(UserTaskAttempt.attempted_at <= date_to)

    # Группируем по task_id для получения уникальных заданий
    subquery = subquery.group_by(UserTaskAttempt.task_id).subquery()

    # Шаг 2: Основной запрос с JOIN к ExamTask и подзапросу
    base_query = db.query(
        UserTaskAttempt,
        ExamTask
    ).join(
        ExamTask,
        UserTaskAttempt.task_id == ExamTask.id
    ).join(
        subquery,
        UserTaskAttempt.id == subquery.c.last_attempt_id
    ).filter(
        UserTaskAttempt.user_id == user_id
    )

    # Сортировка по дате (новые первые)
    base_query = base_query.order_by(UserTaskAttempt.attempted_at.desc())

    # Получаем общее количество уникальных заданий
    total = base_query.count()

    # Применяем пагинацию
    results = base_query.limit(limit).offset(offset).all()

    # Формируем ответ
    items = []
    for attempt, task in results:
        items.append(TaskAttemptHistory(
            id=attempt.id,
            task_id=attempt.task_id,
            user_answer=attempt.user_answer,
            is_correct=attempt.is_correct,
            subject_id=attempt.subject_id,
            subject_name=get_subject_name(attempt.subject_id),
            exam_type=attempt.exam_type,
            difficulty=attempt.difficulty,
            time_spent=attempt.time_spent,
            attempted_at=attempt.attempted_at,
            # Детали задания
            question_text=task.question_text if task else None,
            correct_answer=task.correct_answer if task else None,
            explanation=task.explanation if task else None,
            points=task.points if task else None
        ))

    has_more = (offset + limit) < total

    logger.info(f"📜 История заданий для пользователя {user_id}: {len(items)} уникальных заданий (total={total})")

    return TaskHistoryResponse(
        total=total,
        items=items,
        has_more=has_more
    )

# =====================================================
# НЕПРАВИЛЬНЫЕ ЗАДАНИЯ
# =====================================================

@router.get("/history/incorrect", response_model=TaskHistoryResponse)
async def get_incorrect_tasks(
        user_id: str = Query(..., description="ID пользователя"),
        exam_type: Optional[str] = Query(None, description="Фильтр по типу экзамена"),
        subject_id: Optional[str] = Query(None, description="Фильтр по предмету"),
        difficulty: Optional[str] = Query(None, description="Фильтр по сложности"),
        limit: int = Query(20, ge=1, le=100, description="Максимальное количество записей"),
        offset: int = Query(0, ge=0, description="Смещение для пагинации"),
        db: Session = Depends(get_db)
):
    """
    Получение истории ТОЛЬКО неправильно решенных заданий

    Логика:
    - Показывает УНИКАЛЬНЫЕ задания, которые пользователь решал неправильно
    - Если для задания есть хотя бы одна правильная попытка - оно НЕ попадает в список
    - Исключаются задания с правильными решениями
    """

    correct_task_ids_query = db.query(UserTaskAttempt.task_id).filter(
        UserTaskAttempt.user_id == user_id,
        UserTaskAttempt.is_correct == True
    ).distinct()

    if exam_type:
        correct_task_ids_query = correct_task_ids_query.filter(
            UserTaskAttempt.exam_type == exam_type
        )

    correct_task_ids = {row[0] for row in correct_task_ids_query.all()}

    base_query = db.query(
        UserTaskAttempt,
        ExamTask
    ).join(
        ExamTask,
        UserTaskAttempt.task_id == ExamTask.id
    ).filter(
        UserTaskAttempt.user_id == user_id,
        UserTaskAttempt.is_correct == False,
        ~UserTaskAttempt.task_id.in_(correct_task_ids)
    )

    if exam_type:
        base_query = base_query.filter(UserTaskAttempt.exam_type == exam_type)

    if subject_id:
        base_query = base_query.filter(UserTaskAttempt.subject_id == subject_id)

    if difficulty:
        base_query = base_query.filter(UserTaskAttempt.difficulty == difficulty)

    subquery = db.query(
        UserTaskAttempt.task_id,
        func.max(UserTaskAttempt.attempted_at).label('last_attempt')
    ).filter(
        UserTaskAttempt.user_id == user_id,
        UserTaskAttempt.is_correct == False,
        ~UserTaskAttempt.task_id.in_(correct_task_ids)
    )

    if exam_type:
        subquery = subquery.filter(UserTaskAttempt.exam_type == exam_type)
    if subject_id:
        subquery = subquery.filter(UserTaskAttempt.subject_id == subject_id)
    if difficulty:
        subquery = subquery.filter(UserTaskAttempt.difficulty == difficulty)

    subquery = subquery.group_by(UserTaskAttempt.task_id).subquery()

    main_query = db.query(
        UserTaskAttempt,
        ExamTask
    ).join(
        ExamTask,
        UserTaskAttempt.task_id == ExamTask.id
    ).join(
        subquery,
        and_(
            UserTaskAttempt.task_id == subquery.c.task_id,
            UserTaskAttempt.attempted_at == subquery.c.last_attempt
        )
    ).filter(
        UserTaskAttempt.user_id == user_id
    ).order_by(UserTaskAttempt.attempted_at.desc())

    total = main_query.count()

    results = main_query.limit(limit).offset(offset).all()

    items = []
    for attempt, task in results:
        items.append(TaskAttemptHistory(
            id=attempt.id,
            task_id=attempt.task_id,
            user_answer=attempt.user_answer,
            is_correct=attempt.is_correct,
            subject_id=attempt.subject_id,
            subject_name=get_subject_name(attempt.subject_id),
            exam_type=attempt.exam_type,
            difficulty=attempt.difficulty,
            time_spent=attempt.time_spent,
            attempted_at=attempt.attempted_at,
            question_text=task.question_text if task else None,
            correct_answer=task.correct_answer if task else None,
            explanation=task.explanation if task else None,
            points=task.points if task else None
        ))

    has_more = (offset + limit) < total

    return TaskHistoryResponse(
        total=total,
        items=items,
        has_more=has_more
    )


@router.get("/history/incorrect/summary", response_model=IncorrectTasksSummary)
async def get_incorrect_summary(
        user_id: str = Query(..., description="ID пользователя"),
        exam_type: Optional[str] = Query(None, description="Фильтр по типу экзамена"),
        db: Session = Depends(get_db)
):
    """
    Получение сводки по неправильно решенным заданиям

    Показывает:
    - Общее количество УНИКАЛЬНЫХ ошибок (только задания без правильных решений)
    - Распределение по предметам
    - Распределение по сложности
    - Типичные ошибки
    """

    # Шаг 1: Получаем все task_id с правильными решениями
    correct_task_ids_query = db.query(UserTaskAttempt.task_id).filter(
        UserTaskAttempt.user_id == user_id,
        UserTaskAttempt.is_correct == True
    ).distinct()

    if exam_type:
        correct_task_ids_query = correct_task_ids_query.filter(
            UserTaskAttempt.exam_type == exam_type
        )

    correct_task_ids = {row[0] for row in correct_task_ids_query.all()}

    logger.info(f"🔍 Найдено {len(correct_task_ids)} заданий с правильными решениями")

    # Шаг 2: Получаем последнюю попытку для каждого УНИКАЛЬНОГО неправильного задания
    # Подзапрос: находим ID последней попытки для каждого task_id
    subquery = db.query(
        UserTaskAttempt.task_id,
        func.max(UserTaskAttempt.id).label('last_attempt_id')
    ).filter(
        UserTaskAttempt.user_id == user_id,
        UserTaskAttempt.is_correct == False,
        ~UserTaskAttempt.task_id.in_(correct_task_ids)  # Исключаем задания с правильными решениями
    )

    if exam_type:
        subquery = subquery.filter(UserTaskAttempt.exam_type == exam_type)

    subquery = subquery.group_by(UserTaskAttempt.task_id).subquery()

    # Основной запрос: получаем последние попытки для уникальных заданий
    incorrect_attempts = db.query(UserTaskAttempt).join(
        subquery,
        UserTaskAttempt.id == subquery.c.last_attempt_id
    ).all()

    # Подсчеты
    total_incorrect = len(incorrect_attempts)

    logger.info(f"📊 Найдено {total_incorrect} уникальных заданий с ошибками (без правильных решений)")

    # По предметам
    by_subject = {}
    for attempt in incorrect_attempts:
        subject_name = get_subject_name(attempt.subject_id)
        by_subject[subject_name] = by_subject.get(subject_name, 0) + 1

    # По сложности
    by_difficulty = {}
    for attempt in incorrect_attempts:
        diff = attempt.difficulty
        by_difficulty[diff] = by_difficulty.get(diff, 0) + 1

    # Типичные ошибки
    most_common_mistakes = []
    if total_incorrect > 0:
        if by_difficulty.get('hard', 0) > total_incorrect * 0.4:
            most_common_mistakes.append("Много ошибок в сложных заданиях")
        if by_difficulty.get('easy', 0) > total_incorrect * 0.3:
            most_common_mistakes.append("Невнимательность в простых заданиях")

    return IncorrectTasksSummary(
        total_incorrect=total_incorrect,
        by_subject=by_subject,
        by_difficulty=by_difficulty,
        most_common_mistakes=most_common_mistakes
    )

# =====================================================
# ПОВТОРНОЕ РЕШЕНИЕ ЗАДАНИЯ
# =====================================================

@router.get("/task/{task_id}/retry", response_model=dict)
async def get_task_for_retry(
        task_id: int,
        user_id: str = Query(..., description="ID пользователя"),
        db: Session = Depends(get_db)
):
    """
    Получение задания для повторного решения

    Возвращает полную информацию о задании БЕЗ правильного ответа,
    чтобы пользователь мог попробовать решить заново.
    """

    # Проверяем, что пользователь действительно решал это задание
    attempt = db.query(UserTaskAttempt).filter(
        UserTaskAttempt.user_id == user_id,
        UserTaskAttempt.task_id == task_id
    ).first()

    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Вы еще не решали это задание"
        )

    # Получаем задание
    task = db.query(ExamTask).filter(ExamTask.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задание не найдено"
        )

    # Возвращаем без правильного ответа
    return {
        "id": task.id,
        "subject_id": task.subject_id,
        "subject_name": get_subject_name(task.subject_id),
        "exam_type": task.exam_type,
        "task_number": task.task_number,
        "difficulty": task.difficulty,
        "question_text": task.question_text,
        "answer_type": task.answer_type,
        "answer_options": task.answer_options,
        "points": task.points,
        "estimated_time": task.estimated_time,
        # История попыток пользователя (для контекста)
        "previous_attempts": db.query(UserTaskAttempt).filter(
            UserTaskAttempt.user_id == user_id,
            UserTaskAttempt.task_id == task_id
        ).count(),
        "last_attempt_was_correct": attempt.is_correct
    }

# =====================================================
# UTILS
# =====================================================

@router.get("/subjects/available")
async def get_available_subjects():
    """
    Получение списка всех доступных предметов для ОГЭ и ЕГЭ
    """
    return AvailableSubjects()