from datetime import datetime

from sqlalchemy import Column, String, JSON, Boolean, ForeignKey, DateTime
from base.orm import Base


class Event(Base):
    __tablename__ = "event"

    user = Column(ForeignKey("user.id"), index=True)
    createdAt = Column(DateTime, nullable=False, default=datetime.now, index=True)
    seen = Column(Boolean, nullable=False, default=False, index=True)
    type = Column(String, nullable=False)
    data = Column(JSON, nullable=True)

