# app/repositories/base_repository.py
from typing import Generic, TypeVar, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.database import Base
import logging

logger = logging.getLogger(__name__)
ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType], db: Session):
        self.model = model
        self.db = db

    def create(self, **kwargs) -> ModelType:
        try:
            obj = self.model(**kwargs)
            self.db.add(obj)
            self.db.commit()
            self.db.refresh(obj)
            return obj
        except SQLAlchemyError as e:
            self.db.rollback()
            raise

    def get_by_id(self, id: Any) -> Optional[ModelType]:
        # Простая реализация - ищем по первичному ключу
        return self.db.query(self.model).filter(
            list(self.model.__table__.primary_key.columns)[0] == id
        ).first()
