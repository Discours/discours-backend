from datetime import datetime
from enum import Enum as Enumeration

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String

from base.orm import Base


class ReactionKind(Enumeration):
    AGREE = 1  # +1
    DISAGREE = 2  # -1
    PROOF = 3  # +1
    DISPROOF = 4  # -1
    ASK = 5  # +0 bookmark
    PROPOSE = 6  # +0
    QUOTE = 7  # +0 bookmark
    COMMENT = 8  # +0
    ACCEPT = 9  # +1
    REJECT = 0  # -1
    LIKE = 11  # +1
    DISLIKE = 12  # -1
    # TYPE = <reaction index> # rating diff


class Reaction(Base):
    __tablename__ = "reaction"
    body = Column(String, nullable=True, comment="Reaction Body")
    createdAt = Column(
        DateTime, nullable=False, default=datetime.now, comment="Created at"
    )
    createdBy = Column(ForeignKey("user.id"), nullable=False, index=True, comment="Sender")
    updatedAt = Column(DateTime, nullable=True, comment="Updated at")
    updatedBy = Column(ForeignKey("user.id"), nullable=True, index=True, comment="Last Editor")
    deletedAt = Column(DateTime, nullable=True, comment="Deleted at")
    deletedBy = Column(ForeignKey("user.id"), nullable=True, index=True, comment="Deleted by")
    shout = Column(ForeignKey("shout.id"), nullable=False, index=True)
    replyTo = Column(
        ForeignKey("reaction.id"), nullable=True, comment="Reply to reaction ID"
    )
    range = Column(String, nullable=True, comment="Range in format <start index>:<end>")
    kind = Column(Enum(ReactionKind), nullable=False, comment="Reaction kind")
    oid = Column(String, nullable=True, comment="Old ID")
