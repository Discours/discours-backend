from decimal import Decimal
from json import JSONEncoder


class CustomJSONEncoder(JSONEncoder):
    """
    Расширенный JSON энкодер с поддержкой сериализации объектов SQLAlchemy.

    Примеры:
    >>> import json
    >>> from decimal import Decimal
    >>> from orm.topic import Topic
    >>> json.dumps(Decimal("10.50"), cls=CustomJSONEncoder)
    '"10.50"'
    >>> topic = Topic(id=1, slug="test")
    >>> json.dumps(topic, cls=CustomJSONEncoder)
    '{"id": 1, "slug": "test", ...}'
    """

    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)

        # Проверяем, есть ли у объекта метод dict() (как у моделей SQLAlchemy)
        if hasattr(obj, "dict") and callable(obj.dict):
            return obj.dict()

        return super().default(obj)
