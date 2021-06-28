from typing import List
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Datetime

from orm import Permission
from orm.base import Base


class Shout(Base):
    __tablename__ = 'shout'

    author_id: str = Column(ForeignKey("user.id"), nullable=False, comment="Author")
    body: str = Column(String, nullable=False, comment="Body")
    createdAt: str = Column(datetime, nullable=False, comment="Created at")
    updatedAt: str = Column(datetime, nullable=False, comment="Updated at")

    # TODO: add all the fields