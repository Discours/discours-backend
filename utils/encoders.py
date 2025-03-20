from decimal import Decimal

import orjson


class CustomJSONEncoder(orjson.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)
