from datetime import datetime
from sqlalchemy import Column, String, ForeignKey, DateTime
from orm.base import Base, local_session

class CommunityFollower(Base):
	__tablename__ = 'community_followers'

	id = None
	follower = Column(ForeignKey('user.slug'), primary_key = True)
	community = Column(ForeignKey('community.slug'), primary_key = True)
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")


class Community(Base):
	__tablename__ = 'community'

	name: str = Column(String, nullable=False, comment="Name")
	slug: str = Column(String, nullable = False, unique=True, comment="Slug")
	desc: str = Column(String, nullable=False, default='')
	pic: str = Column(String, nullable=False, default='')
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	createdBy: str = Column(ForeignKey("user.slug"), nullable=False, comment="Author")

	@staticmethod
	def init_table():
		with local_session() as session:
			default = session.query(Community).filter(Community.slug == "discours").first()
		if not default:
			default = Community.create(
				name = "Дискурс",
				slug = "discours",
				createdBy = "discours"
			)

		Community.default_community = default
