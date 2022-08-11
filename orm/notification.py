from sqlalchemy import Column, String, JSON as JSONType
from base.orm import Base

class Notification(Base):
	__tablename__ = 'notification'

	kind: str = Column(String, unique = True, primary_key = True)
	template: str = Column(String, nullable = False)
	variables: JSONType = Column(JSONType, nullable = True) # [ <var1>, .. ]

	# looks like frontend code