
from sqlalchemy import Column, Integer, String, ForeignKey
from orm.base import Base

class Rating(Base):
	__tablename__ = 'rating'

	id: int = Column(Integer, primary_key = True)
	createdBy: int = Column(ForeignKey("user.id"), primary_key = True)
	value: int = Column(Integer, nullable=False)