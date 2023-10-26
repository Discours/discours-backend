from pydantic import BaseModel
from typing import Optional, Text


class AuthInput(BaseModel):
    id: Optional[int]
    email: Optional[Text]
    phone: Optional[Text]
    password: Optional[Text]


class TokenPayload(BaseModel):
    user_id: int
    username: Optional[Text]
    exp: int
    iat: int
    iss: Text
