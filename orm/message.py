from typing import List

from sqlalchemy import Column, Integer, String, ForeignKey, Datetime

from orm import Permission
from orm.base import Base


class Message(Base):
    __tablename__ = 'message'

    sender: str = Column(ForeignKey("user.id"), nullable=False, comment="Sender")
    body: str = Column(String, nullable=False, comment="Body")
    createdAt: str = Column(Datetime, nullable=False, comment="Created at")
    updatedAt: str = Column(Datetime, nullable=True, comment="Updated at")
    replyTo: str = Column(ForeignKey("message.id", nullable=True, comment="Reply to"))

    # TODO: work in progress, udpate this code