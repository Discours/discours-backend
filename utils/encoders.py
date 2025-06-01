"""
JSON encoders and utilities
"""

import datetime
import decimal
from typing import Any, Union

import orjson


def default_json_encoder(obj: Any) -> Any:
    """
    Default JSON encoder для объектов, которые не поддерживаются стандартным JSON

    Args:
        obj: Объект для сериализации

    Returns:
        Сериализуемое представление объекта

    Raises:
        TypeError: Если объект не может быть сериализован
    """
    if hasattr(obj, "dict") and callable(obj.dict):
        return obj.dict()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return obj.isoformat()
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if hasattr(obj, "__json__"):
        return obj.__json__()
    msg = f"Object of type {type(obj)} is not JSON serializable"
    raise TypeError(msg)


def orjson_dumps(obj: Any, **kwargs: Any) -> bytes:
    """
    Сериализует объект в JSON с помощью orjson

    Args:
        obj: Объект для сериализации
        **kwargs: Дополнительные параметры для orjson.dumps

    Returns:
        bytes: JSON в виде байтов
    """
    # Используем правильную константу для orjson
    option_flags = orjson.OPT_SERIALIZE_DATACLASS
    if kwargs.get("indent"):
        option_flags |= orjson.OPT_INDENT_2

    return orjson.dumps(obj, default=default_json_encoder, option=option_flags)


def orjson_loads(data: Union[str, bytes]) -> Any:
    """
    Десериализует JSON с помощью orjson

    Args:
        data: JSON данные в виде строки или байтов

    Returns:
        Десериализованный объект
    """
    return orjson.loads(data)


class JSONEncoder:
    """Кастомный JSON кодировщик на основе orjson"""

    @staticmethod
    def encode(obj: Any) -> str:
        """Encode object to JSON string"""
        return orjson_dumps(obj).decode("utf-8")

    @staticmethod
    def decode(data: Union[str, bytes]) -> Any:
        """Decode JSON string to object"""
        return orjson_loads(data)


# Создаем экземпляр для обратной совместимости
CustomJSONEncoder = JSONEncoder()


def fast_json_dumps(obj: Any, indent: bool = False) -> str:
    """
    Быстрая сериализация JSON

    Args:
        obj: Объект для сериализации
        indent: Форматировать с отступами

    Returns:
        JSON строка
    """
    return orjson_dumps(obj, indent=indent).decode("utf-8")


def fast_json_loads(data: Union[str, bytes]) -> Any:
    """
    Быстрая десериализация JSON

    Args:
        data: JSON данные

    Returns:
        Десериализованный объект
    """
    return orjson_loads(data)


# Экспортируем для удобства
dumps = fast_json_dumps
loads = fast_json_loads
