import time
from enum import Enum as Enumeration

from sqlalchemy import Column, ForeignKey, Integer, String

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

    body = Column(String, default="", comment="Reaction Body")
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()), index=True)
    updated_at = Column(Integer, nullable=True, comment="Updated at", index=True)
    deleted_at = Column(Integer, nullable=True, comment="Deleted at", index=True)
    deleted_by = Column(ForeignKey("author.id"), nullable=True)
    reply_to = Column(ForeignKey("reaction.id"), nullable=True)
    quote = Column(String, nullable=True, comment="Original quoted text")
    shout = Column(ForeignKey("shout.id"), nullable=False, index=True)
    created_by = Column(ForeignKey("author.id"), nullable=False)
    kind = Column(String, nullable=False, index=True)

    oid = Column(String)
