from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship, backref
from orm.base import Base


class Community(Base):
	__tablename__ = 'community'
    # id is auto number
	name: str = Column(String, nullable=False, comment="Name")
	slug: str = Column(String, unique = True, nullable = False)
    desc: str = Column(String, nullable=False, default='')
    pic: str = Column(String, nullable=False, default='')
	org_id: str = Column(ForeignKey("organization.id"), nullable=True)
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	createdBy: str = Column(ForeignKey("user.id"), nullable=False, comment="Creator")
	