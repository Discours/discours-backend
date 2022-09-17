from datetime import datetime

from sqlalchemy import Column, String, ForeignKey, DateTime

from base.orm import Base


class ShoutCollection(Base):
    __tablename__ = "shout_collection"

    id = None  # type: ignore
    shout = Column(ForeignKey("shout.slug"), primary_key=True)
    collection = Column(ForeignKey("collection.slug"), primary_key=True)


class Collection(Base):
    __tablename__ = "collection"

    id = None  # type: ignore
    slug = Column(String, primary_key=True)
    title = Column(String, nullable=False, comment="Title")
    body = Column(String, nullable=True, comment="Body")
    pic = Column(String, nullable=True, comment="Picture")
    createdAt = Column(DateTime, default=datetime.now, comment="Created At")
    createdBy = Column(ForeignKey("user.id"), comment="Created By")
    publishedAt = Column(DateTime, default=datetime.now, comment="Published At")
