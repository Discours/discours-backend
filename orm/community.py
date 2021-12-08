from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship, backref
from orm.base import Base, local_session


class Community(Base):
	__tablename__ = 'community'

	name: str = Column(String, nullable=False, comment="Name")
	slug: str = Column(String, unique = True, nullable = False)
	desc: str = Column(String, nullable=False, default='')
	pic: str = Column(String, nullable=False, default='')
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	createdBy: str = Column(ForeignKey("user.id"), nullable=False, comment="Creator")

	@staticmethod
	def init_table():
		with local_session() as session:
			default = session.query(Community).filter(Community.slug == "default").first()
		if default:
			Community.default_community = default
			return

		default = Community.create(
			name = "default",
			slug = "default",
			createdBy = 0
		)

		Community.default_community = default
