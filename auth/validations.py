from datetime import datetime
from typing import Optional, Text

from pydantic import BaseModel


class User(BaseModel):
    id: Optional[int]
    # age: Optional[int]
    username: Optional[Text]
    # phone: Optional[Text]
    password: Optional[Text]


class PayLoad(BaseModel):
    user_id: int
    device: Text
    exp: datetime
    iat: datetime


class CreateUser(BaseModel):
    email: Text
    # username: Optional[Text]
    # age: Optional[int]
    # phone: Optional[Text]
    password: Optional[Text]

# TODO: update validations
