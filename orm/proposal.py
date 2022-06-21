from typing import List
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from orm import Permission
from orm.base import Base


class ProposalRating(Base):
	__tablename__ = "proposal_rating"

	id = None
	proposal_id = Column(ForeignKey('proposal.id'), primary_key = True)
	createdBy = Column(ForeignKey('user.slug'), primary_key = True)
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Timestamp")
	value = Column(Integer)

class Proposal(Base):
	__tablename__ = 'proposal'

	shout: str = Column(String, ForeignKey("shout.slug"), nullable=False, comment="Shout")
	range: str = Column(String, nullable=True, comment="Range in format <start index>:<end>")
	body: str = Column(String, nullable=False, comment="Body")
	createdBy: int = Column(Integer, ForeignKey("user.id"), nullable=False, comment="Author")
	createdAt: str = Column(DateTime, nullable=False, comment="Created at")
	updatedAt: str = Column(DateTime, nullable=True, comment="Updated at")
	acceptedAt: str = Column(DateTime, nullable=True, comment="Accepted at")
	acceptedBy: str = Column(Integer, ForeignKey("user.id"), nullable=True, comment="Accepted by")
	declinedAt: str = Column(DateTime, nullable=True, comment="Declined at")
	declinedBy: str = Column(Integer, ForeignKey("user.id"), nullable=True, comment="Declined by")
	ratings = relationship(ProposalRating, foreign_keys=ProposalRating.proposal_id)
	deletedAt: str = Column(DateTime, nullable=True, comment="Deleted at") 
	# TODO: debug, logix