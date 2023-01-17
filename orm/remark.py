from datetime import datetime
from enum import Enum as Enumeration

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String

from base.orm import Base


class Remark(Base):

    __tablename__ = "remark"

    body = Column(String, nullable=False)
    desc = Column(String, default='')
    shout = Column(ForeignKey("shout.id"), nullable=True, index=True, comment="Shout")
