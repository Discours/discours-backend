import time
from enum import Enum as Enumeration

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from auth.orm import Author
from orm.base import BaseModel as Base


class ReactionKind(Enumeration):
    # TYPE = <reaction index> # rating diff

    # editor specials
    AGREE = "AGREE"  # +1
    DISAGREE = "DISAGREE"  # -1

    # coauthor specials
    ASK = "ASK"  # 0
    PROPOSE = "PROPOSE"  # 0

    # generic internal reactions
    ACCEPT = "ACCEPT"  # +1
    REJECT = "REJECT"  # -1

    # experts speacials
    PROOF = "PROOF"  # +1
    DISPROOF = "DISPROOF"  # -1

    # comment and quote
    QUOTE = "QUOTE"  # 0
    COMMENT = "COMMENT"  # 0

    # generic rating
    LIKE = "LIKE"  # +1
    DISLIKE = "DISLIKE"  # -1

    # credit artist or researcher
    CREDIT = "CREDIT"  # +1
    SILENT = "SILENT"  # 0


REACTION_KINDS = ReactionKind.__members__.keys()


class Reaction(Base):
    __tablename__ = "reaction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    body: Mapped[str] = mapped_column(String, default="", comment="Reaction Body")
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=lambda: int(time.time()), index=True)
    updated_at: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Updated at", index=True)
    deleted_at: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Deleted at", index=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey(Author.id), nullable=True)
    reply_to: Mapped[int | None] = mapped_column(ForeignKey("reaction.id"), nullable=True)
    quote: Mapped[str | None] = mapped_column(String, nullable=True, comment="Original quoted text")
    shout: Mapped[int] = mapped_column(ForeignKey("shout.id"), nullable=False, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey(Author.id), nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False, index=True)

    oid: Mapped[str | None] = mapped_column(String)

    __table_args__ = (
        Index("idx_reaction_created_at", "created_at"),
        Index("idx_reaction_created_by", "created_by"),
        Index("idx_reaction_shout", "shout"),
        Index("idx_reaction_kind", "kind"),
        {"extend_existing": True},
    )
