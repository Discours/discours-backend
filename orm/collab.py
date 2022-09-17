from datetime import datetime

from sqlalchemy import Boolean, Column, String, ForeignKey, DateTime

from base.orm import Base


class CollabAuthor(Base):
    __tablename__ = "collab_author"

    id = None  # type: ignore
    collab = Column(ForeignKey("collab.id"), primary_key=True)
    author = Column(ForeignKey("user.slug"), primary_key=True)
    accepted = Column(Boolean, default=False)


class Collab(Base):
    __tablename__ = "collab"

    authors = Column()
    title = Column(String, nullable=True, comment="Title")
    body = Column(String, nullable=True, comment="Body")
    pic = Column(String, nullable=True, comment="Picture")
    createdAt = Column(DateTime, default=datetime.now, comment="Created At")
    createdBy = Column(ForeignKey("user.id"), comment="Created By")
