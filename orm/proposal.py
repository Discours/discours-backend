from typing import List
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Datetime

from orm import Permission
from orm.base import Base


class Proposal(Base):
    __tablename__ = 'proposal'

    author_id: str = Column(ForeignKey("user.id"), nullable=False, comment="Author")
    body: str = Column(String, nullable=False, comment="Body")
    createdAt: str = Column(datetime, nullable=False, comment="Created at")
    shout: str = Column(ForeignKey("shout.id"), nullable=False, comment="Updated at")
    range: str = Column(String, nullable=True, comment="Range in format <start index>:<end>")

    # TODO: debug, logix