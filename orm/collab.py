from datetime import datetime

from sqlalchemy import Boolean, Column, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from base.orm import Base
from orm.user import User


class CollabAuthor(Base):
    __tablename__ = "collab_author"

    id = None  # type: ignore
    collab = Column(ForeignKey("collab.id"), primary_key=True)
    authorId = Column(ForeignKey("user.id"), primary_key=True)
    accepted = Column(Boolean, default=False)


class Collab(Base):
    __tablename__ = "collab"

    title = Column(String, nullable=True, comment="Title")
    body = Column(String, nullable=True, comment="Body")
    pic = Column(String, nullable=True, comment="Picture")
    authors = relationship(lambda: User, secondary=CollabAuthor.__tablename__)
    createdAt = Column(DateTime, default=datetime.now, comment="Created At")
    createdBy = Column(ForeignKey("user.id"), comment="Created By")
