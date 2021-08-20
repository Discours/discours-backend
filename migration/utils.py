from datetime import datetime
from json import JSONEncoder

class DateTimeEncoder(JSONEncoder):
    def default(self, z):
        if isinstance(z, datetime):
            return (str(z))
        else:
            return super().default(z)