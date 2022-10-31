from datetime import datetime
from typing import Optional, Text

from pydantic import BaseModel


class AuthInput(BaseModel):
    id: Optional[int]
    email: Optional[Text]
    phone: Optional[Text]
    password: Optional[Text]


class TokenPayload(BaseModel):
    user_id: int
    exp: datetime
    iat: datetime
