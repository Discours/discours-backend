from datetime import datetime

from sqlalchemy import Column, ForeignKey, DateTime, String
from sqlalchemy.orm import relationship
from base.orm import Base
from orm.user import User


class CollabAuthor(Base):
    __tablename__ = "collab_author"

    id = None  # type: ignore
    collab = Column(ForeignKey("collab.id"), primary_key=True)
    author = Column(ForeignKey("user.slug"), primary_key=True)
    invitedBy = Column(ForeignKey("user.slug"))


class CollabInvited(Base):
    __tablename__ = "collab_invited"

    id = None  # type: ignore
    collab = Column(ForeignKey("collab.id"), primary_key=True)
    author = Column(ForeignKey("user.slug"), primary_key=True)
    invitedBy = Column(ForeignKey("user.slug"))


class Collab(Base):
    __tablename__ = "collab"

    shout = Column(ForeignKey("shout.id"), primary_key=True)
    authors = relationship(lambda: User, secondary=CollabAuthor.__tablename__)
    invites = relationship(lambda: User, secondary=CollabInvited.__tablename__)
    createdAt = Column(DateTime, default=datetime.now, comment="Created At")
    chat = Column(String, unique=True, nullable=False)
