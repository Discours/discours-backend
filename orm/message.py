from typing import List
from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime

from orm import Permission
from orm.base import Base


class Message(Base):
    __tablename__ = 'message'

    author: int = Column(ForeignKey("user.id"), nullable=False, comment="Sender")
    body: str = Column(String, nullable=False, comment="Body")
    createdAt = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
    updatedAt = Column(DateTime, nullable=True, comment="Updated at")
    replyTo: int = Column(ForeignKey("message.id"), nullable=True, comment="Reply to")
    

    # TODO: work in progress, udpate this code
