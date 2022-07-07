from typing import List
from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship

from orm.base import Base

class CommentRating(Base):
	__tablename__ = "comment_rating"

	id = None
	comment_id = Column(ForeignKey('comment.id'), primary_key = True)
	createdBy = Column(ForeignKey('user.slug'), primary_key = True)
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Timestamp")
	value = Column(Integer)

class Comment(Base):
	__tablename__ = 'comment'
	body: str = Column(String, nullable=False, comment="Comment Body")
	createdAt = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	createdBy: str = Column(ForeignKey("user.slug"), nullable=False, comment="Sender")
	updatedAt = Column(DateTime, nullable=True, comment="Updated at")
	updatedBy = Column(ForeignKey("user.slug"), nullable=True, comment="Last Editor")
	deletedAt = Column(DateTime, nullable=True, comment="Deleted at")
	deletedBy = Column(ForeignKey("user.slug"), nullable=True, comment="Deleted by")
	shout = Column(ForeignKey("shout.slug"), nullable=False)
	replyTo: int = Column(ForeignKey("comment.id"), nullable=True, comment="comment ID")
	ratings = relationship(CommentRating, foreign_keys=CommentRating.comment_id)
	oid: str = Column(String, nullable=True)