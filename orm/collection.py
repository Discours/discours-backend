from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String

from base.orm import Base


class ShoutCollection(Base):
    __tablename__ = "shout_collection"

    id = None
    shout = Column(ForeignKey("shout.id"), primary_key=True)
    collection = Column(ForeignKey("collection.id"), primary_key=True)


class Collection(Base):
    __tablename__ = "collection"

    slug = Column(String, unique=True)
    title = Column(String, nullable=False, comment="Title")
    body = Column(String, nullable=True, comment="Body")
    pic = Column(String, nullable=True, comment="Picture")
    createdAt = Column(DateTime, default=datetime.now, comment="Created At")
    createdBy = Column(ForeignKey("user.id"), comment="Created By")
    publishedAt = Column(DateTime, default=datetime.now, comment="Published At")
