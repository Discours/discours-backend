from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey
from base.orm import Base


class ViewedEntry(Base):
    __tablename__ = "viewed"

    viewer = Column(ForeignKey("user.slug"), default='anonymous')
    shout = Column(ForeignKey("shout.slug"))
    createdAt = Column(
        DateTime, nullable=False, default=datetime.now, comment="Created at"
    )
