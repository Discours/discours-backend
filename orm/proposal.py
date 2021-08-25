from typing import List
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Datetime

from orm import Permission
from orm.base import Base


class Proposal(Base):
    __tablename__ = 'proposal'

    author_id: int = Column(Integer, ForeignKey("user.id"), nullable=False, comment="Author")
    shout_id: int = Column(Integer, ForeignKey("shout.id"), nullable=False, comment="Shout")
    body: str = Column(String, nullable=False, comment="Body")
    createdAt: str = Column(datetime, nullable=False, comment="Created at")
    range: str = Column(String, nullable=True, comment="Range in format <start index>:<end>")

    # TODO: debug, logix