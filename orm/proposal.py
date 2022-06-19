from typing import List
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Datetime

from orm import Permission
from orm.base import Base


class Proposal(Base):
    __tablename__ = 'proposal'

    shout: int = Column(Integer, ForeignKey("shout.id"), nullable=False, comment="Shout")
    range: str = Column(String, nullable=True, comment="Range in format <start index>:<end>")
    body: str = Column(String, nullable=False, comment="Body")
    createdBy: int = Column(Integer, ForeignKey("user.id"), nullable=False, comment="Author")
    createdAt: str = Column(datetime, nullable=False, comment="Created at")
    updatedAt: str = Column(datetime, nullable=True, comment="Updated at")
    acceptedAt: str = Column(datetime, nullable=True, comment="Accepted at")
    acceptedBy: str = Column(datetime, nullable=True, comment="Accepted by")
    deletedAt: str = Column(datetime, nullable=True, comment="Deleted at") 
    declinedAt: str = Column(datetime, nullable=True, comment="Declined at)
    declinedBy: str = Column(datetime, nullable=True, comment="Declined by")
    # TODO: debug, logix