from datetime import datetime
from sqlalchemy import Column, String, ForeignKey, DateTime, JSON as JSONType
from base.orm import Base

class ShoutCollection(Base):
	__tablename__ = 'shout_collection'
	
	id = None
	shout = Column(ForeignKey('shout.slug'), primary_key = True)
	collection = Column(ForeignKey('collection.slug'), primary_key = True)
 
class Collection(Base):
	__tablename__ = 'collection'

	id = None
	slug: str = Column(String, primary_key = True)
	title: str = Column(String, nullable=False, comment="Title")
	body: str = Column(String, nullable=True, comment="Body")
	pic: str = Column(String, nullable=True, comment="Picture")
	createdAt: datetime = Column(DateTime, default=datetime.now, comment="Created At")
	createdBy: str = Column(ForeignKey('user.id'), comment="Created By")

