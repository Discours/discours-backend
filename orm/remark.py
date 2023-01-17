from datetime import datetime
from enum import Enum as Enumeration

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String

from base.orm import Base


class Remark(Base):

    tablename = "remark"

    slug = Column(String, unique=True, nullable=False)
    body = Column(String, nullable=False)
    shout = Column(ForeignKey("shout.id"), nullable=True, index=True, comment="Shout")
