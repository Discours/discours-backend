from sqlalchemy import Column, Integer, String, ForeignKey, JSON as JSONType
from orm.base import Base

class Notification(Base):
	__tablename__ = 'notification'

	kind: str = Column(String, unique = True, primary_key = True)
	template: str = Column(String, nullable = False)
	variables: JSONType = Column(JSONType, nullable = True) # [ <var1>, .. ]

class UserNotification(Base):
	__tablename__ = 'user_notification'

	id: int = Column(Integer, primary_key = True)
	user_id: int = Column(Integer, ForeignKey("user.id"))
	kind: str = Column(String, ForeignKey("notification.kind"))
	values: JSONType = Column(JSONType, nullable = True) # [ <var1>, .. ]