from typing import List
from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship

from orm.base import Base

class CommentRating(Base):
	__tablename__ = "comment_rating"

	id = None
	comment_id = Column(ForeignKey('comment.id'), primary_key = True)
	createdBy = Column(ForeignKey('user.id'), primary_key = True)
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Timestamp")
	value = Column(Integer)

class Comment(Base):
	__tablename__ = 'comment'

	author: int = Column(ForeignKey("user.id"), nullable=False, comment="Sender")
	body: str = Column(String, nullable=False, comment="Comment Body")
	createdAt = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	updatedAt = Column(DateTime, nullable=True, comment="Updated at")
	deletedAt = Column(DateTime, nullable=True, comment="Deleted at")
	deletedBy = Column(ForeignKey("user.id"), nullable=True, comment="Deleted by")
	shout: int = Column(ForeignKey("shout.id"), nullable=True, comment="Shout ID")
	rating: int = Column(Integer, nullable=True, comment="Comment Rating")
	ratings = relationship(CommentRating, foreign_keys=CommentRating.comment_id)
	old_id: str = Column(String, nullable = True)
	old_thread: str = Column(String, nullable = True)
	

	# TODO: work in progress, udpate this code
