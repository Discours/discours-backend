from sqlalchemy import Column, Integer, String, ForeignKey, JSON as JSONType
from orm.base import Base

class Notification(Base):
	__tablename__ = 'notification'

	kind: str = Column(String, unique = True, primary_key = True)
	template: str = Column(String, nullable = False)
	variables: JSONType = Column(JSONType, nullable = True) # [ <var1>, .. ]