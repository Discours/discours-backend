from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer
from base.orm import Base


class ViewedByDay(Base):
    __tablename__ = "viewed_by_day"

    id = None
    shout = Column(ForeignKey("shout.slug"), primary_key=True)
    day = Column(DateTime, primary_key=True, default=datetime.now)
    value = Column(Integer)
