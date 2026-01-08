# app/routers/exam_router.py
"""
API endpoints для экзаменационной системы
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, timedelta

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
    ExamType, Difficulty
)
from app.models import ExamSettings, ExamSubject, ExamTask

router = APIRouter(prefix="/exam", tags=["Экзамены"])


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
    """Обновление настроек экзамена (даты)"""
    settings = ExamService.update_exam_settings(db, settings_id, user_id, data.exam_date)

    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Настройки экзамена не найдены"
        )

    return settings


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

    return task


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

        return {
            "id": attempt.id,
            "task_id": attempt.task_id,
            "user_answer": attempt.user_answer,
            "is_correct": is_correct,
            "points_earned": points,
            "time_spent": attempt.time_spent,
            "attempted_at": attempt.attempted_at,
            "task": task
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
# UTILS
# =====================================================

@router.get("/subjects/available")
async def get_available_subjects():
    """
    Получение списка всех доступных предметов для ОГЭ и ЕГЭ
    """
    return AvailableSubjects()