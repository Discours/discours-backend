import time
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from auth.orm import Author
from orm.base import BaseModel as Base
from orm.topic import Topic


class DraftTopic(Base):
    __tablename__ = "draft_topic"

    draft: Mapped[int] = mapped_column(ForeignKey("draft.id"), index=True)
    topic: Mapped[int] = mapped_column(ForeignKey("topic.id"), index=True)
    main: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint(draft, topic),
        Index("idx_draft_topic_topic", "topic"),
        Index("idx_draft_topic_draft", "draft"),
        {"extend_existing": True},
    )


class DraftAuthor(Base):
    __tablename__ = "draft_author"

    draft: Mapped[int] = mapped_column(ForeignKey("draft.id"), index=True)
    author: Mapped[int] = mapped_column(ForeignKey(Author.id), index=True)
    caption: Mapped[str | None] = mapped_column(String, nullable=True, default="")

    __table_args__ = (
        PrimaryKeyConstraint(draft, author),
        Index("idx_draft_author_author", "author"),
        Index("idx_draft_author_draft", "draft"),
        {"extend_existing": True},
    )


class Draft(Base):
    __tablename__ = "draft"
    # required
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=lambda: int(time.time()))
    created_by: Mapped[int] = mapped_column(ForeignKey(Author.id), nullable=False)
    community: Mapped[int] = mapped_column(ForeignKey("community.id"), nullable=False, default=1)

    # optional
    layout: Mapped[str | None] = mapped_column(String, nullable=True, default="article")
    slug: Mapped[str | None] = mapped_column(String, unique=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    subtitle: Mapped[str | None] = mapped_column(String, nullable=True)
    lead: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str] = mapped_column(String, nullable=False, comment="Body")
    media: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    cover: Mapped[str | None] = mapped_column(String, nullable=True, comment="Cover image url")
    cover_caption: Mapped[str | None] = mapped_column(String, nullable=True, comment="Cover image alt caption")
    lang: Mapped[str] = mapped_column(String, nullable=False, default="ru", comment="Language")
    seo: Mapped[str | None] = mapped_column(String, nullable=True)  # JSON

    # auto
    updated_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    deleted_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey(Author.id), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey(Author.id), nullable=True)
    authors = relationship(Author, secondary=DraftAuthor.__table__)
    topics = relationship(Topic, secondary=DraftTopic.__table__)

    # shout/publication
    # Временно закомментировано для совместимости с тестами
    # shout: Mapped[int | None] = mapped_column(ForeignKey("shout.id"), nullable=True)

    __table_args__ = (
        Index("idx_draft_created_by", "created_by"),
        Index("idx_draft_community", "community"),
        {"extend_existing": True},
    )
