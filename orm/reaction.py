from datetime import datetime
from sqlalchemy import Column, String, ForeignKey, DateTime
from base.orm import Base
from sqlalchemy import Enum
from services.stat.reacted import ReactedStorage, ReactionKind
from services.stat.viewed import ViewedStorage

class Reaction(Base):
	__tablename__ = 'reaction'
	body: str = Column(String, nullable=True, comment="Reaction Body")
	createdAt = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	createdBy: str = Column(ForeignKey("user.slug"), nullable=False, comment="Sender")
	updatedAt = Column(DateTime, nullable=True, comment="Updated at")
	updatedBy = Column(ForeignKey("user.slug"), nullable=True, comment="Last Editor")
	deletedAt = Column(DateTime, nullable=True, comment="Deleted at")
	deletedBy = Column(ForeignKey("user.slug"), nullable=True, comment="Deleted by")
	shout = Column(ForeignKey("shout.slug"), nullable=False)
	replyTo: int = Column(ForeignKey("reaction.id"), nullable=True, comment="Reply to reaction ID")
	range: str = Column(String, nullable=True, comment="Range in format <start index>:<end>")
	kind: int = Column(Enum(ReactionKind), nullable=False, comment="Reaction kind")
	oid: str = Column(String, nullable=True, comment="Old ID")

	@property
	async def stat(self):
		rrr = await ReactedStorage.get_reaction(self.id)
		print(rrr[0])
		return {
			"viewed": await ViewedStorage.get_reaction(self.id),
			"reacted": len(rrr),
			"rating": await ReactedStorage.get_reaction_rating(self.id)
		}
