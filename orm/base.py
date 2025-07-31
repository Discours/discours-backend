import builtins
import logging
from typing import Any, Type

import orjson
from sqlalchemy import JSON
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

# Глобальный реестр моделей
REGISTRY: dict[str, Type[Any]] = {}

# Список полей для фильтрации при сериализации
FILTERED_FIELDS: list[str] = []


class BaseModel(DeclarativeBase):
    """
    Базовая модель с методами сериализации и обновления
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        REGISTRY[cls.__name__] = cls
        super().__init_subclass__(**kwargs)

    def dict(self, access: bool = False) -> builtins.dict[str, Any]:
        """
        Конвертирует ORM объект в словарь.

        Пропускает атрибуты, которые отсутствуют в объекте, но присутствуют в колонках таблицы.
        Преобразует JSON поля в словари.

        Returns:
            Dict[str, Any]: Словарь с атрибутами объекта
        """
        column_names = filter(lambda x: x not in FILTERED_FIELDS, self.__table__.columns.keys())
        data: builtins.dict[str, Any] = {}
        logger.debug(f"Converting object to dictionary {'with access' if access else 'without access'}")
        try:
            for column_name in column_names:
                try:
                    # Проверяем, существует ли атрибут в объекте
                    if hasattr(self, column_name):
                        value = getattr(self, column_name)
                        # Проверяем, является ли значение JSON и декодируем его при необходимости
                        if isinstance(value, (str, bytes)) and isinstance(
                            self.__table__.columns[column_name].type, JSON
                        ):
                            try:
                                data[column_name] = orjson.loads(value)
                            except (TypeError, orjson.JSONDecodeError) as e:
                                logger.warning(f"Error decoding JSON for column '{column_name}': {e}")
                                data[column_name] = value
                        else:
                            data[column_name] = value
                    else:
                        # Пропускаем атрибут, если его нет в объекте (может быть добавлен после миграции)
                        logger.debug(f"Skipping missing attribute '{column_name}' for {self.__class__.__name__}")
                except AttributeError as e:
                    logger.warning(f"Attribute error for column '{column_name}': {e}")
        except Exception as e:
            logger.warning(f"Error occurred while converting object to dictionary {e}")
        return data

    def update(self, values: builtins.dict[str, Any]) -> None:
        for key, value in values.items():
            if hasattr(self, key):
                setattr(self, key, value)


# Alias for backward compatibility
Base = BaseModel
