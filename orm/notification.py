from sqlalchemy import Column, Integer, String, ForeignKey, JSON as JSONType
from orm.base import Base

class Notification(Base):
	__tablename__ = 'notification'

	kind: str = Column(String, primary_key = True)
	template: str = Column(String, nullable = False)
	variables: JSONType = Column(JSONType, nullable = True) # [ <var1>, .. ]

class UserNotification(Base):
	__tablename__ = 'user_notification'

	id: int = Column(Integer, primary_key = True)
	user: int = Column(ForeignKey("user.id"))
	kind: int = Column(ForeignKey("notification.kind"), nullable = False)
	values: JSONType = Column(JSONType, nullable = True) # [ <var1>, .. ]