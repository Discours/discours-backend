from enum import Enum as Enumeration

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, func

from base.orm import Base


class ReactionKind(Enumeration):
    AGREE = 1  # +1
    DISAGREE = 2  # -1
    PROOF = 3  # +1
    DISPROOF = 4  # -1
    ASK = 5  # +0
    PROPOSE = 6  # +0
    QUOTE = 7  # +0 bookmark
    COMMENT = 8  # +0
    ACCEPT = 9  # +1
    REJECT = 0  # -1
    LIKE = 11  # +1
    DISLIKE = 12  # -1
    REMARK = 13  # 0
    FOOTNOTE = 14  # 0
    # TYPE = <reaction index> # rating diff


class Reaction(Base):
    __tablename__ = "reaction"
    body = Column(String, nullable=True, comment="Reaction Body")
    createdAt = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="Created at"
    )
    createdBy: Column = Column(ForeignKey("user.id"), nullable=False, index=True, comment="Sender")
    updatedAt = Column(DateTime(timezone=True), nullable=True, comment="Updated at")
    updatedBy: Column = Column(
        ForeignKey("user.id"), nullable=True, index=True, comment="Last Editor"
    )
    deletedAt = Column(DateTime(timezone=True), nullable=True, comment="Deleted at")
    deletedBy: Column = Column(
        ForeignKey("user.id"), nullable=True, index=True, comment="Deleted by"
    )
    shout: Column = Column(ForeignKey("shout.id"), nullable=False, index=True)
    replyTo: Column = Column(
        ForeignKey("reaction.id"), nullable=True, comment="Reply to reaction ID"
    )
    range = Column(String, nullable=True, comment="Range in format <start index>:<end>")
    kind = Column(Enum(ReactionKind), nullable=False, comment="Reaction kind")
    oid = Column(String, nullable=True, comment="Old ID")
