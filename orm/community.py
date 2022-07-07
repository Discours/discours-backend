from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship, backref
from orm.base import Base, local_session

class CommunitySubscription(Base):
	__tablename__ = 'community_subscription'

	id = None
	subscriber = Column(ForeignKey('user.slug'), primary_key = True)
	community = Column(ForeignKey('community.slug'), primary_key = True)
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")


class Community(Base):
	__tablename__ = 'community'

	name: str = Column(String, nullable=False, comment="Name")
	slug: str = Column(String, nullable = False)
	desc: str = Column(String, nullable=False, default='')
	pic: str = Column(String, nullable=False, default='')
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	createdBy: str = Column(ForeignKey("user.slug"), nullable=False, comment="Creator")

	@staticmethod
	def init_table():
		with local_session() as session:
			default = session.query(Community).filter(Community.slug == "discours").first()
		if not default:
			default = Community.create(
				name = "Дискурс",
				slug = "discours",
				createdBy = 0 #TODO: use default user
			)

		Community.default_community = default
