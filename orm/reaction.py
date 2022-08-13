from datetime import datetime
from sqlalchemy import Column, String, ForeignKey, DateTime
from base.orm import Base, local_session
import enum
from sqlalchemy import Enum
from services.stat.viewed import ViewedStorage

class ReactionKind(enum.Enum):
	AGREE 	= 1 # +1
	DISAGREE = 2 # -1
	PROOF 	= 3	# +1
	DISPROOF = 4 # -1
	ASK		= 5 # +0 bookmark
	PROPOSE	= 6 # +0
	QUOTE	= 7 # +0 bookmark
	COMMENT	= 8 # +0
	ACCEPT	= 9 # +1
	REJECT	= 0 # -1
	LIKE	= 11 # +1
	DISLIKE	= 12 # -1
	# TYPE = <reaction index> # rating diff

def kind_to_rate(kind) -> int:
	if kind in [
		ReactionKind.AGREE,
		ReactionKind.LIKE,
		ReactionKind.PROOF,
		ReactionKind.ACCEPT
	]: return 1
	elif kind in [
		ReactionKind.DISAGREE,
		ReactionKind.DISLIKE,
		ReactionKind.DISPROOF,
		ReactionKind.REJECT
	]: return -1
	else: return 0

def get_bookmarked(reactions):
    c = 0
    for r in reactions:
        c += 1 if r.kind in [ ReactionKind.QUOTE, ReactionKind.ASK] else 0
    return c

def get_rating(reactions):
    rating = 0
    for r in reactions:
        rating += kind_to_rate(r.kind)
    return rating

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
		reacted = []
		try:
			with local_session() as session:
				reacted = session.query(Reaction).filter(Reaction.replyTo == self.id).all()
		except Exception as e:
			print(e)
		return {
			"viewed": await ViewedStorage.get_reaction(self.id),
			"reacted": reacted.count(),
			"rating": get_rating(reacted),
			"bookmarked": get_bookmarked(reacted)
		}