from sqlalchemy import Column, Integer, String, ForeignKey
# from orm import Permission
from orm.base import Base

class Rating(Base):
	__tablename__ = "rating"

	createdBy: int = Column(Integer, ForeignKey("user.id"), primary_key = True)
	value: int = Column(Integer, nullable=False)
