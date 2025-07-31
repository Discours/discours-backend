"""
JSON encoders and utilities
"""

import json
from datetime import date, datetime
from typing import Any, Union

import orjson


def default_json_encoder(obj: Any) -> Any:
    """
    Кастомный JSON энкодер для сериализации нестандартных типов.

    Args:
        obj: Объект для сериализации

    Returns:
        Сериализованное представление объекта

    Raises:
        TypeError: Если объект не может быть сериализован
    """
    # Обработка datetime
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    serialized = False

    # Обработка объектов с методом __json__
    if hasattr(obj, "__json__"):
        try:
            result = obj.__json__()
            serialized = True
            return result
        except Exception as _e:
            serialized = False

    # Обработка объектов с методом to_dict
    if hasattr(obj, "to_dict"):
        try:
            result = obj.to_dict()
            serialized = True
            return result
        except Exception as _e:
            serialized = False

    # Обработка объектов с методом dict
    if hasattr(obj, "dict"):
        try:
            result = obj.dict()
            serialized = True
            return result
        except Exception as _e:
            serialized = False

    # Если ни один из методов не сработал, вызываем TypeError
    if not serialized:
        error_text = f"Object of type {type(obj).__name__} is not JSON serializable"
        raise TypeError(error_text)


def orjson_dumps(obj: Any, **kwargs: Any) -> bytes:
    """
    Сериализация объекта с помощью orjson.

    Args:
        obj: Объект для сериализации
        **kwargs: Дополнительные параметры

    Returns:
        bytes: Сериализованный объект
    """
    return orjson.dumps(obj, default=default_json_encoder, **kwargs)


def orjson_loads(data: Union[str, bytes]) -> Any:
    """
    Десериализация объекта с помощью orjson.

    Args:
        data: Строка или байты для десериализации

    Returns:
        Десериализованный объект
    """
    return orjson.loads(data)


class JSONEncoder(json.JSONEncoder):
    """
    Расширенный JSON энкодер с поддержкой кастомной сериализации.
    """

    def default(self, obj: Any) -> Any:
        """
        Метод для сериализации нестандартных типов.

        Args:
            obj: Объект для сериализации

        Returns:
            Сериализованное представление объекта
        """
        try:
            return default_json_encoder(obj)
        except TypeError:
            return super().default(obj)


def fast_json_dumps(obj: Any, **kwargs: Any) -> str:
    """
    Быстрая сериализация объекта в JSON-строку.

    Args:
        obj: Объект для сериализации
        **kwargs: Дополнительные параметры

    Returns:
        str: JSON-строка
    """
    return json.dumps(obj, cls=JSONEncoder, **kwargs)


def fast_json_loads(data: str, **kwargs: Any) -> Any:
    """
    Быстрая десериализация JSON-строки.

    Args:
        data: JSON-строка
        **kwargs: Дополнительные параметры

    Returns:
        Десериализованный объект
    """
    return json.loads(data, **kwargs)
