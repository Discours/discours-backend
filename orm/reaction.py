from datetime import datetime
from sqlalchemy import Column, String, ForeignKey, DateTime
from orm.base import Base, local_session
import enum
from sqlalchemy import Enum

from storages.viewed import ViewedStorage

class ReactionKind(enum.Enum):
	AGREE 	= 1 # +1
	DISAGREE 	= 2 # -1
	PROOF 	= 3	# +1
	DISPROOF 	= 4	# -1
	ASK		= 5 # +0
	PROPOSE	= 6 # +0
	QOUTE		= 7 # +0
	COMMENT	= 8 # +0
	ACCEPT	= 9 # +1
	REJECT	= 0 # -1
	LIKE		= 11 # +1
	DISLIKE	= 12 # -1
	# TYPE = <reaction index> # rating change guess


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
	async def stat(self) -> Dict:
		reacted = 0
		try:
			with local_session() as session:
				reacted = session.query(Reaction).filter(Reaction.replyTo == self.id).count()
		except Exception as e:
			print(e)
		return {
			"viewed": await ViewedStorage.get_reaction(self.slug),
			"reacted": reacted
		}