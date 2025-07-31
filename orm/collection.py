import time

from sqlalchemy import ForeignKey, Index, Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from orm.base import BaseModel as Base


class ShoutCollection(Base):
    __tablename__ = "shout_collection"

    shout: Mapped[int] = mapped_column(ForeignKey("shout.id"))
    collection: Mapped[int] = mapped_column(ForeignKey("collection.id"))
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    created_by: Mapped[int] = mapped_column(ForeignKey("author.id"), comment="Created By")

    __table_args__ = (
        PrimaryKeyConstraint(shout, collection),
        Index("idx_shout_collection_shout", "shout"),
        Index("idx_shout_collection_collection", "collection"),
        {"extend_existing": True},
    )


class Collection(Base):
    __tablename__ = "collection"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String, unique=True)
    title: Mapped[str] = mapped_column(String, nullable=False, comment="Title")
    body: Mapped[str | None] = mapped_column(String, nullable=True, comment="Body")
    pic: Mapped[str | None] = mapped_column(String, nullable=True, comment="Picture")
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    created_by: Mapped[int] = mapped_column(ForeignKey("author.id"), comment="Created By")
    published_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))

    created_by_author = relationship("Author", foreign_keys=[created_by])
